"""The inbound-triage agent: classify an inbound message, then route it.

Pipeline: classify intent → route by intent:
  * INTERESTED            → generate a booking link + reply
  * OBJECTION             → RAG rebuttal (retrieve from the Chroma KB, then compose)
  * NOT_THE_RIGHT_PERSON  → extract the referred contact (LLM + regex)
  * OUT_OF_OFFICE         → snooze
  * SPAM                  → drop

Classification and extraction go through ``lumifie_core`` (tool use where
supported, JSON fallback otherwise), so any litellm model works.
"""

from __future__ import annotations

from lumifie_core import BaseAgent, LLMProvider

from inbound_triage import models
from inbound_triage.config import TriageSettings
from inbound_triage.contacts import extract_emails, extract_phones
from inbound_triage.knowledge import RebuttalKnowledgeBase
from inbound_triage.models import (
    Action,
    BookingResult,
    Classification,
    ContactExtraction,
    InboundMessage,
    Intent,
    RebuttalResult,
    TriageResult,
)

CLASSIFY_SYSTEM = (
    "You triage inbound replies to sales outreach. Classify the message into exactly "
    "one intent: INTERESTED (wants to talk/learn more), OBJECTION (pushback on price, "
    "timing, incumbent, need, or trust), NOT_THE_RIGHT_PERSON (refers you elsewhere), "
    "OUT_OF_OFFICE (auto-reply), or SPAM. Give a confidence 0-1 and brief reasoning."
)
REBUTTAL_SYSTEM = (
    "You are a thoughtful SDR. Write a brief, respectful reply that addresses the "
    "prospect's objection using the provided rebuttal guidance. No pressure, no "
    "false claims, one clear low-commitment next step. Under 120 words."
)
CONTACT_SYSTEM = (
    "Extract referral contact details from a 'wrong person' reply: the name and title "
    "of who to contact instead, plus any emails/phones mentioned. Use null if absent."
)


class InboundTriageAgent(BaseAgent):
    name = "inbound-triage"
    description = "Classifies inbound replies and routes them to the right action."

    def __init__(
        self,
        provider: LLMProvider,
        settings: TriageSettings,
        knowledge_base: RebuttalKnowledgeBase,
    ) -> None:
        super().__init__(provider, settings)
        self.settings: TriageSettings = settings
        self._kb = knowledge_base

    # -- public API --------------------------------------------------------

    def run(self, message: InboundMessage) -> TriageResult:  # type: ignore[override]
        return self.triage(message)

    def triage(self, message: InboundMessage) -> TriageResult:
        cls = self._classify(message)
        self.log.info("[{}] intent={} ({:.2f})", message.id, cls.intent.value, cls.confidence)

        rebuttal = booking = contact = None
        if cls.intent is Intent.INTERESTED:
            action = Action.BOOKING
            booking = self._booking(message)
        elif cls.intent is Intent.OBJECTION:
            action = Action.REBUTTAL
            rebuttal = self._rebuttal(message)
        elif cls.intent is Intent.NOT_THE_RIGHT_PERSON:
            action = Action.EXTRACT_CONTACT
            contact = self._extract_contact(message)
        elif cls.intent is Intent.OUT_OF_OFFICE:
            action = Action.SNOOZE
        else:
            action = Action.DROP

        self.log.info("[{}] action={}", message.id, action.value)
        return TriageResult(
            message_id=message.id,
            intent=cls.intent,
            confidence=cls.confidence,
            reasoning=cls.reasoning,
            action=action,
            model=self.provider.model,
            rebuttal=rebuttal,
            booking=booking,
            contact=contact,
            token_usage=dict(self.token_usage),
        )

    # -- steps -------------------------------------------------------------

    def _classify(self, message: InboundMessage) -> Classification:
        data = self.structured(
            system=CLASSIFY_SYSTEM,
            prompt=message.as_text(),
            schema=models.classification_schema(),
            tool_name="classification",
        )
        try:
            return Classification.model_validate(data)
        except Exception as exc:
            self.log.warning("Classification failed ({}); defaulting to OBJECTION.", exc)
            return Classification(intent=Intent.OBJECTION, confidence=0.0, reasoning="fallback")

    def _booking(self, message: InboundMessage) -> BookingResult:
        link = f"{self.settings.booking_base_url}?ref={message.id}"
        who = f" {message.sender_name.split()[0]}" if message.sender_name else ""
        reply = (
            f"Great to hear from you{who}! Grab whatever time works best and we'll take "
            f"it from there: {link}"
        )
        return BookingResult(link=link, reply=reply)

    def _rebuttal(self, message: InboundMessage) -> RebuttalResult:
        hits = self._kb.retrieve(message.body, k=self.settings.rebuttal_top_k)
        guidance = "\n".join(f"- ({h['id']}) {h['objection']} → {h['rebuttal']}" for h in hits)
        prompt = (
            f"Prospect message:\n{message.as_text()}\n\n"
            f"Rebuttal guidance (retrieved playbook):\n{guidance or '(none)'}\n\n"
            "Write the reply."
        )
        data = self.structured(
            system=REBUTTAL_SYSTEM,
            prompt=prompt,
            schema=models.rebuttal_schema(),
            tool_name="rebuttal",
        )
        try:
            result = RebuttalResult.model_validate(data)
        except Exception as exc:
            self.log.warning("Rebuttal generation failed: {}", exc)
            result = RebuttalResult(body="", key_points=[])
        result.sources = [h["id"] for h in hits]
        return result

    def _extract_contact(self, message: InboundMessage) -> ContactExtraction:
        data = self.structured(
            system=CONTACT_SYSTEM,
            prompt=message.as_text(),
            schema=models.contact_schema(),
            tool_name="contact",
        )
        try:
            contact = ContactExtraction.model_validate(data)
        except Exception as exc:
            self.log.warning("Contact extraction failed: {}", exc)
            contact = ContactExtraction()
        # Augment with deterministic regex extraction over the raw message.
        contact.emails = _merge(contact.emails, extract_emails(message.body))
        contact.phones = _merge(contact.phones, extract_phones(message.body))
        return contact


def _merge(a: list[str], b: list[str]) -> list[str]:
    return list(dict.fromkeys([*a, *b]))


__all__ = ["InboundTriageAgent"]

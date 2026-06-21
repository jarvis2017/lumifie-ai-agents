# Inbound Triage — example run

_Five mock messages, one per intent (offline stub provider)._

## msg_interested_01 → INTERESTED → `booking`

_[offline stub] positive buying language detected_

- **Booking link:** https://cal.com/lumifie/intro?ref=msg_interested_01
- **Reply:** Great to hear from you Dana! Grab whatever time works best and we'll take it from there: https://cal.com/lumifie/intro?ref=msg_interested_01

## msg_objection_01 → OBJECTION → `rebuttal`

_[offline stub] objection language detected_

- **Rebuttal** (KB sources: incumbent, no_need, trust):
  > Thanks for the candid reply — totally fair. A quick thought before you go: most teams in your position find the cost of the status quo outweighs the investment within a quarter. Open to a 15-minute look at the numbers?

## msg_wrongperson_01 → NOT_THE_RIGHT_PERSON → `extract_contact`

_[offline stub] referral language detected_

- **Referred contact:** Jordan Mills | emails: reception@vertexlabs.com, jordan.mills@vertexlabs.com | phones: 415-555-0142

## msg_ooo_01 → OUT_OF_OFFICE → `snooze`

_[offline stub] auto-reply language detected_


## msg_spam_01 → SPAM → `drop`

_[offline stub] spam markers detected_


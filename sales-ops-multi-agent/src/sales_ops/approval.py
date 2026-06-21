"""Human approval gate for external actions.

An ``Approver`` is any callable ``(ProposedAction) -> bool``. Built-ins cover CLI
confirmation (default), auto-approve, deny-all, and an optional **Telegram**
channel that notifies a chat and waits for a yes/no reply. Dry-run never calls an
approver (the orchestrator skips execution entirely).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from lumifie_core import logger

from sales_ops.config import ApprovalConfig
from sales_ops.models import ProposedAction

Approver = Callable[[ProposedAction], bool]


def describe(action: ProposedAction) -> str:
    return f"[{action.type.value}] lead={action.lead_id} :: {action.summary}" + (
        f"\n    why: {action.rationale}" if action.rationale else ""
    )


def auto_approve(action: ProposedAction) -> bool:
    return True


def deny_all(action: ProposedAction) -> bool:
    return False


def cli_approver(action: ProposedAction) -> bool:
    """Prompt on the terminal. Defaults to NO on empty/EOF input (safe)."""
    print("\n🔔 Approval required:")
    print("    " + describe(action).replace("\n", "\n    "))
    try:
        resp = input("    Approve this external action? [y/N] ").strip().lower()
    except EOFError:
        return False
    return resp in ("y", "yes")


class RecordingApprover:
    """Test/automation approver: records every action and returns a fixed decision."""

    def __init__(self, decision: bool = True) -> None:
        self.decision = decision
        self.seen: list[ProposedAction] = []

    def __call__(self, action: ProposedAction) -> bool:
        self.seen.append(action)
        return self.decision


class TelegramApprover:
    """Notify a Telegram chat and wait for a 'yes'/'no' reply (optional channel).

    Sends the proposed action via the Bot API and polls ``getUpdates`` for a reply
    from ``chat_id``. Returns False on timeout (safe default). Real network channel;
    not exercised in offline tests.
    """

    def __init__(
        self, bot_token: str, chat_id: str, *, timeout: int = 300, poll_interval: int = 3
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.timeout = timeout
        self.poll_interval = poll_interval

    def __call__(self, action: ProposedAction) -> bool:  # pragma: no cover - network
        import httpx  # noqa: PLC0415

        base = f"https://api.telegram.org/bot{self.bot_token}"
        text = "🔔 Approval required (reply YES/NO):\n" + describe(action)
        try:
            httpx.post(
                f"{base}/sendMessage", json={"chat_id": self.chat_id, "text": text}, timeout=15
            )
            offset = None
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                params = {"timeout": self.poll_interval}
                if offset is not None:
                    params["offset"] = offset
                resp = httpx.get(
                    f"{base}/getUpdates", params=params, timeout=self.poll_interval + 10
                )
                for upd in resp.json().get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    if str((msg.get("chat") or {}).get("id")) != self.chat_id:
                        continue
                    answer = (msg.get("text") or "").strip().lower()
                    if answer in ("yes", "y", "approve"):
                        return True
                    if answer in ("no", "n", "deny"):
                        return False
                time.sleep(self.poll_interval)
        except Exception as exc:
            logger.warning("Telegram approval failed ({}); denying for safety.", exc)
        return False


def build_approver(config: ApprovalConfig) -> Approver:
    """Resolve the configured approval channel into an Approver callable."""
    channel = (config.channel or "cli").lower()
    if channel == "auto":
        return auto_approve
    if channel == "deny":
        return deny_all
    if channel == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token and config.telegram_chat_id:
            return TelegramApprover(token, config.telegram_chat_id)
        logger.warning("Telegram not configured (need TELEGRAM_BOT_TOKEN + chat id); using CLI.")
        return cli_approver
    return cli_approver


__all__ = [
    "Approver",
    "auto_approve",
    "deny_all",
    "cli_approver",
    "RecordingApprover",
    "TelegramApprover",
    "build_approver",
    "describe",
]

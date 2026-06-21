"""Inbox + email-sending backends (injectable; fakes for offline runs/tests)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lumifie_core import logger

from sales_ops.models import Reply


@runtime_checkable
class Mailbox(Protocol):
    def fetch_replies(self) -> list[Reply]: ...


@runtime_checkable
class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...


class FakeMailbox:
    """In-memory inbox seeded with replies (used for demo + tests)."""

    def __init__(self, replies: list[Reply] | None = None) -> None:
        self._replies = list(replies or [])

    def fetch_replies(self) -> list[Reply]:
        return list(self._replies)


class FakeEmailSender:
    """Records sends instead of hitting a real mail server."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, to: str, subject: str, body: str) -> bool:
        self.sent.append({"to": to, "subject": subject, "body": body})
        logger.info("[fake-email] -> {} :: {}", to, subject)
        return True


class SMTPEmailSender:  # pragma: no cover - network/credentials
    """Real SMTP sender. Reads SMTP_HOST/PORT/USER/PASSWORD/FROM from env."""

    def __init__(self, host: str, port: int, user: str, password: str, sender: str) -> None:
        self.host, self.port, self.user, self.password, self.sender = (
            host,
            port,
            user,
            password,
            sender,
        )

    def send(self, to: str, subject: str, body: str) -> bool:
        import smtplib  # noqa: PLC0415
        from email.message import EmailMessage  # noqa: PLC0415

        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.send_message(msg)
            return True
        except Exception as exc:
            logger.warning("SMTP send failed: {}", exc)
            return False


__all__ = ["Mailbox", "EmailSender", "FakeMailbox", "FakeEmailSender", "SMTPEmailSender"]

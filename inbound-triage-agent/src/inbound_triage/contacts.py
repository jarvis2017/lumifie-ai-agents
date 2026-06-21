"""Lightweight contact extraction (regex) used to augment LLM/NER output."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Matches common US/international phone formats with 7+ digits.
_PHONE_RE = re.compile(r"(?:(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4})")


def extract_emails(text: str) -> list[str]:
    seen: list[str] = []
    for m in _EMAIL_RE.findall(text):
        if m not in seen:
            seen.append(m)
    return seen


def extract_phones(text: str) -> list[str]:
    out: list[str] = []
    for m in _PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", m)
        if 7 <= len(digits) <= 15 and m.strip() not in out:
            out.append(m.strip())
    return out


__all__ = ["extract_emails", "extract_phones"]

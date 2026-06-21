"""Detect trigger conditions from fetched CRM records.

Each detector is a pure function of records + parameters, so it is trivial to
test and reason about. Parameters (e.g. the staleness window, the required-field
list) come from the rules file, so a non-technical user tunes behavior in YAML
without touching this code.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from crm_automation.models import Contact, Deal, Trigger, TriggerType


def _now() -> datetime:
    return datetime.now(UTC)


def _today() -> date:
    return _now().date()


def _aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC so comparisons never raise."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def detect_new_leads(
    contacts: list[Contact], deals: list[Deal], *, within_days: int = 1
) -> list[Trigger]:
    """A contact or deal created within ``within_days`` is a new lead."""
    cutoff = _now()
    triggers: list[Trigger] = []
    for c in contacts:
        if c.created_at and (cutoff - _aware(c.created_at)).days < within_days:
            triggers.append(
                Trigger(
                    type=TriggerType.NEW_LEAD,
                    target_id=c.id,
                    detail=f"New contact: {c.display()}",
                    context={"kind": "contact", "name": c.display(), "email": c.email},
                )
            )
    for d in deals:
        if d.created_at and (cutoff - _aware(d.created_at)).days < within_days:
            triggers.append(
                Trigger(
                    type=TriggerType.NEW_LEAD,
                    target_id=d.id,
                    detail=f"New deal: {d.name}",
                    context={"kind": "deal", "name": d.name, "stage": d.stage},
                )
            )
    return triggers


def detect_stale_deals(deals: list[Deal], *, days: int = 30) -> list[Trigger]:
    """A deal with no activity for more than ``days`` is stale."""
    now = _now()
    triggers: list[Trigger] = []
    for d in deals:
        if d.last_activity_at is None:
            continue
        idle = (now - _aware(d.last_activity_at)).days
        if idle > days:
            triggers.append(
                Trigger(
                    type=TriggerType.DEAL_STALE,
                    target_id=d.id,
                    detail=f"Deal '{d.name}' has had no activity for {idle} days.",
                    context={
                        "name": d.name,
                        "stage": d.stage,
                        "days_stale": idle,
                        "owner": d.owner,
                    },
                )
            )
    return triggers


def detect_overdue_follow_ups(deals: list[Deal]) -> list[Trigger]:
    """A deal whose ``next_follow_up`` is in the past is overdue."""
    today = _today()
    triggers: list[Trigger] = []
    for d in deals:
        if d.next_follow_up and d.next_follow_up < today:
            overdue = (today - d.next_follow_up).days
            triggers.append(
                Trigger(
                    type=TriggerType.FOLLOW_UP_OVERDUE,
                    target_id=d.id,
                    detail=f"Follow-up for '{d.name}' is {overdue} day(s) overdue.",
                    context={
                        "name": d.name,
                        "stage": d.stage,
                        "days_overdue": overdue,
                        "due": d.next_follow_up.isoformat(),
                    },
                )
            )
    return triggers


def detect_missing_fields(
    contacts: list[Contact], *, required_fields: list[str]
) -> list[Trigger]:
    """A contact missing any configured required field triggers MISSING_FIELDS.

    A field is "missing" if it is absent or empty. ``email`` and ``name`` are
    checked on the contact itself; everything else is checked in ``fields``.
    """
    triggers: list[Trigger] = []
    for c in contacts:
        missing = [f for f in required_fields if _is_empty(c, f)]
        if missing:
            c.missing_required = missing
            triggers.append(
                Trigger(
                    type=TriggerType.MISSING_FIELDS,
                    target_id=c.id,
                    detail=f"{c.display()} is missing: {', '.join(missing)}.",
                    context={"name": c.display(), "missing": missing},
                )
            )
    return triggers


def _is_empty(contact: Contact, field: str) -> bool:
    if field == "email":
        value: object = contact.email
    elif field == "name":
        value = contact.name
    else:
        value = contact.fields.get(field)
    return value is None or (isinstance(value, str) and not value.strip())


__all__ = [
    "detect_missing_fields",
    "detect_new_leads",
    "detect_overdue_follow_ups",
    "detect_stale_deals",
]

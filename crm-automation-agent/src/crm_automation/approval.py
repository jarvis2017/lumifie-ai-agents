"""The human approval gate.

Before any action that mutates an external system (update a deal stage, create a
task) executes, a human must approve it. The gate is a simple callable so tests
can inject auto-approve / auto-deny without prompting, and automation can pass
``--yes``.

Modes:
* ``--dry-run``  -> nothing executes and nothing is prompted (handled by the agent).
* default        -> :func:`interactive_approval` prompts ``y/N`` per external action.
* ``--yes``      -> :func:`auto_approve` approves everything (for cron/automation).
"""

from __future__ import annotations

from collections.abc import Callable

from crm_automation.models import ProposedAction

# An approver decides whether a single proposed action may execute.
Approver = Callable[[ProposedAction], bool]


def auto_approve(_action: ProposedAction) -> bool:
    """Approve every action (used by ``--yes`` and tests)."""
    return True


def auto_deny(_action: ProposedAction) -> bool:
    """Deny every action (used by tests)."""
    return False


def interactive_approval(action: ProposedAction) -> bool:
    """Prompt the operator to approve one external mutation (default mode)."""
    print("\n" + "-" * 70)
    print(f"PROPOSED EXTERNAL ACTION  [{action.type.value}]")
    print(f"  rule    : {action.rule_name}")
    print(f"  target  : {action.target_id}")
    print(f"  params  : {action.params}")
    print(f"  why     : {action.rationale}")
    answer = input("Approve this action? [y/N] ").strip().lower()
    return answer in ("y", "yes")


__all__ = ["Approver", "auto_approve", "auto_deny", "interactive_approval"]

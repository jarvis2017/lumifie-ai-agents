"""Load and apply the YAML rules file.

The rules file is the single place a non-technical user controls the agent: each
rule names a trigger (with parameters like a staleness window or a required-field
list) and the action to take when it fires. This module loads and validates that
file, runs the trigger detectors, and turns matches into :class:`ProposedAction`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from crm_automation import triggers as trig
from crm_automation.models import (
    ActionType,
    Contact,
    Deal,
    ProposedAction,
    Trigger,
    TriggerType,
)


class RuleTrigger(BaseModel):
    type: TriggerType
    params: dict[str, Any] = Field(default_factory=dict)


class RuleAction(BaseModel):
    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)


class Rule(BaseModel):
    name: str
    enabled: bool = True
    description: str = ""
    trigger: RuleTrigger
    action: RuleAction

    @field_validator("name")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("rule name must not be empty")
        return v


class RuleSet(BaseModel):
    rules: list[Rule] = Field(default_factory=list)

    def enabled_rules(self) -> list[Rule]:
        return [r for r in self.rules if r.enabled]


def load_rules(path: str | Path) -> RuleSet:
    """Load and validate a YAML rules file into a :class:`RuleSet`."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Rules file {path} must be a mapping with a 'rules' key.")
    return RuleSet.model_validate(data)


def _detect_for_rule(
    rule: Rule, contacts: list[Contact], deals: list[Deal]
) -> list[Trigger]:
    params = rule.trigger.params
    t = rule.trigger.type
    if t == TriggerType.NEW_LEAD:
        return trig.detect_new_leads(
            contacts, deals, within_days=int(params.get("within_days", 1))
        )
    if t == TriggerType.DEAL_STALE:
        return trig.detect_stale_deals(deals, days=int(params.get("days", 30)))
    if t == TriggerType.FOLLOW_UP_OVERDUE:
        return trig.detect_overdue_follow_ups(deals)
    if t == TriggerType.MISSING_FIELDS:
        required = list(params.get("required_fields", []))
        return trig.detect_missing_fields(contacts, required_fields=required)
    return []


def _rationale(rule: Rule, trigger: Trigger) -> str:
    return f"Rule '{rule.name}' matched {trigger.type.value}: {trigger.detail}"


def evaluate(
    ruleset: RuleSet, contacts: list[Contact], deals: list[Deal]
) -> tuple[list[Trigger], list[ProposedAction]]:
    """Run every enabled rule, returning all detected triggers and proposed actions."""
    all_triggers: list[Trigger] = []
    proposed: list[ProposedAction] = []
    for rule in ruleset.enabled_rules():
        for trigger in _detect_for_rule(rule, contacts, deals):
            all_triggers.append(trigger)
            params = dict(rule.action.params)
            # Carry trigger context the actions/email drafter can use.
            params.setdefault("trigger_detail", trigger.detail)
            proposed.append(
                ProposedAction(
                    type=rule.action.type,
                    target_id=trigger.target_id,
                    params=params,
                    rule_name=rule.name,
                    rationale=_rationale(rule, trigger),
                    trigger_type=trigger.type,
                )
            )
    return all_triggers, proposed


__all__ = [
    "Rule",
    "RuleAction",
    "RuleSet",
    "RuleTrigger",
    "evaluate",
    "load_rules",
]

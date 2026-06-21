"""Tests for ICP loading and model schemas."""

from __future__ import annotations

import json

from lead_research import models
from lead_research.icp import DEFAULT_ICP, ICPProfile, load_icp


def test_load_default_icp_when_no_path():
    assert load_icp(None) is DEFAULT_ICP


def test_load_icp_from_file(tmp_path):
    p = tmp_path / "icp.json"
    p.write_text(json.dumps({"name": "Custom", "target_industries": ["healthcare"]}))
    icp = load_icp(p)
    assert isinstance(icp, ICPProfile)
    assert icp.name == "Custom"
    assert icp.target_industries == ["healthcare"]


def test_icp_as_prompt_is_json():
    block = DEFAULT_ICP.as_prompt()
    assert json.loads(block)["name"] == DEFAULT_ICP.name


def test_schemas_are_closed_objects():
    for schema_fn in (models.enrichment_schema, models.icp_score_schema, models.outreach_schema):
        schema = schema_fn()
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) <= set(schema["properties"])


def test_icp_score_bounds():
    s = models.ICPScore(fit_score=50, tier="Moderate", reasoning="ok")
    assert s.fit_score == 50

"""Shared content-title guard used by the outreach agents."""
from __future__ import annotations

import pytest

from lumifie_core import is_content_title


@pytest.mark.parametrize("name", [
    "How to Build an AI Agent", "How to create AI Agents with LangGraph?",
    "Best AI Automation Agencies of 2026", "Top 10 AI Agencies",
    "The Real Estate Agent's Guide to Lead Follow", "How Realtors Can Automate Leads",
    "About Us", "Contact", "Pricing", "Job Application for AI Implementation Specialist",
    "What is an AI agent", "",
])
def test_content_titles_rejected(name):
    assert is_content_title(name)


@pytest.mark.parametrize("name", [
    "Acme AI", "AI Product Development Company", "AI Automation Agency for B2B",
    "PixlerLab", "Smith & Associates Law", "Northgate Realty", "Inceptive Technologies",
])
def test_real_company_names_pass(name):
    assert not is_content_title(name)

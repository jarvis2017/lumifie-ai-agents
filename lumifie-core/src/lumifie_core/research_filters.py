"""Shared research false-positive filters for the outreach agents.

`is_content_title` drops search results whose extracted name reads like a content page, listicle,
how-to, job post, or nav page rather than a real company/prospect (e.g. "How to Build an AI Agent",
"Best ... Agencies of 2026", "About Us", "Job Application for ..."). Both lumifie-agency-outreach
and lumifie-lead-gen apply it after their own (intentionally different) domain blacklists.
"""
from __future__ import annotations

# Title prefixes that signal content rather than a company name.
CONTENT_TITLE_PREFIXES: tuple[str, ...] = (
    "how to", "how do", "how i", "how a", "how can", "how realtors", "what is", "what are",
    "why ", "best ", "top ", "the best", "the top", "guide to", "a guide", "your guide",
    "the ultimate", "ultimate guide", "introduction to", "intro to", "getting started",
    "step-by-step", "step by step", "tutorial", "ways to", "tips for",
)

# Whole-name matches that are nav/utility pages, not companies.
CONTENT_TITLE_EXACT: frozenset[str] = frozenset({
    "about", "about us", "home", "homepage", "home page", "contact", "contact us", "blog",
    "our blog", "careers", "career", "jobs", "job application", "privacy policy", "privacy",
    "terms", "terms of service", "login", "log in", "sign in", "sign up", "faq", "404",
    "page not found", "not found", "services", "our services", "our work", "portfolio", "work",
    "team", "our team", "pricing", "products", "resources",
})

# Substrings anywhere in the name that signal content/listicle/job posts.
CONTENT_TITLE_SUBSTRINGS: tuple[str, ...] = (
    "tutorial", "step-by-step", " vs ", "job application", "we're hiring", "now hiring",
    "apply now", "job description", "cheat sheet", "best practices", "explained", "for beginners",
    "'s guide to", "s guide to", " guide:", "top 5", "top 7", "top 10",
    "in 2024", "in 2025", "in 2026", "of 2024", "of 2025", "of 2026",
)


def is_content_title(name: str) -> bool:
    """True if the candidate name reads like a content/nav/job page rather than a real company."""
    n = (name or "").strip().lower()
    if not n:
        return True
    if n in CONTENT_TITLE_EXACT:
        return True
    if any(n.startswith(p) for p in CONTENT_TITLE_PREFIXES):
        return True
    return any(sub in n for sub in CONTENT_TITLE_SUBSTRINGS)


__all__ = [
    "CONTENT_TITLE_PREFIXES",
    "CONTENT_TITLE_EXACT",
    "CONTENT_TITLE_SUBSTRINGS",
    "is_content_title",
]

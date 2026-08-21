"""Tests for technical fact extraction (CVE / CVSS / versions)."""

from __future__ import annotations

from app.pipeline.facts import extract_facts, facts_block


def test_nothing_technical_yields_nothing():
    """An empty block is the point: the model gets no blanks to fill in."""
    facts = extract_facts("A thread about why I switched coffee brands")
    assert not facts
    assert facts_block(facts) == ""


def test_a_full_advisory_is_extracted():
    facts = extract_facts(
        "CVE-2026-1234 in libfoo. CVSS 9.8 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H), "
        "CWE-79. Affects versions before 2.4.0, fixed in 2.4.1. Actively exploited in the wild."
    )
    assert facts.cves == ["CVE-2026-1234"]
    assert facts.cvss == "9.8"
    assert facts.cvss_vector.startswith("CVSS:3.1/")
    assert facts.cwes == ["CWE-79"]
    assert facts.affected_versions == ["2.4.0"]
    assert facts.fixed_versions == ["2.4.1"]
    assert facts.actively_exploited is True


def test_cve_ids_are_normalised_and_deduped():
    facts = extract_facts("cve-2026-1234 and CVE-2026-1234 and CVE-2026-9999")
    assert facts.cves == ["CVE-2026-1234", "CVE-2026-9999"]


def test_a_version_string_is_not_mistaken_for_a_cvss_score():
    """'CVSS' near a number is not enough — 14.2 is not a severity."""
    facts = extract_facts("CVSS coverage in release 14.2 of the scanner")
    assert facts.cvss is None


def test_kev_language_marks_active_exploitation():
    assert extract_facts("Added to the KEV catalog today").actively_exploited is True
    assert extract_facts("A theoretical weakness, no PoC").actively_exploited is False


def test_the_block_forbids_inventing_identifiers():
    block = facts_block(extract_facts("CVE-2026-1111, CVSS 7.5"))
    assert "CVE-2026-1111" in block
    assert "7.5" in block
    assert "not in this list" in block

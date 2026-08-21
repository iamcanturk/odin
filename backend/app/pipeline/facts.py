"""Pull the hard numbers out of source material before generating (PROJECT.md §22).

A security post without the CVE id, the CVSS score and the fixed version is a vibe.
The LLM won't invent those reliably — and shouldn't be asked to. So we extract them
from the source text with plain regex, hand them to the generator as facts it must
reproduce verbatim, and never let it fill in a blank we didn't find.

Extraction is deliberately conservative: a number we can't source is a number we
don't pass along.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
CWE = re.compile(r"\bCWE-\d{1,4}\b", re.IGNORECASE)
# "CVSS 9.8", "CVSS score of 9.8", "CVSS:3.1 ... 9.8", "(9.8 critical)"
CVSS_SCORE = re.compile(
    r"CVSS[^\d\n]{0,24}(\d{1,2}\.\d)|\b(\d{1,2}\.\d)\s*(?:/\s*10\b|\(?(?:critical|high|kritik)\)?)",
    re.IGNORECASE,
)
CVSS_VECTOR = re.compile(r"CVSS:\d\.\d/(?:[A-Z]{1,2}:[A-Z]/?)+")
# "fixed in 2.4.1", "patched in v3.0", "upgrade to 1.2.3", "yükseltin 1.2.3"
FIXED_VERSION = re.compile(
    r"(?:fixed in|patched in|upgrade to|update to|resolved in|güncelleyin|sürüm)"
    r"\s+v?(\d+\.\d+(?:\.\d+)?(?:[-.][\w]+)?)",
    re.IGNORECASE,
)
AFFECTED_VERSION = re.compile(
    r"(?:before|prior to|earlier than|öncesi)\s+v?(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE
)
EPSS = re.compile(r"EPSS[^\d\n]{0,16}(\d{1,3}(?:\.\d+)?)\s*%?", re.IGNORECASE)
EXPLOITED = re.compile(
    r"\b(?:actively exploited|exploited in the wild|known exploited|KEV|"
    r"aktif olarak istismar|proof[- ]of[- ]concept|PoC available)\b",
    re.IGNORECASE,
)

MAX_PER_KIND = 4


@dataclass
class TechnicalFacts:
    """Only what was literally present in the source."""

    cves: list[str] = field(default_factory=list)
    cwes: list[str] = field(default_factory=list)
    cvss: str | None = None
    cvss_vector: str | None = None
    epss: str | None = None
    fixed_versions: list[str] = field(default_factory=list)
    affected_versions: list[str] = field(default_factory=list)
    actively_exploited: bool = False

    def __bool__(self) -> bool:
        return bool(
            self.cves
            or self.cwes
            or self.cvss
            or self.fixed_versions
            or self.affected_versions
            or self.actively_exploited
        )


def _dedupe(matches: list[str], *, upper: bool = False) -> list[str]:
    seen: list[str] = []
    for m in matches:
        value = m.upper() if upper else m
        if value not in seen:
            seen.append(value)
    return seen[:MAX_PER_KIND]


def _first_cvss(text: str) -> str | None:
    for match in CVSS_SCORE.finditer(text):
        raw = match.group(1) or match.group(2)
        if raw is None:
            continue
        try:
            score = float(raw)
        except ValueError:
            continue
        # A "CVSS" score outside 0-10 is a version string or a price, not a severity.
        if 0.0 <= score <= 10.0:
            return f"{score:.1f}"
    return None


def extract_facts(*texts: str) -> TechnicalFacts:
    """Scan title, summary and source items for citable technical detail."""
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return TechnicalFacts()

    return TechnicalFacts(
        cves=_dedupe(CVE.findall(blob), upper=True),
        cwes=_dedupe(CWE.findall(blob), upper=True),
        cvss=_first_cvss(blob),
        cvss_vector=(m.group(0) if (m := CVSS_VECTOR.search(blob)) else None),
        epss=(m.group(1) if (m := EPSS.search(blob)) else None),
        fixed_versions=_dedupe(FIXED_VERSION.findall(blob)),
        affected_versions=_dedupe(AFFECTED_VERSION.findall(blob)),
        actively_exploited=bool(EXPLOITED.search(blob)),
    )


def facts_block(facts: TechnicalFacts) -> str:
    """The prompt fragment. Empty when there's nothing citable — no invented specifics."""
    if not facts:
        return ""

    lines: list[str] = []
    if facts.cves:
        lines.append(f"CVE: {', '.join(facts.cves)}")
    if facts.cvss:
        vector = f" ({facts.cvss_vector})" if facts.cvss_vector else ""
        lines.append(f"CVSS: {facts.cvss}{vector}")
    if facts.epss:
        lines.append(f"EPSS: {facts.epss}%")
    if facts.cwes:
        lines.append(f"CWE: {', '.join(facts.cwes)}")
    if facts.affected_versions:
        lines.append(f"Affected: before {', '.join(facts.affected_versions)}")
    if facts.fixed_versions:
        lines.append(f"Fixed in: {', '.join(facts.fixed_versions)}")
    if facts.actively_exploited:
        lines.append("Status: actively exploited in the wild")

    return (
        "Verified technical facts from the source — reproduce these EXACTLY as written, "
        "and do not state any identifier, score or version that is not in this list:\n"
        + "\n".join(f"  {line}" for line in lines)
        + "\nLead with the identifier and the score. A security post without them is "
        "unusable to the reader who has to act on it."
    )

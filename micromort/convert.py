"""Convert assorted risk expressions into micromorts.

A micromort = 1e-6 probability of death. All helpers return a `float` in
micromorts. Helpers raise `ValueError` rather than silently producing nonsense.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MICRO = 1_000_000


def from_one_in(n: float) -> float:
    """Probability '1 in N' (of death) → micromorts."""
    if n <= 0:
        raise ValueError("n must be positive")
    return MICRO / n


def from_probability(p: float) -> float:
    """Raw probability in [0,1] → micromorts."""
    if not 0 <= p <= 1:
        raise ValueError("p must be in [0,1]")
    return p * MICRO


def from_percent(pct: float) -> float:
    """Percentage (0–100) → micromorts."""
    return from_probability(pct / 100)


def from_deaths_per(deaths: float, exposures: float) -> float:
    """`deaths` per `exposures` people/events → micromorts per exposure."""
    if exposures <= 0:
        raise ValueError("exposures must be positive")
    return (deaths / exposures) * MICRO


def from_rate_per_100k(rate: float) -> float:
    """Deaths per 100,000 per year (CDC/WHO style) → micromorts/year."""
    return rate * 10


def from_rate_per_million(rate: float) -> float:
    return rate


def hourly_to_activity(per_hour_mm: float, hours: float) -> float:
    """Scale a per-hour micromort rate to a typical activity duration."""
    if hours < 0:
        raise ValueError("hours must be >= 0")
    return per_hour_mm * hours


def annual_to_daily(annual_mm: float) -> float:
    return annual_mm / 365.25


def annual_to_hourly(annual_mm: float) -> float:
    return annual_mm / (365.25 * 24)


def lifetime_to_annual(lifetime_mm: float, life_years: float = 80.0) -> float:
    """Crude amortization of a lifetime risk over a typical life expectancy."""
    if life_years <= 0:
        raise ValueError("life_years must be positive")
    return lifetime_mm / life_years


# --- Parsing -----------------------------------------------------------------

_ONE_IN_RE = re.compile(r"\b1\s*(?:in|/|:)\s*([0-9][0-9,\.\s]*)", re.I)
_PER_RE = re.compile(
    r"([0-9][0-9,\.]*)\s*(?:deaths?|fatalit(?:y|ies))?\s*per\s*([0-9][0-9,\.]*)",
    re.I,
)


def _to_float(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


@dataclass
class ParsedRisk:
    micromorts: float
    original: str


def parse(text: str) -> ParsedRisk:
    """Best-effort parse of common phrasings: '1 in 11,000', '5 per 100000', etc."""
    m = _ONE_IN_RE.search(text)
    if m:
        return ParsedRisk(from_one_in(_to_float(m.group(1))), text.strip())
    m = _PER_RE.search(text)
    if m:
        return ParsedRisk(
            from_deaths_per(_to_float(m.group(1)), _to_float(m.group(2))),
            text.strip(),
        )
    raise ValueError(f"cannot parse risk expression: {text!r}")

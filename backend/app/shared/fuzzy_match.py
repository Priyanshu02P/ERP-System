"""
Fuzzy matching of free-text line descriptions (as read off a vendor
PDF/photo by an OCR bot) against the internal Product master.

Stdlib-only (difflib) on purpose - this is a first-pass match to route
ingested lines into "confidently mapped" vs "needs human review", not a
production-grade search index. See
docs/Procurement_Implementation_Plan.md \u00a72.5.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional

# Below this confidence, a line is left unmapped (product_id = NULL) and
# must be resolved by a human during review rather than trusted blindly.
DEFAULT_MATCH_THRESHOLD = 0.55


@dataclass
class ProductMatchCandidate:
    id: int
    code: str
    name: str


@dataclass
class ProductMatchResult:
    product_id: Optional[int]
    confidence: float


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def best_product_match(
    raw_description: str,
    candidates: Iterable[ProductMatchCandidate],
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> ProductMatchResult:
    """
    Score `raw_description` against each candidate's code and name, taking
    the best of the two per candidate, then return the overall best match.

    Always returns a confidence score (even below threshold) so the review
    UI can show "closest guess: 0.42" rather than nothing - but product_id
    is only populated when confidence clears the threshold.
    """
    best_id: Optional[int] = None
    best_score = 0.0

    for candidate in candidates:
        score = max(_similarity(raw_description, candidate.name), _similarity(raw_description, candidate.code))
        if score > best_score:
            best_score = score
            best_id = candidate.id

    if best_score >= threshold:
        return ProductMatchResult(product_id=best_id, confidence=round(best_score, 3))
    return ProductMatchResult(product_id=None, confidence=round(best_score, 3))

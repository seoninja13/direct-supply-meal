"""
agents/depth_scorer.py — 6-dimension exploration depth scoring at agent entry.

Per AGENT-WORKFLOW §9: every route into an agent Director calls `score_query()`
first. In Phase 1 the score is advisory — logged on the trace row but never
acted on. Phase 2 flips `should_decompose()` from False to real dispatch.

Phase 1 heuristic: keyword-based buckets. Works because NL Ordering queries
are short (20-100 chars) and Menu Planner queries are longer and carry
distinctive verbs ("plan", "optimize", "balance").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["shallow", "moderate", "deep", "very_deep", "exhaustive", "strategic"]

# (low, high) total score bucket -> (level, n_agents, hierarchy_shape).
_DISPATCH: dict[tuple[int, int], tuple[Level, int, str]] = {
    (0, 2): ("shallow", 1, "single_worker"),
    (3, 4): ("moderate", 3, "manager_plus_workers"),
    (5, 6): ("deep", 5, "director_plus_managers_plus_workers"),
    (7, 8): ("very_deep", 10, "director_plus_2_3_managers_plus_workers"),
    (9, 10): ("exhaustive", 15, "full_hierarchy"),
    (11, 12): ("strategic", 20, "multi_director"),
}


@dataclass
class DepthDimensions:
    """Raw 0-2 scores for each of the 6 rubric axes."""

    scope: int = 0
    information_density: int = 0
    reasoning_depth: int = 0
    verification_need: int = 0
    consistency_risk: int = 0
    domain_breadth: int = 0

    @property
    def total(self) -> int:
        return (
            self.scope
            + self.information_density
            + self.reasoning_depth
            + self.verification_need
            + self.consistency_risk
            + self.domain_breadth
        )


_PLAN_WORDS = ("plan", "optimize", "balance", "compose", "design", "replan")
_COMPLIANCE_WORDS = (
    "diabet",
    "renal",
    "sodium",
    "allergen",
    "puree",
    "soft food",
    "compliance",
)
_VAGUE_WORDS = ("roughly", "something like", "around", "maybe", "a few", "some")
_DOMAIN_KEYWORDS = {
    "recipes": ("recipe", "dish", "meal", "food"),
    "orders": ("order", "delivery", "deliver"),
    "facility": ("facility", "wing", "unit", "kitchen"),
    "inventory": ("inventory", "stock", "on hand"),
    "budget": ("budget", "cost", "price", "cent"),
}


def _dimension_scores(text: str) -> DepthDimensions:
    t = text.lower()
    tokens = t.split()

    # Scope: distinct entity types mentioned (facility + date + ingredient / recipe).
    entity_hits = 0
    if any(w in t for w in ("facility", "wing", "unit")):
        entity_hits += 1
    if any(w in t for w in ("today", "tomorrow", "monday", "tuesday", "wednesday",
                            "thursday", "friday", "saturday", "sunday", "next week")):
        entity_hits += 1
    if any(w in t for w in ("recipe", "meal", "dish")):
        entity_hits += 1
    scope = min(entity_hits, 2)

    # Information density: length buckets.
    n = len(tokens)
    if n < 30:
        density = 0
    elif n <= 100:
        density = 1
    else:
        density = 2

    # Reasoning depth: planning verbs demand synthesis, not lookup.
    reasoning = 2 if any(w in t for w in _PLAN_WORDS) else 0

    # Verification need: compliance/dietary keywords → must deterministically check.
    verification = 2 if any(w in t for w in _COMPLIANCE_WORDS) else 0

    # Consistency risk: vague language → high variance across runs.
    vague = sum(1 for w in _VAGUE_WORDS if w in t)
    consistency = 2 if vague >= 2 else (1 if vague == 1 else 0)

    # Domain breadth: how many of the 5 canonical domains the query touches.
    domains_hit = sum(
        any(kw in t for kw in kws) for kws in _DOMAIN_KEYWORDS.values()
    )
    if domains_hit >= 4:
        breadth = 2
    elif domains_hit >= 2:
        breadth = 1
    else:
        breadth = 0

    return DepthDimensions(
        scope=scope,
        information_density=density,
        reasoning_depth=reasoning,
        verification_need=verification,
        consistency_risk=consistency,
        domain_breadth=breadth,
    )


def _dispatch_bucket(total: int) -> tuple[Level, int, str]:
    for (low, high), triple in _DISPATCH.items():
        if low <= total <= high:
            return triple
    return ("shallow", 1, "single_worker")


def score_query(text: str) -> tuple[Level, int, str]:
    """Score a raw user query and return (level, n_agents, hierarchy_shape).

    If any single dimension scored 2, the bucket is escalated by one step
    (per CLAUDE.md § Exploration Depth Scoring rule). Below we cap that at
    the highest bucket.
    """
    dims = _dimension_scores(text or "")
    total = dims.total
    if any(
        v == 2
        for v in (
            dims.scope,
            dims.information_density,
            dims.reasoning_depth,
            dims.verification_need,
            dims.consistency_risk,
            dims.domain_breadth,
        )
    ):
        total = min(total + 1, 12)
    return _dispatch_bucket(total)


def should_decompose(total_score: int) -> bool:
    """Phase 1: always False. Phase 2 seam: `return total_score >= 7`."""
    return False


# Phase 2 Graduation: should_decompose() body flips from unconditional False
# to `return total_score >= 7`; a pre-flight cheap Haiku decomposition then
# fans out to N Director sessions and recomposes. Seam is this function only.

"""
agents/depth_scorer.py — 6-dimension exploration depth scoring at agent entry.

PSEUDOCODE (Phase 3 stub — no behavior).

Per AGENT-WORKFLOW §9: every route into an agent Director calls score_query()
first. The score is logged on the trace row even when decomposition is skipped.

Phase 1 behavior: score + log. Phase 2 behavior: flip should_decompose() from
False to actual-dispatch.

  1. score_query(text) -> (level: str, n_agents: int, shape: str)
     - Apply 6-dimension rubric: scope, information_density, reasoning_depth,
       verification_need, consistency_risk, domain_breadth (each 0-2).
     - Total 0-12 → level string "shallow"/"moderate"/"deep"/"very_deep"/
       "exhaustive"/"strategic"; n_agents + hierarchy shape follow the
       DuloCore dispatch mapping.
  2. should_decompose(total_score) -> bool
     - Phase 1: ALWAYS return False regardless of score.
     - Phase 2 seam: return total_score >= 7.

Typical NL Ordering scores 2–4; Menu Plan 5–6; score ≥ 7 = out-of-scope
"replan every facility for next month."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["shallow", "moderate", "deep", "very_deep", "exhaustive", "strategic"]

# Dispatch mapping from CLAUDE.md + AGENT-WORKFLOW §9 rubric.
# (level, n_agents, hierarchy_shape) keyed by total score buckets.
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
        """Sum of the six 0-2 axes, 0-12."""
        return (
            self.scope
            + self.information_density
            + self.reasoning_depth
            + self.verification_need
            + self.consistency_risk
            + self.domain_breadth
        )


def score_query(text: str) -> tuple[Level, int, str]:
    """Score a raw user query and return the (level, n_agents, shape) triple.

    Args:
        text: free-form user input that initiated an agent session.

    Returns:
        (level, n_agents, hierarchy_shape) per the DuloCore depth dispatch table.
    """
    # PSEUDO: 1. Lowercase + tokenize text.
    # PSEUDO: 2. Score each of the 6 dimensions by simple heuristics:
    # PSEUDO:    - scope: count distinct entities (facility, date, ingredient) → 0/1/2.
    # PSEUDO:    - information_density: token length buckets (<30, 30-100, >100) → 0/1/2.
    # PSEUDO:    - reasoning_depth: presence of "plan"/"optimize"/"balance" → 2, else 0 or 1.
    # PSEUDO:    - verification_need: compliance/dietary keywords → 2; deterministic lookup → 0.
    # PSEUDO:    - consistency_risk: open-ended language ("roughly", "something like") → 1 or 2.
    # PSEUDO:    - domain_breadth: how many of {recipes,orders,facility,inventory,budget} are mentioned.
    # PSEUDO: 3. Build DepthDimensions; take .total.
    # PSEUDO: 4. If any single axis == 2, escalate by one bucket (per CLAUDE.md rule).
    # PSEUDO: 5. Look up triple in _DISPATCH by bucket containing total.
    # PSEUDO: 6. Return triple.
    raise NotImplementedError("Phase 3 stub — score_query not yet implemented")


def should_decompose(total_score: int) -> bool:
    """Decide whether a query should trigger pre-flight decomposition.

    Phase 1 contract: ALWAYS False regardless of score.
    Phase 2 contract (at the seam): True when total_score >= 7.
    """
    # PSEUDO: Phase 1 body = `return False` unconditionally.
    # PSEUDO: Phase 2 seam replacement = `return total_score >= 7`.
    return False


def _dispatch_bucket(total: int) -> tuple[Level, int, str]:
    """Find the (low, high) bucket in _DISPATCH that contains `total` and return the triple."""
    # PSEUDO: Iterate _DISPATCH.items(); return value where low <= total <= high.
    # PSEUDO: Fallback to ("shallow", 1, "single_worker") if total out of range.
    raise NotImplementedError


# Phase 2 Graduation: should_decompose() body flips from unconditional False to
# `return total_score >= 7`; a pre-flight cheap Haiku decomposition pass then fans
# out to N Director sessions and recomposes. Seam is this function only — the
# score_query() body stays identical. Per AGENT-WORKFLOW §9 + §10 row 6.

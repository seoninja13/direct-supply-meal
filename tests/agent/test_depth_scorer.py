"""Unit tests for agents.depth_scorer."""

from __future__ import annotations

from agents.depth_scorer import (
    DepthDimensions,
    _dimension_scores,
    _dispatch_bucket,
    score_query,
    should_decompose,
)


def test_dispatch_bucket_maps_total_to_triple():
    assert _dispatch_bucket(0) == ("shallow", 1, "single_worker")
    assert _dispatch_bucket(3) == ("moderate", 3, "manager_plus_workers")
    assert _dispatch_bucket(6) == ("deep", 5, "director_plus_managers_plus_workers")
    assert _dispatch_bucket(12) == ("strategic", 20, "multi_director")


def test_dispatch_bucket_fallback_for_out_of_range():
    assert _dispatch_bucket(-1) == ("shallow", 1, "single_worker")
    assert _dispatch_bucket(99) == ("shallow", 1, "single_worker")


def test_depth_dimensions_total_sums_axes():
    d = DepthDimensions(scope=2, reasoning_depth=1, domain_breadth=1)
    assert d.total == 4


def test_nl_ordering_typical_query_scores_shallow_or_moderate():
    """"50 Overnight Oats for Tuesday breakfast" — canonical NL order. Short,
    one domain, no planning verbs, no compliance keywords. Should not exceed
    moderate."""
    level, n_agents, _ = score_query("50 Overnight Oats for Tuesday breakfast")
    assert level in ("shallow", "moderate")
    assert n_agents <= 3


def test_menu_planner_query_escalates_to_deep_or_higher():
    """"Plan next week's menus balancing renal, low-sodium, and soft-food residents"
    — planning + compliance + multi-domain. Must not score shallow."""
    level, _, _ = score_query(
        "Plan next week's menus balancing renal, low-sodium, and soft-food residents"
    )
    assert level not in ("shallow",)


def test_compliance_keywords_set_verification_axis_to_two():
    dims = _dimension_scores("Check renal compliance for dinner")
    assert dims.verification_need == 2


def test_planning_verb_sets_reasoning_to_two():
    dims = _dimension_scores("optimize our weekly menu")
    assert dims.reasoning_depth == 2


def test_vague_language_raises_consistency_risk():
    dims = _dimension_scores("maybe something like a few meals roughly around Tuesday")
    assert dims.consistency_risk >= 1


def test_domain_breadth_counts_matches():
    dims = _dimension_scores(
        "Order a recipe for the facility with a budget cap, checking inventory"
    )
    # recipe + facility + budget + inventory + order = 5 domains → breadth == 2.
    assert dims.domain_breadth == 2


def test_should_decompose_is_false_in_phase_one():
    assert should_decompose(0) is False
    assert should_decompose(12) is False

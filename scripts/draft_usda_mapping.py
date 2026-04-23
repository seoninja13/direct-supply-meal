"""
ONE-SHOT UTILITY — draft candidate USDA mappings for recipe ingredients.

Per PRP-USDA-MACROS-001 §5 T-USDA-MACROS-005 (Phase B).

This script is a ONE-SHOT developer utility, not a service. It is run by hand
to generate `fixtures/ingredient_fdc_mapping_candidates.json`, which a human
then reviews and prunes into the final authoritative map (T-006 PoC +
T-013 full) `fixtures/ingredient_fdc_mapping.json`.

PSEUDOCODE:
1. One-line summary of module purpose.
   - For each distinct ingredient name in fixtures/recipes.json, emit the
     top-3 closest USDA foods by fuzzy description match, flagged with
     raw/cooked/canned/dried/powdered keywords so the human reviewer can
     prefer raw per PRP §D10.
2. Ordered steps.
   a. Load recipes.json, collect distinct ingredient names (verbatim).
   b. Load all `usda_food` rows (fdc_id, description) from the SQLite DB.
   c. For each ingredient name, lightly normalize (lowercase + strip common
      recipe qualifiers: diced, chopped, fresh, raw, large, small, baby)
      for MATCHING only, and keep the raw verbatim name for output.
   d. Score every USDA description against the normalized name.
      - Primary: rapidfuzz.fuzz.token_set_ratio (handles "chicken, broiler
        or fryers, breast" vs "chicken breast" well).
      - Fallback (if rapidfuzz unavailable): difflib.SequenceMatcher.ratio
        on the lowercased strings, scaled ×100.
   e. Raw bias: when two candidates tie on score, prefer the one whose
      description contains "raw" and does NOT contain any of
      cooked / fried / roasted / baked / grilled / boiled / canned /
      powder / dried — UNLESS the ingredient name itself carries one of
      those qualifiers (e.g. "dried cranberries"), in which case we do NOT
      bias against it.
   f. Return top-3 per ingredient by final score.
   g. Flag each candidate's description with any of
      [raw, cooked, canned, dried, powdered] keywords that appear in it,
      surfaced to the human reviewer in the output JSON.
3. Inputs / Outputs.
   - Input:  /app/data/ds-meal.db (usda_food table, 14,585 rows),
             fixtures/recipes.json.
   - Output: fixtures/ingredient_fdc_mapping_candidates.json.
4. Side effects.
   - Writes one JSON file under fixtures/. Read-only against the DB.

IMPLEMENTATION: Phase B (T-USDA-MACROS-005).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.db.database import _sync_url
from app.db.init_schema import init_schema  # noqa: F401 — registers tables
from app.models.usda_food import UsdaFood

# --- Paths --------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
RECIPES_JSON = FIXTURES_DIR / "recipes.json"
OUTPUT_JSON = FIXTURES_DIR / "ingredient_fdc_mapping_candidates.json"

# --- Scoring backend ----------------------------------------------------
# Prefer rapidfuzz.token_set_ratio; fall back to difflib.SequenceMatcher.
try:
    from rapidfuzz import fuzz as _rf_fuzz

    _SCORER_NAME = "rapidfuzz.token_set_ratio"

    def _score(a: str, b: str) -> float:
        # token_set_ratio is robust to word-order and extra tokens such as
        # "Chicken, broilers or fryers, breast, skinless, boneless, meat only, raw".
        return float(_rf_fuzz.token_set_ratio(a, b))

except ImportError:  # pragma: no cover — stdlib fallback path.
    from difflib import SequenceMatcher

    _SCORER_NAME = "difflib.SequenceMatcher.ratio"

    def _score(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100.0


# --- Normalization ------------------------------------------------------
# Common recipe qualifiers we strip before matching. Ordered longest-first
# so multi-word qualifiers bind before single-word ones.
_RECIPE_QUALIFIERS = (
    "chopped",
    "diced",
    "fresh",
    "large",
    "small",
    "baby",
    "raw",
)

# Keyword families for flagging / raw-bias tie-breaking.
_RAW_KEYWORD = "raw"
_NON_RAW_KEYWORDS = (
    "cooked",
    "fried",
    "roasted",
    "baked",
    "grilled",
    "boiled",
    "canned",
    "powder",
    "dried",
)

# What we publish in the `flags` array on each candidate.
_FLAG_KEYWORDS = ("raw", "cooked", "canned", "dried", "powdered")


def _normalize(name: str) -> str:
    """Light normalization for MATCHING only. Preserves original for output."""
    tokens = name.lower().split()
    cleaned = [t for t in tokens if t not in _RECIPE_QUALIFIERS]
    # If stripping removed everything (e.g. ingredient was literally "fresh"),
    # fall back to the lowercased original so we still have something to match.
    if not cleaned:
        return name.lower()
    return " ".join(cleaned)


def _has_keyword(text: str, keyword: str) -> bool:
    """Word-boundary keyword match (so 'cooked' does NOT match 'uncooked').

    For 'powder' we also want to match 'powdered' — so allow an optional
    trailing 'ed'. Same convention for 'dried' which we match only as a
    whole word.
    """
    # Allow a single 'ed' suffix to catch 'powder'/'powdered' both ways.
    pattern = rf"\b{re.escape(keyword)}(?:ed)?\b"
    return re.search(pattern, text) is not None


def _flags_for(description: str) -> list[str]:
    """Return keyword flags present in a USDA description (word-boundary match)."""
    d = description.lower()
    return [kw for kw in _FLAG_KEYWORDS if _has_keyword(d, kw)]


def _ingredient_carries_qualifier(normalized_name: str) -> bool:
    """Did the user's ingredient name itself include a non-raw qualifier?

    E.g. "dried cranberries" → we should NOT down-rank dried USDA entries.
    Note: normalization already stripped "raw", so "raw" as a carried
    qualifier is handled separately via the raw-bias path.
    """
    # We check the NORMALIZED name for non-raw qualifiers. The normalized form
    # has already stripped common recipe qualifiers like "diced", so anything
    # left here is an intentional food-state descriptor from the user.
    return any(_has_keyword(normalized_name, kw) for kw in _NON_RAW_KEYWORDS)


def _raw_bias_key(description: str, allow_non_raw: bool) -> int:
    """Tie-breaker key — higher is more preferred.

    Returns:
      2  — description contains "raw" AND no non-raw keyword.
      1  — description has neither a raw nor non-raw keyword (neutral).
      0  — description contains a non-raw keyword (cooked/fried/canned/...).

    If `allow_non_raw` is True (user asked for e.g. "dried cranberries"),
    the penalty on non-raw entries is lifted and we return 1 for them.
    """
    d = description.lower()
    has_raw = _has_keyword(d, _RAW_KEYWORD)
    has_non_raw = any(_has_keyword(d, kw) for kw in _NON_RAW_KEYWORDS)

    if has_raw and not has_non_raw:
        return 2
    if not has_raw and not has_non_raw:
        return 1
    # has_non_raw (possibly with or without raw)
    return 1 if allow_non_raw else 0


def _collect_ingredient_names(recipes_path: Path) -> list[str]:
    """Read recipes.json; return verbatim distinct ingredient names, sorted."""
    with recipes_path.open("r", encoding="utf-8") as fh:
        recipes = json.load(fh)
    seen: set[str] = set()
    for recipe in recipes:
        for ing in recipe.get("ingredients", []):
            seen.add(ing["name"])
    return sorted(seen)


def _load_usda_rows(session: Session) -> list[tuple[int, str]]:
    """Return all (fdc_id, description) tuples from usda_food."""
    rows = session.exec(select(UsdaFood.fdc_id, UsdaFood.description)).all()
    return [(int(fdc), str(desc)) for fdc, desc in rows]


def _top_candidates(
    normalized_name: str,
    usda_rows: list[tuple[int, str]],
    allow_non_raw: bool,
    k: int = 3,
) -> list[dict[str, object]]:
    """Score every USDA row against the normalized name; return top-k."""
    scored: list[tuple[float, int, int, int, str]] = []
    for fdc_id, description in usda_rows:
        s = _score(normalized_name, description.lower())
        bias = _raw_bias_key(description, allow_non_raw)
        # Length penalty — shorter descriptions at the same score are
        # usually the "cleaner" USDA reference (e.g. "Olive oil" beats
        # "Mayonnaise, reduced fat, with olive oil" at tied score=100).
        length = len(description)
        scored.append((s, bias, length, fdc_id, description))

    # Primary sort: score desc. Tie-break chain:
    #   raw-bias desc, then length asc (shorter = cleaner), then fdc_id asc.
    scored.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))

    top: list[dict[str, object]] = []
    for s, _bias, _length, fdc_id, description in scored[:k]:
        top.append(
            {
                "fdc_id": fdc_id,
                "description": description,
                "score": round(s, 2),
                "flags": _flags_for(description),
            }
        )
    return top


def main() -> int:
    if not RECIPES_JSON.exists():
        print(f"ERROR: recipes fixture not found at {RECIPES_JSON}", file=sys.stderr)
        return 1

    ingredient_names = _collect_ingredient_names(RECIPES_JSON)
    if not ingredient_names:
        print("ERROR: no ingredients found in recipes.json", file=sys.stderr)
        return 1

    engine = create_engine(_sync_url(), future=True)
    with Session(engine) as session:
        usda_rows = _load_usda_rows(session)

    if not usda_rows:
        print(
            "ERROR: usda_food table is empty — run scripts/seed_usda.py first",
            file=sys.stderr,
        )
        return 1

    entries: list[dict[str, object]] = []
    for name in ingredient_names:
        normalized = _normalize(name)
        allow_non_raw = _ingredient_carries_qualifier(normalized)
        candidates = _top_candidates(normalized, usda_rows, allow_non_raw, k=3)
        entries.append(
            {
                "ingredient_name": name,
                "normalized": normalized,
                "candidates": candidates,
                "chosen": None,
                "note": None,
            }
        )

    out = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "scorer": _SCORER_NAME,
        "notes": (
            "One-shot output from scripts/draft_usda_mapping.py. "
            "Human finalizes selections per T-USDA-MACROS-006 (PoC: Veggie "
            "Omelette) and T-USDA-MACROS-013 (remaining 44)."
        ),
        "ingredients": entries,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(
        f"Wrote {len(entries)} ingredient candidate entries "
        f"to {OUTPUT_JSON.relative_to(REPO_ROOT)} using {_SCORER_NAME}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Phase 2 Graduation: once mapping is finalized (T-013), delete this script
# and fold any re-run logic into an Alembic data migration that ships the
# frozen ingredient→fdc_id map.

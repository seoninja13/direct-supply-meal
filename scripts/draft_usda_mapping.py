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
     top-3 closest USDA foods by fuzzy description match, re-ranked to
     prefer raw / short / head-word-matched entries per PRP §D10 so a
     human reviewer (T-013) sees useful top-1 picks instead of the junk
     descriptions that token_set_ratio tied at 100.
2. Ordered steps.
   a. Load recipes.json, collect distinct ingredient names (verbatim).
   b. Load all `usda_food` rows (fdc_id, description) from the SQLite DB.
   c. For each ingredient name, lightly normalize (lowercase + strip common
      recipe qualifiers: diced, chopped, fresh, raw, large, small, baby)
      for MATCHING only, and keep the raw verbatim name for output.
   d. Score every USDA description against the normalized name and its
      simple singular/plural variant (max of the two) so "eggs" scores
      "Egg, whole, raw" correctly.
      - Primary: rapidfuzz.fuzz.token_set_ratio.
      - Fallback (if rapidfuzz unavailable): difflib.SequenceMatcher.ratio
        on the lowercased strings, scaled ×100.
   e. Rerank the base score with multiplicative/additive heuristics:
      raw-preference (+30%), processed-token penalty (−50%), compound-
      dish penalty (−60%), brand-caps penalty (−40%), short-description
      bias (+15%), exact whole-word bonus (+15), head-word bonus (+30
      comma-structured / +10 otherwise). See `_rerank_score`.
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


def _plural_variants(normalized: str) -> tuple[str, ...]:
    """Return normalized + a simple singular/plural sibling for scoring.

    USDA uses both forms: "Onions, raw" but "Egg, whole, raw". Ingredient
    names likewise mix: "large eggs" (plural) vs "onion" (singular).
    Flipping only the last (head) word is enough for our fixture and
    avoids the complexity of a full lemmatizer.
    """
    words = normalized.split()
    if not words:
        return (normalized,)
    head = words[-1]
    variants = [normalized]
    if len(head) > 3 and head.endswith("s") and not head.endswith("ss"):
        variants.append(" ".join([*words[:-1], head[:-1]]))
    else:
        variants.append(" ".join([*words[:-1], head + "s"]))
    return tuple(variants)


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


# --- Rerank penalty/bonus terms (PRP §D10) -----------------------------
# The base rapidfuzz score often ties junk descriptions at 100 because
# token_set_ratio ignores unmatched tokens on either side. The heuristics
# below push raw / short / exact-prefix USDA entries above compound
# dishes, brand SKUs, and fried/baked/canned variants — unless the
# ingredient itself names that state.

# Tokens marking a USDA description as processed / ready-made / not-raw.
# 0.50 multiplier UNLESS the ingredient name carries the same word.
_PROCESSED_TOKENS = (
    "cooked",
    "fried",
    "roasted",
    "baked",
    "grilled",
    "boiled",
    "canned",
    "frozen dinner",
    "pizza",
    "babyfood",
    "bread,",
    "roll,",
    "cookie",
    "cracker",
    "muffin",
    "school lunch",
    "mcdonald's",
    "burger king",
    "fast food",
    "tortilla chip",
)

# Prepared-dish prefixes — 0.40 multiplier unless ingredient names dish.
_COMPOUND_DISH_PREFIXES = (
    "salad, ",
    "soup, ",
    "stew, ",
    "sandwich, ",
    "pizza, ",
    "burrito, ",
    "pie, ",
    "cake, ",
    "meal, ",
    "entree, ",
    "dinner, ",
)

# All-caps brand tokens (≥ 4 uppercase letters): 0.60 multiplier.
_BRAND_CAPS_RE = re.compile(r"\b[A-Z]{4,}\b")


def _rerank_score(
    base: float,
    description: str,
    ingredient_words: set[str],
    normalized_name: str,
) -> float:
    """Apply heuristic reranking to a base rapidfuzz score (PRP §D10).

    Heuristics:
      1. Raw preference — x1.30 if description contains "raw" and the
         ingredient isn't explicitly cooked.
      2. Processed-token penalty — x0.50 for ready-made tokens UNLESS the
         ingredient name carries the token.
      3. Compound-dish penalty — x0.40 for "Salad, X"/"Soup, X"/...
         unless the ingredient itself names the dish.
      4. Brand-caps penalty — x0.60 for ALL-CAPS brand tokens.
      5. Short-description bias — x1.15 when ingredient name is short
         (<= 3 words) AND USDA entry is short (<= 5 words).
      6. Exact whole-word bonus — +15 if every ingredient word appears
         (plural-tolerant) as a whole word in the description.
      7. Head-word bonus — +30 if the description's first token
         (pre-comma) equals an ingredient word AND is followed by a
         comma (strong USDA "Food, qualifier" pattern); +10 if matched
         but not comma-structured (e.g. "Onion dip, light").
    """
    score = base
    d_lower = description.lower()
    ingredient_is_cooked = any(
        _has_keyword(normalized_name, kw) for kw in _NON_RAW_KEYWORDS
    )

    # 1. Raw preference.
    if _has_keyword(d_lower, _RAW_KEYWORD) and not ingredient_is_cooked:
        score *= 1.30

    # 2. Processed-token penalty (skip tokens the ingredient itself carries).
    for tok in _PROCESSED_TOKENS:
        if tok in d_lower:
            bare = tok.rstrip(",").strip()
            if bare and bare in normalized_name:
                continue
            score *= 0.50
            # Only apply once — multiple hits don't compound.
            break

    # 3. Compound-dish prefix penalty.
    for prefix in _COMPOUND_DISH_PREFIXES:
        if d_lower.startswith(prefix):
            dish_word = prefix.rstrip(", ").strip()
            if dish_word and dish_word in normalized_name:
                break
            score *= 0.40
            break

    # 4. Brand-caps penalty.
    if _BRAND_CAPS_RE.search(description):
        score *= 0.60

    # 5. Short-description bias for short ingredient names.
    if len(ingredient_words) <= 3 and len(description.split()) <= 5:
        score *= 1.15

    # 6. Exact whole-word match bonus (plural tolerant — "eggs" ↔ "egg").
    def _word_in(w: str) -> bool:
        if re.search(rf"\b{re.escape(w)}\b", d_lower):
            return True
        if w.endswith("s") and re.search(rf"\b{re.escape(w[:-1])}\b", d_lower):
            return True
        if re.search(rf"\b{re.escape(w)}s\b", d_lower):
            return True
        return False

    if ingredient_words and all(_word_in(w) for w in ingredient_words):
        score += 15.0

    # 7. Head-word bonus — USDA uses "Butter, salted" / "Onions, raw".
    # Require the description's first token (pre-comma/space) to match
    # an ingredient word, plural tolerant. Reward comma-structured
    # entries more (pattern "Food, X" strongly signals a base ingredient
    # over "Onion dip, light").
    first_comma = d_lower.find(",")
    first_token = re.split(r"[,\s]", d_lower, maxsplit=1)[0]
    has_comma_after_head = first_comma != -1 and first_comma == len(first_token)
    for w in ingredient_words:
        if first_token == w or first_token == w + "s" or first_token + "s" == w:
            score += 30.0 if has_comma_after_head else 10.0
            break

    return score


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
    """Score every USDA row; return top-k after heuristic rerank (PRP §D10).

    Base score = rapidfuzz.token_set_ratio of (normalized ingredient
    name OR its plural sibling) vs lowercased description — max of the
    two so singular/plural mismatch doesn't drop the obvious winner.
    `_rerank_score` then applies raw-bias, processed-token penalty,
    compound-dish penalty, brand-caps penalty, short-desc bias, exact-
    word bonus, and head-word bonus.
    """
    ingredient_words = {
        w for w in re.findall(r"\b[a-z]+\b", normalized_name) if len(w) > 1
    }
    variants = _plural_variants(normalized_name)
    scored: list[tuple[float, int, int, int, str]] = []
    for fdc_id, description in usda_rows:
        d_lower = description.lower()
        base = max(_score(v, d_lower) for v in variants)
        final = _rerank_score(base, description, ingredient_words, normalized_name)
        bias = _raw_bias_key(description, allow_non_raw)
        # Length penalty — shorter descriptions at the same final score
        # are usually the "cleaner" USDA reference (e.g. "Olive oil" beats
        # "Mayonnaise, reduced fat, with olive oil" at tied score).
        length = len(description)
        scored.append((final, bias, length, fdc_id, description))

    # Primary sort: final (reranked) score desc. Tie-break chain:
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

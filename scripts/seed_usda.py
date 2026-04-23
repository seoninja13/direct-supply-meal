"""
Seed fixtures/macro.csv (USDA per-100g macronutrient reference) into the
`usda_food` table. Idempotent loader for T-USDA-MACROS-004 of
PRP-USDA-MACROS-001 (Phase A).

PSEUDOCODE:
1. One-line summary of module purpose.
   - Bulk-load 14,585 USDA rows from fixtures/macro.csv into usda_food.
2. Ordered steps.
   a. Build a sync engine via `_sync_url()` (mirrors scripts/seed_db.py).
   b. Ensure SQLModel schema is created (idempotent create_all).
   c. If the target row count already matches the CSV row count, short-circuit
      with `Seeded 0 USDA rows (already present)` and exit 0.
   d. Otherwise clear the table (DELETE) and bulk-insert rows in chunks of
      1000 per commit for performance on 14k rows.
3. Inputs / Outputs.
   - Input:  fixtures/macro.csv columns
              fdc_id,description,calories,proteinInGrams,
              carbohydratesInGrams,fatInGrams
   - Output: rows in `usda_food` table
              (fdc_id, description, kcal_per_100g,
               protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g)
4. Side effects.
   - Writes to the configured SQLite DB (DATABASE_URL sync form).
   - DELETEs all rows in `usda_food` on a non-idempotent run.

IMPLEMENTATION: Phase A (T-USDA-MACROS-004).
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import create_engine, delete, func, select
from sqlmodel import Session, SQLModel

from app.db.database import _sync_url
from app.db.init_schema import init_schema  # noqa: F401 — registers tables

# Ensure SQLModel.metadata sees the UsdaFood table before create_all.
from app.models.usda_food import UsdaFood

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
MACRO_CSV = FIXTURES_DIR / "macro.csv"

CHUNK_SIZE = 1000


def _iter_rows(path: Path) -> Iterable[dict[str, str]]:
    """Yield CSV rows (as dicts) from fixtures/macro.csv."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        yield from reader


def _float_or_zero(value: str) -> float:
    """Coerce a CSV field to float; treat empty strings as 0.0.

    fixtures/macro.csv has ~850 rows where one or more macro columns are
    blank (USDA didn't report that macro for that food). Representing
    those as 0.0 in the per-100g reference is the standard convention
    the downstream scaling service (T-USDA-MACROS-007) already expects.
    """
    stripped = value.strip()
    if not stripped:
        return 0.0
    return float(stripped)


def _to_model(row: dict[str, str]) -> UsdaFood:
    """Map a CSV row to a UsdaFood model instance."""
    return UsdaFood(
        fdc_id=int(row["fdc_id"]),
        description=row["description"],
        kcal_per_100g=_float_or_zero(row["calories"]),
        protein_g_per_100g=_float_or_zero(row["proteinInGrams"]),
        carbs_g_per_100g=_float_or_zero(row["carbohydratesInGrams"]),
        fat_g_per_100g=_float_or_zero(row["fatInGrams"]),
    )


def _csv_row_count(path: Path) -> int:
    """Count data rows (excluding header) in fixtures/macro.csv."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        # Subtract 1 for the header line.
        return sum(1 for _ in fh) - 1


def _seed_usda(session: Session, csv_path: Path) -> int:
    """Bulk-load fixtures/macro.csv into usda_food. Returns rows inserted.

    Idempotency contract: if the existing row count already equals the CSV row
    count, return 0 and leave the table untouched. Otherwise DELETE and
    repopulate in CHUNK_SIZE-per-commit batches.
    """
    expected = _csv_row_count(csv_path)
    # `session.exec(...)` on a plain SQLAlchemy Core select returns a Row;
    # `.scalar()` gives us the bare integer.
    current_count = session.scalar(select(func.count()).select_from(UsdaFood))

    if current_count == expected:
        return 0

    # Clear and reload. ON CONFLICT UPDATE would also work for Postgres, but
    # the Phase A target is SQLite and a clean DELETE + bulk insert is simpler
    # and matches the "reset" semantics the tests exercise.
    session.exec(delete(UsdaFood))
    session.commit()

    inserted = 0
    batch: list[UsdaFood] = []
    for row in _iter_rows(csv_path):
        batch.append(_to_model(row))
        if len(batch) >= CHUNK_SIZE:
            session.add_all(batch)
            session.commit()
            inserted += len(batch)
            batch = []

    if batch:
        session.add_all(batch)
        session.commit()
        inserted += len(batch)

    return inserted


def main() -> int:
    # Use a SYNC engine for the script; app runtime uses the async engine.
    engine = create_engine(_sync_url(), future=True)

    # Ensure parent dir for SQLite file.
    url = str(engine.url)
    if url.startswith("sqlite:////"):
        db_path = Path("/" + url.split("sqlite:////", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)
    elif url.startswith("sqlite:///"):
        db_path = Path(url.split("sqlite:///", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # Create tables (idempotent).
    SQLModel.metadata.create_all(engine)

    if not MACRO_CSV.exists():
        print(
            f"ERROR: fixtures/macro.csv not found at {MACRO_CSV}",
            file=sys.stderr,
        )
        return 1

    with Session(engine) as session:
        inserted = _seed_usda(session, MACRO_CSV)

    if inserted == 0:
        print("Seeded 0 USDA rows (already present)")
    else:
        print(f"Seeded {inserted} USDA rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# Phase 2 Graduation: move to Alembic data migration that streams CSV in a
# server-side COPY (Postgres) for O(1) memory regardless of catalog size.

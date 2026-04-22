"""
agents/observability.py — Trace ingestion for Layer 1 of the Karpathy Auto-Research loop.

PSEUDOCODE (Phase 3 stub — no behavior).

Implements the single entry point `record_outcome(trace_row)` called from every
agent driver in a `finally` block. Writes one row to the SQLite `agent_trace`
table AND one JSONL line to `logs/agent_trace.jsonl`. Optionally dumps full
payloads to `logs/agent_payloads/{trace_id}.json`.

Per KARPATHY-AUTO-RESEARCH-WORKFLOW §3 and §4, per AGENT-WORKFLOW §3 observability.

  1. Accept a trace_row dict with the 10 canonical fields (id is auto-assigned
     post-insert; caller passes the rest).
  2. Validate required fields are present.
  3. Open a short-lived async SQLite session.
  4. INSERT into agent_trace. Commit. Close.
  5. Append one JSONL line to logs/agent_trace.jsonl (atomic append).
  6. If payload passed, write logs/agent_payloads/{trace_id}.json.
  7. Return the assigned trace id.

Design rules from the workflow:
  - NEVER fails in a way that breaks the agent (wrap exceptions, log, swallow).
  - NEVER clusters, embeds, or calls LLMs here — pure ingestion.
  - Keeps the function body short (~30 lines Phase 1).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Canonical trace row field contract per KARPATHY §3 (agent_trace table).
TRACE_FIELDS: tuple[str, ...] = (
    "ts",
    "agent_name",
    "query_text",
    "tool_calls_json",
    "outcome",
    "confidence_score",
    "latency_ms",
    "cost_cents",
    "notes",
)

# Filesystem sinks.
JSONL_PATH = Path("logs/agent_trace.jsonl")
PAYLOADS_DIR = Path("logs/agent_payloads")


async def record_outcome(trace_row: dict[str, Any], payload: dict[str, Any] | None = None) -> int:
    """Persist one agent invocation outcome to SQLite + JSONL.

    Args:
        trace_row: dict containing the 9 canonical agent_trace fields (TRACE_FIELDS).
                   `id` is auto-assigned by SQLite.
        payload: optional full request/response payload for deep post-mortems.
                 Written to logs/agent_payloads/{trace_id}.json when provided.

    Returns:
        int — the newly assigned agent_trace.id.

    Raises:
        Never — all failures are caught + logged. This function MUST NOT break
        the caller's finally block. On failure returns -1.
    """
    # PSEUDO: 1. Validate required fields — every field in TRACE_FIELDS must exist.
    # PSEUDO:    Missing or None for any field → log warning, fill with sensible default.
    # PSEUDO: 2. Serialize tool_calls_json if caller passed a list instead of string.
    # PSEUDO: 3. Open async SQLite session via app/db (import at call time to avoid cycle).
    # PSEUDO: 4. Execute INSERT INTO agent_trace(...) VALUES(...); capture lastrowid.
    # PSEUDO: 5. Commit + close session.
    # PSEUDO: 6. Append `{"id": trace_id, **trace_row}` as one line to JSONL_PATH.
    # PSEUDO:    Create parent dir if missing. Open in append mode.
    # PSEUDO: 7. If payload not None: PAYLOADS_DIR.mkdir(parents=True, exist_ok=True);
    # PSEUDO:    write JSON to PAYLOADS_DIR / f"{trace_id}.json".
    # PSEUDO: 8. Return trace_id.
    # PSEUDO: 9. Wrap 3-8 in try/except — catch ALL, log exception, return -1.
    raise NotImplementedError("Phase 3 stub — record_outcome not yet implemented")


def _validate_trace_row(trace_row: dict[str, Any]) -> dict[str, Any]:
    """Ensure every TRACE_FIELDS key is present; fill defaults."""
    # PSEUDO: For each field in TRACE_FIELDS, if missing set a safe default
    #         (empty string, 0, None per column type).
    # PSEUDO: Coerce tool_calls_json to str via json.dumps if it's a list/dict.
    # PSEUDO: Return the normalized row dict.
    raise NotImplementedError


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Atomic-enough append of one JSON line to the trace log."""
    # PSEUDO: path.parent.mkdir(parents=True, exist_ok=True)
    # PSEUDO: with path.open("a", encoding="utf-8") as f: f.write(json.dumps(row) + "\n")
    raise NotImplementedError


# Phase 2 Graduation: record_outcome() grows an embedding step — MiniLM 384-dim vector
# of query_text serialized to the new agent_trace.embedding BLOB column (Alembic migration).
# Seam is this function's body; signature unchanged. Per KARPATHY §4 "App-Phase 2 note."

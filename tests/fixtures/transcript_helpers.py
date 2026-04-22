"""Helpers for loading + replaying canned Claude transcripts in tests."""

from __future__ import annotations

import copy
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent
CLAUDE_RESPONSES = FIXTURES_DIR / "claude_responses.json"


def load_transcript(key: str, substitutions: dict[str, Any] | None = None) -> list[dict]:
    """Load a named transcript from claude_responses.json.

    `substitutions` replaces `__KEY__` sentinels anywhere in the event tree
    (e.g. __DELIVERY_DATE__ → "2026-04-28"). Returns a deep copy so callers
    can mutate without leaking into other tests.
    """
    data = json.loads(CLAUDE_RESPONSES.read_text(encoding="utf-8"))
    events = copy.deepcopy(data[key]["events"])
    subs = substitutions or {}

    def replace_sentinels(obj):
        if isinstance(obj, dict):
            return {k: replace_sentinels(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [replace_sentinels(v) for v in obj]
        if isinstance(obj, str):
            for sentinel, value in subs.items():
                obj = obj.replace(sentinel, str(value))
            return obj
        return obj

    return replace_sentinels(events)


def replay(events: list[dict]):
    """Return an async-generator factory that yields the given events once.

    The factory accepts the driver's `context` dict (unused by the fake) so
    its shape matches `TranscriptFn`.
    """

    async def _query_fn(_context: dict) -> AsyncIterator[dict]:
        for event in events:
            yield event

    return _query_fn

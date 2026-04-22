"""
agents/llm_client.py — thin one-shot wrapper around claude_agent_sdk.query().

PSEUDOCODE (Phase 3 stub — no behavior).

Used for **stateless single-turn** LLM calls from non-agent code paths:
  - wiki/compiler.py — Haiku synthesis per cluster (cheap, deterministic).
  - app/services/pricing.py — Sonnet cost-estimation refinement.

NOT used by the L1 Directors — those build their own ClaudeSDKClient sessions
(see agents/drivers/menu_planner.py + nl_ordering.py).

  1. call_haiku(prompt, max_tokens) — single-shot Haiku; returns assistant text.
  2. call_sonnet(prompt, max_tokens) — single-shot Sonnet.

Both wrap the SDK's query() generator, consume it to completion, and return the
final assistant string. Errors raise LLMUnavailable (caller can fall back).

Env requirements:
  - ANTHROPIC_API_KEY must be set.
  - CLAUDECODE env var must be UNSET before calling (see DuloCore feedback memo).
"""

from __future__ import annotations

import logging
from typing import Final

# Referenced SDK per CLAUDE.md § "Everything Through Claude Agent SDK".
# Actual import deferred to call sites to keep module import cheap.
try:
    from claude_agent_sdk import query  # noqa: F401
except ImportError:  # pragma: no cover — SDK not installed in stub phase
    query = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

HAIKU_MODEL: Final[str] = "claude-haiku-4-5"
SONNET_MODEL: Final[str] = "claude-sonnet-4-5"

DEFAULT_MAX_TOKENS: Final[int] = 1500


class LLMUnavailable(RuntimeError):
    """Raised when the underlying Anthropic call fails (missing key, 429, 5xx).

    Callers are expected to catch this and fall back — e.g. wiki/compiler.py
    logs and skips the cluster; app/services/pricing.py falls back to static.
    """


async def call_haiku(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """One-shot Haiku call. Returns the assistant text.

    Args:
        prompt: user-turn text. System prompt is intentionally NOT parameterized
                here — this is a stateless utility call, not an agent session.
        max_tokens: hard cap on the response length.

    Returns:
        The assistant text as a plain string.

    Raises:
        LLMUnavailable: any SDK error, network timeout, or 4xx/5xx from upstream.
    """
    # PSEUDO: 1. Verify ANTHROPIC_API_KEY is set; if not, raise LLMUnavailable.
    # PSEUDO: 2. Verify os.environ.get("CLAUDECODE") is unset; if set, unset it
    # PSEUDO:    in a process-local way (see feedback_unset_claudecode_for_sdk).
    # PSEUDO: 3. Build options dict with model=HAIKU_MODEL, max_tokens=max_tokens.
    # PSEUDO: 4. Drive the async generator from claude_agent_sdk.query(prompt, options).
    # PSEUDO: 5. Collect streamed text chunks into a buffer.
    # PSEUDO: 6. Return the joined string.
    # PSEUDO: 7. On ANY exception: log + raise LLMUnavailable(original_error).
    raise NotImplementedError("Phase 3 stub — call_haiku not yet implemented")


async def call_sonnet(prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """One-shot Sonnet call. Same contract as call_haiku, different model."""
    # PSEUDO: Same algorithm as call_haiku with model=SONNET_MODEL.
    # PSEUDO: Kept as a distinct function so callers state intent at the call site.
    raise NotImplementedError("Phase 3 stub — call_sonnet not yet implemented")


# Phase 2 Graduation: swap the bare claude_agent_sdk.query() driver for
# execution.agents.seo.llm_client.call_llm() (DuloCore's OAuth-aware wrapper)
# once ds-meal joins the metered-billing pool. Seam is the body of call_haiku /
# call_sonnet; signatures stay identical. Per CLAUDE.md feedback_anthropic_key_is_max_oauth.

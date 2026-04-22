"""
PSEUDOCODE:
1. Session-start advisory hook. Reads the Karpathy wiki and prepends relevant topic pages to the session's system prompt.
2. Determine agent_name from the hook's stdin JSON (Claude Agent SDK passes session metadata).
3. Read wiki/topics/{agent_name}/TOPICS-INDEX.md (or the global wiki/TOPICS-INDEX.md filtered by agent).
4. Pick top-3 relevant topic pages by recency + confidence_score (Phase 1 heuristic; Phase 2: semantic match).
5. Read those topic files. Concatenate their body text.
6. Output JSON to stdout: `{"hookSpecificOutput": {"additionalContext": "<concatenated wiki content>"}}`.
7. Inputs: stdin JSON from the SDK hook harness.
8. Outputs: stdout JSON per Claude Agent SDK hook protocol.
9. Side effects: read-only filesystem access.

IMPLEMENTATION: Phase 4.

Contract: docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md §8.
"""

import json
import sys
from pathlib import Path


# PSEUDO:
# - payload = json.loads(sys.stdin.read())
# - agent_name = payload.get("agent_name") or derive from ClaudeSDKClient config
# - index_path = Path(".claude/state") ... fallback to wiki/TOPICS-INDEX.md
# - topics = parse_index_for_agent(index_path, agent_name)
# - selected = pick_top_k(topics, k=3)  # by last_compiled desc + confidence_score
# - body = "\n\n".join(read(path) for path in selected)
# - print(json.dumps({"hookSpecificOutput": {"additionalContext": body}}))
def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    # Phase 1: no-op silently (fail-open) so missing wiki never blocks a session.
    # Phase 4: uncomment below.
    # sys.exit(main())
    sys.exit(0)


# Phase 2 Graduation:
#   - pick_top_k() body swaps from heuristic to semantic match against the user's first message.
#     Seam: pick_top_k() body.
#   - When topic count > 50, the hook reads a compact "routing digest" instead of full topic bodies.

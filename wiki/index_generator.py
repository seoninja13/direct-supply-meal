"""
PSEUDOCODE:
1. Walk wiki/topics/**/*.md. Skip files that don't parse as Markdown with YAML frontmatter.
2. Parse each file's frontmatter (title, sources, related_topics, last_compiled, memory_types, confidence_score).
3. Extract the first sentence of the body as the one-line description.
4. Group entries by agent_name (topic file's parent dir).
5. Render wiki/TOPICS-INDEX.md as one Markdown table per agent: topic | file | sources_count | last_compiled | description.
6. Atomic write via tempfile + rename.
7. Inputs: none (walks filesystem).
8. Outputs: wiki/TOPICS-INDEX.md rewritten.
9. Side effects: filesystem writes only.

IMPLEMENTATION: Phase 4.

Rationale: docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md §7 — index + LLM-picks-pages
beats vector search at prototype scale (few pages, LLM judgment > cosine, debuggability).
"""

from pathlib import Path
from typing import Any


# PSEUDO:
# - for path in Path("wiki/topics").rglob("*.md"): parse; collect entry dict.
# - group by parent dir name (= agent_name).
# - render to Markdown.
# - atomic write.
def build_index(wiki_root: Path | None = None) -> Path:
    raise NotImplementedError


# PSEUDO:
# - Return {"title", "sources_count", "last_compiled", "memory_types", "confidence_score", "description"}.
# - description = first sentence of body (split on "\n" then on ". ").
def parse_topic(path: Path) -> dict[str, Any]:
    raise NotImplementedError


# Phase 2 Graduation:
#   - Add optional companion build_vector_index() that also writes a FAISS index alongside the Markdown index,
#     for when topic count exceeds ~50 per agent. Markdown index stays authoritative.

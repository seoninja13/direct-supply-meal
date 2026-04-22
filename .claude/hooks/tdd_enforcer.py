"""
PSEUDOCODE:
1. Advisory PostToolUse hook. Warns when a source file under app/ or agents/ is edited without a corresponding tests/ file edit in the same session.
2. Maps source paths to expected test paths:
   - app/services/compliance.py → tests/unit/test_compliance.py
   - app/routes/orders.py → tests/integration/test_orders_api.py
   - agents/tools_sdk.py → tests/agent/test_tools_sdk.py
3. State is journaled to .claude/state/tdd_enforcer.jsonl — one line per Edit/Write event.
4. On each invocation: check if the edited source file has a test path that has NOT been touched in this session.
5. If mismatch → print warning to stderr with `decision: warn`. Never blocks.
6. Inputs: stdin JSON from SDK hook harness (includes tool_name, tool_input.file_path).
7. Outputs: stdout JSON `{"decision": "warn", "reason": "..."}` OR silent.
8. Side effects: append to .claude/state/tdd_enforcer.jsonl.

IMPLEMENTATION: Phase 4.

Reference: docs/workflows/PROTOCOL-APPLICATION-MATRIX.md §P10.
"""

import json
import sys
from pathlib import Path


SOURCE_TO_TEST_MAP = {
    # app/services/{name}.py → tests/unit/test_{name}.py
    # app/routes/{name}.py → tests/integration/test_{name}_api.py
    # agents/tools_sdk.py → tests/agent/test_tools_sdk.py
    # agents/drivers/{name}.py → tests/agent/test_{name}_driver.py
    # wiki/compiler.py → tests/unit/test_wiki_compiler.py
}


# PSEUDO:
# - payload = json.loads(sys.stdin.read())
# - if tool not in {"Edit", "Write"}: exit 0
# - src = payload["tool_input"]["file_path"]
# - expected_test = map_source_to_test(src). If none, exit 0.
# - append row to .claude/state/tdd_enforcer.jsonl with {ts, src, expected_test}
# - read state; if expected_test not present in any recent row → print warn.
def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    # Phase 1: no-op silently.
    # Phase 4: uncomment.
    # sys.exit(main())
    sys.exit(0)


# Phase 2 Graduation:
#   - Expand SOURCE_TO_TEST_MAP as code lands.
#   - Optionally upgrade from warn to deny after contributor count > 1.

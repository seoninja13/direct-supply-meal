# Phase 4 Execution Plan — direct-supply-meal

**Status:** APPROVED — ready to execute Slice A.
**Authored:** 2026-04-22 after a structured pre-flight audit.
**Entry criteria:** Phase 3 pseudocode complete (HEAD commit `e8177f6`).
**Exit criteria:** All 8 slices green, `ds-meal.dulocore.com` live, 5-minute demo walkthrough passes without narration.

## External dependency status (updated 2026-04-22)

| Resource | Status | Notes |
|---|---|---|
| Clerk "DS-Meal" Development app | ✅ PROVISIONED | Keys pasted into `/opt/direct-supply-meal/.env.ds-meal` on VPS (mode 0600, gitignored). Frontend domain: `ample-honeybee-65.clerk.accounts.dev`. |
| Claude Max subscription via Claude Agent SDK | ✅ AVAILABLE | **No ANTHROPIC_API_KEY needed.** SDK uses Claude Code OAuth credentials on the host. Original plan was wrong — corrected in this revision. |
| Cloudflare DNS `ds-meal.dulocore.com` | ✅ LIVE | Created via `/cd-cloudflare` skill, record_id `f91a99572ebdadcde53e2a958ea506c3`. Proxied, 72.60.112.205 origin, Cloudflare edge IPs (104.21.17.151, 172.67.177.11) resolving via 1.1.1.1. Traefik returns 404 until container ships in Slice G — expected. |

## 1. Purpose and Scope

Phase 4 replaces every `raise NotImplementedError` and `pass` body in the Phase 3 pseudocode stubs with real, test-driven Python code. It also fills the Phase 3 gap where the `tests/` directory was left empty.

**What Phase 4 produces:**
- A live FastAPI app at `https://ds-meal.dulocore.com` running the 5 user journeys from DOMAIN-WORKFLOW §4.
- A SQLite DB seeded with real fixtures (10 recipes, 5 facilities, 30 residents, 5 demo orders, 1 admin user).
- Two working agentic flows (Menu Planner + NL Ordering) using Claude Agent SDK with native retry + escalation.
- A Karpathy Auto-Research loop: trace → compile wiki → session-start inject → next session smarter.
- A test pyramid across unit / integration / agent / E2E.
- A CI workflow at `.github/workflows/ci.yml`.
- A README demo script walkthrough.

**What Phase 4 deliberately does NOT produce:** anything on the PHASE-2-ROADMAP list. Those 22 items are named, seamed, and deferred.

## 2. Pre-flight Gap Closures (must resolve BEFORE Slice A begins)

The pre-flight audit uncovered 11 real contradictions between planning docs and pseudocode stubs. Every gap below must be resolved (by editing either the relevant stub or the relevant doc) before the slice that depends on it starts. Each row has a recommended resolution; deviating requires an explicit note in the slice commit.

| # | Gap | Location | Recommended resolution |
|---|---|---|---|
| G1 | `DELIVERYWINDOW` + `DIETARYFLAG` shown as tables in ER diagram but implemented as enum + join | `docs/workflows/DOMAIN-WORKFLOW.md` §2 | Edit ER diagram: mark `DELIVERYWINDOW` as enum, collapse `DIETARYFLAG` to `ResidentDietaryFlag(resident_id, flag)` join. |
| G2 | `Resident.allergen_flags` referenced but does not exist | `app/services/compliance.py::check_allergens`, `app/services/menu_fallback.py` | Add helper `Resident.get_allergen_flags()` that filters `dietary_flags` for `allergen_*` prefixes. No schema change. |
| G3 | `Recipe.tags` column referenced but does not exist | `agents/tools_sdk.py::search_recipes`, `agents/tools.py::db_search_recipes` | Drop the `tags` parameter; `search_recipes` filters by `exclude_allergens`, `max_cost_cents`, `texture_level` only. Update AGENT-WORKFLOW §5. |
| G4 | State-machine transitions in `agents/tools.py` docstring use outdated 3-state model (`pending → prepping → delivered`) | `agents/tools.py::db_append_order_status_event` | Rewrite docstring to match the 6-state machine from `app/services/orders.py` + DOMAIN-WORKFLOW §3. |
| G5 | Sync vs async session-factory mismatch | `scripts/seed_db.py`, `scripts/seed_traces.py` reference `get_sync_session`; `app/db/database.py` only has async | Add `get_sync_session()` synchronous factory in `app/db/database.py` for scripts. Routes keep async. |
| G6 | `CLERK_SIGN_IN_URL` referenced in route pseudocode but missing from `app/config.py::Settings` | `app/config.py`, `.env.example` (already has it) | Add `CLERK_SIGN_IN_URL: str` field to `Settings`. |
| G7 | `SYSTEM_USER_ID = 0` for fallback menu author, but no user row is seeded at id=0; demo orders reference `placed_by_user_id: 1` with no user-0 or user-1 seed | `app/services/menu_fallback.py`, `scripts/seed_db.py`, `fixtures/demo_orders.json` | Seed step inserts user id=1 (admin@dulocore.com, `clerk_user_id=NULL` placeholder) before loading demo_orders. First real sign-in `UPDATE`s `clerk_user_id`. Drop the user-id-0 concept; fallback menus use `placed_by_user_id=1` too. |
| G8 | `mechanical_soft` is an enum value but has no compliance rule | `app/models/resident.py::DietaryFlag`, `app/services/compliance.py` | Add 7th compliance rule `check_mechanical_soft(recipe, resident) → texture_level ≤ 3`. Update DOMAIN-WORKFLOW §5. |
| G9 | `max_carbs_per_meal` read via `getattr` but has no home | `app/services/compliance.py::check_diabetic` | Read from `Resident.demographics` JSON dict with key `max_carbs_per_meal`, default 60g. No schema change. |
| G10 | `generate_from_meal_plan` hard-codes `delivery_window_slot="midday_11_1"` for all orders | `app/services/orders.py::generate_from_meal_plan` | Rule: group by `(day_of_week, meal_type)` → one order per meal per day → 21 orders/week max. Slot mapping: breakfast→morning_6_8, lunch→midday_11_1, dinner→evening_4_6. |
| G11 | `DATABASE_URL` uses `sqlite:///` but async engine needs `sqlite+aiosqlite://` | `.env.example`, `app/db/database.py` | Standardize on `sqlite+aiosqlite:///./data/ds-meal.db` for the async engine; `get_sync_session()` uses `sqlite:///...` synchronously. |
| G12 | `init_schema` import path mismatch: `main.py` pseudocode imports `app.db.session.init_schema` but the module is `app.db.init_schema` | `app/main.py` | Use `from app.db.init_schema import init_schema`. |
| G13 | Depth scorer called in BOTH route handlers AND driver `run()` — double-logged | `app/routes/agents.py`, `agents/drivers/*.py` | Call `score_query()` ONCE in the route (before `invoke_director`); pass `depth_score` in the driver's request payload. |
| G14 | NL Ordering `resume_session` plans to pickle SDK client state — fragile | `agents/drivers/nl_ordering.py::resume_session` | Persist only a **JSON decision payload** `{recipe_id, n_servings, service_date, delivery_window}` keyed by `trace_id` in a small `nl_session_state` SQLite table. On confirm, re-instantiate a fresh client, pass payload, call `schedule_order` directly — no SDK state replay. |

The gap resolutions are **small** — none of them are architectural rework. They are spelling-correction-level fixes to the pseudocode stubs that would otherwise cause test failures in their respective slices. All 14 are addressed in-line during the slice where they first surface (marked per-slice below).

## 3. External Dependencies (Ivan-only, must be in place by the slice that needs them)

Phase 4 has three external resources that cannot be provisioned from agent code. They block specific slices. Start them in parallel with Slice A.

| Resource | Blocks slice | Provisioning steps | ETA |
|---|---|---|---|
| **Clerk "DS-Meal" Development app** | B | ✅ Provisioned 2026-04-22. Keys in `/opt/direct-supply-meal/.env.ds-meal`. Google OAuth provider needs to be enabled in the Clerk dashboard before first sign-in (Slice B). | Done |
| **Claude Max subscription via Claude Agent SDK** | D and E | ✅ Available. No metered `ANTHROPIC_API_KEY` — the SDK uses the Claude Code OAuth creds already present on the host. Our Dockerfile needs to mount `/root/.claude/.credentials.json` read-only into the container at runtime so the SDK can authenticate. | Done (Dockerfile update in Slice D) |
| **Cloudflare DNS `ds-meal.dulocore.com`** | G | ✅ A-record created 2026-04-22 via `/cd-cloudflare` skill. Proxied. Resolves via 1.1.1.1. Traefik returns 404 until Slice G. | Done |

**All three external dependencies are provisioned.** Phase 4 can proceed without blockers. Start with Slice A.

## 4. Test Pyramid Setup

The Phase 3 pseudocode pass left `tests/` empty. Slice A must bootstrap the whole pyramid.

**Directory layout:**
```
tests/
├── conftest.py                  # shared fixtures
├── fixtures/
│   ├── claude_responses.json    # canned SDK multi-turn payloads
│   ├── jwt_keys.json            # RS256 test keypair for Clerk middleware tests
│   └── demo_seed.json           # smaller test seed (not production fixtures)
├── unit/                        # pure-function tests, no DB, no SDK
│   ├── test_scaling.py
│   ├── test_compliance.py       # ≥18 tests (6 rules × pass/warn/fail)
│   ├── test_pricing.py
│   ├── test_calendar_view.py
│   ├── test_orders_state_machine.py
│   ├── test_depth_scorer.py
│   └── test_wiki_compiler.py
├── integration/                 # route → DB → response
│   ├── test_recipes_api.py
│   ├── test_auth.py
│   ├── test_orders_api.py
│   ├── test_calendar_api.py
│   ├── test_meal_plans_api.py
│   └── test_wiki_pipeline.py
├── agent/                       # agent tests with mocked claude_agent_sdk
│   ├── test_nl_ordering_driver.py
│   ├── test_menu_planner_driver.py
│   └── test_observability.py
└── e2e/                         # Playwright headless Chromium
    ├── test_recipes_e2e.py
    ├── test_signin.py
    ├── test_dashboard_flow.py
    ├── test_nl_order_flow.py
    └── test_realauth.py         # Clerk test-mode bypass → gated route
```

**conftest.py contract (slice A writes this once):**
- `db_session` — function-scoped async fixture, SQLite in `tmp_path`, seeded with minimum rows per test.
- `client` — httpx `AsyncClient` with `dependency_overrides[get_session] = db_session`.
- `mock_claude` — monkeypatches `claude_agent_sdk.query` to yield canned messages from `tests/fixtures/claude_responses.json` keyed by `fixture_key`.
- `mock_clerk_jwt` — returns a pre-signed RS256 token using the test keypair in `tests/fixtures/jwt_keys.json`.

**Markers** (declared in `pyproject.toml` `[tool.pytest.ini_options]`):
```toml
markers = [
  "unit: pure-function tests, no I/O",
  "integration: route + DB tests",
  "agent: agent tests with mocked SDK",
  "e2e: Playwright browser tests",
]
```

**Mock strategy for Claude SDK:** hand-authored canned messages in `tests/fixtures/claude_responses.json`. Each entry is keyed by `fixture_key` (e.g., `"nl_ordering__oats_happy_path"`) and contains an array of SDK message objects. No live LLM calls in CI. A `make refresh-cassettes` target recorded against staging can be added in Phase 2-of-tests.

**Coverage targets (per module, enforced by `coverage report --fail-under`):**
- `app/services/` — 85%
- `app/routes/` — 80%
- `app/auth/` — 80%
- `agents/` — 80% (LLM wire code excluded via `.coveragerc`)
- `wiki/` — 85%
- Overall minimum — 80%.

## 5. CI Workflow

`.github/workflows/ci.yml` runs on every push and pull request.

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - run: pip install -e ".[dev]"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: pw-${{ runner.os }}-${{ hashFiles('pyproject.toml') }}
      - run: playwright install --with-deps chromium
      - run: ruff check .
      - run: mypy app agents wiki
      - run: pytest tests/unit --cov=app --cov=agents --cov=wiki --cov-report=xml
      - run: pytest tests/integration --cov-append
      - run: pytest tests/agent --cov-append
      - run: pytest tests/e2e
      - run: coverage report --fail-under=80
```

**Secrets handling:** No secrets in CI. All agent tests use mocked SDK; all E2E tests use a mock Clerk token minted at runtime from `tests/fixtures/jwt_keys.json`. CI never touches real Clerk or real Anthropic. Real-key tests live only on VPS and run manually via `make test-live`.

**Matrix:** Python 3.12 only. Ubuntu only. No multi-OS, no multi-Python. Kata prototype doesn't need it.

## 6. Slice Execution (A–H)

Every slice commits to `main` when green. No feature branches for this prototype — trunk-based solo dev. If a slice breaks `main`, revert the commit; don't try to fix forward.

### Slice A — Kata baseline (J1 anonymous browse)

**Deliverable:** live at `https://ds-meal.dulocore.com`: `GET /recipes` lists 10 recipes, `GET /recipes/{id}` renders metadata, `GET /recipes/{id}/ingredients?servings=N` scales grams. `/health` returns 200 JSON. `/api/v1/*` twins exist for all three. First E2E browser test green. Test pyramid infrastructure bootstrapped. CI green on push.

**Pre-flight gap closures addressed this slice:** G5, G6, G11, G12 (all DB + config plumbing).

**Acceptance criteria:**
1. `pytest tests/unit/test_scaling.py` green — 3 tests: base yield, 2x scale, 0.5x scale.
2. `pytest tests/integration/test_recipes_api.py` green — 6 tests: list / detail 200 / detail 404 / ingredients with servings / ingredients default / JSON twin shape parity.
3. `pytest tests/e2e/test_recipes_e2e.py` green — 1 test: `/recipes` → click first row → `/recipes/{id}` → click "Ingredients" → table renders with 10+ `<tr>` rows.
4. `curl -sI https://ds-meal.dulocore.com/health` returns `200 OK`.
5. `curl -s https://ds-meal.dulocore.com/api/v1/recipes | jq length` returns `10`.
6. `.github/workflows/ci.yml` green on the commit.

**Coverage target:** 85% on `app/services/scaling.py`, `app/routes/recipes.py`, `app/models/recipe.py`, `app/models/ingredient.py`.

**Files to create/modify (absolute paths):**
- `/opt/direct-supply-meal/tests/conftest.py` (new — shared fixtures scaffold)
- `/opt/direct-supply-meal/tests/unit/test_scaling.py`
- `/opt/direct-supply-meal/tests/integration/test_recipes_api.py`
- `/opt/direct-supply-meal/tests/e2e/test_recipes_e2e.py`
- `/opt/direct-supply-meal/tests/fixtures/claude_responses.json` (empty `{}` stub, filled later)
- `/opt/direct-supply-meal/app/models/recipe.py` (fill in `NotImplementedError` bodies)
- `/opt/direct-supply-meal/app/models/ingredient.py`
- `/opt/direct-supply-meal/app/services/scaling.py`
- `/opt/direct-supply-meal/app/routes/recipes.py`
- `/opt/direct-supply-meal/app/db/database.py` (G5, G11)
- `/opt/direct-supply-meal/app/db/init_schema.py` (G12)
- `/opt/direct-supply-meal/scripts/seed_db.py` (recipes + ingredients + RecipeIngredient only — facilities/residents/orders come in Slice B/C)
- `/opt/direct-supply-meal/app/templates/base.html`
- `/opt/direct-supply-meal/app/templates/landing.html`
- `/opt/direct-supply-meal/app/templates/recipes/list.html`
- `/opt/direct-supply-meal/app/templates/recipes/detail.html`
- `/opt/direct-supply-meal/app/templates/recipes/ingredients.html`
- `/opt/direct-supply-meal/app/static/css/main.css` (add table + typography rules; ~80 lines total)
- `/opt/direct-supply-meal/app/main.py` (fill factory, startup hook for init_schema)
- `/opt/direct-supply-meal/app/config.py` (G6)
- `/opt/direct-supply-meal/app/routes/public.py` (`/`, `/health` only — sign-in stubs stay in Slice B)
- `/opt/direct-supply-meal/.env.example` (G11)
- `/opt/direct-supply-meal/.github/workflows/ci.yml` (new)

**Dependencies:** none. Can start immediately.

**Estimated hours:** 4.

**Go/no-go gate:** `https://ds-meal.dulocore.com/recipes` returns 200 with 10 recipes in the HTML. If this gate does not pass, Slice B does not start.

**Rollback:** `git revert HEAD` if main breaks. Local SQLite is disposable.

---

### Slice B — Clerk authentication (J2)

**Deliverable:** `/sign-in` redirects to Clerk hosted page, `/sign-in/callback` verifies the JWT + provisions a User row for `admin@dulocore.com` bound to Riverside SNF, `require_login` gates `/facility/dashboard` (placeholder view), `/sign-out` clears the cookie. Non-allowlisted email → 403 with "Access denied" page.

**Pre-flight gap closures addressed:** G7 (seed a user id=1 at seed time for `admin@dulocore.com` with `clerk_user_id=NULL`; provisioning updates it on first sign-in).

**Acceptance criteria:**
1. Unit test for `verify_clerk_jwt` with a hand-crafted RS256 token signed by the test keypair → claims dict.
2. Unit test for `verify_clerk_jwt` with a forged signature → raises `InvalidTokenError`.
3. Integration test: empty user table → `/sign-in/callback` with valid Clerk token for `admin@dulocore.com` → User row exists with `facility_id=2` (Riverside SNF).
4. Integration test: `/sign-in/callback` with email `random@example.com` → 403 + "Access denied" body.
5. Integration test: GET `/facility/dashboard` without session cookie → 302 to `/sign-in`.
6. Integration test: GET `/facility/dashboard` WITH valid session cookie → 200.
7. E2E test using Clerk test-mode token bypass (Clerk Backend API creates a session, extracts session JWT, sets as cookie, requests dashboard, asserts 200).
8. Real Ivan signs in live at `https://ds-meal.dulocore.com`, lands on dashboard placeholder.

**Coverage target:** 80% on `app/auth/*`.

**Files to create/modify:**
- `app/auth/clerk_middleware.py`
- `app/auth/dependencies.py`
- `app/auth/provisioning.py`
- `app/routes/public.py` (add `/sign-in`, `/sign-in/callback`, `/sign-out`)
- `app/routes/facility.py` (shell endpoint only)
- `app/models/user.py` (fill stub)
- `app/models/facility.py` (fill stub)
- `app/templates/facility/dashboard.html` (placeholder)
- `app/templates/access_denied.html` (new — for the 403)
- `scripts/seed_db.py` (add facilities + user id=1 seed)
- `tests/fixtures/jwt_keys.json` (new — generate RS256 keypair for tests)
- `tests/unit/test_clerk_middleware.py`
- `tests/integration/test_auth.py`
- `tests/e2e/test_signin.py`

**Dependencies:** Slice A complete. Clerk app created + keys in `.env.ds-meal` on VPS.

**Estimated hours:** 4.

**Go/no-go gate:** Ivan successfully signs in live and sees the dashboard placeholder. If Clerk test-mode bypass doesn't work, Slice H's RealAuth stage is impossible — but dev-bypass path can still ship, with a visible warning.

**Rollback:** `git revert`. Users and facilities in SQLite can be wiped via `rm -rf data/ds-meal.db && make seed-db`.

---

### Slice C — Dashboard + orders history/detail + calendar (J2 landing, J5)

**Deliverable:** `/facility/dashboard` shows a summary of 5 seeded demo orders for Riverside (1 delivered, 1 out_for_delivery, 1 in_preparation, 1 confirmed, 1 pending). `/orders` paginated list, `?status=` filter, status badges. `/orders/{id}` shows OrderLines + status timeline + progress bar. `/calendar` renders month grid with colored delivery dots. Cross-facility access returns 403.

**Pre-flight gap closures addressed:** G4 (state-machine docstring), G10 (defer — generate_from_meal_plan isn't used here; Slice E handles it).

**Acceptance criteria:**
1. Unit tests for order state machine: all 7 legal transitions pass, all illegal combinations raise `InvalidTransitionError`. ~10 tests.
2. Unit tests for `build_month_grid`: correct weeks structure, today-highlight, prev-month wrap at January, next-month wrap at December, empty facility. ~6 tests.
3. Unit tests for `list_orders_for_facility`: pagination (page 1 vs page 2), status filter (only `pending`), cross-facility exclusion. ~5 tests.
4. Integration test: GET `/orders` as admin → 5 orders visible. GET `/orders?status=delivered` → 1 order.
5. Integration test: GET `/orders/101` → 200, timeline has 5 events. GET `/orders/999` → 404. GET `/orders/101` as a different user (mocked) → 403.
6. Integration test: GET `/calendar?year=2026&month=4` → 200 with orders on April 16, 22, 23, 24, 25.
7. E2E test: sign in → dashboard → click an order → detail page shows timeline → back to calendar → prev/next month nav works.

**Coverage target:** 85% on `app/services/orders.py`, `app/services/calendar_view.py`. 80% on routes.

**Files to create/modify:**
- `app/models/order.py`, `app/models/meal_plan.py` (fill stubs)
- `app/services/orders.py` (state machine, list, get_with_timeline; DEFER generate_from_meal_plan to Slice E)
- `app/services/calendar_view.py`
- `app/routes/orders.py`, `app/routes/calendar.py`, `app/routes/facility.py`
- `agents/tools.py` (G4 — fix state-machine docstring)
- Templates: `orders/list.html`, `orders/detail.html`, `facility/dashboard.html`, `calendar/month.html`, `_partials/status_badge.html`, `_partials/timeline.html`, `_partials/progress_bar.html`
- `app/static/css/main.css` (add table + badge + timeline + progress-bar + calendar-grid rules)
- `scripts/seed_db.py` (extend: residents + demo_orders + OrderStatusEvent histories)
- `tests/unit/test_orders_state_machine.py`, `tests/unit/test_calendar_view.py`, `tests/unit/test_orders_service.py`
- `tests/integration/test_orders_api.py`, `tests/integration/test_calendar_api.py`
- `tests/e2e/test_dashboard_flow.py`

**Dependencies:** Slice B.

**Estimated hours:** 5.

**Go/no-go gate:** `/facility/dashboard` shows 5 order tiles with 4 distinct status colors; `/calendar?year=2026&month=4` shows ≥ 5 delivery dots.

**Rollback:** `git revert`.

---

### Slice D — NL Ordering agent (J4)

**Deliverable:** POST `/orders/new` with free text (`"50 Overnight Oats for Tuesday breakfast"`) returns a proposal card; POST with `confirm=true` persists Order + OrderLine + OrderStatusEvent(`pending`). Agent trace row written to SQLite + JSONL. `make compile-wiki` against 20 seeded traces produces ≥ 1 topic page under `wiki/topics/nl_ordering/`. Session-inject hook reads the topic page into the next agent call's system prompt.

**Pre-flight gap closures addressed:** G3 (drop `tags` from `search_recipes`), G13 (depth-score called once in route), G14 (JSON decision payload for resume, not pickle).

**Acceptance criteria:**
1. Agent test with mocked `claude_agent_sdk.query` yielding canned multi-turn messages from `tests/fixtures/claude_responses.json` key `"nl_ordering__oats_happy_path"`: asserts `resolve_recipe` called with `{"name_query": "Overnight Oats"}`, then `scale_recipe(3, 50)`, then `check_inventory(...)`. No LLM text content assertions.
2. Agent test: unconfirmed POST returns `{status: "awaiting_confirmation", proposal: {...}, trace_id: "..."}`. Confirmed POST (with trace_id) calls `schedule_order(..., confirmed=true)` and returns `{status: "pending", order_id}`.
3. Agent test: ambiguous recipe (`resolve_recipe` returns 2 candidates above 0.5 threshold) → agent emits disambiguation turn.
4. Integration test: after a successful agent call, `agent_trace` table has exactly one new row with correct agent_name, outcome, tools_called shape.
5. Integration test: after a successful agent call, `logs/agent_trace.jsonl` has one new line.
6. Integration test: `make compile-wiki` against 20 seeded traces produces ≥ 1 file under `wiki/topics/nl_ordering/` with valid YAML frontmatter (title, sources, related_topics, last_compiled, memory_types, confidence_score).
7. E2E test: sign in → `/orders/new` → type in text → see proposal card → click Confirm → redirected to `/orders/{id}` showing the new order.

**Coverage target:** 80% on `agents/drivers/nl_ordering.py`, `agents/tools_sdk.py` (implement all 9 tools, test the 5 used by NL flow), `agents/observability.py`, `agents/depth_scorer.py`, `wiki/compiler.py`, `wiki/index_generator.py`.

**Files to create/modify:**
- `agents/tools_sdk.py` (all 9 tools — G3 fix)
- `agents/tools.py` (all helpers)
- `agents/drivers/nl_ordering.py` (G14 — JSON decision payload)
- `agents/drivers/dispatch.py`
- `agents/observability.py`
- `agents/depth_scorer.py`
- `agents/llm_client.py`
- `agents/prompts/nl_ordering.md`
- `app/routes/agents.py`, `app/routes/orders.py` (G13 — score_query in route)
- `app/templates/orders/new.html` (two-branch template: form + proposal card)
- `wiki/compiler.py`, `wiki/index_generator.py`
- `scripts/seed_traces.py` (fill 20 realistic rows)
- `.claude/hooks/wiki_session_inject.py`
- Test files: `tests/fixtures/claude_responses.json` (add nl_ordering fixtures), `tests/agent/test_nl_ordering_driver.py`, `tests/agent/test_tools_sdk.py`, `tests/agent/test_observability.py`, `tests/integration/test_wiki_pipeline.py`, `tests/integration/test_orders_api.py` (add POST /new tests), `tests/e2e/test_nl_order_flow.py`

**Dependencies:** Slice C. Claude Max subscription via Claude Agent SDK (no API key needed). Dockerfile must mount `/root/.claude/.credentials.json` read-only into the container so the SDK can authenticate against the Max OAuth token.

**Estimated hours:** 5.

**Go/no-go gate:** demo walk-through — type `"50 Overnight Oats for Tuesday breakfast"` → proposal → confirm → new order visible on `/orders` list; `make compile-wiki` produces topic pages.

**Rollback:** `git revert`. Trace DB table can be truncated via `DELETE FROM agent_trace`.

---

### Slice E — Menu Planner agent (J3) + MealPlan → Orders

**Deliverable:** POST `/meal-plans/new` → Menu Planner runs (Sonnet, multi-turn) → returns 21-slot week grid with compliance badges → user saves → 21 daily Orders generated (one per meal per day). LLM-unavailable path falls back to `menu_fallback.generate_fallback_menu` with visible `static_fallback` badge.

**Pre-flight gap closures addressed:** G2 (Resident.get_allergen_flags helper), G8 (mechanical_soft rule added), G9 (max_carbs_per_meal via demographics), G10 (delivery_window_slot rule by meal_type).

**Acceptance criteria:**
1. 18+ unit tests for compliance rules: 6 rules × 3 paths (pass / warn / fail) each. Plus 6 tests for `check_compliance_facility` roll-up logic (any-fail, 10%-warn threshold, happy-path pass).
2. Unit test for `mechanical_soft` rule (G8).
3. Unit test for `check_diabetic` override via `demographics.max_carbs_per_meal` (G9).
4. Agent test with mocked multi-turn Sonnet: 21-slot plan saved. Asserts `search_recipes` × 2, `check_compliance` × N (per slot-tranche), `estimate_cost`, `save_menu` call patterns.
5. Integration test: successful save → 21 Orders exist in DB with correct `delivery_window_slot` per `meal_type` (G10).
6. Integration test: `ANTHROPIC_API_KEY` unset or invalid → `/meal-plans/new` POST still returns 200 with `static_fallback` badge, `menu_fallback.generate_fallback_menu` wrote a MealPlan.
7. E2E: sign in → `/meal-plans/new` → submit form → redirect to `/meal-plans/{id}` → orders appear on calendar on correct days and slots.

**Coverage target:** 90% on `app/services/compliance.py`, 85% on `menu_fallback.py`, 80% on `pricing.py`, driver, remaining tools.

**Files to create/modify:**
- `app/services/compliance.py` (6 rules + 7th for G8 + facility-level roll-up)
- `app/services/pricing.py` (static_rollup + estimate_cost LLM refinement)
- `app/services/menu_fallback.py`
- `app/services/orders.py::generate_from_meal_plan` (G10)
- `app/models/resident.py` (G2 — `get_allergen_flags` helper method)
- `agents/drivers/menu_planner.py`
- `agents/prompts/menu_planner.md`
- `app/routes/meal_plans.py`, `app/routes/agents.py` (add `/agents/menu-plan`)
- Templates: `meal_plans/list.html`, `meal_plans/new.html`, `meal_plans/detail.html` (new)
- Tests: `tests/unit/test_compliance.py` (big file), `tests/unit/test_pricing.py`, `tests/unit/test_menu_fallback.py`, `tests/agent/test_menu_planner_driver.py`, `tests/integration/test_meal_plans_api.py`, `tests/e2e/test_meal_planner_flow.py`
- `tests/fixtures/claude_responses.json` (add menu_planner fixtures)

**Dependencies:** Slice D.

**Estimated hours:** 5.

**Go/no-go gate:** `/meal-plans/new` produces a 21-slot plan for Riverside in ≤ 30 seconds, compliance badges visible, budget shown, Save generates Orders, orders appear on the calendar.

**Rollback:** `git revert`.

---

### Slice F — Karpathy Auto-Research loop end-to-end (real Haiku)

**Deliverable:** `make compile-wiki` runs against the combined corpus of seeded traces + organic traces accumulated in Slices D & E, producing synthesized topic pages via real Haiku calls. `TOPICS-INDEX.md` regenerates. Session-inject hook reads the index and prepends relevant topic pages to the driver's system prompt. Demo moment: run NL order with "oats" → `make compile-wiki` → re-run NL order → agent resolves in one tool round (confidence ≥ 0.85) instead of asking disambiguation.

**Pre-flight gap closures addressed:** none new.

**Acceptance criteria:**
1. Unit test for `cluster_traces` hand-clustering: 15 hand-authored traces cluster into expected groups.
2. Unit test for `parse_topic`: valid frontmatter → dict; invalid frontmatter → raises.
3. Integration test: seed 20 traces → `make compile-wiki` → ≥ 3 topic pages exist with valid frontmatter. Cost ≤ $0.05. Wall time ≤ 60s.
4. Integration test: `wiki/TOPICS-INDEX.md` regenerated with entries for every topic page.
5. Observability assertion: compile run logs `cost_usd` and `duration_ms` to stdout.

**Coverage target:** 85% on `wiki/*.py`.

**Files to create/modify:**
- `wiki/compiler.py` (real body, real Haiku calls)
- `wiki/index_generator.py`
- `wiki/schema.yaml` (already complete, no changes)
- `scripts/seed_traces.py` (expand from stub list to 20+ real entries covering aliases + meal-type shorthands + delivery-window shorthands)
- `agents/llm_client.py::call_haiku` (real implementation)
- Tests: `tests/unit/test_wiki_compiler.py`, `tests/integration/test_wiki_pipeline.py`

**Dependencies:** Slices D & E.

**Estimated hours:** 3.

**Go/no-go gate:** `make compile-wiki` against seeded traces produces ≥ 4 topic pages with valid YAML frontmatter; TOPICS-INDEX lists them; cost logged ≤ $0.05.

**Rollback:** `git revert` + `rm -rf wiki/topics/*`.

---

### Slice G — Production deploy + TLS + health + smoke

**Deliverable:** `docker compose up -d --build` on VPS serves the full app at `https://ds-meal.dulocore.com`. Traefik TLS cert issued via ACME. HEALTHCHECK passes. All five user journeys (J1–J5) work live.

**Pre-flight gap closures addressed:** none new.

**Acceptance criteria:**
1. `curl -I https://ds-meal.dulocore.com/health` returns 200 with valid Let's Encrypt cert.
2. Full E2E suite passes against the production URL via `BASE_URL=https://ds-meal.dulocore.com pytest tests/e2e`.
3. `docker inspect ds-meal --format='{{.State.Health.Status}}'` returns `healthy`.
4. `cat /opt/direct-supply-meal/logs/agent_trace.jsonl` shows rows accumulating as flows run.
5. Ivan completes the 5-minute demo walkthrough live without errors.

**Files to create/modify:** VPS deploy — minimal code changes. `.env.ds-meal` populated on VPS with real Clerk + Anthropic keys.

**Dependencies:** Slices A–F merged to main. Cloudflare DNS record live. Clerk + Anthropic keys provisioned.

**Estimated hours:** 2 (including Traefik cert issuance wait time).

**Go/no-go gate:** Ivan completes the 5-minute demo walkthrough live.

**Rollback:** `docker compose down`. DNS stays, cert stays, container stops; re-deploy when ready.

---

### Slice H — Polish + README demo script + RealAuth stage

**Deliverable:** `README.md` contains a 5-minute demo walkthrough that works verbatim from a fresh `git clone`. RealAuth E2E test (uses Clerk test-mode token to sign in and touch a gated route) is a CI-enforceable check — DoD Stage 5 visible. CSS final pass. Ops docs fleshed out.

**Pre-flight gap closures addressed:** none new.

**Acceptance criteria:**
1. README demo script works verbatim.
2. `tests/e2e/test_realauth.py` passes against staging in CI.
3. `make lint && make test` green with coverage ≥ 80%.
4. 6-stage DoD matrix: 5/5 complete (UserAccessible skipped by design, documented).
5. `docs/ops/RUNNING-LOCALLY.md`, `docs/ops/TESTING.md`, `docs/ops/DEPLOYING.md`, `docs/ops/SEED-DATA.md`, `docs/ops/REPO-LAYOUT.md` all exist and are accurate.

**Files to create/modify:** `README.md` (full rewrite with demo script), `tests/e2e/test_realauth.py`, `app/static/css/main.css` (final pass, ≤ 500 lines total), 5 ops docs under `docs/ops/`.

**Dependencies:** Slice G.

**Estimated hours:** 2.

**Go/no-go gate:** A fresh reader can clone and redeploy in < 5 minutes per the README. Interview-ready.

---

## 7. Deployment Runbook

### First deploy (from VPS)

```bash
cd /opt/direct-supply-meal
git pull origin main
cp .env.example .env.ds-meal        # edit with real values
mkdir -p data logs
docker compose up -d --build
docker logs -f ds-meal               # wait for "Application startup complete"
curl -I https://ds-meal.dulocore.com/health
```

### Config-only reload (SAFE from VPS — per DuloCore safety rule)

```bash
docker compose -f docker-compose.yml up -d --no-deps --force-recreate ds-meal
```

### Full rebuild (FROM WINDOWS ONLY — per DuloCore safety rule)

```bash
# On Windows via SSH to VPS:
docker compose build --no-cache
docker compose up -d ds-meal
```

### Health-check verification

```bash
curl -sI https://ds-meal.dulocore.com/health
docker inspect ds-meal --format='{{.State.Health.Status}}'
```

### TLS cert verification (after first deploy)

```bash
echo | openssl s_client -servername ds-meal.dulocore.com -connect ds-meal.dulocore.com:443 2>/dev/null | openssl x509 -noout -issuer -dates
```

## 8. 6-Stage DoD Matrix

| Stage | Name | Slice that completes it | Evidence |
|-------|------|-------------------------|----------|
| 1 | Unit Tests | A (bootstrap) + incremental each slice | `pytest tests/unit --cov --cov-report=term` green, ≥ 80% |
| 2 | Integration | A + incremental | `pytest tests/integration --cov-append` green |
| 3 | E2E Playwright | A (first), final coverage in H | `pytest tests/e2e` green headless |
| 4 | Deployed | G | `curl https://ds-meal.dulocore.com/health` 200 + Docker HEALTHCHECK |
| 5 | Real Auth | H | `tests/e2e/test_realauth.py` via Clerk test-mode in CI |
| 6 | User Accessible | **Skipped by design** | Covered by public URL + H README walkthrough |

## 9. Demo Script (5-minute walkthrough)

Exact inputs the presenter types, exact outputs to expect. Reset procedure at the end.

1. **Open** `https://ds-meal.dulocore.com/recipes` in a fresh browser. *Expect:* 10 recipes in a table.
2. **Click** "Chicken Stir-Fry" → recipe detail → "Ingredients" → ingredients table. *Expect:* 7 rows with grams.
3. **Click** "Sign in" → Google OAuth popup → sign in as `admin@dulocore.com`. *Expect:* redirect to `/facility/dashboard`.
4. **Dashboard** shows "Riverside SNF — 120 beds. 4 active orders. Next delivery: tomorrow 6 AM." *Expect:* 4 status tiles.
5. **Click** `/calendar` → April 2026. *Expect:* dots on April 16 (delivered), 22 (out for delivery), 23, 24, 25.
6. **Click** `/orders` → filter `?status=in_preparation`. *Expect:* 1 order visible.
7. **Click** the order → detail. *Expect:* timeline with 3 events + 60% progress bar.
8. **Click** `/orders/new` → type `"40 oats for tomorrow morning"` → Submit. *Expect:* proposal card showing "Overnight Oats × 40, morning 6-8 AM delivery tomorrow, total $112.00." Confidence 0.88+ (thanks to wiki aliases).
9. **Click** Confirm. *Expect:* redirect to new order detail page.
10. **Click** `/meal-plans/new` → fill form (week_start next Monday, budget 15,000¢/day, headcount 120) → Submit. *Expect:* 21-slot grid populated, compliance badges green/amber/red per slot.
11. **Click** Save plan → 21 orders auto-generated, visible on calendar.
12. **Sign out** → visit `/orders`. *Expect:* 302 to `/sign-in`.
13. **Sign in** with a non-allowlisted Google email. *Expect:* 403 "Access denied."

**Reset between runs:**
```bash
docker compose exec ds-meal bash -c "rm -f /app/data/ds-meal.db && python scripts/seed_db.py && python scripts/seed_traces.py && python -m wiki.compiler"
```

**Fallback path (to exercise):** Unset `ANTHROPIC_API_KEY` temporarily; repeat step 10; expect `static_fallback` badge on the resulting menu.

## 10. Phase 2 Deferrals Acknowledged

See `docs/PHASE-2-ROADMAP.md` for the full 22-item list with seams. Key items an interviewer might ask about and the prepared answer:

| Question | Answer |
|---|---|
| "Why not Inngest from day one?" | See roadmap item 1. Seam: `agents/drivers/dispatch()` — one function body swap when latency exceeds ~30s/flow. |
| "Your wiki compiler doesn't use embeddings?" | See roadmap item 2. Seam: `wiki/compiler.py::cluster_traces()` — hand-clustering today; MiniLM vectors when trace count > 500/agent. |
| "How do you detect gaps in the knowledge base?" | See roadmap item 3. Phase 2 introduces a graph KB (Kuzu / Neo4j / NetworkX) in new `wiki/graph.py` to detect orphan concepts and trigger targeted re-compiles. |
| "What about multi-tenant?" | See roadmap item 6. Seam: `app/auth/dependencies.py::require_login` extends to `require_role()`. |
| "Payments? ERP? Mobile app?" | Roadmap items 20–22. Out of scope. Separate services, never this repo. |

## 11. Open Questions Log

| # | Question | Required input | Target resolution |
|---|---|---|---|
| Q1 | ✅ Clerk "DS-Meal" Development app | RESOLVED 2026-04-22 | Keys in `.env.ds-meal` on VPS. Google provider to be enabled in Clerk dashboard before first sign-in test (Slice B). |
| Q2 | ✅ Anthropic auth path | RESOLVED — **no metered key needed**. Claude Agent SDK uses Claude Max subscription via OAuth creds on the host. Dockerfile mounts `/root/.claude/.credentials.json` read-only. |
| Q3 | ✅ Cloudflare DNS `ds-meal.dulocore.com` | RESOLVED 2026-04-22 via `/cd-cloudflare` skill. Proxied. |
| Q4 | LLM test strategy | **DEFAULT applied:** hand-author canned messages in `tests/fixtures/claude_responses.json`. Deterministic, cheap, portable across SDK version changes. |
| Q5 | CI budget for real LLM calls | **DEFAULT applied:** none. CI mocks the SDK entirely. Real SDK calls happen only on the VPS against the Max subscription (zero marginal cost). |
| Q6 | `mechanical_soft` rule | **DEFAULT applied:** add a 7th compliance rule `check_mechanical_soft(recipe, resident) → texture_level ≤ 3`. See G8. |
| Q7 | MealPlan → Order generation cardinality | **DEFAULT applied:** 21 orders/week, one per meal per day. Slot mapping: breakfast→morning_6_8, lunch→midday_11_1, dinner→evening_4_6. See G10. |

---

**This plan is standalone-executable.** An engineer who has never read the master plan file or any of the other workflow docs can start at §2 (gap closures), work through §6 (the 8 slices), and produce the demo. Cross-references to `DOMAIN-WORKFLOW.md` §5 (dietary rules) and `AGENT-WORKFLOW.md` §5 (tool contract) are the only two external dependencies worth preserving — both are stable, reviewable, and one hop away.

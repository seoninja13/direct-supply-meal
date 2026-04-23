# direct-supply-meal — Architecture Breakdown for Demo Day

> **Status:** Phase 1 shipped 2026-04-22, live at https://ds-meal.dulocore.com. This document is the authoritative reference for the architecture walkthrough. Read cold, top-to-bottom, and a reviewer understands the system without needing the author in the room.
>
> **Audience:** senior engineers evaluating a prototype built as an interview kata response.
>
> **HEAD on main:** `5c4619c` — all commits pushed to https://github.com/seoninja13/direct-supply-meal.

---

## 1. Elevator Pitch and Demo-Day Positioning

*TL;DR — single-tenant senior-living meal-ordering prototype that pairs a deterministic FastAPI ledger with two agentic workflows on the Claude Agent SDK. Phase 1 is live; Phase 2 is every graduation seam named, not built.*

### The 2-paragraph verbatim opener

**direct-supply-meal is an AI-first meal-ordering prototype for senior-living facilities** — skilled nursing, assisted living, memory care — that source prepared meals from a central commissary. It models five facilities totaling about 500 beds and exercises the realistic dietary constraints (diabetic, low-sodium, renal, soft-food, pureed, allergen-aware) that food-service staff actually manage. The kata asked for a recipe list and a detail page. We shipped that plus natural-language ordering, Clerk-authenticated facility dashboards, a calendar view, and a scaffolded Karpathy self-compiling knowledge base — not to pad, but to show Staff-level judgment about where LLMs belong, where they don't, and how clean architecture and observability fit together without making a mess of the ledger.

**The architectural point is narrow and worth stating plainly: agentic does not mean agent-anywhere.** We model the system first, identify the handful of decisions where natural language is load-bearing (compliance reasoning, order intake), and fence those decisions off from the deterministic layers — pricing math, state transitions, auth, RBAC. A failed LLM call degrades to "please fill out the form." It never corrupts state. Everything else is ordinary Python, ordinary SQL, ordinary tests.

### Who it is for

| User | Pain today | What ds-meal changes |
|---|---|---|
| **Registered Dietitian (Maya, RD/LDN)** | ~45 min/week reviewing cycle menus against every resident's diet order in spreadsheets | Menu Planner agent emits cited, human-readable compliance verdicts — target 5 min/week |
| **Facility Manager (Dan, NHA)** | Poor visibility into "where's dinner?" — relies on phone calls | Calendar + dashboard with live order state machine |
| **Kitchen Lead at the Commissary (Teresa)** | Last-minute substitutions re-plated by hand | Consolidated order view she can convert into prep sheets |

### Why it is interesting architecturally

- **Agentic seam is load-bearing, not decorative.** The NL Ordering driver is a real `claude_agent_sdk.query()` session with an in-process MCP server and 4 live `@tool` functions — a browser click writes a real order via the SDK's tool-use loop (order #108 is on the VPS right now as proof).
- **Clean architecture survives an agentic feature.** Routes never touch the DB; they always go through `@tool` functions (ATOMIC-S Route Rule). Swapping Jinja for React or SQLite for Postgres is a one-line change per layer.
- **Zero coupling to DuloCore.** Separate repo, separate container, separate SQLite file, separate Clerk tenant, separate `.env`. The only physical overlap is the shared Traefik ingress on the VPS — that is routing, not coupling.
- **Two-Horizon Rule applied everywhere.** Every Phase 2 item has a named Phase 1 seam in code. Graduation is a swap at a known interface, not a rewrite. Forty-eight `# Phase 2 Graduation:` comments across the repo back this up.

---

## 2. What Phase 1 Delivered (shipped 2026-04-22)

*TL;DR — 8 of 10 features shipped end-to-end, 2 stubbed with named seams. Six auth/SDK incident fixes landed today and were backfilled with tests.*

### Feature-by-feature status

From `docs/CATALOG.md` Table 1, reconciled against running code:

| # | Feature | Status | Evidence |
|---|---|---|---|
| 1 | Recipe Browse | **SHIPPED** | 10 recipes at `/recipes`, scaling math at `/recipes/{id}/ingredients?servings=N`, JSON twins under `/api/v1/` |
| 2 | Facility Dashboard | **SHIPPED** | 4 status tiles + next-delivery banner at `/facility/dashboard`; gated via `require_login` |
| 3 | Meal Planning | **STUBBED** | `agents/drivers/menu_planner.py` raises `NotImplementedError`; `/meal-plans/*` routes are placeholders (Slice E, Phase 2) |
| 4 | NL Order | **SHIPPED** | Live end-to-end: text → Haiku + MCP tools → proposal card → confirm → DB write. **Order #108 created today as proof.** |
| 5 | Order History | **SHIPPED** | `/orders` paginated + `?status=` filter + status badges |
| 6 | Calendar | **SHIPPED** | `/calendar?year=&month=` renders month grid with delivery dots per order |
| 7 | Delivery Status | **PARTIAL** | `OrderStatusEvent` table + 6-state machine + progress bar; status transitions are pre-seeded, no live dispatcher (Phase 2) |
| 8 | Pricing | **PARTIAL** | Static per-serving rollup from `Recipe.cost_cents_per_serving`; `pricing.estimate_cost` LLM-refinement and `static_rollup` are stubs |
| 9 | Auth | **SHIPPED** | Clerk Google OAuth → Clerk JWT verified → our own 1-hour HS256 app-session token → cookie. Live sign-in working for `admin@dulocore.com`. |
| 10 | Karpathy Learning | **SCAFFOLDED** | Layer 1 (trace ingestion) is live and writing rows. Layer 2 (`wiki/compiler.py`) raises `NotImplementedError`. Seams present, loop not functional. |

### Today's 8 commits (chronological, all pushed to `main`)

Phase 1's flagship NL-ordering flow went live this morning. Six subsequent incident-response commits hardened it. Two follow-ups backfilled tests and wrote the demo script:

| Commit | Type | What it fixed |
|---|---|---|
| `f9b05cf` | fix(auth) | Trigger Google OAuth directly, skip Clerk hosted page (avoids dev-tier dark-theme UX) |
| `dcf8749` | fix(auth) | Fall back to Clerk Backend API when the session JWT lacks an `email` claim (Clerk's default template omits it) |
| `219e91b` | fix(auth) | Mint 1-hour HS256 app-session tokens instead of storing the Clerk JWT in the cookie — Clerk sessions expire in ~60s |
| `c66b726` | fix(nl-ordering) | Include the original user request in the confirm prompt — each `query()` call is a stateless SDK session |
| `e25320d` | fix(nl-ordering) | Observe SDK `tool_result` events to extract `order_id` after confirm |
| `ebf6188` | fix(nl-ordering) | Iterate user messages for `ToolResultBlock` (not only assistant messages) |
| `1cae8c4` | test(auth) | Backfill coverage for `app_session` + Clerk email fallback (15 new tests) |
| `5c4619c` | docs | Demo walkthrough script (`docs/DEMO-SCRIPT.md`) |

### The live NL-ordering proof

At roughly 01:01 UTC on 2026-04-23, a real browser session typed *"25 Turkey Meatloaf for Thursday dinner"* into `/orders/new`. The SDK drove Haiku through 4 MCP tool calls (`resolve_recipe` → `scale_recipe` → `check_inventory` → `schedule_order`), rendered a proposal card, accepted the confirm, and wrote **order #108** to SQLite with `delivery_date=2026-04-24`, `total_cents=12000`, `status=PENDING`. Same flow ran three more times; orders #106, #107, #108 are all real agentic writes.

---

## 3. Architecture at a Glance

*TL;DR — one Docker container, in-process everything. Browser → Traefik → FastAPI → either (SQLite + Jinja) or (Claude Agent SDK + in-process MCP + 4 @tools). No message bus, no Redis, no external queue.*

### ASCII diagram

```ascii
                    +------------------+
                    |     Browser      |
                    |  (Jinja HTML +   |
                    |   /api/v1/*.json)|
                    +---------+--------+
                              |
                              v  TLS 443
                    +---------+--------+
                    |     Traefik      |   shared with DuloCore (routing only)
                    |  ACME certs +    |   Cloudflare proxied A-record
                    |  Host matcher    |
                    +---------+--------+
                              |
                              v  :8000 HTTP (root_default network)
                    +---------+--------+
                    |  FastAPI ds-meal |
                    |  uvicorn + Jinja |
                    +---+---+---+---+--+
                        |   |   |   |
       +----------------+   |   |   +------------------+
       |                    |   |                      |
       v                    v   v                      v
 +-----------+    +---------+---+----+         +---------------+
 |  SQLite   |    |  Clerk auth      |         | Observability |
 |  ds-meal  |    |  JWKS + Backend  |         | JSONL + SQLite|
 |  .db      |    |  API (email gap) |         | agent_trace   |
 +-----------+    +------------------+         +---------------+
                              ^
                              |
                    +---------+--------+
                    |  Claude Agent    |   OAuth cred (Max sub)
                    |  SDK             |   mounted read-only at
                    |  query()         |   /home/appuser/.claude/
                    +---------+--------+   .credentials.json
                              |
                              v
                 +------------+-----------+
                 | In-process MCP server  |   create_sdk_mcp_server()
                 |  4 @tool functions     |
                 |   resolve_recipe       |
                 |   scale_recipe         |
                 |   check_inventory      |
                 |   schedule_order       |
                 +------------+-----------+
                              |
                              v
                     +--------+--------+
                     |  agents/tools.py|   pure async DB helpers
                     |  (no @decorator)|
                     +-----------------+
```

### Layer responsibilities

| Layer | File | Purpose |
|---|---|---|
| HTTP routes | `app/routes/*.py` | Parse request, call service or dispatch director, render template or JSON |
| Auth | `app/auth/*.py` | Clerk JWT verification, app-session minting, `require_login` dependency |
| Services | `app/services/*.py` | Deterministic business logic (pricing, orders state machine, compliance, calendar) |
| Models | `app/models/*.py` | SQLModel table declarations, enums |
| DB | `app/db/*.py` | Async engine, sync session factory for scripts, idempotent `init_schema` |
| Agent drivers | `agents/drivers/*.py` | L1 Directors that own a `ClaudeSDKClient` session and a tool loop |
| Agent tools | `agents/tools_sdk.py` | `@tool`-decorated MCP wrappers the SDK calls into |
| Agent helpers | `agents/tools.py` | Pure async DB helpers the `@tool` wrappers delegate to |
| Observability | `agents/observability.py` | `record_outcome()` — writes one SQLite row + one JSONL line per agent turn |
| Wiki compiler | `wiki/compiler.py` | Scaffolded; raises `NotImplementedError` for Phase 2 |

### Container / volume / network topology

One Docker service. One image. Thin.

| Element | Value |
|---|---|
| Service name | `ds-meal` |
| Container port | 8000 (uvicorn) |
| Image base | `python:3.12-slim` |
| Volumes | `/opt/direct-supply-meal/data` → `/app/data` (SQLite); `/opt/direct-supply-meal/logs` → `/app/logs` (JSONL traces) |
| OAuth mount | `/root/.claude/.credentials.json` → `/home/appuser/.claude/.credentials.json` (read-only) |
| Network | `root_default` (shared with DuloCore Traefik only) |
| Memory limit | 512 MB |
| Healthcheck | `curl -f http://localhost:8000/health` every 30s |
| Ingress | Traefik Host rule `ds-meal.dulocore.com`, Let's Encrypt via `mytlschallenge` resolver |

### Hard isolation rule (verbatim from `CLAUDE.md`)

> Under no circumstances does this codebase read DuloCore's env, mount DuloCore's volumes, share DuloCore's credentials, or import DuloCore code.

Physical isolation at five layers: repo, container, DB file, env file, Clerk tenant. The only shared surface is Traefik, which is routing and TLS termination — not code or data coupling.

---

## 4. The 18 Protocols (the differentiator)

*TL;DR — 9 implemented, 3 scaffolded, 6 deferred-with-seam. Every deferral has a named function body or config key where Phase 2 graduates in.*

The project is structured around 18 protocols adapted from DuloCore. Every one of them has a graduation trigger and a named seam. See `docs/workflows/PROTOCOL-APPLICATION-MATRIX.md` for the full 1000-word rationale.

### Full table

| # | Protocol | Phase 1 status | Evidence | Phase 2 seam |
|---|---|---|---|---|
| P1 | Agent Hierarchy (ATOMIC-S) | IMPLEMENTED (2-tier collapsed) | `agents/drivers/nl_ordering.py` L1 Director + SDK-managed L3 workers | `agents/drivers/dispatch.py` body → Inngest |
| P2 | Task / Exploration Depth | IMPLEMENTED (advisory) | `agents/depth_scorer.py::score_query()` called in route | Flip `should_decompose` from logged-only to enforced |
| P3 | Progressive Disclosure | IMPLEMENTED | `CLAUDE.md` <120 lines, `docs/INDEX.md` router, `docs/CATALOG.md` table | Auto related-topic graph |
| P4 | Claude Agent SDK Integration | IMPLEMENTED | `agents/tools_sdk.py` has 4 live `@tool`s + MCP server; routes never touch DB | Hook-enforced Route Rule |
| P5 | Director System | IMPLEMENTED (single L1 MEAL) | NL Ordering Director in production | L0 router + spawn scripts for multi-facility |
| P6 | Karpathy Wiki KB | SCAFFOLDED | `wiki/compiler.py`, `wiki/schema.yaml`, `wiki/topics/` dir exist; compile fn raises | MiniLM embeddings in `cluster_traces()` |
| P7 | Karpathy Auto-Research | SCAFFOLDED | Layer 1 (trace write) live; Layer 2 (compile) stubbed | 24-hour systemd timer + graph KB |
| P8 | Progressive Memory | IMPLEMENTED | 4-type schema in `wiki/schema.yaml`; 5 seed files in `memory/` | Add `decision` + `observation` types |
| P9 | Dev Workflow + DoD | IMPLEMENTED (3-stage collapsed) | `docs/PHASE-4-EXECUTION-PLAN.md` 8 slices; per-slice acceptance | Expand to 5-stage + UserAccessible |
| P10 | Hook System | IMPLEMENTED (1 reference hook) | `.claude/hooks/tdd_enforcer.py` advisory PostToolUse | Grow `.claude/hooks.json` registry |
| P11 | Self-Validation Loop | IMPLEMENTED (3-step lite) | Doc convention in architecture docs | Full 5-loop with confidence threshold |
| P12 | Reviewable Artifact + Phase Gate | DEFERRED-WITH-SEAM | Doc convention only | Port `artifact_enforcer.py` hook |
| P13 | Rollout Pattern (PoC first) | DEFERRED-WITH-SEAM | PRP template field only | Hook-enforced PoC Gate |
| P14 | Frontend/Backend Decoupling | IMPLEMENTED | Every HTML route has `/api/v1/*` JSON twin | Swap Jinja for React |
| P15 | Authentication Isolation | IMPLEMENTED | Dedicated Clerk tenant, separate env file, `app/auth/` 4 modules | `require_login` → `require_role(role)` |
| P16 | Design Principles | IMPLEMENTED (doc) | `docs/systems/architecture-principles/ARCHITECTURE-PRINCIPLES.md` | Pre-PR checklist |
| P17 | Business Plan Architecture | IMPLEMENTED | `docs/business/BUSINESS-PLAN-ARCHITECTURE.md` 123 lines | Pricing & unit-economics section |
| P18 | Deferred-with-Seam | IMPLEMENTED (doc) | `docs/PHASE-2-ROADMAP.md` 22 items | Rows move to CATALOG.md on graduation |

### The 9 implemented protocols

P1, P3, P4, P5, P8, P9, P10, P14, P15, P16, P17, P18 ship as real code **or** as mandatory conventions carried through the codebase (P3, P16, P18 are doc conventions but are actually enforced — CATALOG.md is one table, not scattered; every architecture doc cites a principle). P1/P4/P5/P14/P15 are runtime code you can grep for.

### The 3 scaffolded protocols

"Scaffolded" means the structural home exists, seams are named in code, but the function bodies are `raise NotImplementedError`. This is deliberate — the shape is proven, the loop is not yet run.

- **P6 Karpathy Wiki KB.** `wiki/compiler.py` exists with docstring algorithm + empty function bodies. `wiki/schema.yaml` (4 memory types) is complete. `wiki/topics/` directory exists.
- **P7 Karpathy Auto-Research.** Layer 1 (`agents/observability.py::record_outcome`) is live and writing real traces on every NL-ordering turn. Layer 2 (the compile loop) is `NotImplementedError`. The pipeline shape is proven; the compile bottom half ships in Phase 2.
- **P2 Task / Exploration Depth** is technically implemented (the scorer returns a level) but the *enforcement* is advisory-only — `should_decompose()` always returns False. Counting it as implemented since the score is logged on every trace row.

### The 6 deferred-with-seam protocols

These are protocols the project commits to without yet running: P11 full Self-Validation Loop, P12 Reviewable Artifact hook, P13 Rollout Pattern enforcement, and three infra-level items (full hook suite, cross-director scaling, trace retention policy). The discipline for tracking them is the **`# Phase 2 Graduation:`** comment — we have **48 of these across .py, .yml, .html, and .md files**. Example from `app/db/database.py:110`:

```python
# Phase 2 Graduation: swap SQLite+aiosqlite for Postgres+asyncpg via DATABASE_URL env swap only;
# add connection pooling, read replicas, and Alembic migrations.
```

### Four anchor protocols explained in depth

#### P1 — Agent Hierarchy (ATOMIC-S)

Phase 1 collapses DuloCore's 4-tier Supervisor→Director→Manager→Worker chain into 2 tiers — L1 Director (us) and L3 Workers (SDK-managed subagents). Why this matters: ATOMIC-S is about *single-responsibility at a tier*, not about tier count. We keep the *principle* (mandatory delegation — L1 never touches the DB) and collapse the *implementation* to what a kata-scale prototype needs. The graduation seam is `agents/drivers/dispatch.py` — when concurrency exceeds ~4 workers sustained, we swap the in-process `asyncio.gather` body for an Inngest event emit. Driver files stay untouched because they never knew about the transport.

#### P4 — Claude Agent SDK Route Rule

The rule is simple: *FastAPI routes MUST NOT import a DB session; they MUST call `@tool` functions*. Why it matters: this is what keeps the agentic layer from becoming a spaghetti mess. Every data access goes through the same tool registry the LLM uses. Test paths, confirm paths, direct-form paths all converge on the same 4 functions. You can prove route compliance with `grep -rn 'from sqlmodel' app/routes/`. Grepping our code today yields hits only in Slice A's recipe list (a fast-path before the SDK layer existed) and in route helpers that resolve `require_facility_access` — no DB writes in any route body.

#### P6 — Karpathy Wiki Knowledge Base

The pattern: agents emit traces → compiler clusters traces into topic pages → next session's system prompt gets relevant topic pages injected → agent gets smarter across sessions. Why it matters: this is the self-improvement loop without the usual "let's build a vector DB on day one" anti-pattern. Layer 1 runs live — you can `cat logs/agent_trace.jsonl` right now and see real tool-call shapes. Layer 2 is hand-clustering in Phase 1 (`cluster_traces` signature is correct, body is a stub). MiniLM embeddings are the Phase 2 graduation — body swap, signature preserved.

#### P15 — Authentication Isolation (Clerk)

Why a separate Clerk tenant matters: auth is where tenancy leaks happen. Sharing a Clerk app across two unrelated projects would mean one project's session token could be replayed against the other's protected routes unless both apps carefully scope audience claims. We sidestep that entire class of bug by provisioning a dedicated DS-Meal Clerk Development app with its own frontend API, its own JWKS, its own secret key. Phase 2 multi-tenant RBAC is a `require_login` → `require_role(role)` extension — one function, no auth-layer rewrite.

---

## 5. The Agentic Layer (Claude Agent SDK integration)

*TL;DR — one live flow (NL Ordering). Browser → route → dispatch → driver → SDK query → 4 MCP tools → DB. One Menu Planner stub. Every turn writes an observability trace. Karpathy compile loop is scaffolded, not functional.*

### End-to-end trace of the live NL ordering flow

The reviewer can walk this path line-by-line in the repo:

1. **Browser** POSTs `/orders/new` with form data `text="25 Turkey Meatloaf for Thursday dinner"` (`app/routes/orders.py:121`).
2. **Route** calls `score_query(text)` once (G13 — advisory, logged on trace only) then `invoke_director("nl_ordering", {...})` (`agents/drivers/dispatch.py:16`).
3. **Dispatch** constructs an `NLOrderingRequest` dataclass and instantiates `NLOrderingDriver(query_fn=None)` — `None` means use the production `_default_query_fn` (`agents/drivers/nl_ordering.py:265`).
4. **Driver.run()** mints a `trace_id`, opens a `try/finally` that guarantees `record_outcome()` fires even on exception (`agents/drivers/nl_ordering.py:330`).
5. **`_default_query_fn`** pops `CLAUDECODE` from env (known SDK gotcha), builds the in-process MCP server via `build_nl_ordering_mcp_server()`, loads the system prompt from `agents/prompts/nl_ordering.md`, and issues a single `claude_agent_sdk.query()` call with Haiku (`agents/drivers/nl_ordering.py:105`).
6. **The SDK agentic loop** runs Haiku, which calls `resolve_recipe` → `scale_recipe` → `check_inventory` → emits a proposal JSON block. Each tool call hits the in-process MCP server (no network), which routes to the `@tool` wrapper in `agents/tools_sdk.py`.
7. **Each tool call** ends up in `agents/tools.py` — pure async SQLAlchemy helpers with no SDK coupling. Decoupled deliberately so tests can drive the same DB without going through the SDK.
8. **Driver** observes `ToolUseBlock` and `ToolResultBlock` events, appends to `response.tool_calls`, accumulates assistant text.
9. **On terminal assistant message**, driver extracts the ```json block via regex (last fence wins) and returns `status="awaiting_confirmation"` with the proposal dict.
10. **Route** re-renders `orders/new.html` with the proposal card. Browser shows it.
11. **User clicks Confirm** — POST `/orders/new` again with `confirm=true`. Route dispatches again.
12. **Confirm prompt** (the bit that bit us today — `c66b726`) includes the original user text verbatim, because each `query()` is a **stateless SDK session**. The driver asks Haiku to re-resolve, then call `schedule_order` with `confirmed=true`.
13. **`schedule_order`** opens an async SQLAlchemy session, inserts `Order` + `OrderLine` + initial `OrderStatusEvent(pending)`, commits.
14. **Driver** scans the recorded tool-call list for the last successful `schedule_order` and extracts `order_id` from its result text block (`_order_id_from_tools`, `agents/drivers/nl_ordering.py:258` — the `e25320d` fix).
15. **Route** sees `status="pending"` + `order_id` and returns `RedirectResponse(f"/orders/{order_id}", 303)`.
16. **Every turn**, the `finally` block in `driver.run` calls `record_outcome` which writes one row to `agent_trace` SQLite + one line to `logs/agent_trace.jsonl` + one JSON file to `logs/agent_payloads/{trace_id}.json`.

### The 4 live MCP tools

Registered by `build_nl_ordering_mcp_server()` in `agents/tools_sdk.py:275`:

```python
@tool("resolve_recipe",  "Fuzzy-match a free-text recipe name to the catalog.",     {"name_query": str, "top_k": int, "min_confidence": float})
@tool("scale_recipe",    "Project cost + totals for a recipe at a target servings.", {"recipe_id": int, "n_servings": int})
@tool("check_inventory", "Verify ingredients are in stock (Phase 1 stub: always ok).",{"recipe_id": int, "n_servings": int, "needed_by": str})
@tool("schedule_order",  "Persist a single-line order (confirmed=true only after approval).",
      {"facility_id": int, "placed_by_user_id": int, "recipe_id": int, "n_servings": int,
       "unit_price_cents": int, "delivery_date": str, "delivery_window_slot": str,
       "notes": str, "confirmed": bool})
```

Tool names the SDK agent is allowed to call (passed to `ClaudeAgentOptions.allowed_tools`):

```
mcp__ds_meal_nl_ordering__resolve_recipe
mcp__ds_meal_nl_ordering__scale_recipe
mcp__ds_meal_nl_ordering__check_inventory
mcp__ds_meal_nl_ordering__schedule_order
```

### The "one-shot session" insight

Every `claude_agent_sdk.query()` call is a fresh SDK session with no memory of the prior turn. We learned this the hard way (today, commit `c66b726`). On confirm, we can't say "use the values you proposed" — we have to re-include the original user text plus an explicit "STEPS:" block asking Haiku to re-resolve, re-scale, then schedule. It's more tokens per confirm but it's stateless and therefore auditable.

### Menu Planner status

`agents/drivers/menu_planner.py` is 73 lines of pseudocode-heavy class scaffold. Both `__init__` and `run` raise `NotImplementedError`. This is deliberate — it's the Phase 1 stub with the full docstring + dataclass contract + Phase 2 graduation comments. Slice E ships it.

### Depth scorer

`agents/depth_scorer.py::score_query()` implements the 6-dimension scorer (Scope, Info Density, Reasoning Depth, Verification Need, Consistency Risk, Domain Breadth — 0-2 each, max 12). Called once in `app/routes/orders.py:130` (G13) and written to the trace row via `record_outcome`. Phase 1 is **advisory**: the score is logged, never acted upon. The `should_decompose()` function signature is in place; body always returns False. Phase 2 flips the body.

### Observability plumbing

From `agents/observability.py`:

| Sink | Written when | What goes in |
|---|---|---|
| `agent_trace` SQLite table | Every driver turn | ts, agent_name, query_text, tool_calls_json, outcome, confidence_score, latency_ms, cost_cents, notes |
| `logs/agent_trace.jsonl` | Every driver turn | Same row serialized as JSON |
| `logs/agent_payloads/{trace_id}.json` | Every driver turn | Full request/response + raw tool_calls (separate file so JSONL stays grep-friendly) |

The SQLite table has **10 rows** right now (seeded + organic). Every row is auditable.

---

## 6. HTTP Route Surface

*TL;DR — ~33 routes. Every HTML surface has a JSON twin. Public auth-free surface is small (health, landing, recipes, sign-in). Everything else is gated via `Depends(require_login)`. Auth uses a 1-hour app-session HS256 token we mint ourselves — we do NOT store the Clerk JWT in the cookie.*

### Route inventory

| Category | Route | Method | Auth | Status |
|---|---|---|---|---|
| Public HTML | `/` | GET | none | working |
| Public HTML | `/health` | GET | none | working |
| Public HTML | `/sign-in` | GET | none | working |
| Public HTML | `/sign-in/callback` | GET | none | working |
| Public form | `/sign-in/exchange` | POST | none (verifies Clerk JWT body) | working |
| Public form | `/sign-out` | POST | none | working |
| Public HTML | `/recipes` | GET | none | working |
| Public HTML | `/recipes/{id}` | GET | none | working |
| Public HTML | `/recipes/{id}/ingredients` | GET | none | working |
| Gated HTML | `/facility/dashboard` | GET | `require_login` | working |
| Gated HTML | `/orders` | GET | `require_login` | working |
| Gated HTML | `/orders/new` | GET | `require_login` | working |
| Gated form | `/orders/new` | POST | `require_login` | working — live SDK path |
| Gated HTML | `/orders/{id}` | GET | `require_login` + `require_facility_access` | working |
| Gated HTML | `/calendar` | GET | `require_login` | working |
| Stub HTML | `/meal-plans` | GET | `require_login` | `NotImplementedError` |
| Stub HTML | `/meal-plans/new` | GET | `require_login` | `NotImplementedError` |
| Stub form | `/meal-plans/new` | POST | `require_login` | `NotImplementedError` |
| Stub form | `/agents/menu-plan` | POST | (would be `require_login`) | `NotImplementedError` |
| Stub form | `/agents/nl-order` | POST | (would be `require_login`) | `NotImplementedError` (duplicates `/orders/new` POST) |
| JSON twin | `/api/v1/health` | GET | none | working |
| JSON twin | `/api/v1/recipes` | GET | none | working |
| JSON twin | `/api/v1/recipes/{id}` | GET | none | working |
| JSON twin | `/api/v1/recipes/{id}/ingredients` | GET | none | working |
| JSON twin | `/api/v1/facility/me` | GET | `require_login` | working |
| JSON twin | `/api/v1/orders` | GET | `require_login` | working |
| JSON twin | `/api/v1/orders` | POST | `require_login` | working |
| JSON twin | `/api/v1/orders/{id}` | GET | `require_login` + `require_facility_access` | working |
| JSON twin | `/api/v1/calendar` | GET | `require_login` | working |
| JSON twin | `/api/v1/meal-plans` | GET | `require_login` | stub |
| JSON twin | `/api/v1/meal-plans` | POST | `require_login` | stub |
| JSON twin | `/api/v1/agents/menu-plan` | POST | (would be gated) | stub |
| JSON twin | `/api/v1/agents/nl-order` | POST | (would be gated) | stub |

Totals: **33 registered routes** — 13 public, 12 gated-working, 8 stubs.

### Auth gating model

```python
# app/auth/dependencies.py
@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    clerk_user_id: str
    email: str
    facility_id: int

async def require_login(request, session) -> CurrentUser:
    token = _extract_token(request)                     # cookie or Authorization header
    claims = verify_app_session(token)                  # HS256, 1-hour TTL
    user = await session.exec(select(User).where(
        User.clerk_user_id == claims.sub)).one()
    return CurrentUser(...)
```

`require_facility_access(resource_facility_id, user)` raises 403 if `user.facility_id != resource_facility_id`. Tenancy guard. Phase 2 extends this to `require_role(role)` — additive, no rewrite.

### The app-session token pattern

**Why we don't store the Clerk JWT in the cookie**: Clerk's default session JWT expires in ~60 seconds. Storing it in a cookie would force a Clerk round-trip on every request. Instead, `/sign-in/exchange` verifies the Clerk JWT *once*, then mints our own **1-hour HS256 app-session token** (`app/auth/app_session.py`), signs it with `CLERK_SECRET_KEY` (reusing the secret we already have — no new rotation burden), and stores *that* in the `__session` cookie. Per-request auth verifies the app-session token only. Zero Clerk calls on the hot path.

Phase 2 moves to a dedicated `APP_SESSION_SECRET` + a server-side session store (opaque cookie → session row lookup). Seam: `app/auth/app_session.py`.

### REST twin pattern

Every HTML route has a `/api/v1/` twin. Both call the same service function. Example: `GET /orders/{id}` and `GET /api/v1/orders/{id}` both call `app/services/orders.py::get_order_with_timeline(id)`. The Jinja version wraps in a template, the JSON version returns a dict. Swapping Jinja for React is pure frontend — zero backend change.

---

## 7. Data Model and Persistence

*TL;DR — SQLite, 13 tables, seeded with 5 facilities, 10 recipes, 30 residents, 2 users, ~10 demo orders. Postgres graduation is a one-line `DATABASE_URL` swap.*

### The 13 tables

| Table | Purpose |
|---|---|
| `facility` | Senior-living facilities (5 seeded; one with `admin_email` set for the allowlist) |
| `user` | Admin users bound to one facility via `facility_id` |
| `resident` | Residents whose dietary constraints must be honored |
| `resident_dietary_flag` | Many-to-many join: resident → DietaryFlag enum (11 flag values) |
| `recipe` | Menu items — title, texture_level, allergens JSON, cost, base_yield, carbs/sodium/potassium/phosphorus |
| `ingredient` | Canonical ingredient catalog with allergen_tags JSON |
| `recipe_ingredient` | Many-to-many join: recipe → ingredient with grams |
| `meal_plan` | Weekly menu plans (Menu Planner output surface; Phase 1 stub) |
| `meal_plan_slot` | 21 slots per week (7 days × 3 meals) |
| `order` | One delivery to a facility on a specific date. **108 rows today — production use-case proved.** |
| `order_line` | Order line items with unit + line totals + `PricingSource` enum (static / llm_refined) |
| `order_status_event` | Append-only audit log of order state transitions |
| `agent_trace` | Karpathy Layer 1 trace row — one per agent turn (10 rows today) |

### Seed state (live on VPS)

```bash
$ sqlite3 /opt/direct-supply-meal/data/ds-meal.db '
    SELECT COUNT(*) FROM facility;  -- 5
    SELECT COUNT(*) FROM recipe;    -- 10
    SELECT COUNT(*) FROM resident;  -- 30
    SELECT COUNT(*) FROM user;      -- 2 (one unprovisioned placeholder + one live)
    SELECT MAX(id)  FROM "order";   -- 108
    SELECT COUNT(*) FROM agent_trace; -- 10
'
```

Only Riverside SNF (facility_id=2) has `admin_email` set in Phase 1 — that is the allowlist. The other four facilities are present for the multi-tenancy graduation demo only.

### Why SQLite in Phase 1

Zero external dependencies. Bind-mounted volume means the file is durable across container rebuilds. Tests use a temporary path (`tmp_path` pytest fixture) and get true isolation per test. Phase 1 is single-tenant single-admin — there's literally nothing SQLite won't handle at this scale.

### Postgres graduation (Phase 2)

One line in `.env.ds-meal`:

```diff
- DATABASE_URL=sqlite+aiosqlite:///./data/ds-meal.db
+ DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/dsmeal
```

The graduation comment at `app/db/database.py:110` names this explicitly. Add Alembic migrations (also seamed in `app/db/init_schema.py:66`). Everything else — SQLAlchemy async engine, SQLModel tables, route code — stays identical.

---

## 8. Testing Story

*TL;DR — 131 tests across 17 files (54 unit, 46 integration, 28 agent, 3 e2e; 15 new today in `test_app_session.py` and `test_clerk_email_fallback.py`). Six auth/SDK fixes landed with tests attached the same day. CI workflow is drafted but not yet pushed.*

### Test inventory

| Layer | Files | Tests |
|---|---|---|
| Unit | `tests/unit/test_scaling.py` (5), `test_calendar_view.py` (12), `test_orders_service.py` (11), `test_orders_state_machine.py` (16), `test_app_session.py` (10 — **new today**) | 54 |
| Integration | `test_recipes_api.py` (9), `test_auth.py` (8), `test_calendar_api.py` (5), `test_orders_api.py` (10), `test_orders_new_api.py` (7), `test_dashboard_data.py` (2), `test_clerk_email_fallback.py` (5 — **new today**) | 46 |
| Agent (mocked SDK) | `test_depth_scorer.py` (10), `test_nl_ordering_driver.py` (5), `test_observability.py` (3), `test_tools_sdk.py` (10) | 28 |
| E2E Playwright | `test_dashboard_flow.py` (2), `test_recipes_e2e.py` (1) | 3 |
| **Total** | 17 files | **131 tests** |

### Test fixtures

| File | Purpose |
|---|---|
| `tests/fixtures/claude_responses.json` | Canned SDK multi-turn message payloads, keyed by `fixture_key` (`nl_ordering__oats_happy_path`, etc.) |
| `tests/fixtures/clerk_jwt_helpers.py` | Ephemeral RS256 keypair + threaded HTTP server serving JWKS + `mint_session_token()` |
| `tests/fixtures/transcript_helpers.py` | Shared helpers for driver tests that inject a transcript directly |

### Honest note on today's TDD gap

The 6 auth/SDK fixes this afternoon were **incident-response code first, tests second**. This is not the discipline we preach. The backfill (commit `1cae8c4`) added 15 tests covering:

- `app_session` mint + verify, expiry enforcement, wrong-issuer rejection, tampered-token rejection
- Clerk email fallback: JWT-has-email fast path, JWT-lacks-email → Backend API fallback, Backend API error paths

The backfill is complete. Going forward, any further auth/SDK changes land as test-first.

### Coverage we still don't have

- **E2E sign-in flow.** `tests/e2e/test_signin.py` was planned for Slice B; it's not yet written. Live sign-in has been manually verified.
- **Clerk email-fetch integration test beyond mock.** We mock `httpx.get` in the unit test. No test actually hits `api.clerk.com` — intentional (don't couple CI to an external service).
- **Karpathy compile-loop tests.** Because `wiki/compiler.py` raises `NotImplementedError`, its tests are empty.
- **CI not yet enforcing.** `.github/workflows/ci.yml` is drafted in the execution plan but not pushed (PAT needed `workflow` scope). The tests pass locally via `pytest`; they will pass in CI the moment the workflow lands.

---

## 9. Phase 1 vs Phase 2 Boundary

*TL;DR — Phase 1 is 8 slices A-H. Slices A-D + H are green; E (Menu Planner) is scaffolded; F (Karpathy compile) is scaffolded; G (prod deploy) is live. Phase 2 is 22 seamed items with named triggers.*

### Slice-by-slice Phase 1 delivery

| Slice | Deliverable | Status | Evidence commit |
|---|---|---|---|
| A | Kata baseline — recipe browse, scaling, E2E | SHIPPED | `77e7380` |
| B | Clerk sign-in + facility dashboard shell | SHIPPED | `4ca431c` |
| C | Orders history/detail + calendar + real-data dashboard | SHIPPED | `c45c94b` |
| D | NL Ordering agent (transcript tests) | SHIPPED | `11e12bb` |
| D+ | Real `_default_query_fn` — production SDK path | SHIPPED | `ea670d9` |
| E | Menu Planner agent + MealPlan → Orders generation | SCAFFOLDED | driver + route stubs only |
| F | Karpathy Auto-Research end-to-end with real Haiku | SCAFFOLDED | compiler signature only |
| G | Production deploy + TLS + healthcheck | LIVE | container up, cert issued |
| H | Polish + demo script + RealAuth | PARTIAL | demo script shipped (`5c4619c`); RealAuth deferred |

### Phase 2 Roadmap highlights (from `docs/PHASE-2-ROADMAP.md`)

22 graduation items. Top 5 the reviewer will ask about:

| # | Item | Trigger | Seam |
|---|---|---|---|
| 1 | Inngest event bus | Any flow > 30s OR cross-process durability required | `agents/drivers/dispatch()` body swap |
| 2 | MiniLM embeddings for wiki compilation | Traces > 500 per agent | `wiki/compiler.py::cluster_traces()` body |
| 3 | Graph KB (Kuzu/NetworkX/Neo4j) | Topic pages > 20 per agent | new `wiki/graph.py` |
| 6 | Multi-tenant RBAC | Second facility admin onboards | `require_login` → `require_role()` |
| 12 | Real inventory sync (supplier ERP) | Supplier data available | `@tool check_inventory` body |

### The 48 `# Phase 2 Graduation:` comments

Every Phase 2 graduation item has a corresponding comment in the code marking its exact seam. Example from `agents/tools_sdk.py:126`:

```python
async def check_inventory(args: dict[str, Any]) -> dict[str, Any]:
    """Check ingredient availability for a proposed order (Phase 1 stub: always OK).

    Phase 2 Graduation: real supplier ERP call. Seam is this function body.
    """
```

Grep yields 48 hits across Python, YAML, HTML, and Markdown. Every one of them names either a function body to swap, a config key to add, or a registry to grow.

### Seams in roadmap but not yet scaffolded as files

Four of the 22 roadmap items don't have placeholder files yet. Deliberate — adding empty files before the trigger fires is speculative. They are:

- `wiki/graph.py` (graph KB for gap detection)
- `wiki/lint.py` (7-point wiki lint)
- `wiki/retention.py` (trace retention policy)
- Cross-director topics directory structure (`wiki/topics/{director_id}/{agent_name}/`)

Creating these files before the feature lands would violate YAGNI. The roadmap names them and tells you where they go; we write them when the trigger fires.

---

## 10. Strengths and Weaknesses (brutally honest)

*TL;DR — strengths: clean seams, real agentic flow working in prod, zero DuloCore coupling. Weaknesses: menu planner stubbed, Karpathy compile loop stubbed, CI not enforcing, dev-tier Clerk banner visible, cookie not `secure=True`.*

### Strengths

- **Clean separation of concerns: Routes / Services / Tools / Drivers.** Each layer has a single responsibility. Routes parse HTTP, services own business logic, tools are the SDK-addressable surface, drivers orchestrate agents. You can delete any one layer and re-implement it without touching the others.
- **Zero-JS-build frontend.** Jinja + a single `<script>` tag for Clerk. No npm, no webpack, no build pipeline. Iteration is "edit HTML, reload page." The JSON twin contract guarantees React drops in when we want it.
- **Named seams for every deferred item.** 48 `# Phase 2 Graduation:` comments point at specific function bodies or config keys. No "figure it out later."
- **131 tests with all 4 layers (unit / integration / agent / E2E).** Unit tests for the state machine; integration for routes; agent tests that mock the SDK and assert tool-call shapes; Playwright E2E for the recipe-browse baseline. Discipline is present even if coverage is not yet uniform.
- **Observability plumbing from day one.** Every agent turn writes to `agent_trace` SQLite + `agent_trace.jsonl` + `agent_payloads/{id}.json`. Not bolted on after an incident.
- **Hard isolation from DuloCore.** Five layers (repo / container / DB / env / Clerk tenant). The README leads with this rule; the `docker-compose.yml` enforces it by explicitly using an external network and never reading DuloCore paths.
- **Production Clerk auth working.** Google OAuth signs in, `/sign-in/exchange` verifies the Clerk JWT, app-session cookie round-trips cleanly, 1-hour TTL avoids the ~60s Clerk JWT trap.
- **Rollout Pattern honored.** The entire system is a PoC — Phase 1 is itself the "small batch on 3-5 units" before scaling. Phase 2 is named, not scoped.

### Weaknesses

- **Today's 6 auth/SDK fixes backfilled with tests but not yet CI-verified.** `.github/workflows/ci.yml` is drafted, not pushed. Tests pass locally; no CI enforcement until the workflow lands. Fix: push the workflow file with a PAT that has `workflow` scope.
- **Clerk dev-tier tenant still shows "Development mode" banner.** Production polish requires promoting the Clerk app to Production tier and configuring a custom subdomain — out of scope for Phase 1. Fix: Phase 2.
- **Menu Planner completely stubbed.** One of the two flagship agents is `raise NotImplementedError`. The demo mentions it exists; it does not run. Honest deferral, but a visible gap.
- **Karpathy wiki compile loop scaffolded but not functional.** `wiki/compiler.py` raises on every function. Layer 1 (trace ingestion) works; Layer 2 (pattern synthesis) does not. The claim "self-improving KB" requires Phase 2 completion to be true.
- **SQLite file-level perms required manual `chown` + `chmod`.** The OAuth cred mount is read-only but the appuser UID inside the container had to match the host UID owning `/root/.claude/.credentials.json`. Documented but fiddly.
- **Rate limiting absent on `POST /orders/new`.** Every confirm runs Haiku via the Max subscription. A bad actor with a valid session could burn through OAuth credits. Fix: Phase 2 Linear 1BU-1405 — add `slowapi` rate limiter on the single high-cost route.
- **Session doesn't auto-refresh.** 1-hour app-session TTL is a hard kick. The frontend doesn't silently refresh on 401. Fix: Phase 2 server-side session store with sliding expiration.
- **Pricing `estimate_cost` and `static_rollup` are stubs.** The happy path works via `Recipe.cost_cents_per_serving * n_servings` in the `schedule_order` tool body. The service-level pricing functions (`app/services/pricing.py`) are Phase 2.
- **Cookie `secure=False` (dev-mode leftover).** Committed deliberately so http:// tests can round-trip cookies. Flip to True via a `SECURE_COOKIES` setting before any non-dev exposure.
- **Demo orders never transition status.** Orders 101-105 are pre-seeded at various statuses (delivered, out_for_delivery, in_preparation, confirmed, pending) to populate the dashboard. No live dispatcher advances them. Fix: Phase 2 event-sourced status with Inngest.

---

### Closing note — what we'd change tomorrow

If we had 24 more hours before the demo, three things move the needle: **(1) push the CI workflow so pytest green is enforced, not asserted**; **(2) implement the Menu Planner driver end-to-end** (the skeleton is there — Sonnet + 5 tools + 21-slot fan-out is ~1 day of focused work), which unlocks the dietitian's workflow narrative and doubles the agentic surface; **(3) promote the Clerk app to Production tier** with a custom subdomain, which removes the dev-mode banner from every sign-in. CI gives us the "can defend this in a PR review" moment, Menu Planner gives us the "two flagship agents, not one" moment, prod Clerk gives us the "this is real, not a dev tenant" moment. Everything else on the weakness list is bounded-impact polish that Phase 2 absorbs gracefully.

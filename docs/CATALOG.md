# direct-supply-meal — Feature & Protocol Catalog

> **Updated: 2026-04-22 EOD** — Status columns now reflect post-Phase-1 implementation reality (features shipped on VPS, protocols implemented/scaffolded/deferred-with-seam, infra live on `ds-meal.dulocore.com`).
> Phase 2 graduation seams remain unchanged; only current-state columns were refreshed.

Status matrix for the prototype. Three tables:
1. **Features** — user-visible capabilities
2. **Protocols** — the 18 architectural patterns ported (or deferred with seam) from DuloCore
3. **Infrastructure** — external resources the project depends on

Status legend: **PLANNED** / **TODO** / **IN-PROGRESS** / **CODED** / **TESTED** / **DEPLOYED** / **DEFERRED** (base lifecycle) · **SHIPPED** / **PARTIAL** / **STUBBED** (Phase 1 feature reality) · **IMPLEMENTED** / **SCAFFOLDED** / **DEFERRED-WITH-SEAM** (protocol reality) · **LIVE** / **ACTIVE** / **PROVISIONED** (infra).

Post-Phase-1: Feature statuses describe what a user can actually do today; Protocol statuses describe whether the pattern is wired into code, scaffolded (seam present, core stubbed), or deferred-with-seam (convention-only for now).

---

## Table 1 — Features

| Feature | Phase | Stage | Verification | Key files | Status |
|---|---|---|---|---|---|
| Recipe Browse | App Phase 1 | Plan | Unit + E2E | `app/routes/recipes.py`, `app/templates/recipes/*.html`, `fixtures/recipes.json` | SHIPPED |
| Facility Dashboard | App Phase 1 | Plan | Integration + E2E (Real Auth) | `app/routes/facility.py`, `app/templates/facility/dashboard.html` | SHIPPED |
| Meal Planning | App Phase 1 | Plan | Agent + Integration | `app/routes/meal_plans.py`, `agents/drivers/menu_planner.py`, `agents/prompts/menu_planner.md` | STUBBED |
| NL Order | App Phase 1 | Plan | Agent + E2E | `app/routes/orders.py`, `agents/drivers/nl_ordering.py`, `agents/prompts/nl_ordering.md` | SHIPPED |
| Order History | App Phase 1 | Plan | Integration | `app/routes/orders.py`, `app/templates/orders/list.html` | SHIPPED |
| Calendar | App Phase 1 | Plan | Unit + Integration | `app/routes/calendar.py`, `app/services/calendar_view.py` | SHIPPED |
| Delivery Status | App Phase 1 | Plan | Unit + Integration | `app/services/orders.py`, `app/models/order.py` (OrderStatusEvent) | PARTIAL |
| Pricing | App Phase 1 | Plan | Unit + Agent | `app/services/pricing.py`, `agents/tools_sdk.py::estimate_cost` | STUBBED |
| Auth | App Phase 1 | Plan | Integration + E2E (Real Auth) | `app/auth/clerk_middleware.py`, `app/auth/dependencies.py`, `app/auth/provisioning.py` | SHIPPED |
| Karpathy Learning | App Phase 1 | Plan | Agent (seeded traces) | `wiki/compiler.py`, `wiki/schema.yaml`, `agents/observability.py`, `wiki/TOPICS-INDEX.md` | STUBBED |
| USDA Macros | App Phase 1 | Done (PRP approved) | In Progress (15/18 tasks + deploy pending) | `app/services/scaling.py`, `app/models/usda_food.py`, `app/models/recipe.py`, `app/routes/recipes.py`, `app/templates/recipes/detail.html`, `app/templates/recipes/ingredients.html`, `fixtures/macro.csv`, `fixtures/ingredient_fdc_mapping.json`, `scripts/seed_usda.py` | IN-PROGRESS (15/18 tasks done; awaiting T-016 verification + T-017 ship + deploy) |

---

## Table 2 — Protocols

Type key: **Pattern** (code shape ported), **Convention** (doc rule only), **Infra** (runtime component), **Domain** (ds-meal specific).

| Protocol | Type | Phase 1 status | Phase 2 graduation seam |
|---|---|---|---|
| P1 Agent Hierarchy (ATOMIC-S) | Pattern | IMPLEMENTED | Add L2 Manager tier when concurrency > 4 workers |
| P2 Task / Exploration Depth | Pattern | SCAFFOLDED | Wire as PreToolUse hook with blocking enforcement |
| P3 Progressive Disclosure | Convention | IMPLEMENTED | Auto cross-reference + related-topic graph generator |
| P4 Claude Agent SDK Integration | Pattern | IMPLEMENTED | Hook-enforced Route Rule (no direct DB in routes) |
| P5 Director System | Pattern | IMPLEMENTED | Add L0 router + spawn scripts for multi-facility |
| P6 Karpathy Wiki Knowledge Base | Pattern | IMPLEMENTED | MiniLM embeddings replace hand-clustering in `wiki/compiler.py::cluster_traces()` |
| P7 Karpathy Auto-Research | Pattern | SCAFFOLDED | 24-hour systemd timer replaces `make compile-wiki` |
| P8 Progressive Memory | Convention | IMPLEMENTED | 6-type schema (add observation + decision) + 7-point lint |
| P9 Dev Workflow + DoD | Convention | DEFERRED-WITH-SEAM | Add UserAccessible stage + full 5-stage dev workflow |
| P10 Hook System | Pattern | IMPLEMENTED | Grow `.claude/hooks.json` registry past 1 reference hook |
| P11 Self-Validation Loop | Convention | DEFERRED-WITH-SEAM | Full 5-loop (add Prove + Measure blast radius) |
| P12 Reviewable Artifact + Phase Gate | Convention | DEFERRED-WITH-SEAM | Hook-enforced commit-before-path |
| P13 Rollout Pattern (PoC First) | Convention | DEFERRED-WITH-SEAM | PoC Gate field in PRP template enforced by hook |
| P14 Frontend/Backend Decoupling | Pattern | SCAFFOLDED | Swap Jinja for React/Angular — zero backend change |
| P15 Authentication Isolation (Clerk) | Infra | IMPLEMENTED | Multi-tenant RBAC via role checks in `require_login` |
| P16 Design Principles | Convention | IMPLEMENTED | Pre-PR checklist referencing each principle |
| P17 Business Plan Architecture | Domain | IMPLEMENTED | Live pricing + unit-economics section |
| P18 Deferred-with-Seam | Convention | IMPLEMENTED | Per-item seams catalogued in PHASE-2-ROADMAP.md |

---

## Table 3 — Infrastructure

| Item | Owner | Status | Location |
|---|---|---|---|
| Docker container (`ds-meal`) | Ivan | LIVE | VPS `/opt/direct-supply-meal/`, compose file at `docker-compose.yml` |
| Traefik label block | Ivan | LIVE | `docker-compose.yml` labels, joins `root_default` network |
| Cloudflare DNS record | Ivan | LIVE | `ds-meal.dulocore.com` A-record → `72.60.112.205`, proxy ON |
| SQLite volume (bind-mount) | Ivan | LIVE | `/opt/direct-supply-meal/data/ds-meal.db` |
| GitHub repo | Ivan | ACTIVE | https://github.com/seoninja13/direct-supply-meal |
| Claude Agent SDK auth (Max subscription) | Ivan | ACTIVE | Uses Claude Code OAuth credentials on host; Dockerfile mounts `/root/.claude/.credentials.json` read-only. No metered Anthropic API key. |
| Clerk "DS-Meal" Development app | Ivan | LIVE | `/opt/direct-supply-meal/.env.ds-meal` (mode 0600, gitignored). Frontend: `ample-honeybee-65.clerk.accounts.dev`. |
| Cloudflare DNS `ds-meal.dulocore.com` | Ivan | LIVE | Proxied A-record → 72.60.112.205. record_id `f91a99572ebdadcde53e2a958ea506c3`. |

---

## Further reading

- [DEMO-SCRIPT.md](DEMO-SCRIPT.md) — Phase 1 demo walkthrough (recipes → order → calendar → history)
- [DR_MEAL_ARCHITECTURE_BREAKDOWN.md](DR_MEAL_ARCHITECTURE_BREAKDOWN.md) — architecture presentation reference
- [PHASE-2-ROADMAP.md](PHASE-2-ROADMAP.md) — graduation seams & what lands next

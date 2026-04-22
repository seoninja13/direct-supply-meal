# direct-supply-meal — Feature & Protocol Catalog

Status matrix for the prototype. Three tables:
1. **Features** — user-visible capabilities
2. **Protocols** — the 18 architectural patterns ported (or deferred with seam) from DuloCore
3. **Infrastructure** — external resources the project depends on

Status legend: **PLANNED** / **TODO** / **IN-PROGRESS** / **CODED** / **TESTED** / **DEPLOYED** / **DEFERRED**.

All rows below are set to PLANNED / TODO during Phase 2 (Workflow Design). Statuses update as Phase 3 (pseudocode) and Phase 4 (code) land.

---

## Table 1 — Features

| Feature | Phase | Stage | Verification | Key files | Status |
|---|---|---|---|---|---|
| Recipe Browse | App Phase 1 | Plan | Unit + E2E | `app/routes/recipes.py`, `app/templates/recipes/*.html`, `fixtures/recipes.json` | PLANNED |
| Facility Dashboard | App Phase 1 | Plan | Integration + E2E (Real Auth) | `app/routes/facility.py`, `app/templates/facility/dashboard.html` | PLANNED |
| Meal Planning | App Phase 1 | Plan | Agent + Integration | `app/routes/meal_plans.py`, `agents/drivers/menu_planner.py`, `agents/prompts/menu_planner.md` | PLANNED |
| NL Order | App Phase 1 | Plan | Agent + E2E | `app/routes/orders.py`, `agents/drivers/nl_ordering.py`, `agents/prompts/nl_ordering.md` | PLANNED |
| Order History | App Phase 1 | Plan | Integration | `app/routes/orders.py`, `app/templates/orders/list.html` | PLANNED |
| Calendar | App Phase 1 | Plan | Unit + Integration | `app/routes/calendar.py`, `app/services/calendar_view.py` | PLANNED |
| Delivery Status | App Phase 1 | Plan | Unit + Integration | `app/services/orders.py`, `app/models/order.py` (OrderStatusEvent) | PLANNED |
| Pricing | App Phase 1 | Plan | Unit + Agent | `app/services/pricing.py`, `agents/tools_sdk.py::estimate_cost` | PLANNED |
| Auth | App Phase 1 | Plan | Integration + E2E (Real Auth) | `app/auth/clerk_middleware.py`, `app/auth/dependencies.py`, `app/auth/provisioning.py` | PLANNED |
| Karpathy Learning | App Phase 1 | Plan | Agent (seeded traces) | `wiki/compiler.py`, `wiki/schema.yaml`, `agents/observability.py`, `wiki/TOPICS-INDEX.md` | PLANNED |

---

## Table 2 — Protocols

Type key: **Pattern** (code shape ported), **Convention** (doc rule only), **Infra** (runtime component), **Domain** (ds-meal specific).

| Protocol | Type | Phase 1 status | Phase 2 graduation seam |
|---|---|---|---|
| P1 Agent Hierarchy (ATOMIC-S) | Pattern | PLANNED | Add L2 Manager tier when concurrency > 4 workers |
| P2 Task / Exploration Depth | Pattern | PLANNED | Wire as PreToolUse hook with blocking enforcement |
| P3 Progressive Disclosure | Convention | PLANNED | Auto cross-reference + related-topic graph generator |
| P4 Claude Agent SDK Integration | Pattern | PLANNED | Hook-enforced Route Rule (no direct DB in routes) |
| P5 Director System | Pattern | PLANNED | Add L0 router + spawn scripts for multi-facility |
| P6 Karpathy Wiki Knowledge Base | Pattern | PLANNED | MiniLM embeddings replace hand-clustering in `wiki/compiler.py::cluster_traces()` |
| P7 Karpathy Auto-Research | Pattern | PLANNED | 24-hour systemd timer replaces `make compile-wiki` |
| P8 Progressive Memory | Convention | PLANNED | 6-type schema (add observation + decision) + 7-point lint |
| P9 Dev Workflow + DoD | Convention | PLANNED | Add UserAccessible stage + full 5-stage dev workflow |
| P10 Hook System | Pattern | PLANNED | Grow `.claude/hooks.json` registry past 1 reference hook |
| P11 Self-Validation Loop | Convention | PLANNED | Full 5-loop (add Prove + Measure blast radius) |
| P12 Reviewable Artifact + Phase Gate | Convention | PLANNED | Hook-enforced commit-before-path |
| P13 Rollout Pattern (PoC First) | Convention | PLANNED | PoC Gate field in PRP template enforced by hook |
| P14 Frontend/Backend Decoupling | Pattern | PLANNED | Swap Jinja for React/Angular — zero backend change |
| P15 Authentication Isolation (Clerk) | Infra | PLANNED | Multi-tenant RBAC via role checks in `require_login` |
| P16 Design Principles | Convention | PLANNED | Pre-PR checklist referencing each principle |
| P17 Business Plan Architecture | Domain | PLANNED | Live pricing + unit-economics section |
| P18 Deferred-with-Seam | Convention | PLANNED | Per-item seams catalogued in PHASE-2-ROADMAP.md |

---

## Table 3 — Infrastructure

| Item | Owner | Status | Location |
|---|---|---|---|
| Docker container (`ds-meal`) | Ivan | TODO | VPS `/opt/direct-supply-meal/`, compose file at `docker-compose.yml` |
| Traefik label block | Ivan | TODO | `docker-compose.yml` labels, joins `root_default` network |
| Cloudflare DNS record | Ivan | TODO | `ds-meal.dulocore.com` A-record → `72.60.112.205`, proxy ON |
| SQLite volume (bind-mount) | Ivan | TODO | `/opt/direct-supply-meal/data/ds-meal.db` |
| GitHub repo | Ivan | IN-PROGRESS | https://github.com/seoninja13/direct-supply-meal |
| Clerk app (`ds-meal-prototype`) | Ivan | TODO | Clerk dashboard — dedicated tenant, Google provider only, allowlist `admin@dulocore.com` |
| Anthropic API key (metered) | Ivan | TODO | `.env.ds-meal` on VPS (gitignored), `ANTHROPIC_API_KEY=sk-ant-api03-...` |

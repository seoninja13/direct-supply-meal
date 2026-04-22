# Phase 2 Roadmap — direct-supply-meal

Every deferred item with its exact graduation seam. This doc is the seam index — when an item graduates, its row moves to `docs/CATALOG.md` as "Built."

The repo follows the **Two-Horizon Rule**: every feature ships a working App Phase 1, and every Phase 2 extension has a named code seam. Graduation is a swap at a known interface, not a rewrite.

---

## Deferred Items (App Phase 2)

| # | Item | Phase 1 state | Seam | Trigger condition |
|---|------|---------------|------|-------------------|
| 1 | **Inngest event bus** | Synchronous in-process dispatch via `ClaudeSDKClient` | `agents/drivers/dispatch()` — swap function body | Any agent flow end-to-end exceeds ~30s OR cross-process durability required |
| 2 | **MiniLM embeddings for wiki compilation** | Hand-clustered patterns in `wiki/compiler.py::cluster_traces()` | Body of `cluster_traces()` (signature unchanged) | Trace count per agent > 500 AND hand patterns miss >20% of obvious clusters |
| 3 | **Graph knowledge base for wiki gap detection** | Implicit (none) — only flat Markdown topic pages | New file `wiki/graph.py` consumed by the compiler | Topic page count > 20 per agent. Build a concept graph from topic-page frontmatter + body entities; detect orphan concepts (entity referenced but no page covers it) and contradictions; trigger targeted Haiku re-compiles that *write the missing pages*. Options in order of footprint: **NetworkX** (in-memory, JSON-persisted, <1000 concepts) → **Kuzu** (embedded graph DB, single file like SQLite) → **Apache AGE on Postgres** → **Neo4j** (full-fat, separate JVM server). Start with Kuzu; it matches ds-meal's "single Python container + embedded storage" stance. This is the honest self-improvement loop — the system tells us what it doesn't know, and compiles the answer |
| 4 | **7-point wiki lint suite** | No lint in Phase 1 | New file `wiki/lint.py`, invoked after each compile | Topic page count > 20 per agent AND duplicate/contradictory pages surface in review. Rules: (1) duplicate pages, (2) contradictory rules, (3) staleness, (4) orphans, (5) broken links, (6) size violations, (7) consistency drift |
| 5 | **24-hour automatic compile cron** | `make compile-wiki` on-demand | `wiki/compile_timer.py` + systemd `.timer` unit | App in non-demo production use (at least one active non-demo facility) |
| 6 | **Multi-tenant RBAC** | Single-admin Clerk allowlist (Riverside SNF only) | `app/auth/dependencies.py::require_login` extends to `require_role(role)` | Second facility admin onboards |
| 7 | **Full 6-type memory schema + lint enabled** | 4 types (feedback/project/reference/user), lint disabled | `wiki/schema.yaml::type_strategies` + `lint.enabled: true` | Decision/observation types begin accumulating organically in traces |
| 8 | **Full 5-step Self-Validation Loop** | 3-step lite (State/Steel-man/Score) | `docs/systems/self-validation-loop/SVL-ARCHITECTURE.md` adds Prove + Measure | HIGH-magnitude architectural decisions occur weekly or more |
| 9 | **Depth-scorer actual decomposition** | Logs `should_decompose=true`, doesn't act | `agents/depth_scorer.py::should_decompose()` | Query depth scores consistently land ≥7 in production |
| 10 | **Hook-enforced Reviewable Artifact + Phase Gate** | Doc convention only | Port DuloCore's `artifact_enforcer.py` into `.claude/hooks.json` | Convention violated in a code review |
| 11 | **Hook-enforced Route Rule** | Convention in `CLAUDE.md` | Add PreToolUse hook to `.claude/hooks.json` that greps routes for DB imports | Direct DB call slips into a route in a code review |
| 12 | **Real inventory sync / ERP integration** | Stub `@tool check_inventory` returning `{ok:true}` | `@tool check_inventory` body | Real supplier data becomes available |
| 13 | **Supplier ERP-driven pricing** | Static seed + optional LLM refinement | `app/services/pricing.py::static_rollup()` body | Real unit-cost data available from a supplier API |
| 14 | **React/Angular SPA frontend** | Jinja2 server-rendered templates | Jinja deleted; SPA consumes `/api/v1/*` JSON twins | Product team wants a richer UX; `/api/v1/` contract already frozen |
| 15 | **Event-sourced order status** | `OrderStatusEvent` rows in SQLite | `app/services/orders.py::advance_order_status()` body emits an Inngest event | Status changes need to reach external systems (kitchen, logistics, notifications) |
| 16 | **Full enforcement hook suite** | One reference hook (`tdd_enforcer.py`) | `.claude/hooks.json` registry grows | Contributor count makes advisory convention insufficient |
| 17 | **Cross-director scaling** | Single MEAL director | `wiki/topics/{director_id}/{agent_name}/` + `agents/drivers/__init__.py` factory | Second director domain joins the codebase |
| 18 | **Trace retention policy** | All traces kept forever | New `wiki/retention.py`, nightly job | `agent_trace` table size > 100 MB. Policy: keep last 6 months hot, archive older rows to cold SQLite file |
| 19 | **Pricing & unit economics in business plan** | Directional claims only | New section in `docs/business/BUSINESS-PLAN-ARCHITECTURE.md` | Paid pilot signed |
| 20 | **Payment integration** | Out of Phase 1 scope | Separate service (not in this repo) | Paid pilot requires billing |
| 21 | **Delivery route optimization** | Out of Phase 1 scope | Separate service | Multi-facility delivery logistics required |
| 22 | **Mobile app** | Responsive web only | Separate repo consuming `/api/v1/*` | Facility staff demand native mobile |

---

## Graduation Policy

1. **No item graduates in isolation.** Each graduation is its own PRP, reviewed and approved before code lands.
2. **The seam is the contract.** If a graduation requires changing the seam's *signature*, it's not a graduation — it's a redesign, and the Phase 1 design has failed.
3. **Every graduation moves a row.** When item N graduates, its row is deleted here and a row is added (or updated) in `docs/CATALOG.md` with status `Built` or `Deployed`.
4. **The graduation trigger is honest.** Don't ship Phase 2 before its trigger fires. Premature optimization is the anti-pattern this doc is designed to prevent.

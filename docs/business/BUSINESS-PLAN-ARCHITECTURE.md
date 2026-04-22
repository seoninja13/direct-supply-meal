# BUSINESS PLAN ARCHITECTURE — ds-meal (Direct-Supply Meal Prototype)

**Author:** Ivan Dachev (dachevivo@gmail.com)
**Date:** 2026-04-22
**Status:** Interview artifact, Phase 1 scope
**Audience:** Direct Supply engineering leadership; internal reviewers

## 1. Executive Summary

ds-meal is a working prototype of a meal-ordering application for senior-living facilities — skilled nursing, assisted living, and memory care — that source prepared meals from a central commissary. It models five facilities totaling roughly 500 beds and exercises the realistic dietary constraints (diabetic, low-sodium, renal, soft-food, pureed, allergen-aware) that food-service staff actually manage.

The prototype pairs a deterministic, cleanly-factored API with two focused agentic workflows — an AI Menu Planner and a natural-language Ordering assistant — to show how LLMs can be deployed in healthcare-adjacent software without replacing the deterministic math and state transitions that operations depend on.

The exercise originates from an interview kata that asks only for a recipe list and a recipe-detail page. This deliverable exceeds that scope intentionally, to demonstrate Staff-level judgment about product scope, AI seams, and deferred complexity.

## 2. Business Problem

Senior-care food service is an underappreciated compliance engine. A 120-bed skilled-nursing facility serves roughly 360 meals per day across a resident population whose diet orders are legally attached to the care plan. CMS §483.60 requires that therapeutic diets align with the attending physician's orders and the resident's comprehensive assessment, and state surveyors cite F-tags for food-service deficiencies. In practice, the work looks like this:

- **Registered Dietitians** review weekly cycle menus against every resident's current diet order, allergen profile, and texture modification — often in spreadsheets, often manually, often under time pressure before a survey window.
- **Kitchen leads at the commissary** absorb last-minute substitutions and have to re-plate without breaking any individual resident's constraint.
- **Facility managers** have poor visibility into where their order is in the pipeline.

The underlying pain is not that the software is missing — most facilities have *something*. It is that the software does not reason. It stores. The humans do the reasoning, at 5:30 AM, repeatedly, against the same constraints.

## 3. Target Users

**Dietitian (Maya, RD/LDN).** Credentialed, salaried, stretched across two or three facilities. Owns compliance. Needs fast confidence that next week's menu does not violate any active diet order, with reasoning legible enough to defend to a surveyor.

**Facility Manager (Dan, NHA).** Licensed administrator for Riverside SNF. Owns resident experience and operating margin. Needs weekly budget visibility, delivery ETAs, and a single pane of glass for "what is happening with dinner tonight."

**Kitchen Lead at the Commissary (Teresa).** Runs production scheduling for the central kitchen. Needs a consolidated order view she can convert into prep sheets, with changes flagged early.

## 4. Value Proposition

1. Compliance review collapses from roughly 45 min/week to roughly 5 min/week via the Menu Planner agent's cited, human-readable verdict.
2. Order entry time drops by roughly an order of magnitude for routine reorders via natural-language intake.
3. Delivery visibility becomes ambient via a first-class order state machine and calendar view.
4. Pricing is defensible: a deterministic subtotal, with an LLM refinement that explains variance in prose the facility manager can pass to finance.
5. Dietary constraints are auditable: every order carries a snapshot of the constraints applied at order time.

These are the directional claims the prototype is designed to support. Quantitative validation is explicitly out of scope for Phase 1.

## 5. Product Scope (App Phase 1)

- Recipe browsing (public, kata baseline)
- Google authentication via Clerk (single admin identity per facility; `admin@dulocore.com` bound to Riverside SNF)
- Weekly meal planning with AI compliance check (Claude Sonnet)
- Natural-language order placement (Claude Haiku)
- Order history with status tracking (`pending` → `confirmed` → `in_preparation` → `out_for_delivery` → `delivered`)
- Calendar view of deliveries
- Pricing with LLM-refined estimates
- Karpathy Auto-Research loop for cross-session learning

## 6. AI Value Framing

LLMs are used only where language is the problem: compliance reasoning over free-text dietary constraints, and natural-language order intake. Everything else — pricing math, inventory decrements, state transitions, auth, RBAC — is deterministic code with deterministic tests. A failed LLM call degrades to "please fill out the form," it never corrupts state.

The Staff-level point is narrow and worth stating plainly: *agentic does not mean agent-anywhere.* Model the system first, identify the handful of decisions where natural language is load-bearing, and fence those decisions off from the ledger.

## 7. Product Roadmap (App Phase 2+)

- Inngest event bus for durable agent communication
- Full MiniLM-backed Karpathy wiki compilation
- **Graph knowledge base (Neo4j or lighter equivalent) for gap detection** — see `docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md` §12
- 7-point wiki lint
- 24-hour automatic compile cron
- Multi-facility / multi-tenant auth
- Payment integration
- Real inventory sync / ERP integration
- Delivery route optimization
- Mobile app

Each item has a named code seam in Phase 1 so the graduation is a contained change, not a rewrite. See the Two-Horizon Rule table at the end of this memo.

## 8. Success Metrics for the Demo

- Kata baseline visibly satisfied
- End-to-end workflow demoable in ≤5 minutes
- Architecture docs standalone-readable (reviewer can understand the system without pairing with the author)
- Agentic flows behave deterministically in the demo (retries, fallbacks, and non-agentic error paths are exercised live)
- Deployed live at `ds-meal.dulocore.com` — not localhost, not a screen recording

## 9. Explicit Non-Goals

- Not production-ready
- Not HIPAA-compliant (synthetic dietary data only)
- Not integrated with any real Direct Supply system
- Not marketable as-is
- **Not coupled to the author's unrelated project DuloCore.** ds-meal has its own GitHub repo (`seoninja13/direct-supply-meal`), its own Docker container, its own SQLite database (separate file on a separate bind-mounted volume), its own Clerk application (separate tenant, separate keys), its own `.env.ds-meal` file, its own metered `ANTHROPIC_API_KEY`, and its own working directory (`/opt/direct-supply-meal` on the VPS; never inside `/opt/dulocore/...`). The only physical overlap with DuloCore is the shared Traefik container on the VPS, which provides ingress and TLS termination for every subdomain — that is routing, not code or data coupling. DuloCore serves as a *pattern reference* only: architectural ideas are re-read and re-implemented from scratch, never imported.

## 10. How This Demonstrates Staff-Level Engineering

- **Decoupling as a discipline.** Physical, operational, and identity boundaries with DuloCore are enforced at the repo, container, DB, env, and auth-tenant layers — not asserted in a README.
- **Deferred complexity is designed, not skipped.** Every Phase 2 capability has a named Phase 1 seam. Graduation is a contained change.
- **AI with load-bearing judgment, not load-bearing faith.** LLMs own the language-shaped decisions; deterministic code owns the ledger. Fallbacks are exercised during the demo.
- **TDD where it matters.** Unit, integration, agent-behavior, and E2E Playwright layers; agent tests pin prompts and tool-call shapes, not exact phrasing.
- **Inline pseudocode and documented protocols.** Every `.py` file opens with numbered pseudocode; every protocol has its own architecture doc under `docs/systems/`.
- **Scoped to be defensible in a 45-minute interview.** Nothing in the demo requires narration to make sense.

---

## Two-Horizon Rule Applied

Every Phase 2 item is anchored to a concrete Phase 1 seam, so graduation is a localized change rather than a redesign.

| Phase 1 — ships now | Seam | Phase 2 — graduates when |
|---|---|---|
| Synchronous in-process agent dispatch via Claude Agent SDK | `agents/drivers/dispatch()` | Inngest event bus (when any flow exceeds ~30 s end-to-end, or cross-process durability is required) |
| Hand-clustered wiki compiler over SQLite `agent_trace` table | `wiki/compiler.py::cluster_traces()` | MiniLM embeddings + vector clustering (when trace volume outgrows human clustering) |
| Wiki topic pages as flat Markdown | new `wiki/graph.py` | Graph knowledge base (Neo4j or lighter) — detect gaps and orphan concepts; self-improve by synthesizing missing topic pages |
| On-demand `make compile-wiki` | timer stub | 24-hour systemd compile cron (when compile cadence becomes operational rather than demonstrative) |
| Hand-maintained `TOPICS-INDEX.md` | `wiki/index_generator.py` | Auto cross-reference + related-topics graph (when topic count makes manual curation unreliable) |
| 4-memory-type wiki (feedback / project / reference / user) | `wiki/schema.yaml` | 6-type schema adding observation + decision, with 7-point lint (when contradictions and staleness begin to surface) |
| Clerk single-admin allowlist (one facility, one admin) | `require_login` dependency | Multi-tenant RBAC across facilities (when more than one facility uses the system) |
| Static seed prices with LLM refinement | `services/pricing.py::estimate_with_llm()` | Real inventory sync / supplier ERP integration (when pricing must reconcile against actual supply) |
| Jinja2 server-rendered templates consuming `/api/v1/*` JSON | `/api/v1/*` JSON twins already exist for every HTML route | React or Angular SPA (pure frontend rewrite; backend unchanged) |
| Order status as `OrderStatusEvent` rows | table design | Inngest event-sourced status (when status reads require cross-service fan-out) |
| One reference enforcement hook (`tdd_enforcer.py`) | `.claude/hooks.json` registry | Full enforcement suite (when contributor count makes advisory convention insufficient) |
| 3-step Self-Validation Loop (State / Steel-man / Score) | doc convention | Full 5-loop with confidence threshold (when architectural decisions routinely affect multiple subsystems) |
| Kata-scale recipe catalog + 5-facility seed data | fixture scripts under `scripts/seed/` | Payment integration, delivery route optimization, mobile app (when the prototype graduates to a pilot) |

The common pattern across every row: the Phase 2 work is a swap at a known interface, not a restructuring of the system. That is the signal this document is built to send.

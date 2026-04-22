# direct-supply-meal — Documentation Index

Topic-bucket router. Every doc lives in exactly one bucket below. Detail lives in the linked file, never here.

Three buckets:
1. **Business & Workflow** — why we're building this and how the work flows
2. **Architecture & Systems** — the 18 protocols that shape the codebase
3. **Operations** — how to run, test, seed, and deploy

---

## 1. Business & Workflow

| Document | One-line description |
|---|---|
| [business/BUSINESS-PLAN-ARCHITECTURE.md](business/BUSINESS-PLAN-ARCHITECTURE.md) | Target users, value proposition, App Phase 1 vs Phase 2 scope, explicit non-goals |
| [workflows/DOMAIN-WORKFLOW.md](workflows/DOMAIN-WORKFLOW.md) | Entities, state machine, 5 user journeys, dietary rules, pricing, calendar |
| [workflows/AGENT-WORKFLOW.md](workflows/AGENT-WORKFLOW.md) | Menu Planner + NL Ordering flows, @tool contract, two layers of self-improvement |
| [workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md](workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md) | Cross-task learning loop: trace → compile wiki → inject at session start |
| [workflows/PROTOCOL-APPLICATION-MATRIX.md](workflows/PROTOCOL-APPLICATION-MATRIX.md) | For each of 18 protocols: where it lives, when it runs, Phase 2 seam |
| [CATALOG.md](CATALOG.md) | Protocol status matrix |

## 2. Architecture & Systems

Each protocol below gets its own `{NAME}-ARCHITECTURE.md` in the Phase 3 pseudocode step. Authored in Phase 3 alongside pseudocode stubs.

| Protocol | Planned system doc |
|---|---|
| P1 Agent Hierarchy (ATOMIC-S) | systems/agent-hierarchy/HIERARCHY-ARCHITECTURE.md |
| P2 Task / Exploration Depth | systems/task-depth/TASK-DEPTH-ARCHITECTURE.md |
| P3 Progressive Disclosure | systems/progressive-disclosure/DISCLOSURE-ARCHITECTURE.md |
| P4 Claude Agent SDK Integration | systems/claude-agent-sdk/SDK-ARCHITECTURE.md |
| P5 Director System | systems/director-system/DIRECTOR-ARCHITECTURE.md |
| P6 Karpathy Wiki Knowledge Base | systems/karpathy-wiki/WIKI-ARCHITECTURE.md |
| P7 Karpathy Auto-Research | systems/karpathy-auto-research/KARPATHY-ARCHITECTURE.md |
| P8 Progressive Memory | systems/progressive-memory/MEMORY-ARCHITECTURE.md |
| P9 Dev Workflow + DoD | systems/verification-stages/VERIFICATION-STAGES.md |
| P10 Hook System | systems/hook-system/HOOK-ARCHITECTURE.md |
| P11 Self-Validation Loop | systems/self-validation-loop/SVL-ARCHITECTURE.md |
| P12 Reviewable Artifact + Phase Gate | systems/reviewable-artifact/ARTIFACT-ARCHITECTURE.md |
| P13 Rollout Pattern (PoC First) | systems/rollout-pattern/ROLLOUT-ARCHITECTURE.md |
| P14 Frontend/Backend Decoupling | systems/frontend-backend-contract/CONTRACT-ARCHITECTURE.md |
| P15 Authentication Isolation (Clerk) | systems/authentication/AUTH-ARCHITECTURE.md |
| P16 Design Principles | systems/architecture-principles/ARCHITECTURE-PRINCIPLES.md |
| P17 Business Plan Architecture | business/BUSINESS-PLAN-ARCHITECTURE.md |
| P18 Deferred-with-Seam (Phase 2 Roadmap) | PHASE-2-ROADMAP.md |

## 3. Operations

Authored in Phase 3/4 when the code they describe exists.

| Document | One-line description |
|---|---|
| ops/RUNNING-LOCALLY.md | Local dev: install, migrate, seed, `make run-dev` |
| ops/TESTING.md | Test pyramid (unit / integration / agent / E2E), pytest commands, coverage |
| ops/DEPLOYING.md | Docker Compose on VPS, Traefik labels, Cloudflare DNS, env file wiring |
| ops/SEED-DATA.md | Fixture sources: 10 recipes, 5 facilities, seeded Riverside demo orders |
| ops/REPO-LAYOUT.md | Directory tree, module responsibilities, import rules |

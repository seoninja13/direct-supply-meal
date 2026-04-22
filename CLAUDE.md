# direct-supply-meal

> **REPO LOCATION — THIS IS WHERE WE WORK, NOWHERE ELSE**
> - **GitHub remote:** https://github.com/seoninja13/direct-supply-meal
> - **VPS path:** `/opt/direct-supply-meal/`
> - **Local path:** `C:\Users\ivoda\Repos\direct-supply-meal`
> - **Subdomain:** https://ds-meal.dulocore.com
>
> **Do NOT edit anything outside this repo. Do NOT confuse this with DuloCore.** direct-supply-meal is a separate project. If a path is not under `/opt/direct-supply-meal/`, it is not ours.

AI-first meal-ordering prototype for senior-living facilities. FastAPI + Jinja2 + SQLite + Claude Agent SDK. Built to demonstrate Staff-level architectural judgment: agent hierarchy via Claude Agent SDK, progressive-disclosure docs, frontend/backend decoupling, and a Karpathy-style self-improving agent memory. Deploys as a standalone container at `ds-meal.dulocore.com`.

## Fan-out

- Topic router: [docs/INDEX.md](docs/INDEX.md)
- Feature + protocol status table: [docs/CATALOG.md](docs/CATALOG.md)

## Task Depth Evaluation

Every agentic entry point (Menu Planner, NL Ordering) classifies the user's request through the 6-dimension scorer before dispatching:

- Implementation: `agents/depth_scorer.py`
- Architecture: [docs/systems/task-depth/TASK-DEPTH-ARCHITECTURE.md](docs/systems/task-depth/TASK-DEPTH-ARCHITECTURE.md)

Dimensions: Scope, Info Density, Reasoning, Verification, Consistency, Domain Breadth (0–2 each). Totals map to a dispatch plan (shallow / moderate / deep / very-deep / exhaustive / strategic).

## The Two-Horizon Rule

Every feature ships a working Phase 1 and names the exact Phase 2 graduation seam — if we can't name the seam, we didn't build it right.

## Hard Rule: No Coupling to DuloCore

direct-supply-meal is a **separate repository** (`seoninja13/direct-supply-meal`) with its own container, SQLite DB, env file, Clerk tenant, and Anthropic API key. The only physical overlap with DuloCore is the shared Traefik ingress and the `root_default` Docker network — that is routing, not coupling. Under no circumstances does this codebase read DuloCore's env, mount DuloCore's volumes, share DuloCore's credentials, or import DuloCore code.

## Quick Links

| Topic | Document |
|---|---|
| Business plan | [docs/business/BUSINESS-PLAN-ARCHITECTURE.md](docs/business/BUSINESS-PLAN-ARCHITECTURE.md) |
| Architecture principles | [docs/systems/architecture-principles/ARCHITECTURE-PRINCIPLES.md](docs/systems/architecture-principles/ARCHITECTURE-PRINCIPLES.md) |
| Domain workflow | [docs/workflows/DOMAIN-WORKFLOW.md](docs/workflows/DOMAIN-WORKFLOW.md) |
| Agent workflow | [docs/workflows/AGENT-WORKFLOW.md](docs/workflows/AGENT-WORKFLOW.md) |
| Karpathy Auto-Research loop | [docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md](docs/workflows/KARPATHY-AUTO-RESEARCH-WORKFLOW.md) |
| Protocol application matrix | [docs/workflows/PROTOCOL-APPLICATION-MATRIX.md](docs/workflows/PROTOCOL-APPLICATION-MATRIX.md) |
| Catalog (status table) | [docs/CATALOG.md](docs/CATALOG.md) |

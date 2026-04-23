# ds-meal — Demo Walkthrough Script

> Cold-read narrative for a live demo to a technical reviewer. ~5 minutes end-to-end. Read top-to-bottom; everything you need is here.

## Elevator Pitch

**ds-meal** is an AI-first meal-ordering prototype for senior-living facilities — skilled nursing, assisted living, memory care — that source prepared meals from a central commissary. Phase 1 is a working single-tenant demo that pairs a deterministic FastAPI backend with two agentic workflows (NL Ordering, Menu Planner) built on the **Claude Agent SDK**. The point is not the meals; the point is showing Staff-level judgment about where LLMs belong, where they don't, and how clean architecture, Clerk auth, observability, and a Karpathy self-compiling wiki seam fit together without making a mess of the ledger.

## Architecture at a Glance

```
+-----------+      +---------+      +--------------------------+
|  Browser  | ---> | Traefik | ---> |  FastAPI (ds-meal:8000)  |
+-----------+      +---------+      +------------+-------------+
                                                 |
             +-----------------+------------+----+-----+-----------------+
             |                 |            |          |                 |
             v                 v            v          v                 v
       +-----------+   +-------------+  +-------+  +-------+   +-------------------+
       |  SQLite   |   | Claude      |  | MCP   |  | Clerk |   | Observability     |
       | (ds-meal) |   | Agent SDK   |  | srv   |  | (auth)|   | JSONL + SQLite    |
       +-----------+   +-------------+  +-------+  +-------+   +-------------------+
```

In-process MCP server hosts the `@tool` functions. Routes never touch the DB directly — they call `@tool` functions (ATOMIC-S Route Rule).

## Pre-Flight Checklist

Run these BEFORE the call starts.

```bash
curl -s https://ds-meal.dulocore.com/health
# expect: {"status":"ok"}
```

- Confirm demo browser is **signed in as 1buildermedia@gmail.com**.

```bash
ssh root@72.60.112.205 "docker ps --filter name=ds-meal"
# expect: ds-meal container Up, (healthy)
```

```bash
ssh root@72.60.112.205 "docker exec ds-meal ls /home/appuser/.claude/.credentials.json"
# expect: path prints (Claude Max OAuth mounted read-only)
```

## Live Walkthrough

### Step 1 — Landing
Open `https://ds-meal.dulocore.com/`. Hero copy + two CTAs: **Browse recipes** and **Sign in**.

### Step 2 — Recipe Catalog (public)
Click **Browse recipes**. Land on `/recipes` — a 10-recipe catalog grid, no auth required.

> **Architectural callout:** Notice this is server-rendered Jinja, zero JavaScript build step — but every HTML route has a REST twin at `/api/v1/...`. Frontend/backend are cleanly decoupled; Phase 2 can swap Jinja for React with zero backend change.

### Step 3 — Recipe Detail
Click **Overnight Oats**. Detail page shows: texture **1/4**, **4 servings**, **$2.80/serving**, allergens **dairy + gluten**.

### Step 4 — Ingredient Scaling
Click **Ingredients (4 servings)** → ingredient table renders. Then navigate to:

```
https://ds-meal.dulocore.com/recipes/3/ingredients?servings=50
```

Scale factor **12.50×** applied, total mass **19,875 g**. Deterministic math — no LLM involved in scaling.

### Step 5 — Sign In
Click **Sign in**. Clerk bounces you to Google OAuth, then back to `/facility/dashboard`.

> **Architectural callout:** Auth uses a 1-hour **HS256 app-session token we mint ourselves** — we don't store the Clerk JWT in the cookie, because Clerk sessions expire in 60 seconds. Phase 1 is allowlist-only keyed on `admin_email`.

### Step 6 — Facility Dashboard
Land on `/facility/dashboard`. Four active-order tiles: **Pending / Confirmed / In Preparation / Out For Delivery**. Next-delivery banner shows **#102 on 2026-04-22**. 4-row upcoming table below.

### Step 7 — Order Detail
Click order **#102**. Detail page with 5-stage progress bar: **Pending → Confirmed → Preparing → Out → Delivered**. Line items + timeline render below.

### Step 8 — Calendar View
Navigate to:

```
https://ds-meal.dulocore.com/calendar?year=2026&month=4
```

April grid with 5 delivery dots on **Apr 16, 22, 23, 24, 25**.

### Step 9 — Natural-Language Order
Navigate to `/orders/new`. In the textarea, type:

> **"25 Turkey Meatloaf for Thursday dinner"**

Click **Preview**. The SDK returns within ~10 s:

```json
{ "recipe": "Turkey Meatloaf", "servings": 25, "date": "2026-04-24", "window": "evening 4–6", "total": 120.00 }
```

Click **Confirm** → redirect to the new `/orders/{id}`.

> **Architectural callout:** The LLM is calling **four MCP tools in sequence** — `resolve_recipe`, `scale_recipe`, `check_inventory`, `schedule_order`. Routes never touch the DB directly. That's our ATOMIC-S **Route Rule**.

### Step 10 — Observability Trace
In a second terminal:

```bash
ssh root@72.60.112.205 "docker exec ds-meal tail -3 /app/logs/agent_trace.jsonl"
```

Show the agent-trace row with the `tool_calls_json` field populated.

> **Architectural callout:** Every agent turn writes an observability trace. Phase 2 feeds these into a **Karpathy self-compiling wiki** — cross-session learning, no human curation in the hot path.

## Fallback Recovery

| Symptom | What to do / say |
|---|---|
| OAuth redirect fails | Run `curl -I https://ds-meal.dulocore.com/health`. Say: "Infrastructure is healthy — this is a Clerk dev-tier edge case; production would use a custom subdomain." |
| NL Preview takes >15s | Tail `docker logs ds-meal -f` in a second terminal and narrate the tool calls as they stream. |
| Confirm doesn't redirect | Run `sqlite3 /opt/direct-supply-meal/data/ds-meal.db 'SELECT id FROM "order" ORDER BY id DESC LIMIT 1;'` — proves the order was created even if the UI missed the redirect. |
| Session expired mid-demo | "Let me just hit `/sign-in/callback` and mint a fresh cookie." |

## What You Won't See (Honest Deferrals)

- **Meal Planner UI** — driver is stubbed, lands in Phase 2.
- **Live order-status transitions** — orders are pre-seeded at various statuses; real dispatcher is Phase 2.
- **Karpathy wiki auto-compile** — observability writes traces, but the compile loop is scaffolded-not-live; Phase 2.

## Expected Questions + 1-Line Answers

**Q: Why SQLite?**
A: Phase 1 single-tenant demo, zero external dependencies. Phase 2 swaps to Postgres/Supabase via env-var change — see `app/db/database.py` graduation seam.

**Q: How does the agent know "Thursday" is 2026-04-24?**
A: Haiku reasons from "today" (passed implicitly via the tool call's execution context) + calendar math. The SDK prompt doesn't hardcode it.

**Q: What if I type ambiguous text?**
A: The agent falls through to a disambiguation response (top-3 recipe candidates). Phase 1 is happy-path biased; edge cases tracked in Linear 1BU-1398.

**Q: How do you prevent OAuth-credit abuse?**
A: Currently allowlist-only (Clerk + facility `admin_email` match). Phase 2 adds rate limiting — Linear 1BU-1405.

**Q: Where's the observability?**
A: `/opt/direct-supply-meal/logs/agent_trace.jsonl` + the `agent_trace` SQLite table. Every turn: tool calls + outcome + latency. Cost + confidence are Phase-2 seams.

**Q: How does this scale to N facilities?**
A: `Facility` rows are multi-tenant-ready today (admin_email allowlist keyed). Phase 2 adds `require_role()` + RBAC — see `app/auth/dependencies.py` graduation seam.

**Q: How much code is this?**
A: ~5 k lines of `app/`/`services/`/`agents/`, ~2.2 k lines of tests, ~3 k lines of docs. ~10 k total.

## Post-Demo Follow-Ups

- **Linear project** `ds-meal` in the 1builder workspace — epic **1BU-1386** plus 21 issues.
- **GitHub:** https://github.com/seoninja13/direct-supply-meal
- **Phase 2 roadmap:** `docs/PHASE-2-ROADMAP.md` — 22 graduation items, each with a named code seam.

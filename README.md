# direct-supply-meal

**Repo location:** `https://github.com/seoninja13/direct-supply-meal`
**VPS path:** `/opt/direct-supply-meal/`
**Local path:** `C:\Users\ivoda\Repos\direct-supply-meal`
**Subdomain:** `ds-meal.dulocore.com`

Meal-ordering prototype for senior-living facilities. FastAPI + Jinja2 + SQLite + Claude Agent SDK.

**Absolutely decoupled from DuloCore** — separate repo, separate container, separate DB, separate Clerk app, separate env, own API key. The only physical overlap with any DuloCore stack is the shared Traefik TLS ingress on the VPS.

See `docs/INDEX.md` for the full doc tree. See `CLAUDE.md` for session rules.

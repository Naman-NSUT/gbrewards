# GB Rewards — Testing Plan

Layered testing strategy across the three surfaces: **backend** (FastAPI), **mobile** (Expo RN,
broker), **admin web** (React/Vite). Status markers reflect what exists today:
✅ done · ⚠️ partial · ❌ gap.

## Current test commands

| Surface | Command (from that dir) | Status |
|---|---|---|
| Backend | `uv run pytest -q --cov=app --cov-fail-under=85` (77 tests, 90% cov) | ✅ |
| Backend | `uv run ruff check . && uv run mypy app` | ✅ |
| Admin web | `npm run test` (Vitest+RTL) · `npm run build` · `npx eslint .` | ✅ |
| Admin web | `npm run e2e` (Playwright happy-path) — needs `npx playwright install` + servers | ⚠️ skeleton |
| Mobile | `npm test` (Jest+RNTL) · `npx tsc --noEmit` · `npx eslint .` | ✅ |

CI runs the backend, admin-web, and mobile checks on push/PR (`.github/workflows/*-ci.yml`).

> **Mobile platform:** Expo managed RN is cross-platform. **v1 primary target = Android**
> (mid-range broker devices, PRD P1); iOS is buildable but secondary (TECH_SPEC §2 notes an SDK-55
> iOS camera regression — verify scanning on a real Android device first). Distribution via EAS
> Build → Android APK/AAB.

---

## 1. Backend — pytest

**✅ Covered (current suite):**
- Atomic claim: concurrency (N parallel → exactly one credit), idempotency, all branches
  (invalid / void / already-claimed / own-retry).
- Ledger math (model B): balance, pending, available, total_earned, negative balance (D3).
- OTP auth: full flow, wrong/expired code, attempt cap, resend cooldown, daily cap.
- Auth `aud` separation (broker token rejected on admin, and vice-versa).
- Admin products: CRUD, counts, batch generation, PDF export, void (+ cannot_void_claimed).
- Admin users: list w/ balance+earned, detail, credit/debit, disable→broker blocked, ledger paging.
- Redemptions: holds, insufficient_balance, stacking, approve/reject/fulfill/cancel, double-approve
  conflict, concurrent creates can't over-commit.
- Returns: reverse original credit, can't reactivate active/void, re-claim reverses 2nd user,
  amount-after-price-change, negative balance allowed.
- Reporting: dashboard tiles (incl. backdated-scan exclusion), scan filters + pagination, audit
  filters.

**❌ Gaps to add:**
- `/auth/refresh` rotation + Redis denylist (rotated jti rejected); `/auth/logout`.
- `/me`, `PATCH /me` (name edit, D7), `/me/ledger` pagination (direct).
- `last_active_at` updates on authenticated access.
- `/readyz` failure path (DB/Redis unavailable).
- Parametrized cross-audience check on **every** `/admin/*` route.
- CI **coverage gate** (fail under threshold on `app/services` + `app/api`).

**Run:** `cd backend && uv run pytest -q` · lint/types: `uv run ruff check . && uv run mypy app`.

## 2. Admin web — Vitest + Playwright

- **✅ Static:** `npm run build` (tsc -b + vite build), `npx eslint .`.
- **❌ Component tests** (Vitest + React Testing Library + MSW mocking the API): Login,
  Products create/batch, UserDetail credit/debit, Redemptions actions, Returns reactivate, table
  pagination, error-envelope → AntD message.
- **❌ E2E** (Playwright, headless): login → create product → generate batch → credit user →
  approve redemption → reactivate returned unit → dashboard tiles reflect changes. Run against a
  seeded backend in CI.

## 3. Mobile — Jest + RNTL + device QA

- **✅ Static:** `npx tsc --noEmit`, `npx eslint .`, `npx expo-doctor`.
- **❌ Component/logic tests** (Jest + React Native Testing Library): OTP validation, `AuthContext`
  bootstrap/refresh/logout, `ScanResultSheet` outcome mapping, Redeem amount validation, ledger list.
- **❌ Manual device matrix (camera can't be automated):** real Android (mid + low-end) — scan
  success / already-claimed / invalid / offline-retry (never self-awards), silent re-login, full
  redeem flow. One iOS pass before any iOS release.

## 4. End-to-end scenarios (full stack, staging)

1. Onboard → scan-earn → request redemption → admin approve (debit) → fulfill.
2. Returns: scan → admin reactivate → broker balance reversed → unit re-scannable.
3. Double-spend: simultaneous scans of one QR → exactly one credit.
4. Adjustments + audit: admin credit/debit → broker history + audit trail.

## 5. Non-functional

- **Security:** JWT tamper/expiry rejection, broker↔admin isolation on all routes, OTP brute-force
  caps, RBAC, parameterized queries, secrets via env, token storage review (secure-store / cookie
  hardening in M11). Run `/security-review`.
- **Performance (NFR-PERF):** `/scan/claim` p95 < 1.5s on 4G.
- **Load (NFR-SCALE ~200 users):** k6/Locust on `/scan/claim` (hot codes) + reads; no double-credits.
- **Data integrity:** ledger append-only (no UPDATE/DELETE); periodic balance = SUM(ledger) reconcile.
- **Backups:** restore drill once managed Postgres exists (M11).

## 6. Acceptance (PRD §10 — definition of done)

Checklist suite asserting all 9 bullets: onboarding; scan credits exactly once / idempotent;
balance+history accuracy; redemption with holds; product+batch+printable sheet; dashboard totals +
user drill-down; audited credit/debit; returns reactivation reverses points; immutable audit/ledger.

## 7. CI / environments

- Local: Docker Compose (Postgres + Redis).
- GitHub Actions: backend job (ruff/mypy/alembic/pytest) **✅**; add admin-web job
  (build + eslint + Vitest + Playwright) and mobile job (tsc + eslint + Jest); E2E against an
  ephemeral seeded backend.
- Staging deploy (M11) for manual + device + load testing before prod.

## Priority order
1. Backend gaps + coverage gate (cheap, high value). ← starting here
2. Admin-web Playwright happy-path E2E.
3. Mobile component tests + Android device-QA checklist.
4. Full-stack acceptance suite (PRD §10).
5. Load/perf + security pass (with M11).

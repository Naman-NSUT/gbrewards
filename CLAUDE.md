# CLAUDE.md — Build Guide for GB Rewards

This file orients an AI coding agent (Claude Code) building this project. **Read `docs/PRD.md` and `docs/TECH_SPEC.md` first** — this file is the operating manual; those are the source of requirements and architecture.

---

## 1. What we're building

A QR-driven channel-incentive platform. Brokers scan a unique QR on each physical product via a mobile app and earn points (based on the product). Points are tracked, redeemable on request (admin-approved), and the client runs everything from a web admin panel. Returns reactivate the QR and reverse points. Single-tenant, ~200 users — **right-sized, not over-engineered.**

Three deployables, one backend:
- `backend/` — FastAPI + PostgreSQL (the source of truth)
- `mobile/` — Expo React Native (brokers)
- `admin-web/` — React + Vite + Ant Design (client + staff)

---

## 2. Stack (locked decisions)

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, Uvicorn, Postgres 16, Redis 7 (OTP + rate limit).
- **QR:** `qrcode[pil]` generate, `reportlab` for printable PDF sheets.
- **OTP/SMS:** MSG91 (India, DLT-registered) — abstract behind an `OtpProvider` interface so Twilio/Firebase can swap in. *(Confirm provider — PRD decision D5.)*
- **Mobile:** Expo (managed). **Scanning = `expo-camera` `CameraView` with `onBarcodeScanned` + `barcodeScannerSettings={{ barcodeTypes: ['qr'] }}`.** Do **NOT** use `expo-barcode-scanner` (deprecated since SDK 51). Token storage via `expo-secure-store`; React Navigation; TanStack Query.
- **Admin web:** React + Vite + TS + Ant Design; TanStack Query + Axios; `html5-qrcode` for in-browser return scanning.
- **Auth:** JWT access+refresh, separate `aud` for `broker` vs `admin`; passwords argon2id.

> Pin a known-good Expo SDK and verify QR scanning on a **real Android device** in milestone M4 before building further (a SDK-55 iOS scanning regression exists upstream — keep `react-native-vision-camera` as fallback).

---

## 3. Non-negotiable invariants

These are correctness requirements. Tests must cover each.

1. **Atomic single-scan.** A code is claimed at most once per active period. Implement via conditional update `UPDATE product_units SET status='claimed', claimed_by_user_id=:u, claimed_at=now() WHERE id=:id AND status='active' RETURNING id;` inside one transaction. 0 rows = lost the race → re-read and branch. (See TECH_SPEC §5.)
2. **Server-authoritative points.** The app never self-awards. Points only via the backend claim.
3. **Append-only ledger.** `ledger_entries` is never UPDATEd/DELETEd. Corrections = new compensating rows.
4. **Returns reverse in-transaction.** Reactivation writes `return_reversal` in the same transaction as the `claimed → active` flip.
5. **Redemption holds.** Pending requests reduce *available* balance; approve → `redemption_debit`; reject → release. No double-spend.
6. **Idempotent scan.** Same user re-scanning their own claimed code returns the original result, not a new credit.
7. **Unguessable QR tokens** (UUIDv4 in `product_units.token`); DB is the validity authority.
8. **Audit everything admin.** Every `/admin/*` mutation writes `audit_logs`.
9. **Auth domain separation.** Enforce `aud` on every route; broker tokens can't reach `/admin/*`.

---

## 4. Build order (milestones)

Build backend-first; each milestone is independently testable.

**M0 — Scaffold.** Monorepo per TECH_SPEC §11. Backend app skeleton, Postgres + Alembic, settings via Pydantic, health route, Dockerfile, CI lint/test.

**M1 — Data model + migrations.** All tables (admins, users, products, product_units, qr_batches, ledger_entries, redemption_requests, audit_logs) + indexes. Balance/available helpers (TECH_SPEC §3.2). Unit tests for balance math.

**M2 — Broker auth (OTP).** `OtpProvider` interface + MSG91 impl + a `FakeOtpProvider` for tests/dev. `/auth/otp/request`, `/auth/otp/verify`, refresh. Rate limiting + OTP TTL/attempts in Redis. JWT issuance with `aud=broker`.

**M3 — The claim + ledger.** `/scan/claim` with the atomic conditional update, idempotency, all branches (invalid/void/already-claimed/own-retry). `/me`, `/me/ledger`. **Concurrency test:** fire N parallel claims on one code → exactly one credit.

**M4 — Mobile app (broker).** Expo app: OTP onboarding screens, scanner (`expo-camera`), success/already-claimed/error states, balance + history, profile. Wire to backend. **Verify scanning on a real device.** ≤4 primary screens (Scan, Balance/History, Redeem, Profile).

**M5 — Admin auth + product/QR management.** `/admin/auth/*`. Product CRUD. Batch generation (`/admin/products/{id}/batches`) creating N `active` units. Printable export (`/admin/batches/{id}/export`) as PDF/PNG sheet (each QR labeled with product/batch). Void unit.

**M6 — Admin web shell + products/QR screens.** Vite+AntD app, login, layout/nav, products list+editor, batch generator + "download printable sheet", unit lookup.

**M7 — Points adjustments + users.** `/admin/users*`, credit/debit endpoints (write ledger + audit). Admin users screen with per-user ledger drill-down.

**M8 — Redemptions.** Broker `/redemptions` (create with availability check, list). Admin queue + approve/reject/fulfill. Hold/release logic. Broker redemption screen + status. Admin redemption queue screen.

**M9 — Returns/reactivation.** `/admin/units/{id}/reactivate` (flip + `return_reversal` in one tx; handle negative balance per D3). Admin Returns screen: token search **and** `html5-qrcode` webcam scan.

**M10 — Dashboard + audit + scans feed.** `/admin/dashboard`, `/admin/scans`, `/admin/audit` + their screens (summary tiles, filterable scan feed, audit trail).

**M11 — Hardening & deploy.** Sentry, structured logs, backups, env separation (dev/staging/prod), rate-limit review, EAS build for mobile, deploy backend + admin. Run the full acceptance checklist (PRD §10).

---

## 5. Conventions

- **Backend:** routers in `app/api/v1/`, business logic in `app/services/` (keep routers thin), SQLAlchemy models in `app/models/`, Pydantic in `app/schemas/`. All money/points logic lives in `services/ledger.py` and `services/claim.py` — single source of truth. Type-hint everything; `ruff` + `mypy`. One Alembic migration per schema change.
- **Errors:** uniform `{ "error": { "code, message, details } }`. Use the documented error codes (`invalid_code`, `already_claimed`, `code_void`, `insufficient_balance`, ...).
- **Frontend (both):** TanStack Query for all server state (no ad-hoc fetch-in-effect). Co-locate API calls in `src/api/`. TypeScript strict. Keep the mobile app minimal and fast.
- **Tests:** backend pytest. Mandatory tests: claim concurrency/idempotency, balance & availability math, redemption hold/release, return reversal, auth `aud` enforcement.
- **Secrets:** env only, never committed. Keys: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `MSG91_*` (or `FIREBASE_*`), `QR_HMAC_SECRET` (if HMAC tokens used).

---

## 6. Run / dev commands (target)

```bash
# Backend
cd backend && uv sync   # or: pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Admin web
cd admin-web && npm install && npm run dev   # VITE_API_BASE_URL=http://localhost:8000

# Mobile
cd mobile && npm install && npx expo start    # set API_BASE_URL in app config
```

Use `FakeOtpProvider` + a seeded admin in dev so flows are testable without live SMS.

---

## 7. Open product decisions (see PRD §9 — confirm before/at relevant milestone)

D1 user cap (~200) · **D2** reverse points on return (default yes) · **D3** allow negative balance on reversal (default yes, flag admin) · **D4** broker self-register vs whitelist (default self-register) · **D5** OTP provider (MSG91) · **D6** product-level points only · **D7** name editable · **D8** push notifications (optional) · **D9** add `fulfilled` redemption state (default yes).

Pick the **ledger hold model** (TECH_SPEC §3.3): spec defaults to **model B** (availability = balance − pending). Keep whichever is chosen consistent everywhere.

---

## 8. Definition of done

All of PRD §10 acceptance criteria pass, the invariants in §3 here are covered by tests, and all three apps are deployed to at least staging with the dev/seed path working end-to-end.

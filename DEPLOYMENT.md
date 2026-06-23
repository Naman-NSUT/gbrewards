# GB Rewards — Deployment Runbook

Stack: **backend + Postgres + Redis on Render**, **admin web on Vercel**, **mobile via EAS**.
Everything is env-driven; staging vs prod is just different values. The backend **refuses to boot**
outside `dev` until `JWT_SECRET` (≥32 chars), `CORS_ORIGINS`, and (in prod) a real `OTP_PROVIDER`
are set — fail-fast by design.

---

## 0. Prerequisites (operator)
- Render, Vercel, and Expo (EAS) accounts; this repo connected to each.
- **MSG91** account with **DLT-registered** sender ID + OTP template (TRAI requirement, India).
  This has lead time — start early. Until approved, run **staging** with `OTP_PROVIDER=fake`.
- (Optional) Sentry project(s) → DSNs. A custom domain for the admin web.

## 1. Backend → Render
1. Dashboard → **New → Blueprint** → select this repo. `render.yaml` provisions: the API
   (Docker, from `backend/Dockerfile`), **Postgres 16**, and a **Key Value (Redis)** instance.
2. Set the `sync:false` secrets on the `gbrewards-api` service:
   - `CORS_ORIGINS` = your admin web origin, e.g. `https://admin.yourdomain.com`
   - `MSG91_AUTH_KEY`, `MSG91_SENDER_ID`, `MSG91_TEMPLATE_ID`
   - `SENTRY_DSN` (optional)
   `JWT_SECRET` is auto-generated; `DATABASE_URL`/`REDIS_URL` are wired from the managed resources.
3. Deploy. Migrations run automatically (`alembic upgrade head` in the Docker entrypoint).
4. **Upgrade the Postgres plan** for daily backups / PITR (balances are money-adjacent).
5. Create the first admin via the service **Shell**:
   `python -m app.scripts.create_admin you@example.com 'a-strong-password' "Owner" owner`
6. Smoke: `GET https://<api>/api/v1/healthz` → `{"status":"ok"}`, and `/api/v1/readyz` → DB+Redis ok.

> Staging: a second Render env/service with `ENV=staging` and `OTP_PROVIDER=fake` lets you test the
> full flow (read codes via the `dev`-only endpoint is off in staging — use a real MSG91 test number
> or keep staging on fake and read from logs). Prod must use `msg91`.

## 2. Admin web → Vercel
1. Import the repo, root directory `admin-web` (`vercel.json` sets framework=vite, SPA rewrites).
2. Env vars: `VITE_API_BASE_URL=https://<your-render-api>` and optional `VITE_SENTRY_DSN`.
3. Deploy → log in with the admin you created.

## 3. Mobile → EAS
1. `cd mobile && npx eas login && npx eas build:configure` (project already has `eas.json`).
2. Set the API URL in `eas.json` profiles (`preview`/`production` → `env.API_BASE_URL`) and
   `SENTRY_DSN` if used.
3. Build: `eas build -p android --profile preview` (internal **APK**) or `--profile production`
   (**AAB** for Play Store). Distribute the APK link or submit with `eas submit`.

## Environment variables (backend)
| Var | Required | Notes |
|---|---|---|
| `ENV` | yes | `dev` \| `staging` \| `prod` |
| `DATABASE_URL` | yes | managed Postgres (psycopg URL) |
| `REDIS_URL` | yes | OTP + rate limiting |
| `JWT_SECRET` | yes (prod) | ≥32 chars, non-default |
| `CORS_ORIGINS` | yes (non-dev) | comma-separated admin origins |
| `OTP_PROVIDER` | yes | `msg91` in prod; `fake` only dev/staging |
| `MSG91_*` | prod | DLT-registered |
| `SCAN_RATE_PER_MIN` | no | default 30 |
| `SENTRY_DSN` | no | enables error monitoring |

## Acceptance checklist (PRD §10) — verify on staging before prod
- [ ] Broker onboards with phone+name+OTP and reaches the scanner.
- [ ] Fresh code credits correct points exactly once; re-scan is idempotent; other user → already_claimed.
- [ ] Balance & history reflect credits, debits, redemptions, reversals.
- [ ] Broker requests redemption; admin approve/reject; balances update with holds.
- [ ] Admin creates product, generates a QR batch, downloads the printable sheet (incl. multi-product order).
- [ ] Dashboard tiles + charts accurate; drill into a user's ledger.
- [ ] Admin credit/debit any user with an audited note.
- [ ] Admin reactivates a returned code (token search or webcam), reversing points.
- [ ] Every admin action + point movement appears in the immutable audit/ledger trail.
- [ ] Admin can change their own email/password (Account page).

## Post-deploy smoke
`/api/v1/healthz` · `/api/v1/readyz` · admin login on the web · create product → generate QR order →
download PDF · one mobile scan crediting points.

## Known follow-ups (not blockers)
- Admin token is in `localStorage`; consider httpOnly cookies for extra XSS hardening.
- Add Sentry release/sourcemap upload to CI for symbolicated stack traces.
- iOS build/submission (Android is the v1 target).

# Deployment Guide — GB Rewards

This is the practical "what accounts do I need, where do I put my card, and how do I ship it" guide for the three deployables in this repo:

| Part | What it is | Where it runs |
|------|-----------|---------------|
| `backend/` | FastAPI + Postgres + Redis (source of truth) | Render (recommended) or Railway / Fly.io / a VPS |
| `admin-web/` | React + Vite static site (client + staff panel) | Vercel / Netlify / Render Static (recommended) |
| `mobile/` | Expo React Native app (brokers) | EAS Build → Google Play (Android) |

Plus one optional external dependency:
- **Sentry** — error monitoring for backend + mobile (optional but wired in).

Plus one SMS dependency for login:
- **2Factor.in** — sends the login OTP over SMS (India, DLT-registered).

> **Login is OTP-based.** Brokers enter phone + name + address, receive a 6-digit code over SMS (via 2Factor), and verify it to sign in. The phone number is the identity; the account is created/refreshed on the request step and marked verified once the code is confirmed. The backend generates and stores the code; 2Factor only delivers it.

> The repo already assumes some of these. `mobile/eas.json` points the production build at `https://your-backend.onrender.com`, so **Render is the path of least resistance for the backend** — change that URL once you have your real backend domain.

---

## 0. TL;DR — accounts you need and where the card goes

| Service | Account for | Card / billing needed? | Rough cost |
|---------|-------------|------------------------|------------|
| **Render** | Host backend + Postgres + Redis | **Yes — add card** to leave free tier (free tier sleeps + tiny DB) | ~$7 web + $7 Postgres + $10 Redis ≈ **$20–25/mo** |
| **Vercel** or **Netlify** | Host admin-web static site | Free tier is fine for ~200 users; card only if you exceed it | **$0** (Hobby/free) |
| **Expo (EAS)** | Build the Android app | Free tier gives limited builds; **card for the Production plan** if you build a lot | $0, or **$99/mo** for heavy build usage |
| **Google Play Console** | Publish the Android app | **Yes — one-time $25** registration fee (card/GPay) | **$25 one-time** |
| **Sentry** | Error tracking | Free tier is enough to start; card only to scale | **$0** to start |
| **Domain registrar** (optional) | Custom domain (e.g. `admin.gbrewards.in`) | **Yes** for the domain purchase | ~₹800–1500/yr |

**Minimum to go live:** Render (card) + Google Play ($25) + a **2Factor.in** account with SMS credits and a DLT-approved `OTP1` template (for login OTP). Vercel/Netlify and Sentry can stay free.

---

## 1. Backend — Render (recommended)

The backend is a standard Docker image (`backend/Dockerfile`) that runs Alembic migrations then Uvicorn on port 8000.

### Accounts / billing
1. Create an account at **render.com**.
2. **Add a payment card** under *Account Settings → Billing*. You need this to run a non-sleeping web service and a persistent Postgres/Redis (the free tiers sleep and are size-capped — fine for a demo, not for production).

### What to create on Render
1. **PostgreSQL** (Render → New → Postgres). Pick the smallest paid instance. Copy its **Internal Connection String**.
   - ⚠️ Render gives you a `postgresql://...` URL. This app uses the psycopg3 driver, so change the scheme to **`postgresql+psycopg://...`** in `DATABASE_URL`.
2. **Redis / Key Value** (Render → New → Key Value). Copy its Internal URL → `REDIS_URL`. Used for OTP storage + rate limiting.
3. **Web Service** (Render → New → Web Service):
   - Connect this Git repo, set **Root Directory = `backend`**.
   - Runtime = **Docker** (it auto-detects the Dockerfile).
   - The Dockerfile's `CMD` already runs `alembic upgrade head` on boot, so migrations apply automatically on each deploy.
   - Health check path: `/health` (or whatever the health route is — see `backend/app/main.py`).

### Environment variables to set on the backend service
From `backend/app/core/config.py`, set these (in Render → your service → Environment):

```
ENV=prod
DATABASE_URL=postgresql+psycopg://<user>:<pass>@<host>/<db>   # note the +psycopg
REDIS_URL=redis://<host>:6379/0
JWT_SECRET=<generate a strong random string, >= 32 chars>     # e.g. `openssl rand -hex 32`
CORS_ORIGINS=https://admin.yourdomain.com                     # admin-web's URL, comma-separated
OTP_PROVIDER=twofactor                                        # `fake` (logs the code) only in dev/staging
TWOFACTOR_API_KEY=<from the 2Factor.in dashboard>
TWOFACTOR_TEMPLATE_NAME=OTP1                                   # DLT-approved template
SENTRY_DSN=<from Sentry, optional>
LOG_LEVEL=INFO
```

> The app **refuses to boot in prod** (`assert_production_ready()`) if `JWT_SECRET` is default/weak, `CORS_ORIGINS` is empty, `OTP_PROVIDER=fake`, or `twofactor` is selected without `TWOFACTOR_API_KEY`. Set those correctly or it will crash-loop.

### First-run: seed an admin
Migrations run automatically, but you need at least one admin login. Use the Render **Shell** tab (or a one-off job) to run the repo's admin-seed command (any `seed`/CLI script under `backend/`). Do this once.

### Alternatives to Render
- **Railway** — very similar flow (Postgres + Redis + Docker service as add-ons), card required to leave trial.
- **Fly.io** — cheap, Docker-native, but more manual (`fly.toml`, volumes); card required.
- **VPS (Hetzner/DigitalOcean) + Docker Compose** — cheapest at scale, most ops work (you manage Postgres backups, TLS, etc.).
- **Vercel** is *not* ideal for this backend (long-lived Redis rate-limiting + always-on migrations fit a container host better).

---

## 2. Admin web — Vercel or Netlify (static)

`admin-web/` is a Vite React SPA. Build output is static files, so any static host works and the **free tier covers ~200 users easily**.

### Vercel
1. Account at **vercel.com** (free "Hobby" plan — **no card needed** for this size).
2. New Project → import this repo → set **Root Directory = `admin-web`**.
3. Framework preset: **Vite**. Build command `npm run build`, output dir `dist`.
4. Environment variable:
   ```
   VITE_API_BASE_URL=https://<your-backend>.onrender.com
   ```
5. Because it's an SPA with client-side routing, add a rewrite so deep links work — create `admin-web/vercel.json`:
   ```json
   { "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }] }
   ```

### Netlify (equivalent)
Same idea: base directory `admin-web`, build `npm run build`, publish `dist`, add a `_redirects` file with `/*  /index.html  200`, and set `VITE_API_BASE_URL`.

> After the admin URL is live, put it into the backend's `CORS_ORIGINS`.

---

## 3. Mobile app — Expo EAS → Google Play

`mobile/` is an Expo managed app. It builds in the cloud with **EAS Build** and publishes to the **Google Play Store**. Config lives in `mobile/app.config.ts` and `mobile/eas.json`.

Key facts from the repo:
- Android package: **`com.gbrewards.app`**
- Expo owner: **`naman04`**, EAS project id already set in `app.config.ts`.
- Production profile in `eas.json` builds an **AAB** (`app-bundle`) for the Play Store and points `API_BASE_URL` at `https://your-backend.onrender.com` — **update this to your real backend URL.**

### Accounts / billing
1. **Expo account** (expo.dev) — must be the `naman04` owner (or transfer the project). Free tier gives a limited number of cloud builds per month; **the $99/mo Production plan** is only needed if you build frequently. Card is added on expo.dev → Billing.
2. **Google Play Console** (play.google.com/console) — **one-time $25 registration fee**, paid by card/GPay. Required to publish any Android app. Create the app entry with package `com.gbrewards.app`.

### Build & submit steps
```bash
cd mobile
npm install
npm install -g eas-cli
eas login                    # as naman04
# set production backend URL first: edit eas.json -> build.production.env.API_BASE_URL

eas build --profile production --platform android    # produces an .aab in the cloud
eas submit --profile production --platform android   # uploads to Play Console
```
For `eas submit` you'll create a **Google Play service-account JSON key** (Play Console → Setup → API access) so EAS can upload on your behalf.

### Notes
- The `local`/`preview` profiles in `eas.json` build APKs and currently point at a temporary `trycloudflare.com` tunnel — those are dev/testing only. Production must use your real **HTTPS** backend (release APKs block cleartext HTTP).
- iOS is not configured. To ship iOS later you'd add an **Apple Developer Program** membership (**$99/yr**, card required) and an iOS build profile.

---

## 4. Login — OTP via 2Factor.in

Broker login is **OTP-based**:
1. The app posts phone + name + address to `POST /api/v1/auth/otp/request`. The backend creates/refreshes the user (phone number = identity), generates a 6-digit code (hashed in Redis), and sends it via 2Factor's DLT-approved `OTP1` template.
2. The app posts phone + code to `POST /api/v1/auth/otp/verify`; on success the user is marked verified and receives JWT access/refresh tokens.

**Provision:** create a [2Factor.in](https://2factor.in) account, complete **DLT registration** (sender ID + `OTP1` template) with your telecom operator, buy SMS credits, and copy the **API key** into `TWOFACTOR_API_KEY`. Validate the key without spending a credit:

```bash
curl https://2factor.in/API/V1/<key>/BAL/SMS      # -> {"Status":"Success","Details":"<credits>"}
```

In dev/staging keep `OTP_PROVIDER=fake` (no SMS; the code is written to the server log as `fake_otp_send phone=... code=...`).

---

## 5. Sentry — error monitoring (optional)

Wired into both backend (`SENTRY_DSN`) and mobile (`@sentry/react-native`).
1. Account at **sentry.io** — **free tier is enough** to start; card only if you exceed the quota.
2. Create two projects: one **Python/FastAPI**, one **React Native**.
3. Backend: set `SENTRY_DSN` env var on Render.
4. Mobile: set `SENTRY_DSN` in the EAS build env (note `eas.json` currently sets `SENTRY_DISABLE_AUTO_UPLOAD=true`; configure a Sentry auth token if you want source maps uploaded).

---

## 6. Custom domains (optional but recommended)

Buy a domain from any registrar (GoDaddy, Namecheap, Cloudflare, BigRock for `.in`) — **card required** for the purchase (~₹800–1500/yr).

Suggested setup:
- `api.gbrewards.in` → backend (add as a custom domain in Render; it issues TLS automatically).
- `admin.gbrewards.in` → admin-web (add in Vercel/Netlify; automatic TLS).

Then update:
- Mobile `eas.json` → `API_BASE_URL=https://api.gbrewards.in`
- Admin `VITE_API_BASE_URL=https://api.gbrewards.in`
- Backend `CORS_ORIGINS=https://admin.gbrewards.in`

---

## 7. Recommended go-live order

1. **Render**: create Postgres + Redis + web service, set all env vars, deploy backend. Verify `/health` and seed an admin.
2. **Vercel/Netlify**: deploy admin-web with `VITE_API_BASE_URL` → backend. Log in as the seeded admin. Add its URL to backend `CORS_ORIGINS`.
3. **Google Play + EAS**: register Play Console ($25), set prod `API_BASE_URL`, `eas build`, `eas submit`.
4. **Sentry + domains**: optional hardening once the core flow works.

## 8. Where money is actually spent (summary)

- **Must add a card / pay to launch:** Render (backend hosting), Google Play (one-time $25).
- **Free to start, card only to scale:** Vercel/Netlify (admin web), Expo EAS (unless heavy builds), Sentry.
- **Optional recurring:** custom domain (~₹1k/yr), Apple Developer ($99/yr, only if iOS), Expo Production ($99/mo, only if you build often).

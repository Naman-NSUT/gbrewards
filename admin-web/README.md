# GB Rewards — Admin Web

React + Vite + TypeScript + **Ant Design** admin panel for the client + staff. Talks to the
backend `/api/v1/admin/*` API. Covers dashboard, products/QR (create/edit, batch generate +
printable **PDF**, void), users (ledger drill-down, credit/debit, enable/disable), redemption queue
(approve/reject/fulfill), returns (token search **+ webcam scan** → reactivate), scans feed, and
audit trail.

- **Stack:** Ant Design, TanStack Query + Axios, React Router v6, `html5-qrcode` (webcam returns).
- **Auth:** admin email/password → JWT (`aud=admin`); access+refresh in `localStorage` with an
  axios refresh-on-401 interceptor. (Hardening — httpOnly cookies / shorter TTLs — is an M11 item.)

## Run (dev)

```bash
# 1. Backend running and reachable:
#    cd ../backend && docker compose up -d (from repo root) && uv run uvicorn app.main:app
#    Seed an admin + data:
#      uv run python -m app.scripts.create_admin admin@example.com adminpass123 Ops owner
#      uv run python -m app.scripts.seed_dev 10

cd admin-web
npm install
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8000
npm run dev                   # http://localhost:5173
```

## Static checks (CI-friendly)

```bash
npm run build      # tsc -b + vite build (production); catches type/import/route errors
npx eslint .
```

## Manual verification (browser)

With the backend running and an admin seeded:
1. **Login** with the seeded admin → lands on the Dashboard (tiles reflect counts).
2. **Products & QR**: create a product → "Generate batch" (downloads a printable PDF sheet) →
   "Details" shows unit counts and lets you void an active unit.
3. **Users**: open a broker → view ledger, credit/debit points, toggle active.
4. **Redemptions**: filter Pending → approve / reject; filter Approved → mark fulfilled.
5. **Returns**: paste a *claimed* unit's token (or "Scan with webcam") → Look up → Reactivate
   (reverses the points; unit returns to active).
6. **Scans** / **Audit**: filter by product/entity and date range; page through results.

## Layout

`src/api` (axios client + per-resource calls) · `src/auth` (token store, `AuthContext`,
`ProtectedRoute`) · `src/hooks` (TanStack Query) · `src/layout` (`AppLayout` sider+header) ·
`src/pages` (Login, Dashboard, Products, Users, Redemptions, Returns, Scans, Audit) · `src/lib`
(formatters, blob download).

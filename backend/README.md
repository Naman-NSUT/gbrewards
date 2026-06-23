# GB Rewards — Backend

FastAPI + PostgreSQL + Redis backend for the QR rewards platform. Covers broker
OTP auth, the atomic scan-claim, and the append-only points ledger (milestones
M0–M3). See `../PRD.md` and `../TECH_SPEC.md` for the full spec.

## Local development

```bash
# From the repo root: start Postgres 16 + Redis 7
docker compose up -d

cd backend
uv sync
cp .env.example .env            # OTP_PROVIDER=fake — no SMS needed in dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

> If host port 5432 is taken, the compose file maps Postgres to **5433**; set
> `DATABASE_URL=...@localhost:5433/...` in `.env` to match.

### Seed dev data

```bash
uv run python -m app.scripts.seed_dev 5   # prints an admin + active unit tokens
```

### Exercise the broker flow (fake OTP)

```bash
BASE=http://localhost:8000/api/v1
curl -X POST $BASE/auth/otp/request -H 'content-type: application/json' \
  -d '{"phone":"+919900000001","name":"Broker"}'
curl $BASE/_dev/otp/+919900000001                 # dev-only: read the fake code
curl -X POST $BASE/auth/otp/verify -H 'content-type: application/json' \
  -d '{"phone":"+919900000001","code":"<code>"}'   # -> access_token
curl -X POST $BASE/scan/claim -H "authorization: Bearer <token>" \
  -H 'content-type: application/json' -d '{"token":"<unit_token>"}'
curl $BASE/me        -H "authorization: Bearer <token>"
curl $BASE/me/ledger -H "authorization: Bearer <token>"
```

## Quality gates

```bash
uv run ruff check .       # lint
uv run ruff format .      # format
uv run mypy app           # types (strict)
uv run pytest -q          # tests (claim concurrency/idempotency, balance, auth aud, OTP)
```

### Admin (M5)

```bash
uv run python -m app.scripts.create_admin admin@example.com adminpass123 Ops owner
ADMIN=http://localhost:8000/api/v1/admin
TOK=$(curl -s -X POST $ADMIN/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"adminpass123"}' | jq -r .access_token)
curl -X POST $ADMIN/products -H "authorization: Bearer $TOK" -H 'content-type: application/json' \
  -d '{"name":"SKU-A","points_value":120}'
curl -X POST $ADMIN/products/<pid>/batches -H "authorization: Bearer $TOK" \
  -H 'content-type: application/json' -d '{"quantity":50,"label":"Jun 2026"}'
curl "$ADMIN/batches/<bid>/export?format=pdf" -H "authorization: Bearer $TOK" -o sheet.pdf
```

## Key modules

- `app/services/claim.py` — the atomic conditional-update claim (TECH_SPEC §5).
- `app/services/ledger.py` — balance/available/pending + append-only entries (model B).
- `app/services/qr.py` — QR batch generation + reportlab PDF sheet (FR-P2/P3).
- `app/services/audit.py` — audit row on every admin mutation.
- `app/core/security.py` — argon2 hashing + JWT; `aud=broker` vs `aud=admin` separation.
- `app/api/v1/admin/` — admin auth, products/batches/export, unit lookup/void.
- `alembic/versions/0001_initial_schema.py` — all 8 tables + indexes.

# GB Rewards


## Dealer Rewards

The same physical QR, a second programme. Factory workers scan a mattress during
assembly and earn points (worker app + `admin-web`). Dealers scan the *same* QR
at point of sale, register the customer's 5-year warranty, and earn points for
doing it (`dealer-mobile` + `dealer-admin`), while customers look their warranty
up and raise claims on `support-web`.

| Directory | What |
|---|---|
| `backend/` | one FastAPI app serving both programmes |
| `admin-web/` | worker back office |
| `dealer-admin/` | dealer back office |
| `mobile/` | worker app (Expo) |
| `dealer-mobile/` | dealer app (Expo) |
| `support-web/` | public customer warranty lookup + claims |

Start here: [docs/dealer/ARCHITECTURE.md](docs/dealer/ARCHITECTURE.md), then
[docs/dealer/DECISIONS.md](docs/dealer/DECISIONS.md).

```bash
docker compose up -d
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd dealer-admin && npm install && npm run dev
cd support-web  && npm install && npm run dev
cd dealer-mobile && npm install && npx expo start
```

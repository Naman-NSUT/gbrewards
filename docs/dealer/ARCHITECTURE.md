# Dealer Rewards inside the GB Rewards monorepo

Two programmes, one backend, one database, one QR on the mattress.

```
                    ┌──────────────── one FastAPI app ────────────────┐
 worker app ───────▶│ /api/v1/scan  /me  /catalog   (aud=broker)      │
 (mobile/)          │ /api/v1/admin                 (aud=admin)       │
                    │                                                 │
 dealer app ───────▶│ /api/v1/dealer                (aud=dealer)      │──▶ Postgres
 (dealer-mobile/)   │ /api/v1/dealer-admin          (aud=admin)       │
                    │ /api/v1/public                (no auth)         │
 support site ─────▶│                                                 │
 (support-web/)     └─────────────────────────────────────────────────┘
```

| Directory | What it is | Who signs in |
|---|---|---|
| `backend/` | one API, both programmes | — |
| `admin-web/` | worker back office (unchanged) | `admins` |
| `dealer-admin/` | dealer back office | `admins` (same table) |
| `mobile/` | factory worker app (unchanged) | `users` |
| `dealer-mobile/` | dealer app | `dealer_staff` |
| `support-web/` | public customer site | nobody |

## The physical unit is shared; nothing else is

`products` and `product_units` are created by the worker admin when it generates
a QR batch. **The dealer side only ever reads them.** Nothing under
`app/dealer/` inserts or updates a product_unit, and the allocation upload
rejects a serial that has no unit row rather than inventing one.

This is why the dealer side has no unit table of its own. An earlier design —
when the two were going to be separate services — kept a local mirror with a
read-through and a staleness tolerance. Sharing a database deleted all of it;
what survived is the `UnitSource` interface, which is what made deleting it a
one-file change.

### `claimed` means two different things — never conflate them

`product_units.status = 'claimed'` means **a factory worker scanned it during
assembly**. It happens months before the mattress reaches a shop and says
nothing about whether it has been sold. Whether a unit is sold is
`warranties.status`, a different column in a different table. Reading the worker
status as a sale status would make every correctly assembled mattress look
already sold.

## Table naming

Dealer tables that would have collided carry a `dealer_` prefix:
`dealer_ledger_entries`, `dealer_rewards`, `dealer_redemptions`,
`dealer_point_rates`. Tables with no worker counterpart keep plain names:
`dealers`, `dealer_staff`, `allocations`, `warranties`, `warranty_events`,
`customers`, `claims`, `sms_messages`, `idempotency_keys`.

`admins` and `audit_logs` are **shared on purpose**. One back-office login works
in both panels, and one audit trail answers "who changed this" across the whole
business. `audit_logs` gained a richer actor model (`actor_type`, `actor_id`,
`reason`, `ip`); every pre-existing row defaults to `actor_type='admin'`, which
is exactly what it was.

## Points are per product, in both programmes

| | Worker | Dealer |
|---|---|---|
| Column | `products.points_value` | `dealer_point_rates.points_per_registration` |
| Set in | worker admin | dealer admin |
| Earned for | scanning during assembly | registering the sale |
| Versioned | no | yes — old rows keep their rate |

Two numbers for the same product on purpose: what a worker earns for assembling
a mattress and what a dealer earns for recording its sale are different
economics and must move independently.

A product with no dealer rate still registers — it just earns nothing. Recording
the sale is the product; the points are the incentive. Blocking a registration
over a missing admin setting would break the thing the system exists to do.

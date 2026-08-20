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

## Allocation does not gate registration

Any dealer registered on the app may scan any manufactured label. Allocations are
optional planning data now — uploading them still populates the compliance
denominator, but nothing refuses a registration for their absence.

The consequence to hold in mind when reading `services/registration.py`: the only
things that can refuse a scan are "no such label", "label voided" and "already
registered". See DECISIONS.md §9 for what that costs.

## Nothing is shared

The two programmes share the repository, the FastAPI process and the Postgres
instance. They share no tables.

| Concern | Worker | Dealer |
|---|---|---|
| Back office accounts | `admins` | `dealer_admins` |
| Token audience | `admin` | `dealer_admin` |
| Product catalogue | `products` | `dealer_products` |
| Unit registry | `product_units` | `dealer_units` |
| QR batches | `qr_batches` | `dealer_qr_batches` |
| Points ledger | `ledger_entries` | `dealer_ledger_entries` |
| Rewards | `rewards` | `dealer_rewards` |
| Audit trail | `audit_logs` | `dealer_audit_logs` |

There is **no foreign key from any dealer table into any worker table**, and no
sync between them. Migration 0008 is purely additive: it creates new tables and
does not alter a single existing column.

### Two QR labels per mattress

This is the consequence to internalise. The factory prints a label carrying a
`product_units.token`; the dealer panel prints a second label carrying a
`dealer_units.token`. **The two serials are unrelated and neither can be derived
from the other.**

- The worker app only scans factory labels.
- The dealer app only scans dealer labels.
- Nothing in the system can answer "which factory unit is this dealer unit?"

If that link is ever needed — say, to reconcile warranty claims against
production batches — it has to be added deliberately as a mapping table. It does
not exist today by design.

### `dealer_units.status` is not a sale status

It is `active` or `void` only. Void means the label was scrapped or a print run
went missing, and a voided label cannot be registered — that is what stops "we
lost 200 labels" from becoming 200 payable registrations. Whether a unit has been
**sold** is `warranties.status`, in a different table.

## Table naming

Dealer tables that would have collided carry a `dealer_` prefix:
`dealer_ledger_entries`, `dealer_rewards`, `dealer_redemptions`,
`dealer_point_rates`. Tables with no worker counterpart keep plain names:
`dealers`, `dealer_staff`, `allocations`, `warranties`, `warranty_events`,
`customers`, `claims`, `sms_messages`, `idempotency_keys`.

Nothing is shared, including `admins` and `audit_logs`. A person who works on
both programmes holds two logins, and each programme has its own audit trail.
The panels are served from one origin with different storage keys, so both
sessions coexist in the browser: after signing into each once, the switch button
is instant.

## Points are per product, in both programmes

| | Worker | Dealer |
|---|---|---|
| Column | `products.points_value` | `dealer_point_rates.points_per_registration` |
| Product | `products` | `dealer_products` |
| Set in | worker admin | dealer admin |
| Earned for | scanning during assembly | registering the sale |
| Versioned | no | yes — old rows keep their rate |

Two numbers for the same product on purpose: what a worker earns for assembling
a mattress and what a dealer earns for recording its sale are different
economics and must move independently.

A product with no dealer rate still registers — it just earns nothing. Recording
the sale is the product; the points are the incentive. Blocking a registration
over a missing admin setting would break the thing the system exists to do.

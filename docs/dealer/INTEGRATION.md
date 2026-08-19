# Unit integration — superseded

This document used to specify a cross-service contract: an internal read
endpoint on GB Rewards (`GET /api/v1/internal/units/{serial}`), a service token,
a local mirror with a staleness tolerance, and a reconciliation queue for units
the mirror had not seen.

**None of that is needed any more, and none of it was built.** Dealer Rewards
now lives in this repository, on the same backend and the same database, so the
dealer side reads `product_units` directly. There is no endpoint for the worker
team to add, no service token to issue, no mirror to keep fresh, and no
staleness window to reason about.

What remains of the old design is the `UnitSource` interface in
`backend/app/dealer/services/unitsource/` — kept because it is the seam that
made this simplification a one-file change, and the same seam that would make
splitting the services apart again cheap if that ever becomes necessary.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for how units are actually read, and
why `product_units.status = 'claimed'` must never be read as "sold".

One thing from the original investigation still matters and is still true:

> The QR encodes a **bare UUIDv4** — `services/qr.py` hands `unit.token`
> straight to `qrcode.make`, and prints the same value in Courier beneath the
> code so a scuffed label can be typed in by hand. There is no signature and no
> URL. `normalise_serial()` still strips a URL down to its last path segment,
> because that is the one format change that would silently break every scanner
> and it costs two lines to be immune to it.

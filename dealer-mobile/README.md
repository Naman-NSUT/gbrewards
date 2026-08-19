# GoodBed Dealer (mobile)

The app a shop uses at the counter. Scan the QR on a mattress label, take the
customer's details, and the sale record exists before the customer leaves —
which is the entire point of the product. Points are the incentive, not the
feature.

Expo SDK 56 · React Native 0.85 · React Navigation 7 · TanStack Query 5 · axios.

## Running it

```bash
npm install
API_BASE_URL=http://192.168.1.20:8000 npx expo start   # LAN IP of the backend
```

`API_BASE_URL` defaults to `http://10.0.2.2:8000`, the host loopback as seen from
the Android emulator. Cleartext HTTP is enabled for Android dev builds; production
must be https.

```bash
npx tsc --noEmit     # type check
npx eslint .         # lint
```

## The one design decision that matters

A dealer is standing at a counter with a customer waiting, on shop-floor wifi.
So **nothing in the sale flow blocks on the network**:

1. The dealer taps *Register sale*.
2. `src/offline/queue.ts` mints a UUIDv4 idempotency key, freezes the exact
   request body, and writes both **to disk before any request is attempted**.
3. The confirmation screen follows that queue item, whatever happens next.

The key is reused on every retry forever. If the app is killed mid-request, the
replay carries the same key and the backend returns the ORIGINAL result rather
than creating a second warranty.

Failure handling is by meaning, not by status class:

| Outcome | Treatment |
| --- | --- |
| no response, 5xx, 429, 503 | transient — retry with jittered backoff, forever |
| 401 / `account_disabled` | transient — waits for the dealer to sign in again |
| 409 `already_registered` | **resolved**, shown as "already registered", not a failure |
| 409 `request_in_progress` | the first attempt is still running — short backoff |
| 409 `idempotency_key_reused` | permanent — only reachable via a client bug |
| other 4xx | permanent — the server's own message is kept and shown verbatim |

Every item is in exactly one visible state: the tab badge counts unsent sales,
the banner explains them, and the Sales tab lists each one with its own message
and a Fix / Try again / Discard action. **Nothing is ever dropped silently.**

Editing a rejected submission mints a *new* key (`queue.replace`) because the
backend correctly rejects a changed body under an old key. Queued items are also
stamped with the dealership they were made under and will not send while a
different dealership is signed in on the same phone — replaying them would
create a real registration, and pay points, under the wrong shop.

## Layout

```
src/api/         axios client (typed error envelope, refresh-on-401) + endpoints
src/auth/        secure-store tokens + session, AuthProvider
src/offline/     queue.ts (durable submissions), net.ts (connectivity), useQueue
src/components/  Button, TextField, StatusPill, ScanResultSheet, EmptyState,
                 OfflineBanner, ScreenBackground, AppLogo
src/screens/     Phone, Otp, Scan, CustomerDetails, Confirmation,
                 Registrations, Points, Rewards, Profile
src/navigation/  Root → Auth stack | Main stack (Tabs, CustomerDetails, Confirmation)
```

The theme in `src/theme.ts` is the GoodBed brand palette, identical to the
GB Rewards worker app: navy `#184860`, cyan `#0090D8`, page `#EEF4F8`.

## Backend endpoints this app calls

Live today:

- `POST /api/v1/auth/otp/request` · `POST /auth/otp/verify` · `POST /auth/refresh` · `POST /auth/logout`
- `GET  /api/v1/dealer/units/{serial}/preview`
- `POST /api/v1/dealer/registrations` (requires `Idempotency-Key`)
- `GET  /api/v1/dealer/registrations`
- `GET  /api/v1/dealer/points`

Expected but not yet implemented server-side (see the handover notes):

- `GET  /api/v1/dealer/ledger?limit&offset`
- `GET  /api/v1/dealer/rewards`
- `GET  /api/v1/dealer/redemptions` · `POST /dealer/redemptions` · `POST /dealer/redemptions/{id}/cancel`

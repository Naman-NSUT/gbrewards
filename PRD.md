# Product Requirements Document — QR Rewards & Loyalty Platform

**Working name:** GB Rewards
**Doc owner:** Nonu
**Status:** Draft v1 — for build kickoff
**Audience:** Engineering (Claude Code), client stakeholder

---

## 1. Overview

A QR-driven loyalty / channel-incentive platform. The client ships physical products that each carry a **unique QR code**. Distribution partners ("brokers") scan a product's QR with a mobile app and are credited **points** based on the product type. Points accumulate per user and can be redeemed by raising a request that the client (admin) approves. The client operates everything from a web **admin panel**.

This is a **channel-incentive / broker-commission model**, not a consumer promo: a finite, known set of partners move product and earn points for doing so.

### 1.1 The two surfaces
| Surface | Users | Purpose |
|---|---|---|
| **Mobile app** | Brokers (~200 max) | Scan QR → earn points, view balance/history, request redemption |
| **Admin panel** (web) | Client + staff | Manage products & QR batches, track scans, credit/debit points, handle returns, approve redemptions |

---

## 2. Goals & success metrics

| Goal | Metric |
|---|---|
| Reliable point attribution on scan | 100% of valid scans credited exactly once; 0 double-credits |
| Fraud resistance | A QR can never be claimed twice while in a claimed state; tokens are unguessable |
| Operational control for client | Admin can adjust any balance and audit every point movement |
| Low-friction broker onboarding | Phone + name + OTP only; first scan possible within 2 minutes of install |
| Returns handled correctly | Returned product's QR can be reactivated and its points reversed |

---

## 3. Scope

### 3.1 In scope (v1)
- Broker mobile app: OTP onboarding, QR scan-to-earn, balance & transaction history, redemption requests.
- Admin web panel: dashboard, product CRUD, QR batch generation + printable export, scan/usage tracking, per-user point credit/debit, returns/reactivation, redemption approval queue, full audit trail.
- Backend API + database powering both surfaces.

### 3.2 Out of scope (v1) — noted for later
- Automated payout / cash disbursement on redemption (v1 = manual fulfillment by client after approval).
- Tiered point rules, multipliers, expiry, or promotions/campaigns.
- In-app chat / notifications beyond transactional push (push is optional v1).
- Multi-tenant (multiple independent clients) — v1 is single-tenant.
- Geofencing / location capture on scan.

---

## 4. Personas

**P1 — Broker (mobile user).** Field/distribution partner. Low patience for friction, variable network quality, mid-range Android device is the common case. Wants: scan fast, see my points, get paid.

**P2 — Client Admin (web).** Owns the incentive program. Wants: full visibility of who scanned what, ability to correct balances, control over redemptions and returns. May have 1–3 staff operators.

---

## 5. Functional requirements

IDs are referenced by the tech spec and build plan.

### 5.1 Mobile app — onboarding & auth
- **FR-A1** User signs up / logs in with **name + phone number only**.
- **FR-A2** Phone number is verified via **OTP** (SMS). No password.
- **FR-A3** OTP has a short expiry and limited verification attempts; resend is rate-limited (see NFR-SEC).
- **FR-A4** On successful verification the user gets a session token; subsequent app opens are silent (no re-login) until the token expires or logout.
- **FR-A5** Returning users are identified by phone number; name is captured once at first signup (editable later — *decision D7*).

### 5.2 Mobile app — scan to earn
- **FR-S1** Primary screen is a **scanner**. Tapping/opening it activates the camera and detects QR codes.
- **FR-S2** On detecting a valid, **unclaimed** code, the system credits the product's point value to the user and shows a clear success state (product name + points earned + new balance).
- **FR-S3** If the code is **already claimed**, show "already scanned" with the date it was claimed; award nothing.
- **FR-S4** If the code is **unknown / invalid / tampered**, show an explicit error; award nothing.
- **FR-S5** If the code was previously claimed **by this same user** (e.g. a network retry), the result is **idempotent** — show the original success, do not double-credit.
- **FR-S6** Scanning requires connectivity (the claim is server-authoritative). On no network, show a retry state; never grant points client-side.

### 5.3 Mobile app — balance & history
- **FR-B1** User can view their **current point balance** prominently.
- **FR-B2** User can view a **transaction history**: each scan credit (with product + points + time), each redemption (status), and any admin adjustment, newest first.
- **FR-B3** History entries are labeled by type (earned / redeemed / adjusted / reversed).

### 5.4 Mobile app — redemption
- **FR-R1** User can submit a **redemption request** for some/all of their points.
- **FR-R2** A request cannot exceed the available (non-pending) balance.
- **FR-R3** Submitting a request moves the requested points into a **pending** state so they can't be double-requested.
- **FR-R4** User sees request status: **pending / approved / rejected** and history of past requests.
- **FR-R5** On admin approval, points are debited; on rejection, the held points return to available balance.

### 5.5 Admin — dashboard & tracking
- **FR-D1** Dashboard with summary tiles: total users, total points outstanding (liability), total scans, scans today/this week, pending redemptions, products in catalog.
- **FR-D2** **Users screen**: list all users with name, phone, current balance, total earned, last activity; drill into a single user's full ledger.
- **FR-D3** **Scans / usage screen**: list of all scan events filterable by product, user, and date range; shows which user scanned which unit when.
- **FR-D4** **Products screen**: list products with their point value and counts (units generated / claimed / available / returned).

### 5.6 Admin — product & QR management
- **FR-P1** Admin can **create/edit a product**: name, description, **point value**, active flag.
- **FR-P2** Admin can **generate a batch of N QR codes** for a product. Each code is a unique, unguessable token tied to that product, created in `active` state.
- **FR-P3** Admin can **export a generated batch as a printable sheet** (PDF/PNG) for the client to print and affix to physical products. Export must let the client map each printed QR back to its product/batch.
- **FR-P4** Admin can look up any single code by its token/ID and see its full state and history.
- **FR-P5** Admin can **void** a code (e.g. misprint) so it can never be claimed.

### 5.7 Admin — point adjustments
- **FR-AD1** Admin can **credit** points to any user with a reason/note.
- **FR-AD2** Admin can **debit** points from any user with a reason/note.
- **FR-AD3** Every adjustment is recorded in the ledger and the audit log with the acting admin, timestamp, amount, and note.

### 5.8 Admin — returns / reactivation
- **FR-RT1** When a product is returned, admin can **reactivate its code** (move from `claimed` back to `active` so it becomes scannable again).
- **FR-RT2** Reactivation **reverses the points** that were credited for that scan (a reversing ledger entry against the original scanner) — *default behavior, decision D2*.
- **FR-RT3** Admin reactivates either by **searching the token** or by **scanning the QR via the browser webcam** (convenience).
- **FR-RT4** Reactivation is logged in the audit trail.

### 5.9 Admin — redemption queue
- **FR-RQ1** Admin sees a **queue of pending redemption requests** (user, points, requested-at).
- **FR-RQ2** Admin can **approve** (debits the held points, marks fulfilled-pending or done) or **reject** (releases the hold) with an optional note.
- **FR-RQ3** Approved/rejected requests move to a history view.

### 5.10 Admin — accounts
- **FR-AC1** Admin authenticates with email + password (separate from broker OTP auth).
- **FR-AC2** (Optional v1.1) Multiple admin/staff accounts with a simple role flag (owner vs operator).

---

## 6. Core business rules (authoritative)

1. **One claim per code.** A code in `claimed` state cannot be claimed again. Only a return/reactivation (or void→reactivate) changes that.
2. **Points come from the product.** Scanning a code credits the *current* point value of its product. (Optional per-unit override — *decision D6*.)
3. **Server is the source of truth.** Points are only granted by the backend after an atomic claim. The app never self-awards.
4. **Append-only ledger.** Balances are derived from an immutable transaction log; nothing is edited or deleted, only reversed/adjusted with new entries.
5. **Redemption holds.** Requested points are held (unavailable) until the request is approved (debited) or rejected (released).
6. **Returns reverse points.** Reactivating a returned code reverses its original credit by default.
7. **Everything administrative is audited.** Credits, debits, reactivations, voids, and redemption decisions record who/when/why.

---

## 7. Key user flows

### 7.1 Broker onboarding
1. Install app → enter **name + phone** → request OTP.
2. Receive SMS OTP → enter → verified → account created → session issued.
3. Land on scanner screen.

### 7.2 Scan-to-earn
1. Open scanner → point camera at product QR.
2. App reads token → sends claim request to backend.
3. Backend validates + **atomically claims** the code → writes a `scan_credit` ledger entry.
4. App shows success: product, points earned, updated balance.
5. (Edge) Already-claimed / invalid / same-user-retry handled per FR-S3..S6.

### 7.3 Redemption
1. User taps Redeem → enters amount (≤ available) → submit.
2. Points moved to **pending**; request appears in admin queue.
3. Admin approves → points **debited**, request **approved**; or rejects → hold **released**.
4. User sees updated status and balance. Fulfillment (payout) handled by client out-of-band in v1.

### 7.4 Return / reactivation
1. Product comes back → admin opens Returns → searches token **or** scans QR via webcam.
2. Admin confirms reactivation.
3. Code → `active`; a `return_reversal` ledger entry debits the original scanner.
4. Code is now scannable again.

---

## 8. Non-functional requirements

- **NFR-SCALE.** Target ~**200 total users**, low concurrency. The system is deliberately **right-sized**: a single backend service + one relational database. No microservices / orchestration overhead. Must remain correct under occasional concurrent scans of the *same* code (race-safe claim).
- **NFR-SEC.**
  - QR tokens are **unguessable** (random UUIDv4 or HMAC-signed); sequential IDs must never be the scannable value.
  - OTP: 4–6 digit code, ~5 min expiry, max ~5 verify attempts, resend cooldown (e.g. 30–60s) and per-phone/IP daily cap to control SMS cost and abuse.
  - Broker tokens stored in secure device storage; admin uses password auth with hashing (bcrypt/argon2) + JWT.
  - Role separation between broker and admin auth domains.
  - **India SMS compliance:** transactional SMS requires **DLT-registered** sender ID + templates (TRAI). Factor into OTP provider setup — *see tech spec*.
- **NFR-AUDIT.** Full, immutable audit trail of administrative actions and all point movements.
- **NFR-AVAIL.** Best-effort single-region hosting is acceptable for v1; nightly DB backups required (point balances are financial-adjacent).
- **NFR-UX.** Mobile app must be minimal: scanner is the home screen; ≤4 primary screens (Scan, Balance/History, Redeem, Profile).
- **NFR-PERF.** Scan claim round-trip should feel instant on 4G (target <1.5s server processing + network).

---

## 9. Open decisions (confirm with client)

| # | Decision | Default proposed |
|---|---|---|
| **D1** | Max user base — confirm "~200" | Build for ~200, no hard cap; architecture scales to low-thousands without redesign |
| **D2** | On return, reverse the awarded points? | **Yes**, auto-reverse (creates a debit) |
| **D3** | If reversal pushes a balance negative (points already redeemed), allow negative or block? | **Allow negative**, flag to admin for reconciliation |
| **D4** | Do brokers self-register, or must admin pre-approve/whitelist phone numbers? | **Self-register**; optional whitelist toggle later |
| **D5** | OTP/SMS provider | **2Factor.in** (India, DLT-registered; backend generates the code, 2Factor delivers via the approved `OTP1` template) — MSG91/Firebase as alternatives |
| **D6** | Per-unit point override, or always product-level? | **Product-level only** in v1 |
| **D7** | Can users edit their name later? | Yes, name editable in Profile |
| **D8** | Push notifications on redemption status? | Optional v1; nice-to-have |
| **D9** | Redemption "approved" = done, or a further "fulfilled/paid" status? | Add a **fulfilled** step so client can track payout separately |

---

## 10. Acceptance criteria (v1 done = all true)

- A broker can onboard with phone+name+OTP and reach the scanner.
- Scanning a fresh code credits the correct product points exactly once; re-scanning the same code is rejected/idempotent.
- Balance and history reflect all credits, debits, redemptions, and reversals.
- A broker can request redemption; admin can approve/reject; balances update correctly with holds.
- Admin can create products, generate a QR batch, and export a printable sheet.
- Admin dashboard shows accurate totals; admin can drill into any user's ledger.
- Admin can credit/debit any user with an audited note.
- Admin can reactivate a returned code (token search or webcam scan), reversing its points.
- Every administrative action and point movement appears in an immutable audit/ledger trail.

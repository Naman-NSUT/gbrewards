# Decision record

Every entry states the decision, the reasoning, the trade-off we accepted, and
how to reverse it. If a decision cannot be reversed cheaply, that is said out
loud rather than hidden.

One sentence governs all of them:

> **The sale record is the product. Points are only the incentive.**

A change that makes points nicer at the cost of the sale record being created
less often, later, or less truthfully is a bad change, however good it looks in a
demo.

---

## 1. Unit data: local mirror + read-through, with allocation as the gate

**Decision.** GB Rewards owns the physical unit — serial, model, warranty terms —
because it creates the unit at manufacturing. We keep a local **mirror** of the
units we care about (`units`), refreshed nightly, with a short live read-through
when a scan misses the mirror. Registration is authorised by the **allocation**
table, never by the mirror.

    ALLOCATION answers  "may this dealer register this serial?"
    THE MIRROR answers  "what product is this, and for how long is it covered?"

Code: `app/services/unitsource/` (`base.py` carries the full argument),
`app/services/registration.py`, `UNIT_SOURCE_MODE` in `app/core/config.py`.

**Why not the two alternatives.**

*Read their database directly.* Rejected. It couples our correctness to another
service's migrations with no contract in between: the day GB Rewards renames a
column, our point-of-sale flow breaks with no version negotiation and no warning.
It also puts two write-capable applications on one database, which makes "who
changed this row?" unanswerable.

*Call their API synchronously on every scan.* Rejected as the only mechanism. GB
Rewards runs on Render with a documented cold start — its own mobile client
raises its HTTP timeout to 60 seconds to cope. A dealer at a counter with a
customer waiting cannot be blocked on someone else's cold start, and a
registration that fails because a third party was asleep is exactly the friction
that stops dealers registering, which is the entire problem this product exists
to solve.

**The three questions that had to be answered explicitly.**

*What happens when the source is unreachable mid-sale?* Nothing the dealer sees.
The mirror answers. If the mirror also misses, the allocation still authorises
the sale: the warranty is written with `unit_unverified = true`, the model and
term fall back to `DEFAULT_WARRANTY_MONTHS`, and the record lands on the admin
reconciliation queue. The upstream call is capped at
`UNIT_SOURCE_TIMEOUT_SECONDS` (2.5s) and its failure is a log line, not an error
response. **A sale is never blocked on a third party.**

*Can a dealer register a unit the mirror has not seen?* Yes — if it is allocated
to them. Refusing would mean a mattress that shipped faster than last night's
sync cannot be sold, which teaches dealers the app is unreliable and sends them
back to paper. What a dealer cannot do is register a serial allocated to another
dealer, or to nobody: those are `not_your_unit` and `not_allocated`, both refused
outright.

*Who is authoritative when the two disagree?* GB Rewards owns unit identity.
Sync overwrites our copy of model and warranty months without argument. We own
warranty state, and sync never modifies, voids or deletes a warranty. If upstream
says a serial does not exist at all, that is a reconciliation flag for a human,
never an automatic void — a warranty already sold to a real customer is not
undone by a data mismatch. Note also that upstream's `status = 'claimed'` means
"a factory worker scanned this at assembly"; it is recorded and never read as
"sold".

**Trade-off we accepted.** The mirror can be stale, so a model name shown at the
counter can be out of date, and a warranty registered during an outage may have
the fallback term rather than the unit's real one. We chose a small,
visible, correctable inaccuracy over an unavailable point of sale. Staleness is
surfaced on `/api/v1/readyz` and bounded by `UNIT_MIRROR_STALENESS_HOURS`.

**How to reverse.** `UNIT_SOURCE_MODE` is a single environment variable with
three values and no code change: `mirror` (current design), `api` (always live,
no cache — if the client ever accepts the coupling), `none` (no upstream calls at
all; allocations alone gate registration). A different upstream entirely means
one new class implementing `UnitSource.get()` and a line in `get_unit_source()`.

**Today's setting is `none`,** because the endpoint we need does not exist yet
(see [INTEGRATION.md](INTEGRATION.md)). The system is fully functional in that
state; it simply flags more registrations for reconciliation.

---

## 2. Backdating: seven days of grace, then a human

**Decision.** The warranty clock is server-derived. A dealer may supply an
invoice date, which can pull the start date **backward** by at most
`BACKDATE_GRACE_DAYS` (7). Beyond that the warranty is created in
`pending_backdate`, holding the claimed date, and waits for an admin. A future
invoice date is ignored, silently. Points do not credit until it is approved.

Code: `app/services/warranty_dates.py`.

**Why.** Late registration is the failure this product exists to stop: the clock
starting when someone got around to it rather than when the mattress was sold. So
the dealer must not be able to type a start date freely. But a strict
server-timestamp rule punishes the shop that wrote the invoice on Saturday and
registered on Monday, and a system that punishes normal behaviour gets abandoned.
Seven days absorbs a weekend plus a public holiday while making a year-late
registration impossible to do quietly.

**Trade-off.** Seven days of drift are accepted without review, and a dealer who
learns the window can systematically claim six days. That is a bounded loss —
six days on a 1,825-day warranty — and every non-zero backdate is stored on the
warranty (`backdate_days`) and reportable, so the pattern is visible rather than
invisible. We preferred a bounded, measurable allowance to an unbounded, hidden
one.

**How to reverse.** `BACKDATE_GRACE_DAYS = 0` makes every backdate an approval.
A larger number widens the window. Neither touches stored warranties: the value
that was applied is recorded on each row.

---

## 3. Customer confirmation: notify, do not gate

**Decision.** By default the customer is **notified** by SMS when their warranty
is registered; they are not asked to confirm anything, and the warranty is
`active` immediately. `REQUIRE_CUSTOMER_CONFIRMATION = true` switches to a
confirmation flow: the warranty waits in `pending_confirmation` and **points
credit only on confirmation**.

Code: `app/services/registration.py`, `app/services/warranty.py::confirm`.

**Why not an OTP at the counter.** It costs about ninety seconds of a sale, and
it fails in exactly the situations that matter: the customer's phone is in the
car, the shop is a basement with no signal, the number was given by a spouse who
is not present. Every one of those failures ends with the dealer not registering
the sale — and a registered-but-unconfirmed sale is worth far more to GoodBed
than no record at all. The abuse an OTP would prevent (a dealer inventing sales
to farm points) is already fenced from three other directions: a dealer can only
register serials **allocated to them**, a serial can carry only **one** live
warranty, and velocity limits cap a compromised login.

**What the notification buys anyway.** The SMS gives the customer a link to their
own warranty. A wrong number is discovered by the customer's silence rather than
by a failed OTP, and a customer who did not buy the mattress finds out about the
fake registration — with a "this is not mine" path on the support site. It also
sets `is_phone_verified` when they act on the link, so "a dealer typed this
number" and "the person holding that number responded" remain distinguishable.

**Trade-off.** Without confirmation, a fake registration against a real allocated
serial is possible until someone notices. We judged the loss (points paid on a
mattress that was going to be sold anyway, on a serial that is now consumed)
smaller than the loss from dealers abandoning the flow. That judgement can be
revisited without a migration.

**How to reverse.** Set `REQUIRE_CUSTOMER_CONFIRMATION = true`. The status,
the events and the confirm path already exist. Existing `active` warranties are
untouched.

---

## 4. What a registration is worth: versioned rates, bootstrapped to zero

**Decision.** Points-per-registration is a **row with an effective window**
(`point_rates`), not a config constant. Exactly one rate is current, enforced by
a partial unique index. Every ledger entry records the `rate_version_id` that
produced it. A fresh install bootstraps a rate of **0**.

Code: `app/services/ledger.py::set_rate`, `app/db/bootstrap.py`.

**Why zero.** The client has not decided what a registration is worth. A guessed
default becomes the real number the moment the first dealer registers, and
un-paying it afterwards is a clawback conversation with a business partner. Zero
means registrations are recorded correctly from day one — which is the actual
product — while the economics wait for a decision that is the client's to make.
The first dealer-visible screen says "points pending programme launch" rather
than a fabricated number.

**Why versioned.** The client will change the rate after launch. A constant would
silently rewrite the meaning of history: "why is this row 50 when a registration
is worth 75?" must stay answerable in a year. Versioning also lets a rate change
be scheduled and audited instead of deployed.

**Trade-off.** Registrations made at rate 0 pay nothing, permanently. That is
deliberate: retroactively paying them is a single admin credit with a reason,
which is a decision someone makes on purpose rather than an accident of ordering.

**How to reverse.** Admin → Points → set rate (`set_rate` closes the current row
and opens a new one). Backfilling earlier registrations is `admin_credit` entries
with a reason; the ledger keeps both the original and the correction.

---

## 5. Dealer accounts: a dealership, with staff beneath it

**Decision.** Two levels. `dealers` is the business; `dealer_staff` are the
humans who log in. Points accrue to the **dealership**; the staff member is
recorded on every registration for attribution. Staff are created by an admin —
there is no self-registration.

Code: `app/models/dealer.py`, `app/services/otp.py`.

**Why.** The compliance report the client opens every morning is per-shop ("this
dealer was allocated 40 units and registered 6"). The abuse investigation is
per-person ("all 34 suspicious registrations came from one phone"). One login per
shop cannot express the second; one account per person loses the first. A shop
with a single operator has exactly one staff row, so the model collapses to the
simple case at no cost.

**Why no self-registration.** Dealers are a finite set of contracted businesses
the client already has paperwork for, and every registration pays points. An open
sign-up on a paying system is an open till.

**Trade-off.** Onboarding requires an admin to create the shop and its staff. For
a few hundred dealers that is an afternoon, and it is the same afternoon in which
their allocations get uploaded.

**How to reverse.** Adding self-service staff creation is an admin-approval queue
on top of the existing model, not a schema change. Collapsing to one login per
dealer would lose per-person attribution and is not recommended.

---

## 6. Rewards catalogue: separate from the worker programme

**Decision.** Dealer Rewards has its own `rewards` and `redemptions` tables and
its own catalogue. It shares no rows with the GB Rewards worker programme.

Code: `app/models/reward.py`.

**Why.** They are different populations with different economics. A factory
worker's assembly scan and a dealer's warranty registration are not worth the
same thing, and the two point currencies are not interchangeable. A shared
catalogue means one price edit silently reprices two programmes at once, and one
stock decrement serves whoever redeems first — a worker and a dealer competing
for the same pillow. Same schema shape, separate rows, separate balances.

**Trade-off.** Two catalogues to maintain when an item genuinely appears in both.
That is a copy-paste in an admin screen, and it buys independent pricing forever.

**How to reverse.** If the client ever wants one catalogue, it becomes a shared
service with a `programme` column and per-programme pricing. That is a real
project, not a flag — which is exactly why it should not be done speculatively
now.

---

## 7. Dealer edit window: 24 hours for typos, then admin-only

**Decision.** For `DEALER_EDIT_WINDOW_HOURS` (24) after registering, a dealer may
correct the **customer's name and mobile number** on their own registration.
After that it is admin-only, with a mandatory reason. The serial, the dates and
the owning dealer can never be edited by a dealer, inside the window or out.
Every edit is audited with before and after values, and the confirmation SMS is
re-sent to the corrected number.

Code: `app/api/v1/dealer/corrections.py`.

**Why a window.** Mistyping one digit of a mobile number at a busy counter is the
most likely data error in this system, and it is silently catastrophic: the
customer never gets the SMS, cannot find their warranty, and eventually
self-registers — which then reads as dealer non-compliance and penalises the
dealer for a typo. Making them wait for an admin to fix something they noticed
ten seconds later would be absurd.

**Why it closes.** After a day, an edit is no longer plausibly a typo; it is a
warranty being reassigned to a different person. That is precisely how a dealer
would launder a speculative registration into a real sale once a real buyer
appeared. Past the window it needs a human at the brand and a reason on the
record.

**Trade-off.** A genuine typo discovered on day three costs a support call. That
is the price of closing the laundering path, and the support tooling for it
exists.

**How to reverse.** `DEALER_EDIT_WINDOW_HOURS`. Zero makes every correction
admin-only; a larger number widens it. The audit trail is identical either way.

---

## 8. Returns: void, compensate, free the serial

**Decision.** A returned or cancelled sale is **voided**, never deleted. Voiding
writes a compensating **debit** to the ledger (`registration_reversal`), sets the
warranty to `voided` with a mandatory reason, writes a warranty event, and
releases the allocation back to `allocated` so the unit can legitimately be sold
again. Balances may go negative.

Code: `app/services/warranty.py::void`. The ledger is append-only, enforced by
database triggers that reject UPDATE and DELETE.

**Why compensate rather than edit.** "This dealer earned 50 points and had them
reversed" is a different fact from "this dealer never earned anything", and only
the first can be explained to a dealer who is disputing it. An editable ledger is
a ledger nobody can trust, including the client.

**Why the serial is freed.** A returned mattress goes back on the shelf and gets
sold to somebody else. If the serial stayed consumed, the second sale — a real
one, to a real customer, with a real warranty — could not be registered at all.
The partial unique index permits a new live warranty once the previous one is
voided; releasing the allocation keeps both sides consistent.

**Why negative balances are allowed.** The alternative is refusing to claw back
from a dealer who has already spent the points, which makes "register fakes,
redeem fast" a profitable strategy. A negative balance is a debt the client can
see and chase; a skipped clawback is a loss they cannot.

**Trade-off.** A dealer can see their balance go negative, which is an awkward
conversation. It is a conversation with an audit trail, a reason string, and a
timestamp — which is the best available version of that conversation.

**How to reverse.** Not a global setting, because the right answer depends on the
individual case. The admin void endpoint takes `clawback` (default `true`); send
`false` for a return that is not the dealer's fault — a manufacturing defect,
say — and the warranty is voided with the points left alone. The service also
accepts `free_serial=False`, which keeps the serial consumed for a unit that was
destroyed rather than resold; that one is not yet exposed on the API, and should
be added the first time someone actually needs it rather than speculatively.

---

## Still owned by the client, not by this codebase

| Question | Blocked on | Default until then |
|---|---|---|
| What is a registration worth? | Client decision | Rate 0 — registrations record, nothing pays |
| DLT template approval for SMS | Operator, days | `SMS_PROVIDER=fake` — every message logged, none delivered |
| GB Rewards internal unit endpoint | Their team | `UNIT_SOURCE_MODE=none` — allocations alone gate registration |
| Postgres plan with PITR | Cost approval | Daily backups on `basic-1gb` (see `render.yaml`) |

None of these blocks the others, and none of them blocks a dealer registering a
sale correctly. That was the point of sequencing them this way.


## 9. Open scanning: any registered dealer may register any label

**Decision.** Allocation does not gate registration. A dealer who is registered
on the app can scan any manufactured label and claim the points for it. Stock is
not scoped to shops.

**What this does not break.** Payout stays bounded. `uq_warranties_live_serial`
still allows exactly one live warranty per serial, so a label pays once no
matter who scans it, and total spend is capped by labels printed. Voided labels
remain unregistrable, and the per-staff and per-dealer velocity limits still
apply.

**What it costs, stated plainly.** Attribution. Registration becomes a race:
whoever scans a label first is paid, and the shop that actually sold it is then
refused with `already_registered`. A label photographed in a warehouse, in
transit, or in a competitor's showroom registers exactly as well as one sold
over a counter. This is not a hypothetical — it is the expected steady state
wherever labels are visible before the point of sale, and it is pinned by
`test_first_scanner_wins_and_the_second_is_refused`.

The defences that remain are detective, not preventive:

- the audit trail and per-warranty event history
- the customer's confirmation reply, which is the only evidence that a real buyer
  at that number actually received the mattress
- velocity limits, which are now the main thing standing between a compromised
  login and a large payout — worth tuning down from the current 60/hour/staff if
  abuse appears
- customer self-registrations, which still name a shop (see below)

**Compliance changed shape.** "Units allocated versus warranties registered" has
no denominator without allocations, so `registration_rate` is null unless the
brand happens to have uploaded allocations anyway. The ranking still works
because `non_compliance_score` is driven by customer self-registrations, which
need no allocation: a customer registering their own warranty is direct evidence
that a shop did not.

Self-registrations are attributed by asking the CUSTOMER which shop sold them the
mattress (`dealer_hint`), falling back to an allocation if one exists. That is
arguably better evidence than an allocation ever was — the buyer naming the shop
is a statement, where an allocation was a guess about where stock ended up. An
ambiguous name match attributes to nobody rather than blaming a shop by
inference.

**To reverse.** The gate was a single block in
`app/dealer/services/registration.py`; restoring it means re-adding the
allocation lookup and the two `not_allocated` / `not_your_unit` errors, and
turning the preview's reasons back on. The allocations table, its CSV upload and
its admin screens were all kept, so the data path still exists.

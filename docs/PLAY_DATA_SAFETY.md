# Google Play — Data safety & App content answers

**App:** GB Rewards · `in.gbrewards.gbrewards`
**Audited:** 31 July 2026, against the `release` variant on branch `main`
**Companion document:** [`docs/index.html`](./index.html) — the privacy policy. The two are written to
say the same thing in the same order. If you change one, change the other.

Every declaration below cites the file and line that proves it. Re-verify the citations after any
dependency bump — a new SDK can change these answers without a single line of your own code changing.

---

## Section 1 — Data safety: overview questions

| Play Console question | Answer | Evidence |
|---|---|---|
| Does your app collect or share any of the required user data types? | **Yes** | `mobile/src/api/auth.ts:15` sends `{phone, name, address}` to the backend |
| Is all of the user data collected by your app encrypted in transit? | **Yes** | Production base URL is HTTPS (`mobile/eas.json:29`); the SMS gateway call is HTTPS (`backend/app/services/otp_provider.py:43`). No HTTP endpoint exists in the release build. ⚠️ See UNRESOLVED #1 — a config flag currently *permits* cleartext even though nothing uses it |
| Do you provide a way for users to request that their data be deleted? | **Yes** | No deletion endpoint exists in code (verified: no `DELETE /me`, no admin user-delete; the only teardown is `is_active=false` at `backend/app/api/v1/admin/users.py:189`). Deletion is therefore an **off-app request process**, documented at [`docs/index.html#data-deletion`](./index.html#data-deletion) |
| Deletion request URL (App content → Data deletion) | Your published policy URL + `#data-deletion`, e.g. `{{POLICY_URL}}#data-deletion` | Play accepts a page that explains the request route; the anchor targets that section directly |
| Does your app provide in-app account deletion? | **No** | No such control exists. `ProfileScreen.tsx:95` offers sign-out only, which clears local tokens (`AuthContext.tsx:56-60`) |

---

## Section 2 — Data types

Work down the Play Console category list in order. Categories not listed below are **not selected**;
the reasoning for each exclusion is in Section 3.

### Personal info → Name

| Field | Answer |
|---|---|
| Collected | **Yes** |
| Shared | **No** |
| Processed ephemerally | **No** — persisted in `users.name` (`backend/app/models/user.py:14`) |
| Required or optional | **Required** |
| Purposes | App functionality; Account management |

**Evidence.** Entered at `mobile/src/screens/PhoneScreen.tsx:74-81`, transmitted at
`mobile/src/api/auth.ts:15`, stored at `backend/app/api/v1/auth.py:55`. Editable later at
`mobile/src/api/me.ts:15`.
**Why "required":** submit is blocked when the name is empty — `PhoneScreen.tsx:35-38`.

### Personal info → Phone number

| Field | Answer |
|---|---|
| Collected | **Yes** |
| Shared | **No** — see the sharing note below |
| Processed ephemerally | **No** — persisted in `users.phone` (`backend/app/models/user.py:13`) |
| Required or optional | **Required** |
| Purposes | App functionality; Account management; Fraud prevention, security, and compliance |

**Evidence.** Entered at `PhoneScreen.tsx:84-92`, transmitted at `src/api/auth.ts:15,21`, stored at
`backend/app/api/v1/auth.py:55`. It is the account identity — there is no password
(`backend/app/api/v1/auth.py:76-87`).
**Why "Fraud prevention, security, and compliance":** the number carries the one-time login code, which is
Google's own listed example of this purpose (`backend/app/services/otp.py:53-58`).
**Why "Shared: No" despite the SMS gateway:** `TwoFactorProvider` transmits the number to 2Factor.in
(`backend/app/services/otp_provider.py:45-53`) solely to deliver a code we generated, on our instruction.
Under Play's definition that is a service provider processing on your behalf, not a transfer to a third
party for its own purposes. Disclosed as a recipient in the policy, section 4. **This corrects
`docs/PLAY_STORE_LISTING.md` §3, which declares this as shared — do not use that table.**

### Personal info → Address

| Field | Answer |
|---|---|
| Collected | **Yes** |
| Shared | **No** |
| Processed ephemerally | **No** — persisted in `users.address` (`backend/app/models/user.py:15`) |
| Required or optional | **Required** |
| Purposes | App functionality |

**Evidence.** Entered at `PhoneScreen.tsx:94-102`, transmitted at `src/api/auth.ts:15`, stored at
`backend/app/api/v1/auth.py:55`. Used to fulfil redemptions.
**Why "required":** submit is blocked when the address is empty — `PhoneScreen.tsx:39-42`. Note this is
unusual for a signup flow and a reviewer may query it; the answer is that redemption fulfilment needs the
outlet address. If you ever make it skippable, this flips to **Optional**.

### Personal info → User IDs

| Field | Answer |
|---|---|
| Collected | **Yes** |
| Shared | **No** |
| Processed ephemerally | **No** — it is the primary key of every rewards record |
| Required or optional | **Required** |
| Purposes | App functionality; Account management |

**Evidence.** The server mints a UUID per account (`backend/app/models/user.py` via `UUIDPkMixin`), embeds
it in the JWT subject (`backend/app/api/v1/auth.py:30-31`), the app stores that token in the Android
keystore (`mobile/src/auth/tokenStore.ts:23-26`) and transmits it on every request
(`mobile/src/api/client.ts:36-41`). Because the identifier leaves the device on each call and is persisted
server-side, it meets Play's collection test.
**Judgement call, flagged:** this is an account ID we generate, not an identifier harvested from the
device. Declaring it is the defensible reading for an account-based app; if you disagree, dropping it is
also arguable — but then drop it from the policy's section 1 table too, so the two documents stay parallel.

### App activity → App interactions

| Field | Answer |
|---|---|
| Collected | **Yes** |
| Shared | **No** |
| Processed ephemerally | **No** — the ledger is append-only and permanent by design |
| Required or optional | **Required** |
| Purposes | App functionality; Analytics |

**Evidence.** Scan claims (`mobile/src/api/scan.ts:5` → `backend/app/api/v1/scan.py:15`) write a permanent
ledger row (`backend/app/models/ledger_entry.py:13`) and stamp the product unit with the claiming user and
timestamp (`backend/app/models/product_unit.py:36-39`). Redemption requests are recorded at
`backend/app/models/redemption_request.py:33-41`.
**Why "Analytics" is included:** the admin dashboard aggregates scans per day and top products
(`backend/app/services/reporting.py:73` `analytics()`), which is a Play "Analytics" purpose even though it
is first-party operational reporting with no analytics SDK involved.
**Scope note:** the QR token transmitted at `src/api/scan.ts:5` identifies a *product unit*, not a person;
it becomes personal only once joined to your account, which is what this declaration covers.

---

## Section 3 — Categories deliberately NOT selected

Each of these is a positive finding, not an omission.

| Play category | Answer | Why |
|---|---|---|
| **Photos and videos** | Not collected | The camera decodes QR codes in-memory via `CameraView` `onBarcodeScanned` (`mobile/src/screens/ScanScreen.tsx:76-81`); only the decoded string is transmitted (`:25`). No frame is stored or sent. Not collection at all — no image data leaves the device |
| **Audio files / voice** | Not collected | `RECORD_AUDIO` is in the manifest (`AndroidManifest.xml:5`) but is injected by expo-camera's plugin default `recordAudioAndroid = true` (`node_modules/expo-camera/plugin/build/withCamera.js:8,32`). No audio API is referenced anywhere in `mobile/src/`. See COMPLIANCE_NOTES for how to drop it |
| **Location (precise or approximate)** | Not collected | No location permission in the manifest, no location API in the codebase. The login IP recorded for rate-limiting (`backend/app/services/otp.py:51`, 24h TTL) is never resolved to a location and IP is not itself a Play data type |
| **Financial info** | Not collected | Zero hits for `upi\|bank\|account_number\|ifsc\|card\|payment\|razorpay\|stripe` across `backend/app`. `redemption_requests` holds only an integer point count (`backend/app/models/redemption_request.py:36`) |
| **Health and fitness** | Not collected | No such data anywhere |
| **Messages, Contacts, Calendar** | Not collected | No permissions, no APIs |
| **Files and docs** | Not collected | `READ/WRITE_EXTERNAL_STORAGE` (`AndroidManifest.xml:4,8`, capped at API 32) come from transitive expo manifests. No filesystem API is used in `mobile/src/` |
| **Web browsing history** | Not collected | No WebView, no browser, no `Linking` usage anywhere in `mobile/src/` |
| **App info and performance → Crash logs / Diagnostics** | **Not collected** | `@sentry/react-native` is installed but inert in release: its own manifest sets `io.sentry.auto-init = false`, and the JS init at `mobile/App.tsx:16-19` is gated on a DSN that the production EAS profile never sets (`app.config.ts:17`, `eas.json:24-31`). Confirmed by you that no EAS secret supplies one. **This corrects `docs/PLAY_STORE_LISTING.md` §3, which declares crash logs collected** |
| **Device or other IDs** | Not collected | No `AD_ID` permission anywhere in the app or any dependency manifest (`grep -rl AD_ID node_modules --include=AndroidManifest.xml` → no hits). No `installationId`, `androidId`, or `deviceId` read in `mobile/src/`. No Firebase, no GMS, no `google-services.json` |
| **Anything under "Shared"** | Nothing is shared | The only onward transfers are 2Factor.in (SMS delivery) and Render (hosting) — both processors acting on instruction, neither using the data for its own purposes |

---

## Section 4 — App content declarations

| Declaration | Answer | One-line justification |
|---|---|---|
| **Privacy policy URL** | `{{POLICY_URL}}` | Publish `docs/index.html` via GitHub Pages (Settings → Pages → branch `main`, folder `/docs`). ⚠️ See UNRESOLVED #2 — a second, conflicting policy already exists in this repo |
| **Ads — does your app contain ads?** | **No** | The home carousel renders first-party promotional rows fetched from your own backend (`mobile/src/components/BannerCarousel.tsx:26` → `/catalog/banners`), with images stored in your own database (`backend/app/models/banner.py:19`). No ad network exists in the dependency tree |
| **Advertising ID — does your app use one?** | **No** | No `com.google.android.gms.permission.AD_ID` in the app manifest or any dependency manifest; no Play Services dependency at all |
| **Data collected or shared for advertising or marketing** | **No** | Follows from the two rows above |
| **App access — is any functionality restricted?** | **Yes — all functionality is behind a login.** You must provide reviewer instructions | Nothing is reachable signed-out: `RootNavigator` gates the whole tree on auth state, and every data route requires a bearer token (`backend/app/core/deps.py:43-56`). ⚠️ **Login is SMS-OTP only and there is no bypass** — `assert_production_ready()` forbids the fake OTP provider in production (`backend/app/core/config.py:58-59`). A Google reviewer cannot receive your SMS. See UNRESOLVED #3 — this will block review if unaddressed |
| **Target audience** | **18 and over only** | The app is for authorised dealers and channel partners; nothing in it is directed at or appealing to children. Consistent with policy section 9. Selecting 18+ keeps you out of the Families policy programme entirely |
| **Appeal to children** | **No** | Business utility app: scan, balance, redeem, info |
| **Financial features** | **None** | No payment, lending, or crypto functionality; no financial data field exists (see Section 3). ⚠️ Your store listing draft says points redeem for "vouchers, cash, or goodies" — if any cash payout happens, it happens off-app and outside this build, but consider rewording to avoid a reviewer query |
| **Health apps** | **No** | No health functionality or data |
| **Government apps** | **No** | Private commercial rewards program |
| **News apps** | **No** | — |
| **COVID-19 contact tracing / status** | **No** | — |
| **Content rating questionnaire** | Answer as a **Business / Utility** app | No violence, no user-generated content shown to other users, no gambling, no in-app purchases. Expected rating: Everyone / 3+ |
| **Data deletion** | Request-based, via the URL in Section 1 | No in-app deletion control exists in the code |

---

## UNRESOLVED — answer these before you submit

**1. Cleartext traffic is enabled in the release manifest.**
`android:usesCleartextTraffic="true"` sits in the *main* manifest (`mobile/android/app/src/main/AndroidManifest.xml:18`),
put there by `expo-build-properties` (`mobile/app.config.ts:33-38`) — whose own comment claims release
builds block cleartext. They do not, with this set. Today the declaration "encrypted in transit: Yes" is
still **true**, because the production build only ever calls HTTPS URLs (`eas.json:29`). But nothing in
the build prevents a plain-HTTP call from being added later, at which point that answer silently becomes
false.
**Question for you:** may I move this flag to the development-only path so the release build enforces
HTTPS at the OS level? That is an app-code change, so I have not made it. See COMPLIANCE_NOTES §"Changes
that would let you declare less".

**2. There are now two privacy policies in this repo, and they disagree.**
`admin-web/public/privacy-policy.html` (last updated 16 July 2026) declares crash/diagnostics collection
and lists Sentry as a recipient — neither is true of the published build. The new `docs/index.html` does
not. A reviewer who finds both will see a contradiction.
**Question for you:** which URL goes in Play Console, and may I delete or redirect the other? I have left
it untouched under the read-only constraint.

**3. Reviewer login. This is the most likely cause of a rejection.**
Play requires working credentials for login-gated apps. Your login is SMS-OTP to a real Indian mobile
number, with no test bypass (`backend/app/core/config.py:58-59` actively forbids one in production).
**Question for you:** which do you want?
  (a) Register a phone you control, and put "email us and we will relay the code within minutes" in the
      reviewer notes — workable but slow, and reviewers sometimes reject on it;
  (b) Add a review-only account with a fixed OTP, gated to one specific phone number — the reliable
      option, but it is app-code work and a deliberate auth exception that needs careful scoping;
  (c) Something else you already have in mind.
I have not written any of it — this audit is read-only.

**4. `mobile/CLAUDE.md` and the repo docs still name MSG91 as the SMS provider.**
The shipped code calls 2Factor.in (`backend/app/services/otp_provider.py:43`). The policy and this
document name 2Factor.in, which is correct for the running system. Flagging so nobody "corrects" the
policy back to the stale doc.

**5. Free-text image URLs are a latent third-party disclosure.**
You confirmed all reward and banner images are self-hosted today, so nothing is declared. But `image_url`
is admin-supplied free text up to 1000 chars (`backend/app/schemas/admin.py:181,209`) and the app renders
it directly (`mobile/src/screens/RewardsScreen.tsx:32`, `mobile/src/components/BannerCarousel.tsx:26`).
The day someone pastes an external URL, every user's IP and user-agent reach that host on app open, and
this declaration becomes incomplete. See COMPLIANCE_NOTES for the one-line fix.

# Privacy audit — trail and reasoning

**Subject:** GB Rewards Android app, `in.gbrewards.gbrewards`, `release` variant
**Date:** 31 July 2026 · **Repo state:** branch `main` at `5786677`, working tree clean apart from `.gitignore`
**Outputs:** [`docs/index.html`](./index.html) (privacy policy) · [`docs/PLAY_DATA_SAFETY.md`](./PLAY_DATA_SAFETY.md) (Play Console answers)
**Constraint honoured:** read-only. No application code, manifest, or config was modified. The only files
written are these three docs.

---

## 1. Variant scope

The Android project has **no product flavors**. Build types are `debug`, `debugOptimized`, and `release`
(`mobile/android/app/build.gradle:110-127`). The two debug manifests add only `SYSTEM_ALERT_WINDOW` and a
cleartext override, both of which the main manifest already carries — so **the release manifest is
`mobile/android/app/src/main/AndroidManifest.xml` verbatim**, plus `ACCESS_NETWORK_STATE` merged in from
`@sentry/react-native`'s library manifest at build time.

EAS profiles differ only in `API_BASE_URL` (`mobile/eas.json`): `development` → `http://localhost:8000`,
`local` → a Cloudflare tunnel, `preview`/`production` → `https://gbrewards.onrender.com`. Only
`production` was declared against. **No divergence affects the declarations.**

Note: `mobile/android/` is gitignored (`.gitignore:35`) — it is prebuild output, regenerated from
`app.config.ts` plus installed config plugins. I audited both, and they agree. If someone changes a plugin
option, the manifest changes without any tracked file changing; that is why the citations below point at
`app.config.ts` as well as the generated manifest.

## 2. What was inspected

- **Manifests** — the release manifest, both debug manifests, and every `AndroidManifest.xml` in
  `mobile/node_modules` (swept for `AD_ID`, `<provider>` auto-init entries, and the union of all declared
  permissions).
- **Build config** — `app.config.ts`, `app.json`, `eas.json`, root and app `build.gradle`,
  `gradle.properties`, `sentry.properties`, `MainApplication.kt`.
- **All 47 TypeScript files under `mobile/src/`** plus `App.tsx` and `index.ts` — read, not just grepped.
- **Backend** — every router in `app/api/v1/`, all SQLAlchemy models, `core/config.py`, `core/deps.py`,
  `core/logging.py`, `main.py`, `services/otp.py`, `services/otp_provider.py`, `services/ratelimit.py`,
  `services/reporting.py`, `services/audit.py`, and the admin schemas.
- **Deployment** — `render.yaml`, `backend/.env.production.example`, the three CI workflows.
- **Existing docs** — `docs/PLAY_STORE_LISTING.md` and `admin-web/public/privacy-policy.html`, both of
  which contain declarations that contradict the code (see §5).

Targeted negative searches, each of which returned nothing — these are the basis for the "not collected"
answers, so re-run them after any dependency bump:

```sh
grep -rl "AD_ID" mobile/node_modules --include=AndroidManifest.xml
grep -rni "firebase\|com.google.android.gms\|admob\|appsflyer\|branch.io\|amplitude\|mixpanel" mobile/android mobile/app.config.ts
find . -name "google-services.json"
grep -rn "AsyncStorage\|MMKV\|FileSystem\|MediaLibrary" mobile/src
grep -rn "Linking\|WebBrowser\|WebView\|openURL" mobile/src
grep -rn "installationId\|androidId\|deviceId" mobile/src
grep -rni "upi\|bank\|account_number\|ifsc\|card\|payment\|razorpay\|stripe" backend/app
```

## 3. Findings that decided declarations

**Sentry is installed but inert — this is the finding that most changes the answer.** Three independent
facts, all needed: (a) `@sentry/react-native/android/src/main/AndroidManifest.xml` sets
`io.sentry.auto-init = false`, so the native SDK does not self-start; (b) the JS init at `App.tsx:16-19`
is gated on `extra.sentryDsn`, which resolves from `process.env.SENTRY_DSN ?? ''` (`app.config.ts:17`);
(c) the production EAS profile sets no `SENTRY_DSN` (`eas.json:24-31`). You confirmed no EAS project
secret supplies one, and that the backend's `SENTRY_DSN` is likewise blank. **Result: crash logs and
diagnostics are not declared.** `android/sentry.properties` is build-time source-map upload config and
carries no runtime DSN. This is the textbook "declared dependency that is never initialised collects
nothing" case, and the reason a dependency list alone would have produced a wrong declaration.

**The camera never produces collected data.** `CameraView` with `onBarcodeScanned`
(`ScanScreen.tsx:76-81`) decodes in-memory and hands back a string; only that string is transmitted
(`:25` → `src/api/scan.ts:5`). No frame is written or uploaded. This is not merely the ephemeral-processing
exemption — no image data leaves the device at all, so **Photos and videos is not collected**, full stop.

**Four permissions in the release manifest are vestigial.** `RECORD_AUDIO`, `READ_EXTERNAL_STORAGE`,
`WRITE_EXTERNAL_STORAGE`, `SYSTEM_ALERT_WINDOW`, and `VIBRATE` are all present and none is exercised by
any line of app code. They arrive from config-plugin defaults and transitive library manifests, not from
intent. They do not create a declaration obligation on their own — Play declarations follow data flow,
not permissions — but they widen your Play listing's permission display and invite reviewer questions. §6
covers removing them.

**No advertising or analytics surface exists.** No `AD_ID`, no Play Services, no `google-services.json`,
no ad or analytics SDK anywhere in the tree. The home-screen "banners" are your own promotional rows,
image bytes and all, stored in your own database (`backend/app/models/banner.py:19`) and served from your
own origin. That makes "contains ads: No" and "uses advertising ID: No" solid, not merely arguable.

**Everything the app sends goes to exactly one first-party origin.** One axios instance
(`src/api/client.ts:28-34`) pointed at `API_BASE_URL` (`src/config.ts:7`). No second HTTP client, no
WebView, no raw socket, no WorkManager job, no push registration, no OTA updates
(`expo.modules.updates.ENABLED = false`, release manifest line 17).

**Account data is required, and unusually so.** Name *and* postal address are both hard-blocked at signup
(`PhoneScreen.tsx:35-42`), not merely prompted. That is what makes them "Required" rather than "Optional"
on the form. If either becomes skippable, the declaration must flip — the form asks about the actual code
path, not the intent.

**There is no deletion path anywhere in the codebase.** I searched for it specifically rather than
assuming: no `DELETE /me`, no admin user-delete route, no cascade. The strongest available action is
`is_active = false` (`backend/app/api/v1/admin/users.py:189-208`), which retains every row including the
append-only ledger. The policy therefore documents a request-based process rather than claiming a button
that does not exist — a claim Play can and does verify.

## 4. What was deliberately excluded, and why

**IP address is not declared as Location.** The backend records the requesting IP as a rate-limit key with
a 24-hour TTL (`backend/app/services/otp.py:29-31,51`). IP address is not itself a Play data type, and it
is never resolved to a geographic location — so selecting "Approximate location" would be a false
declaration, not a cautious one. It *is* disclosed in the privacy policy (section 5), because a policy
should describe more than the form has fields for. That asymmetry is not a mismatch: there is no form
field for it to contradict.

**Language preference is not declared.** Stored locally in SecureStore (`I18nProvider.tsx:47`) and never
transmitted — no endpoint accepts it. Data that never leaves the device is not collected.

**Request logs are not declared.** The access-log line records method, path, status, and latency only
(`backend/app/main.py:50-56`) — no bodies, no headers, no identifiers. `FakeOtpProvider` does log the
phone and code (`otp_provider.py:32`), but it cannot run in production:
`assert_production_ready()` rejects `OTP_PROVIDER=fake` when `ENV=prod` (`core/config.py:58-59`), and
`render.yaml:33` pins the real provider.

**2Factor.in and Render are not declared as "sharing".** Both process on your instruction, under contract,
for the sole purpose of delivering your service — 2Factor transmits a code you generated
(`otp_provider.py:45-53`); Render runs your server. Neither uses the data for its own purposes. Under
Play's definition that is collection, not sharing. Both are named as recipients in policy section 4, which
is the right place for it. **`docs/PLAY_STORE_LISTING.md` §3 gets this wrong** and would have you declare
phone number as shared.

**User IDs is the one genuine judgement call, and it is declared.** The account UUID is minted by your
server, not harvested from the device — so "collection" is arguable in both directions. It resolves to
*declare* because the identifier demonstrably leaves the device on every request
(`src/api/client.ts:36-41`) and is persisted. Reasoning and the counter-argument are both recorded in
PLAY_DATA_SAFETY §2 so a future reviewer can revisit without re-deriving it. This is flagged rather than
silently decided precisely because it is the sort of thing that drifts between the two documents.

## 5. Existing documents that contradict the code

Both predate this audit and are **not** consistent with the shipped build. Left untouched under the
read-only constraint; both need your decision.

| File | Problem |
|---|---|
| `admin-web/public/privacy-policy.html` | Declares "Diagnostics & crash data" collected and lists **Sentry** as a recipient. Neither is true of the published build. Also lists Vercel as processing account data, which applies to the admin panel, not the app. It is a second, publicly-servable policy that disagrees with `docs/index.html` |
| `docs/PLAY_STORE_LISTING.md` §3 | Declares crash logs collected (false), declares phone number **shared** with the SMS provider (wrong category — processor, not third party), and asserts "Data deletion request = Yes (users can request deletion per the privacy policy)" without any deletion process actually existing at the time |
| `mobile/CLAUDE.md` and repo docs | Name **MSG91** as the OTP provider; the code calls **2Factor.in** (`backend/app/services/otp_provider.py:43`) |

**Recommendation:** make `docs/index.html` the single published policy, point Play Console at it, and
delete or redirect `admin-web/public/privacy-policy.html`. Supersede `PLAY_STORE_LISTING.md` §3 with
`PLAY_DATA_SAFETY.md` and leave a pointer in its place. Two live policies is a self-inflicted rejection risk.

## 6. Changes that would let you honestly declare less

Ranked by value. All are app-code changes and none has been made.

**1 — Enforce HTTPS in release builds.** `app.config.ts:33-38` sets `usesCleartextTraffic: true`
unconditionally, so it lands in the *main* manifest and applies to release (release manifest line 18),
despite the comment there claiming otherwise. Make it conditional, e.g.
`android: { usesCleartextTraffic: process.env.ALLOW_CLEARTEXT === '1' }`, and set that variable only in
the `development`/`local` EAS profiles. This turns "encrypted in transit: Yes" from *true today* into
*true by construction*, and removes the single most likely way this declaration goes stale.

**2 — Drop the microphone permission.** Pass `recordAudioAndroid: false` in the expo-camera plugin options
(`app.config.ts:22-27`); the option is real and defaults to `true`
(`node_modules/expo-camera/plugin/build/withCamera.js:8,32`). QR scanning does not use audio. Removes
`RECORD_AUDIO` from your Play listing's permission display — the permission most likely to prompt "why
does a QR scanner need my microphone?"

**3 — Drop the storage and overlay permissions.** `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, and
`SYSTEM_ALERT_WINDOW` arrive transitively and are unused. Remove them with a manifest merger rule:
`<uses-permission android:name="…" tools:node="remove" />`, via an `expo-build-properties` manifest mod or
a small config plugin. Verify against the *merged* manifest afterwards
(`android/app/build/intermediates/merged_manifests/release/AndroidManifest.xml`), not the source one —
libraries add permissions at merge time.

**4 — Constrain image URLs to your own origin.** `image_url` is admin-supplied free text
(`backend/app/schemas/admin.py:181,209`) rendered straight into `<Image source={{uri}}>`
(`RewardsScreen.tsx:32`, `BannerCarousel.tsx:26`). Validate it to a relative path or your own host. Today
this changes no declaration; it prevents a future one from becoming false silently (see §7).

**5 — Add a real deletion endpoint.** A `DELETE /me` that anonymises the user row while preserving the
append-only ledger — replace `name`/`phone`/`address` with tombstones, keep `users.id` and the ledger rows
intact — would satisfy both the audit-integrity invariant in `CLAUDE.md` §3 and Play's expectation for
account-based apps. It would let you answer **Yes** to in-app account deletion, which is the answer
reviewers prefer, instead of relying on an email process.

## 7. Code that would make a declaration false under plausible future use

Watch these. Each is a change that would silently invalidate a shipped declaration without looking like a
privacy change to whoever makes it.

| Trigger | Declaration it breaks |
|---|---|
| Setting `SENTRY_DSN` as an EAS secret, or in Render's dashboard (`render.yaml:41` leaves it `sync:false` and inviting) | "Crash logs / Diagnostics: not collected" flips to collected **and shared with a third party**. No code change required — a dashboard toggle alone does it. The backend case is worse: unhandled-exception payloads can carry request bodies containing phone, name, and address |
| Pointing any reward or banner `image_url` at an external host | Every user's IP and user-agent reach that host on app open. Adds a third-party recipient not named in the policy. With cleartext still permitted, an `http://` URL would also transmit unencrypted, breaking "encrypted in transit" |
| Adding any HTTP endpoint, or an SDK that phones home over HTTP | "Encrypted in transit: Yes" becomes false, silently — the manifest currently permits it (see §6.1) |
| Making name or address optional at signup (`PhoneScreen.tsx:35-42`) | "Required" flips to "Optional" for those elements |
| Adding push notifications, Firebase, or any analytics SDK | Introduces Device IDs, likely an `AD_ID` permission, and a genuine third-party sharing relationship — the largest single jump in declaration scope available from here |
| Adding a payout, voucher-code, or bank-detail field to redemptions | Selects **Financial info** and triggers the Play financial-features declaration, which carries its own documentation requirements |
| Storing anything in `AsyncStorage`, plain SharedPreferences, or external files | Policy section 6's "no personal details are cached on the device" becomes false |
| Enabling `expo-updates` / EAS Update (currently `ENABLED=false`, release manifest line 17) | Introduces an OTA channel that can change app behaviour after review — including its data collection — which Play treats as a policy matter in its own right |
| Regenerating `android/` after changing a config plugin | The manifest is generated output; permissions can appear or vanish with no tracked file changing. Re-run the §2 sweeps after any `expo prebuild` |

## 8. Confidence and limits

Answers rest on static reading of this working tree. I did not build the app, so I did not inspect a
**merged** release manifest (no build output exists in the tree — `find android -path "*build*" -name
AndroidManifest.xml` returns nothing). I read every library manifest in `node_modules` instead, which is
what the merger consumes, so the permission set should match — but confirm against the real merged
manifest before you submit, especially if you act on §6.3.

I could not inspect EAS project secrets or Render dashboard environment variables; both can inject a
Sentry DSN with no repo change. You confirmed neither is set, and the declarations rest on that. If that
changes, PLAY_DATA_SAFETY §3 and policy section 2 both need updating — together.

Server-side behaviour was read from source, not observed in production. Retention beyond the Redis TTLs
(OTP 300s, login IP 24h, scan rate-limit 60s, revoked refresh tokens 30 days) is governed by operational
practice rather than code — the database has no retention job, so rows persist until someone deletes
them. That is why the policy states retention in terms of account life plus a `{{RETENTION_PERIOD}}`
placeholder rather than asserting a specific window the code does not enforce.

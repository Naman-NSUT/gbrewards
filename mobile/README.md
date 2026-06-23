# GB Rewards — Mobile (Broker app)

Expo (managed, TypeScript) React Native app for brokers: OTP onboarding, scan-to-earn,
balance + history, redemption requests, and profile. Wired to the backend.

- **SDK:** Expo 56 (RN 0.85, React 19) — past the SDK-55 iOS camera regression noted in
  `../TECH_SPEC.md §2`. Scanning still **must be verified on a real device** (see below);
  `react-native-vision-camera` is the documented fallback if `expo-camera` misbehaves.
- **Stack:** `expo-camera` `CameraView`, `expo-secure-store`, React Navigation (native-stack +
  bottom-tabs), TanStack Query + Axios.

## Run (dev)

```bash
# 1. Backend must be running and reachable from your phone (same LAN).
#    From repo root:  docker compose up -d && (cd backend && uv run uvicorn app.main:app --host 0.0.0.0)
# 2. Seed scannable QR tokens:
#    cd backend && uv run python -m app.scripts.seed_dev 10   # prints unit tokens

cd mobile
npm install
# Point the app at your dev machine's LAN IP (not localhost — the phone can't reach that):
API_BASE_URL=http://<your-lan-ip>:8000 npx expo start
# Open in Expo Go (Android) or a dev build; scan the QR to load the app.
```

## Real-device scan verification (manual — required)

1. Generate a printable batch from the admin API (`POST /admin/products/{id}/batches` →
   `GET /admin/batches/{id}/export?format=pdf`) **or** use a `seed_dev` token rendered as a QR.
2. Onboard: enter name + phone → receive OTP. In dev (`ENV=dev`) read the code from
   `GET /api/v1/_dev/otp/{phone}` instead of SMS.
3. On the **Scan** tab, point at a QR and confirm:
   - fresh code → success sheet with product + points + new balance;
   - re-scan same code → "already yours" (idempotent), balance unchanged;
   - a second account scanning it → "already scanned" + date;
   - unknown/voided code → explicit error.
4. **History** reflects the new balance and a typed `Earned` row; **Profile** can edit the name
   and log out (silent re-login on next launch confirms secure-store persistence).
5. **Redeem**: request an amount ≤ available → appears as `pending` (available drops); have an admin
   approve via `POST /admin/redemptions/{id}/approve` → status flips to `approved` and balance debits;
   over-requesting surfaces `insufficient_balance`; a pending request can be cancelled.

## Static checks (CI-friendly, no device)

```bash
npx tsc --noEmit      # TypeScript (strict)
npx eslint .          # eslint-config-expo
npx expo-doctor       # project health (21 checks)
npx expo export -p android --output-dir /tmp/x   # full Metro bundle (catches import errors)
```

## Layout

`src/api` (axios client + auth-refresh interceptor, endpoint wrappers) · `src/auth`
(secure-store token store + `AuthContext`) · `src/hooks` (TanStack Query) · `src/navigation`
(auth stack vs app tabs) · `src/screens` (Phone, Otp, Scan, History, Redeem, Profile) ·
`src/components` (Button, ScanResultSheet).

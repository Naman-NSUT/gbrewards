# GB Rewards — Google Play Console Submission Pack

Everything you need to publish **GB Rewards** to Google Play. Copy the fields below
straight into Play Console. Items marked ⚠️ need you to supply/replace a value.

- **App name:** GB Rewards
- **Package name:** `in.gbrewards.gbrewards`
- **Default language:** English (India) — en-IN
- **App or game:** App
- **Free or paid:** Free
- **Category:** Business (alt: Shopping)
- **Privacy Policy URL:** `https://gbrewards.in/privacy-policy.html`  ← served from `admin-web/public/privacy-policy.html`

---

## 1. Store listing

**Short description** (≤ 80 chars):
```
Scan GoodBed products, earn reward points, and redeem them — for channel partners.
```

**Full description** (≤ 4000 chars):
```
GB Rewards is the official channel-incentive app for GoodBed partners.

Scan the unique QR code printed on genuine GoodBed mattresses, HR foams, and
pillows to instantly earn reward points. Track your balance, view your full
points history, and redeem points for vouchers, cash, or goodies — all from
your phone.

FEATURES
• Fast QR scanning — point your camera at the product code to claim points.
• Real-time points balance and detailed activity history.
• Rewards catalog — see exactly what your points can get you.
• Simple redemption requests, approved by the GoodBed team.
• Secure OTP login — no passwords to remember.
• Available in English and Hindi.

WHO IS IT FOR
GB Rewards is designed for GoodBed's authorised dealers and channel partners
participating in the rewards program.

Genuine products only. Each QR code can be claimed once; duplicate or copied
codes are not valid.
```

**Release notes / What's new** (for this build):
```
• Fresh new look with the GoodBed brand.
• Rewards catalog and info section.
• Promotional banners on the home screen.
• Faster, more reliable login.
```

---

## 2. Graphic assets required by Play

| Asset | Spec | Status |
|---|---|---|
| App icon | 512×512 PNG, 32-bit | ⚠️ Provide (can derive from `mobile/assets/icon.png`) |
| Feature graphic | 1024×500 PNG/JPG | ⚠️ Provide (the GoodBed poster works well) |
| Phone screenshots | 2–8 images, min 320px, 16:9 or 9:16 | ⚠️ Capture from the new build (Home carousel, Scan, Rewards, Info) |

Tip: install the preview APK, take screenshots of Home (with carousel), the
Rewards tab, and the Info tab — those show the app best.

---

## 3. Data safety form (Play Console → App content → Data safety)

Declare the following. Encryption in transit = **Yes**. Data deletion request = **Yes**
(users can request deletion per the privacy policy).

| Data type | Collected | Shared | Purpose | Optional? |
|---|---|---|---|---|
| Name | Yes | No | Account management | Required |
| Phone number | Yes | Yes (SMS OTP provider) | Account management, App functionality | Required |
| Address (physical) | Yes | No | App functionality (redemption fulfilment) | Required |
| App activity (points/scans) | Yes | No | App functionality | Required |
| Crash logs / diagnostics | Yes | No | Analytics, App stability | Required |

- **Does the app collect financial/payment info?** No
- **Does the app collect precise location?** No
- **Does the app access photos/media/contacts?** No
- **Camera:** used only to scan QR codes on-device; camera images are not collected or stored.

---

## 4. Content rating & other declarations

- **Content rating questionnaire:** answer as a *Business/Utility* app — no violence,
  no user-generated content, no gambling. Expected rating: **Everyone / 3+**.
- **Target audience:** 18+ (business partners). Not designed for children.
- **Ads:** No (the "banners" are your own promotional content, not a third-party ad network).
- **Government app:** No.

---

## 5. The AAB (the actual upload file)

Play Console requires an **`.aab`** (Android App Bundle), which is already built via EAS.

Build a fresh AAB (recommended — includes the new UI + correct backend):
```bash
cd mobile
npx eas-cli build --platform android --profile production
```
Download the resulting `.aab` and upload it under
**Play Console → Testing → Internal testing → Create release → Upload**.

---

## 6. ⚠️ Google service-account key — for `eas submit` (optional automation)

This is the one file that **cannot be generated from the codebase** — it comes from
Google Cloud. You only need it if you want `eas submit` to upload the AAB for you
automatically (otherwise upload the `.aab` by hand in step 5).

To create it:
1. In **Play Console → Setup → API access**, link a Google Cloud project.
2. In **Google Cloud Console → IAM & Admin → Service Accounts**, create a service
   account and create a **JSON key** for it. Download the JSON.
3. Back in **Play Console → API access**, grant that service account access with the
   **Release manager** (or Admin) permission.
4. Save the downloaded JSON as `mobile/google-service-account.json`
   (already git-ignored; path is wired in `mobile/eas.json` → `submit.production.android`).
5. Then run:
   ```bash
   cd mobile
   npx eas-cli submit --platform android --profile production --latest
   ```

---

## 7. First-publish checklist

- [ ] Create the app in Play Console (name, default language, Free, Business).
- [ ] App content: Privacy policy URL → `https://gbrewards.in/privacy-policy.html`.
- [ ] Complete Data safety form (section 3).
- [ ] Complete Content rating questionnaire (section 4).
- [ ] Upload icon, feature graphic, and screenshots (section 2).
- [ ] Paste short + full description (section 1).
- [ ] Create an **Internal testing** release and upload the `.aab` (section 5).
- [ ] Add tester emails, roll out, and share the opt-in link.
- [ ] (Later) Promote Internal → Closed/Production once tested.

# Dealer Rewards — public customer support site

The unauthenticated, public-facing half of Dealer Rewards. A customer lands here
from the warranty SMS, from a QR on the mattress, or from a search, and can:

- **check a warranty** by mobile number or serial (`/`);
- **register a warranty the shop never registered** (`/register`) — the most
  important path on the site, because an unregistered sale is the exact failure
  this whole system exists to catch;
- **raise a warranty claim** and track it (`/claim`, `/claim/status`);
- **confirm or dispute a registration** from the SMS link (`/w/:warrantyId`).

React 19 + Vite + TypeScript, plain CSS, no component library.

## Why this is a separate app from the admin panel

This site is public and unauthenticated. The admin panel is not — it contains
dealer performance data, the points ledger, customer phone numbers in the clear,
the fraud/backdating queues and the SMS log. Building both into one bundle would
ship all of that JavaScript, all of its API surface knowledge and all of its
route names to the open internet, protected by nothing but the fact that the
router does not currently render it. Two apps, two deploys, two origins: the
public bundle cannot leak an admin screen because it does not contain one.

It is also the right call on performance. This page is opened on a cheap Android
phone over a patchy connection, often standing next to a mattress in a shop. The
admin panel's dependency tree (charting, tables, a full component library) would
be several hundred kilobytes of parse time that no customer benefits from.

## Setup

```bash
npm install
cp .env.example .env      # point VITE_API_BASE_URL at the API
npm run dev               # http://localhost:5174
npm run build             # tsc -b && vite build  ->  dist/
```

`VITE_API_BASE_URL` is the API **origin** with no trailing slash; the client
appends `/api/v1`. Leave it empty to call the same origin the site is served
from, which is what a reverse-proxied deployment wants.

`VITE_SUPPORT_PHONE` / `VITE_SUPPORT_EMAIL` are optional. When unset, the
"need a person?" line simply does not render — better an absent line than a
placeholder number nobody answers.

## Deployment

`vercel.json` rewrites every path to `index.html` so a deep link like
`/w/8f3c…` survives a cold load and a refresh — without it, the SMS link 404s,
which would break the confirmation flow completely. Static assets are
fingerprinted by Vite and served immutable; the HTML is not cached.

`PUBLIC_BASE_URL` in the backend `.env` must point at this deployment: it is
what gets interpolated into the `{link}` variable of the `warranty_registered`
SMS template.

## Design notes

- **Light GoodBed theme** (navy `#184860`, cyan `#0090D8`, page `#EEF4F8`) — the
  same palette as the GB Rewards mobile app, so it reads as one product family.
  The admin panel of this system is dark; this one is not, because it is read
  outdoors in sunlight.
- **Cyan is never a text or button colour.** `#0090D8` on white is ~3.1:1, fine
  for borders, icons and focus rings and not fine for anything a customer has to
  read. Primary buttons are navy.
- **No webfont, no icon font, no image requests.** Icons are inline SVG; the
  type stack resolves to Inter/Roboto/San Francisco locally. Nothing blocks first
  paint on a third-party host.
- **Mobile-first**, 17px body text, 52px minimum tap target, real `<label>` on
  every input, visible focus on everything, and status communicated by word as
  well as colour.
- **No layout shift.** Results always render *below* the form that produced
  them, and the loading skeleton is shaped like the card that replaces it.
- Errors come from the API's `{"error": {code, message, details}}` envelope. The
  server's own message is shown except where it is written for an operator —
  a 429 becomes "you have tried a few times in quick succession, please wait a
  minute" rather than "Too many requests, slow down".

## The API contract

Everything this site calls is documented at the top of `src/api/types.ts`, which
is the authoritative statement of what the public API must provide. All of it is
unauthenticated and lives under `/api/v1/public`. Two shapes are deliberate:

1. **Lookups are POSTs even though they read.** The body carries a phone number
   or the last 4 digits of one; a GET would put those in the URL, and from there
   into access logs, browser history and the `Referer` header.
2. **Serial-only lookups come back masked**, with `masked: true` set by the
   server. Anyone can read a serial off a label in a shop — the buyer's name and
   number are not theirs to have. The client renders masked values verbatim and
   never attempts to reconstruct them.

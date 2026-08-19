#!/usr/bin/env bash
# Build BOTH admin panels into one output directory, served from one origin.
#
# Why one origin: the panels share a login. Both authenticate the same `admins`
# row with the same aud='admin' token and read it from the same localStorage
# keys — and localStorage is scoped per origin. Two Vercel projects would mean
# two domains, two storage buckets, and an operator logging in twice to use the
# switch button. So:
#
#   /          worker programme  (admin-web/)
#   /dealer/   dealer programme  (dealer-admin/, vite base=/dealer/)
#   /warranty/ PUBLIC customer site (support-web/, no auth)
#
# The public site is a separate bundle — no admin JavaScript is served to it.
# It does, however, share this origin's localStorage with the panels, which is
# where the admin token lives. Keep that in mind before adding any HTML-injecting
# dependency to support-web; a subdomain would remove the concern entirely.
#
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/public_admin"
rm -rf "$out"
mkdir -p "$out/dealer"

echo "==> worker admin panel"
cd "$root/admin-web"
npm ci --no-audit --no-fund
npm run build
cp -R dist/. "$out/"

echo "==> dealer admin panel"
cd "$root/dealer-admin"
npm ci --no-audit --no-fund
npm run build
cp -R dist/. "$out/dealer/"

echo "==> public customer site"
cd "$root/support-web"
npm ci --no-audit --no-fund
npm run build
mkdir -p "$out/warranty"
cp -R dist/. "$out/warranty/"

echo "==> output"
ls -1 "$out" | sed 's/^/    /'

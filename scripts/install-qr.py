#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["qrcode[pil]"]
# ///
"""Regenerate the install QR for the worker app from the latest EAS APK build.

The QR in docs/install/ points at an EAS artifact URL, and EAS expires build
artifacts after its retention window — so a QR committed once quietly stops
working. Rather than leaving that as a trap, this rebuilds it from whatever the
newest finished APK build is:

    scripts/install-qr.py

Run it after every `eas build --profile preview`. It rewrites the PNG and the
README beside it, so `git diff` shows exactly which build the QR now points to.
"""

import json
import pathlib
import subprocess
import sys
from datetime import UTC, datetime

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

REPO = pathlib.Path(__file__).resolve().parent.parent
MOBILE = REPO / "mobile"
OUT_DIR = REPO / "docs" / "install"
PNG = OUT_DIR / "gbrewards-worker-apk.png"
README = OUT_DIR / "README.md"

# Error correction Q: a quarter of the symbol can be lost and still decode, which
# is what lets this survive being photographed off a screen or printed small.
CORRECTION = ERROR_CORRECT_Q


def latest_apk_build() -> dict:
    """The newest finished APK build, as EAS reports it."""
    raw = subprocess.run(
        [
            "npx", "eas-cli", "build:list",
            "--platform", "android",
            "--limit", "10",
            "--non-interactive", "--json",
        ],
        cwd=MOBILE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    builds = json.loads(raw)
    for b in builds:
        archive = (b.get("artifacts") or {}).get("applicationArchiveUrl") or ""
        if b.get("status") == "FINISHED" and archive.endswith(".apk"):
            return b
    raise SystemExit("No finished APK build found — run `eas build --profile preview` first.")


def main() -> None:
    build = latest_apk_build()
    url = build["artifacts"]["applicationArchiveUrl"]
    version = build.get("appVersion")
    code = build.get("appBuildVersion")

    qr = qrcode.QRCode(error_correction=CORRECTION, border=4, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qr.make_image(fill_color="black", back_color="white").save(PNG)

    README.write_text(
        f"""# Install the GB Rewards worker app

Scan this on an Android phone to download the APK.

![Install QR](gbrewards-worker-apk.png)

| | |
|---|---|
| Version | {version} (versionCode {code}) |
| Build | `{build.get("id")}` |
| Backend | production (`gbrewards.onrender.com`) |
| Regenerated | {datetime.now(UTC):%Y-%m-%d} |

Direct link: <{url}>

The phone will ask to allow installs from unknown sources the first time. That is
normal for a build distributed outside the Play Store, not a problem with the file.

**This link expires.** EAS deletes build artifacts after its retention window, so
after a new build — or if the link stops working — regenerate both this page and
the QR with:

```sh
scripts/install-qr.py
```
""",
    )

    print(f"build    : {build.get('id')}")
    print(f"version  : {version} (versionCode {code})")
    print(f"symbol   : version {qr.version}, {qr.modules_count}x{qr.modules_count} modules")
    print(f"written  : {PNG.relative_to(REPO)}")
    print(f"           {README.relative_to(REPO)}")


if __name__ == "__main__":
    sys.exit(main())

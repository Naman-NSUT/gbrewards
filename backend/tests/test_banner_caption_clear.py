"""Removing a banner's caption.

The app draws the caption over the artwork, so a banner whose own design carries
the greeting needs no caption — and once one was set there was no way to take it
off. FastAPI treats an empty Form value as absent and substitutes the default
(dependencies/utils.py: `value == ""`), so "clear this" and "leave it alone"
arrived at the endpoint identically.

These pin the distinction, because it is invisible in the handler signature: the
parameters still declare `caption: str | None = Form(None)`, and reading them
alone would quietly restore the bug.
"""

import io

from PIL import Image

from tests.factories import admin_headers, make_admin, make_banner


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1600, 800), (200, 60, 40)).save(buf, "JPEG")
    return buf.getvalue()


def test_an_empty_caption_clears_it(client, db) -> None:
    banner = make_banner(db, caption="Happy Diwali GoodBed Family")
    admin = make_admin(db)
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"caption": ""},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["caption"] is None


def test_a_cleared_caption_is_stored_as_null_not_as_empty_text(client, db) -> None:
    """One representation of absence, so the app has one thing to test."""
    banner = make_banner(db, caption="Something")
    admin = make_admin(db)
    db.commit()

    client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"caption": ""},
    )

    db.refresh(banner)
    assert banner.caption is None


def test_omitting_the_field_leaves_the_caption_alone(client, db) -> None:
    """The other half of the distinction: a PATCH that only moves a banner must
    not wipe its text."""
    banner = make_banner(db, caption="Keep me")
    admin = make_admin(db)
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"sort_order": "3"},
    )

    assert resp.json()["caption"] == "Keep me"
    assert resp.json()["sort_order"] == 3


def test_a_caption_can_still_be_set_and_changed(client, db) -> None:
    banner = make_banner(db, caption="Old")
    admin = make_admin(db)
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"caption": "New"},
    )

    assert resp.json()["caption"] == "New"


def test_the_link_can_be_cleared_the_same_way(client, db) -> None:
    banner = make_banner(db, link_url="https://example.com/old")
    admin = make_admin(db)
    db.commit()

    resp = client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"link_url": ""},
    )

    assert resp.json()["link_url"] is None


def test_clearing_the_caption_does_not_disturb_the_image(client, db) -> None:
    """The caption and the artwork are edited from the same form; removing text
    must not cost the banner its image."""
    banner = make_banner(db, caption="Remove me")
    admin = make_admin(db)
    db.commit()
    client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        files={"image": ("b.jpg", _jpeg(), "image/jpeg")},
    )
    db.refresh(banner)
    before = banner.image_data

    client.patch(
        f"/api/v1/admin/banners/{banner.id}",
        headers=admin_headers(admin),
        data={"caption": ""},
    )

    db.refresh(banner)
    assert banner.caption is None
    assert banner.image_data == before

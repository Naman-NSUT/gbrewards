"""Replacing a banner's artwork has to reach phones that already saw the old one.

The serve endpoint sends `Cache-Control: public, max-age=86400` and no validator,
so a cached banner is not re-fetched for a day. The URL is therefore the only
thing that can tell a client the picture changed — and it used to be derived from
the banner id alone, which never changes.
"""

import io

from PIL import Image

from tests.factories import admin_headers, make_admin, make_banner


def _img(colour: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1600, 800), colour).save(buf, "JPEG")
    return buf.getvalue()


def _put_image(client, admin, banner_id, colour):  # type: ignore[no-untyped-def]
    return client.patch(
        f"/api/v1/admin/banners/{banner_id}",
        headers=admin_headers(admin),
        files={"image": ("b.jpg", _img(colour), "image/jpeg")},
    )


def test_replacing_the_artwork_changes_the_url(client, db) -> None:
    """Otherwise a phone keeps the old picture for a day and the admin cannot
    tell whether the upload worked."""
    banner = make_banner(db)
    admin = make_admin(db)
    db.commit()

    first = _put_image(client, admin, banner.id, (200, 60, 40)).json()["image_url"]
    second = _put_image(client, admin, banner.id, (20, 90, 180)).json()["image_url"]

    assert first != second


def test_the_same_artwork_keeps_the_same_url(client, db) -> None:
    """A digest, not a timestamp: re-saving a banner without touching its image
    must not make every phone download it again."""
    banner = make_banner(db)
    admin = make_admin(db)
    db.commit()

    first = _put_image(client, admin, banner.id, (200, 60, 40)).json()["image_url"]
    again = _put_image(client, admin, banner.id, (200, 60, 40)).json()["image_url"]

    assert first == again


def test_the_versioned_url_still_serves_the_image(client, db) -> None:
    """The version is a cache key, not a lookup key — the endpoint ignores it."""
    banner = make_banner(db)
    admin = make_admin(db)
    db.commit()
    url = _put_image(client, admin, banner.id, (200, 60, 40)).json()["image_url"]

    resp = client.get(url)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"


def test_a_stale_version_still_serves_rather_than_404s(client, db) -> None:
    """A client holding an old URL must get the current picture, not an error."""
    banner = make_banner(db)
    admin = make_admin(db)
    db.commit()
    old_url = _put_image(client, admin, banner.id, (200, 60, 40)).json()["image_url"]
    _put_image(client, admin, banner.id, (20, 90, 180))

    assert client.get(old_url).status_code == 200


def test_a_new_upload_is_versioned_too(client, db) -> None:
    admin = make_admin(db)
    db.commit()

    resp = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers(admin),
        files={"image": ("b.jpg", _img((10, 10, 10)), "image/jpeg")},
        data={"caption": "x"},
    )

    assert "?v=" in resp.json()["image_url"]

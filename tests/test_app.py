"""Tests for the Spaces Gallery Flask app."""

import io

import pytest

import app as app_module

# --- Pure helpers ------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("photo.png", True),
        ("A.JPG", True),
        ("x.jpeg", True),
        ("y.gif", True),
        ("z.webp", True),
        ("notes.txt", False),
        ("archive.zip", False),
        ("noextension", False),
    ],
)
def test_allowed_file(name, expected):
    assert app_module.allowed_file(name) is expected


def test_public_url_uses_origin_when_no_cdn(monkeypatch):
    monkeypatch.setattr(app_module, "SPACES_CDN_ENDPOINT", None)
    monkeypatch.setattr(
        app_module, "SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com"
    )
    monkeypatch.setattr(app_module, "SPACES_BUCKET", "demo")
    assert (
        app_module.public_url("uploads/a.png")
        == "https://nyc3.digitaloceanspaces.com/demo/uploads/a.png"
    )


def test_public_url_prefers_cdn(monkeypatch):
    # Trailing slash on the CDN endpoint should be normalized away.
    monkeypatch.setattr(app_module, "SPACES_CDN_ENDPOINT", "https://cdn.example.com/")
    assert app_module.public_url("uploads/a.png") == "https://cdn.example.com/uploads/a.png"


# --- Routes ------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_index_shows_notice_when_not_configured(monkeypatch):
    monkeypatch.setattr(app_module, "SPACES_KEY", None)
    monkeypatch.setattr(app_module, "SPACES_SECRET", None)
    monkeypatch.setattr(app_module, "SPACES_BUCKET", None)
    resp = app_module.app.test_client().get("/")
    assert resp.status_code == 200
    assert b"Spaces is not configured" in resp.data


def test_index_empty_gallery(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"No images yet" in resp.data


def test_upload_rejects_missing_file(client):
    resp = client.post("/upload", data={}, follow_redirects=True)
    assert b"Please select an image" in resp.data


def test_upload_rejects_wrong_type(client):
    data = {"image": (io.BytesIO(b"not an image"), "notes.txt")}
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert b"Invalid file type" in resp.data


def test_upload_stores_original_and_thumbnail(client, fake_s3, png_bytes):
    data = {"image": (io.BytesIO(png_bytes()), "pic.png")}
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert resp.status_code == 200
    keys = list(fake_s3.store)
    assert sum(k.startswith("uploads/") for k in keys) == 1
    assert sum(k.startswith("thumbs/") for k in keys) == 1
    # Original and thumbnail share the same generated filename.
    upload_name = next(k for k in keys if k.startswith("uploads/")).split("/", 1)[1]
    assert f"thumbs/{upload_name}" in fake_s3.store


def test_upload_sets_cache_control(client, fake_s3, png_bytes):
    data = {"image": (io.BytesIO(png_bytes()), "pic.png")}
    client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    # Both the original and its thumbnail are immutable, so they carry a
    # long-lived Cache-Control header for the CDN.
    for key, meta in fake_s3.store.items():
        assert meta["kwargs"]["CacheControl"] == app_module.CACHE_CONTROL, key
    assert "max-age=" in app_module.CACHE_CONTROL
    assert "immutable" in app_module.CACHE_CONTROL


def test_upload_rejects_oversized_file(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 1000
    try:
        data = {"image": (io.BytesIO(b"x" * 4000), "big.png")}
        resp = client.post(
            "/upload",
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert b"File too large" in resp.data
    finally:
        client.application.config["MAX_CONTENT_LENGTH"] = app_module.MAX_CONTENT_LENGTH


def test_delete_removes_object_and_thumbnail(client, fake_s3, png_bytes):
    fake_s3.put_object(Bucket="b", Key="uploads/x.png", Body=png_bytes())
    fake_s3.put_object(Bucket="b", Key="thumbs/x.png", Body=png_bytes())
    resp = client.post(
        "/delete", data={"key": "uploads/x.png"}, follow_redirects=True
    )
    assert b"Image deleted" in resp.data
    assert "uploads/x.png" not in fake_s3.store
    assert "thumbs/x.png" not in fake_s3.store


def test_delete_rejects_key_outside_uploads(client, fake_s3, png_bytes):
    # The guard must refuse to delete arbitrary keys (e.g. thumbnails directly).
    fake_s3.put_object(Bucket="b", Key="thumbs/secret.png", Body=png_bytes())
    resp = client.post(
        "/delete", data={"key": "thumbs/secret.png"}, follow_redirects=True
    )
    assert b"Could not delete" in resp.data
    assert "thumbs/secret.png" in fake_s3.store  # left untouched


# --- Pagination --------------------------------------------------------------


def test_pagination_splits_and_clamps(client, fake_s3, png_bytes):
    for i in range(15):
        fake_s3.put_object(Bucket="b", Key=f"uploads/{i:02d}.png", Body=png_bytes())

    images, pagination = app_module.list_images(page=1)
    assert pagination["total"] == 15
    assert pagination["total_pages"] == 2  # 12 + 3 with PAGE_SIZE=12
    assert len(images) == 12

    second, pag2 = app_module.list_images(page=2)
    assert len(second) == 3

    # Out-of-range pages clamp to the last valid page.
    _, pag_high = app_module.list_images(page=99)
    assert pag_high["page"] == 2
    _, pag_low = app_module.list_images(page=0)
    assert pag_low["page"] == 1

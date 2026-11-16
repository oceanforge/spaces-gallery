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


def test_upload_rejects_non_image_with_image_extension(client, fake_s3):
    # A non-image payload disguised with a .png extension must be rejected and
    # never stored, even though the extension check passes.
    data = {"image": (io.BytesIO(b"definitely not a PNG"), "fake.png")}
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"valid image" in resp.data
    assert len(fake_s3.store) == 0


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
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert resp.status_code == 200
    # The original and its thumbnail must both be written...
    assert len(fake_s3.store) == 2
    # ...and, being immutable, both carry the long-lived Cache-Control header.
    for key, meta in fake_s3.store.items():
        assert meta["kwargs"]["CacheControl"] == app_module.CACHE_CONTROL, key
    assert "max-age=" in app_module.CACHE_CONTROL
    assert "immutable" in app_module.CACHE_CONTROL


def test_cache_max_age_ignores_invalid_env(monkeypatch):
    monkeypatch.setenv("CACHE_MAX_AGE", "not-a-number")
    assert app_module._int_env("CACHE_MAX_AGE", 31536000) == 31536000
    monkeypatch.setenv("CACHE_MAX_AGE", "-5")
    assert app_module._int_env("CACHE_MAX_AGE", 31536000) == 0


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


# --- Direct uploads ----------------------------------------------------------


@pytest.fixture
def direct(client, monkeypatch):
    monkeypatch.setattr(app_module, "DIRECT_UPLOADS", True)
    return client


def test_presign_is_off_by_default(client):
    assert client.post("/upload/presign", json={"filename": "a.png"}).status_code == 404


def test_presign_pins_type_and_size(direct, fake_s3):
    resp = direct.post("/upload/presign", json={"filename": "Cat.PNG"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["key"].startswith("uploads/") and body["key"].endswith(".png")
    conditions = fake_s3.presigned["Conditions"]
    assert {"Content-Type": "image/png"} in conditions
    assert ["content-length-range", 1, app_module.MAX_CONTENT_LENGTH] in conditions
    assert body["fields"]["Content-Type"] == "image/png"


def test_presign_rejects_other_types(direct):
    assert direct.post("/upload/presign", json={"filename": "notes.txt"}).status_code == 400


def test_complete_makes_thumbnail(direct, fake_s3, png_bytes):
    fake_s3.put_object(Bucket="b", Key="uploads/abc.png", Body=png_bytes(size=(800, 600)))
    resp = direct.post("/upload/complete", json={"key": "uploads/abc.png"})
    assert resp.status_code == 200
    assert "thumbs/abc.png" in fake_s3.store
    # The POST can't set Cache-Control, so complete adds it to the original.
    assert fake_s3.store["uploads/abc.png"]["kwargs"]["CacheControl"] == app_module.CACHE_CONTROL


def test_complete_removes_files_that_are_not_images(direct, fake_s3):
    fake_s3.put_object(Bucket="b", Key="uploads/bad.png", Body=b"not an image")
    resp = direct.post("/upload/complete", json={"key": "uploads/bad.png"})
    assert resp.status_code == 400
    assert "uploads/bad.png" not in fake_s3.store


def test_complete_only_accepts_upload_keys(direct, fake_s3, png_bytes):
    fake_s3.put_object(Bucket="b", Key="thumbs/x.png", Body=png_bytes())
    assert direct.post("/upload/complete", json={"key": "thumbs/x.png"}).status_code == 400

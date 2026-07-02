"""Test fixtures for the Spaces Gallery app.

The app talks to DigitalOcean Spaces through a boto3 S3 client. Rather than
hitting a real bucket (or pulling in a mock-AWS dependency that doesn't cleanly
intercept the custom Spaces endpoint), we swap `get_client()` for a tiny
in-memory fake that implements only the calls the app makes.
"""

import io
from datetime import datetime, timedelta

import pytest
from PIL import Image

import app as app_module


class _FakePaginator:
    def __init__(self, store):
        self._store = store

    def paginate(self, Bucket, Prefix=""):
        contents = [
            {
                "Key": key,
                "LastModified": meta["last_modified"],
                "Size": len(meta["body"]),
            }
            for key, meta in self._store.items()
            if key.startswith(Prefix)
        ]
        # The real paginator yields pages; one page is enough for tests.
        yield {"Contents": contents}


class FakeS3Client:
    """Minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self):
        self.store = {}  # key -> {"body": bytes, "last_modified": datetime}
        self._clock = datetime(2020, 1, 1)

    def _tick(self):
        # Monotonic timestamps so newest-first sorting is deterministic.
        self._clock += timedelta(seconds=1)
        return self._clock

    def put_object(self, Bucket, Key, Body, **kwargs):
        body = Body.read() if hasattr(Body, "read") else Body
        self.store[Key] = {
            "body": body,
            "last_modified": self._tick(),
            "kwargs": kwargs,  # ACL, ContentType, CacheControl, ...
        }

    def delete_object(self, Bucket, Key):
        self.store.pop(Key, None)

    def get_paginator(self, operation_name):
        assert operation_name == "list_objects_v2"
        return _FakePaginator(self.store)


@pytest.fixture
def fake_s3(monkeypatch):
    """Patch the app's client factory to return an in-memory fake."""
    fake = FakeS3Client()
    monkeypatch.setattr(app_module, "get_client", lambda: fake)
    return fake


@pytest.fixture
def configured(monkeypatch):
    """Pretend Spaces is configured (without real credentials)."""
    monkeypatch.setattr(app_module, "SPACES_KEY", "test-key")
    monkeypatch.setattr(app_module, "SPACES_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "SPACES_BUCKET", "test-bucket")
    monkeypatch.setattr(app_module, "SPACES_CDN_ENDPOINT", None)


@pytest.fixture
def client(fake_s3, configured):
    """A Flask test client backed by the fake S3 store, with Spaces configured."""
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


@pytest.fixture
def png_bytes():
    """Factory for small valid PNG byte strings (Pillow can thumbnail them)."""

    def _make(color="red", size=(24, 24)):
        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, format="PNG")
        return buf.getvalue()

    return _make

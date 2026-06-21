"""
Spaces Gallery — a tiny Flask app that uploads images to DigitalOcean Spaces
and shows them in a gallery.

It's intentionally small: the goal is to demonstrate how little it takes to run
a real app (web service + object storage) on DigitalOcean App Platform.

Configuration is read from environment variables — see .env.example.
"""

import os
import uuid

import boto3
from botocore.client import Config
from flask import Flask, redirect, render_template, request, url_for

# --- Configuration -----------------------------------------------------------

SPACES_KEY = os.environ.get("SPACES_KEY")
SPACES_SECRET = os.environ.get("SPACES_SECRET")
SPACES_REGION = os.environ.get("SPACES_REGION", "nyc3")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET")

# Direct origin endpoint, e.g. https://nyc3.digitaloceanspaces.com
SPACES_ENDPOINT = os.environ.get(
    "SPACES_ENDPOINT", f"https://{SPACES_REGION}.digitaloceanspaces.com"
)
# Optional CDN endpoint, e.g. https://my-bucket.nyc3.cdn.digitaloceanspaces.com
SPACES_CDN_ENDPOINT = os.environ.get("SPACES_CDN_ENDPOINT")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# --- Spaces client -----------------------------------------------------------

def get_client():
    """Return a boto3 S3 client pointed at DigitalOcean Spaces.

    Spaces is S3-compatible, so the standard AWS SDK works unchanged — we just
    swap in the Spaces endpoint and region.
    """
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_KEY,
        aws_secret_access_key=SPACES_SECRET,
        config=Config(signature_version="s3v4"),
    )


def public_url(key):
    """Build the public URL for an object, preferring the CDN if configured."""
    if SPACES_CDN_ENDPOINT:
        return f"{SPACES_CDN_ENDPOINT.rstrip('/')}/{key}"
    return f"{SPACES_ENDPOINT.rstrip('/')}/{SPACES_BUCKET}/{key}"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def list_images(limit=60):
    """Return public URLs for the most recently uploaded images."""
    client = get_client()
    response = client.list_objects_v2(Bucket=SPACES_BUCKET, Prefix="uploads/")
    objects = response.get("Contents", [])
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    return [public_url(o["Key"]) for o in objects[:limit]]


# --- Routes ------------------------------------------------------------------

@app.route("/")
def index():
    images = []
    error = None
    if not is_configured():
        error = (
            "Spaces is not configured yet. Set SPACES_KEY, SPACES_SECRET and "
            "SPACES_BUCKET (see .env.example)."
        )
    else:
        try:
            images = list_images()
        except Exception as exc:  # noqa: BLE001 — surface any config/storage error
            error = f"Could not list images: {exc}"
    return render_template("index.html", images=images, error=error)


@app.route("/upload", methods=["POST"])
def upload():
    if not is_configured():
        return redirect(url_for("index"))

    file = request.files.get("image")
    if not file or file.filename == "":
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    key = f"uploads/{uuid.uuid4().hex}.{ext}"

    client = get_client()
    client.put_object(
        Bucket=SPACES_BUCKET,
        Key=key,
        Body=file,
        ACL="public-read",
        ContentType=file.mimetype,
    )
    return redirect(url_for("index"))


@app.route("/health")
def health():
    """Lightweight health check for App Platform."""
    return {"status": "ok"}, 200


def is_configured():
    return all([SPACES_KEY, SPACES_SECRET, SPACES_BUCKET])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)

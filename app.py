"""
Spaces Gallery — a tiny Flask app that uploads images to DigitalOcean Spaces
and shows them in a gallery.

It's intentionally small: the goal is to demonstrate how little it takes to run
a real app (web service + object storage) on DigitalOcean App Platform.

Configuration is read from environment variables — see .env.example.
"""

import io
import os
import uuid

import boto3
from botocore.client import Config
from flask import Flask, flash, redirect, render_template, request, url_for
from PIL import Image

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
PAGE_SIZE = 12  # images per gallery page
THUMBNAIL_SIZE = (400, 400)  # max thumbnail dimensions (aspect preserved)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# Used to sign the session for flash messages. The fallback is for local dev only;
# set SECRET_KEY to a strong random value in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")


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


def make_thumbnail(data):
    """Return a downscaled copy of the image bytes, keeping the original format."""
    image = Image.open(io.BytesIO(data))
    fmt = image.format or "PNG"
    image.thumbnail(THUMBNAIL_SIZE)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    buffer.seek(0)
    return buffer


def list_images(page=1, page_size=PAGE_SIZE):
    """Return one page of images (newest first) plus paging metadata.

    Each image is a {key, url, thumb_url} dict — the key drives the delete
    control, and thumb_url is the smaller image for the grid (falling back to
    the full image when no thumbnail exists, e.g. for older uploads).
    """
    client = get_client()
    paginator = client.get_paginator("list_objects_v2")
    objects = []
    for response in paginator.paginate(Bucket=SPACES_BUCKET, Prefix="uploads/"):
        objects.extend(response.get("Contents", []))
    objects.sort(key=lambda o: o["LastModified"], reverse=True)

    # Names that have a generated thumbnail, so we can fall back gracefully.
    thumb_names = set()
    for response in paginator.paginate(Bucket=SPACES_BUCKET, Prefix="thumbs/"):
        for obj in response.get("Contents", []):
            thumb_names.add(obj["Key"].split("/", 1)[1])

    total = len(objects)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    page_objects = objects[start:start + page_size]

    images = []
    for obj in page_objects:
        key = obj["Key"]
        name = key.split("/", 1)[1]
        thumb_url = public_url(f"thumbs/{name}") if name in thumb_names else public_url(key)
        images.append({"key": key, "url": public_url(key), "thumb_url": thumb_url})

    pagination = {"page": page, "total_pages": total_pages, "total": total}
    return images, pagination


# --- Routes ------------------------------------------------------------------

@app.route("/")
def index():
    images = []
    pagination = {"page": 1, "total_pages": 1, "total": 0}
    error = None
    if not is_configured():
        error = (
            "Spaces is not configured yet. Set SPACES_KEY, SPACES_SECRET and "
            "SPACES_BUCKET (see .env.example)."
        )
    else:
        try:
            page = request.args.get("page", 1, type=int)
            images, pagination = list_images(page=page)
        except Exception as exc:  # noqa: BLE001 — surface any config/storage error
            error = f"Could not list images: {exc}"
    return render_template(
        "index.html",
        images=images,
        error=error,
        pagination=pagination,
        total_images=pagination["total"]
    )


@app.route("/upload", methods=["POST"])
def upload():
    if not is_configured():
        flash("Spaces is not configured yet.")
        return redirect(url_for("index"))

    file = request.files.get("image")
    if not file or file.filename == "":
        flash("Please select an image to upload.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash(
            "Invalid file type. Allowed types: png, jpg, jpeg, gif, webp. "
            "Maximum size: 8 MB."
        )
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    key = f"uploads/{name}"

    data = file.read()
    client = get_client()
    client.put_object(
        Bucket=SPACES_BUCKET,
        Key=key,
        Body=data,
        ACL="public-read",
        ContentType=file.mimetype,
    )

    # Generate a thumbnail for the grid. If it fails for any reason, the gallery
    # falls back to serving the full image, so this never blocks an upload.
    try:
        thumb = make_thumbnail(data)
        client.put_object(
            Bucket=SPACES_BUCKET,
            Key=f"thumbs/{name}",
            Body=thumb,
            ACL="public-read",
            ContentType=file.mimetype,
        )
    except Exception:  # noqa: BLE001 — thumbnail is best-effort
        pass

    return redirect(url_for("index"))


@app.route("/delete", methods=["POST"])
def delete():
    if not is_configured():
        flash("Spaces is not configured yet.")
        return redirect(url_for("index"))

    key = request.form.get("key", "")
    # Only allow deleting objects this app created, never an arbitrary key.
    if not key.startswith("uploads/"):
        flash("Could not delete that image.")
        return redirect(url_for("index"))

    client = get_client()
    client.delete_object(Bucket=SPACES_BUCKET, Key=key)
    # Remove the matching thumbnail too (no error if it doesn't exist).
    client.delete_object(Bucket=SPACES_BUCKET, Key=f"thumbs/{key.split('/', 1)[1]}")
    flash("Image deleted.")
    return redirect(url_for("index"))


@app.errorhandler(413)
def file_too_large(error):
    flash(
        "File too large. Maximum allowed size is 8 MB. "
        "Allowed types: png, jpg, jpeg, gif, webp."
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

---
title: "Some friends wanted to see how I use DigitalOcean. So I built them the smallest real app I could."
published: false
description: "A Flask image uploader on DigitalOcean App Platform + Spaces — the whole thing I'd show a friend, including the one config gotcha that'll eat your afternoon."
tags: digitalocean, python, flask, webdev
cover_image: "https://raw.githubusercontent.com/oceanforge/spaces-gallery/main/docs/screenshot.png"
---

A couple of friends know I host most of my side projects on DigitalOcean, and lately they've been asking the same thing: *"Okay, but how do you actually use it? Show me."*

"It depends on your project" is a useless thing to say to a friend, so I did the other thing — I built the smallest app that still does something real. Upload an image, store it somewhere durable, show it back. The whole thing runs on DigitalOcean App Platform + Spaces, and this post is basically me walking them (and you) through it.

It's ~120 lines of Flask, no Dockerfile, and it deploys on `git push`. By the end you'll know whether this stack fits how *you* work — and you'll have dodged the one config gotcha that wasted 20 minutes of my life before it wastes yours.

Code's here if you just want to read it: [oceanforge/spaces-gallery](https://github.com/oceanforge/spaces-gallery).

## What we're building

A page with an upload button and a grid of images. You pick a file, it goes into a [Spaces](https://www.digitalocean.com/products/spaces) bucket (DigitalOcean's S3-compatible object storage), and the grid shows everything you've uploaded so far. That's it.

Why this and not a to-do app? Because it touches the two things you actually care about when evaluating a platform: **does my code run without me babysitting a server, and where do user files go?** A to-do app dodges both.

You'll want a DigitalOcean account (new ones come with trial credit, so this costs nothing to follow), a GitHub account, and Python 3.10+.

## Why App Platform at all?

Quick bit of context, because it explains why this category of product matters again.

In November 2022, Heroku killed its free tier. For a decade Heroku had been the default answer to "where do I put my side project" — `git push heroku main` and you were live. When the free dynos went away, a generation of developers who'd never thought about hosting suddenly had to, and a lot of them landed somewhere uncomfortable: either back in raw VPS territory (you own the server, the patches, the firewall, the 2 a.m. page) or in the full cloud (where deploying a hobby app somehow involves IAM roles and a YAML file longer than the app).

App Platform is DigitalOcean's answer to that gap, and it's the closest thing to old-Heroku's "just push it" feeling that I've used. You connect a repo, it detects the language, it builds and runs it. No Dockerfile required, no cluster to manage. Pricing is flat and legible — you know what the bill is before the month starts, which is its own kind of feature after years of cloud invoices that read like ransom notes.

Pair it with Spaces and the storage story is just as boring, in the good way: it's S3-compatible, so there's no proprietary SDK to learn. If you've ever touched AWS S3, you already know the API. That "boring on purpose" combination — predictable hosting, familiar storage — is the whole reason I keep reaching for it instead of something flashier. The best infrastructure is the kind you stop thinking about.

That's the pitch. The rest of this post is me proving it with actual code.

## The app, in one file

Everything lives in `app.py`. Config comes from environment variables — nothing secret ever touches the repo:

```python
import os
import uuid

import boto3
from botocore.client import Config
from flask import Flask, redirect, render_template, request, url_for

SPACES_KEY = os.environ.get("SPACES_KEY")
SPACES_SECRET = os.environ.get("SPACES_SECRET")
SPACES_REGION = os.environ.get("SPACES_REGION", "nyc3")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET")
SPACES_ENDPOINT = os.environ.get(
    "SPACES_ENDPOINT", f"https://{SPACES_REGION}.digitaloceanspaces.com"
)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB
```

Here's the thing that surprised me the first time: I'm using **boto3, the AWS SDK**, to talk to DigitalOcean. Spaces speaks the S3 API, so all your existing S3 knowledge and tooling just transfers. The only thing that changes is where you point it:

```python
def get_client():
    session = boto3.session.Session()
    return session.client(
        "s3",
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT,
        aws_access_key_id=SPACES_KEY,
        aws_secret_access_key=SPACES_SECRET,
        config=Config(signature_version="s3v4"),
    )
```

### The gotcha that cost me 20 minutes

See `SPACES_ENDPOINT`? It's `https://<region>.digitaloceanspaces.com` — the **region** endpoint. No bucket name.

When you create a bucket, DigitalOcean shows you a URL like `https://my-bucket.atl1.digitaloceanspaces.com`, with the bucket baked into the front. The natural move is to paste *that* into your code. Don't. boto3 wants the region endpoint and adds the bucket itself. Give it the bucket-prefixed URL and you get cryptic signature errors that look like an auth problem but aren't.

That's the one thing I'd tattoo on a beginner's hand. Everything else is downhill from here.

The rest is plumbing — list what's in the bucket, build public URLs:

```python
def public_url(key):
    return f"{SPACES_ENDPOINT.rstrip('/')}/{SPACES_BUCKET}/{key}"


def list_images(limit=60):
    client = get_client()
    response = client.list_objects_v2(Bucket=SPACES_BUCKET, Prefix="uploads/")
    objects = response.get("Contents", [])
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    return [public_url(o["Key"]) for o in objects[:limit]]
```

And the routes — a gallery, an upload handler, and a health check App Platform can ping:

```python
@app.route("/")
def index():
    images = list_images() if all([SPACES_KEY, SPACES_SECRET, SPACES_BUCKET]) else []
    return render_template("index.html", images=images)


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("image")
    if not file or "." not in file.filename:
        return redirect(url_for("index"))

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return redirect(url_for("index"))

    key = f"uploads/{uuid.uuid4().hex}.{ext}"
    client = get_client()
    client.put_object(
        Bucket=SPACES_BUCKET,
        Key=key,
        Body=file,
        ACL="public-read",        # this is what makes the image loadable in a browser
        ContentType=file.mimetype,
    )
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok"}, 200
```

One line worth pausing on: `ACL="public-read"`. Buckets are private by default — a sane default — so without this the upload succeeds but every image 404s in the browser. If you only want *some* things public, this is the lever.

The HTML template and a bit of CSS are in the [repo](https://github.com/oceanforge/spaces-gallery); they're not interesting enough to paste here.

## Getting Spaces ready

In the DigitalOcean panel: **Spaces Object Storage → Create a Spaces Bucket**. Pick a region (I used Atlanta, `atl1`), give it a globally-unique name, create it.

Then the part people miss: you need **Spaces keys**, which are *not* the same as DigitalOcean API tokens. Different screen, different thing. Go to **API → Spaces Keys → Generate New Key**. You get an access key and a secret — and the secret shows **once**. Copy it now or regenerate later; there's no "show again."

## Run it locally first

Always confirm it works on your machine before you blame the cloud:

```bash
export SPACES_KEY="..."        # your access key
export SPACES_SECRET="..."     # your secret
export SPACES_REGION="atl1"
export SPACES_BUCKET="your-bucket"

pip install -r requirements.txt
python app.py
```

Open `http://localhost:8080`, upload something. If it shows up in the grid, your keys and bucket are good and the cloud part is basically free.

## Deploying — this is the part that sells it

Push to GitHub, then in the panel: **App Platform → Create App → point it at your repo**.

Now the moment that made me get it: App Platform looks at the repo, sees Python, and just... builds it. No Dockerfile. No build config. It picks up the start command from a one-line `Procfile`:

```text
web: gunicorn --worker-tmp-dir /dev/shm --bind 0.0.0.0:$PORT app:app
```

Before you hit deploy, add your four env vars under the component's settings:

| Key | Value |
| --- | --- |
| `SPACES_KEY` | your access key |
| `SPACES_SECRET` | your secret key |
| `SPACES_REGION` | `atl1` |
| `SPACES_BUCKET` | your bucket name |

Tick **encrypt** on the key and secret so they're stored as secrets, not plaintext. Deploy. You get a `*.ondigitalocean.app` URL, and from then on every push to `main` redeploys on its own. That feedback loop — push, walk away, it's live — is the whole pitch.

## So… is it for you?

My honest take after building this:

**Reach for App Platform + Spaces if** you want to ship a web app without thinking about servers, you like `git push` being your deploy button, and you'd rather not write Kubernetes manifests to host a side project. The Spaces-is-just-S3 thing means zero new storage API to learn.

**Look elsewhere if** you need fine-grained infra control, exotic runtimes, or you're already deep in another cloud's ecosystem and the migration isn't worth it.

For side projects, demos, internal tools, and "I just need this online today" — it's genuinely hard to beat the effort-to-running-app ratio here.

If you want to push the example further: thumbnails with [Pillow](https://pillow.readthedocs.io/), the [Spaces CDN](https://docs.digitalocean.com/products/spaces/how-to/enable-cdn/) in front for speed, or a [Managed Database](https://www.digitalocean.com/products/managed-databases) for upload metadata.

And here's the open invitation: **the whole thing is open source (MIT), and I'd genuinely love contributions.** I've left a handful of [good first issues](https://github.com/oceanforge/spaces-gallery/issues) — the three above are in there — so if you've been looking for a small, friendly repo to make your first PR against, or you just want to add a feature you wish it had, go for it. Fork it, open a PR, no permission needed.

Code, issues, and the full template: **[github.com/oceanforge/spaces-gallery](https://github.com/oceanforge/spaces-gallery)**. If you build something with it, I'd love to see it.

> Heads up: a running app + bucket cost a few dollars a month. If you spun this up just to try it, destroy the app and bucket and delete the Spaces key when you're done.

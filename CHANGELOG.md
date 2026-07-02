# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Drag-and-drop image uploads: drop an image onto the upload card to upload it,
  with the file picker kept as an accessible fallback ([#18]).
- Display total image count on the index page using `pagination.total` ([#19]).

## [0.4.0] - 2026-06-29

### Added
- pytest test suite covering uploads, deletes, pagination, and the helper
  functions, run in CI via a dependency-free in-memory S3 fake ([#23]).
- Polished empty state (card layout) and a browser favicon ([#22]).
- Copy-to-clipboard button on each gallery item for grabbing an image's public
  URL ([#17]).
- Display image file size and upload date beneath gallery thumbnails.

## [0.3.0] - 2026-06-21

### Added
- Gallery pagination with Newer/Older navigation (12 images per page) ([#5]).
- Thumbnail generation on upload (via Pillow); the grid serves smaller images and
  falls back to the full image when no thumbnail exists ([#4]).

## [0.2.0] - 2026-06-21

### Added
- Pre-commit hooks (`ruff` lint plus `trailing-whitespace`, `end-of-file-fixer`,
  `check-yaml`, `check-added-large-files`) to catch issues before they reach CI ([#12]).

### Changed
- CI now runs `pre-commit run --all-files`, so local checks and CI stay in sync.

## [0.1.1] - 2026-06-21

### Added
- Delete control on each gallery item that removes the object from Spaces ([#2]).
- Validation feedback (flash messages) for rejected uploads — wrong type, no file,
  not configured, and files over the 8 MB limit ([#1]).

## [0.1.0] - 2026-06-21

### Added
- Flask app that uploads images to DigitalOcean Spaces and renders a gallery.
- Health check endpoint at `/health`.
- App Platform spec at `.do/app.yaml`.
- Local development workflow via `.env` and `python app.py`.
- CI workflow (lint) and release workflow (GitHub Releases on tags).

[Unreleased]: https://github.com/oceanforge/spaces-gallery/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/oceanforge/spaces-gallery/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/oceanforge/spaces-gallery/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/oceanforge/spaces-gallery/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/oceanforge/spaces-gallery/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/oceanforge/spaces-gallery/releases/tag/v0.1.0
[#1]: https://github.com/oceanforge/spaces-gallery/issues/1
[#2]: https://github.com/oceanforge/spaces-gallery/issues/2
[#4]: https://github.com/oceanforge/spaces-gallery/issues/4
[#5]: https://github.com/oceanforge/spaces-gallery/issues/5
[#12]: https://github.com/oceanforge/spaces-gallery/issues/12
[#17]: https://github.com/oceanforge/spaces-gallery/issues/17
[#18]: https://github.com/oceanforge/spaces-gallery/issues/18
[#19]: https://github.com/oceanforge/spaces-gallery/issues/19
[#22]: https://github.com/oceanforge/spaces-gallery/issues/22
[#23]: https://github.com/oceanforge/spaces-gallery/issues/23

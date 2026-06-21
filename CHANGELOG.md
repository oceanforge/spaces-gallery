# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Gallery pagination with Newer/Older navigation (12 images per page) ([#5]).

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

[Unreleased]: https://github.com/oceanforge/spaces-gallery/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/oceanforge/spaces-gallery/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/oceanforge/spaces-gallery/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/oceanforge/spaces-gallery/releases/tag/v0.1.0
[#1]: https://github.com/oceanforge/spaces-gallery/issues/1
[#2]: https://github.com/oceanforge/spaces-gallery/issues/2
[#5]: https://github.com/oceanforge/spaces-gallery/issues/5
[#12]: https://github.com/oceanforge/spaces-gallery/issues/12

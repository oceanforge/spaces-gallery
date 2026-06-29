# Contributing

Thanks for taking a look! This is a small showcase project, so contributions of
any size are welcome — fixing a typo counts.

## Getting started

1. Fork and clone the repo.
2. Set up the app locally (see the [README](README.md#run-it-locally)).
3. Enable the pre-commit hooks (one-time):
   ```bash
   pip install pre-commit
   pre-commit install
   ```
   They run automatically on each commit; run them against everything with
   `pre-commit run --all-files`. CI runs the same checks, so this keeps you green.
4. Create a branch: `git checkout -b my-change`.
5. Make your change and test it locally, including `pytest` (see
   [Running the tests](#running-the-tests)).
6. Add a line under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md) describing
   the change (see [Updating the changelog](#updating-the-changelog) below).
7. Open a pull request describing what and why. The PR template includes a short
   checklist — the changelog entry is on it.

## Running the tests

Install the dev dependencies and run the suite:

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a small in-memory fake for DigitalOcean Spaces, so they need no
credentials or network access. CI runs `pytest` on every pull request.

## Guidelines

- Keep it simple. The value of this repo is that it's small and easy to read.
- Match the existing style; keep functions short and commented where helpful.
- One logical change per pull request.
- Add a CHANGELOG entry for anything user-facing.

## Updating the changelog

We follow [Keep a Changelog](https://keepachangelog.com/). Every user-facing
change gets a bullet under the `## [Unreleased]` heading, grouped by type
(`Added`, `Changed`, `Fixed`, …) and ending with the issue link, e.g.:

```markdown
## [Unreleased]

### Added
- Copy-to-clipboard button on each gallery item ([#17]).
```

Add the matching link definition at the bottom of the file if it isn't there
yet (`[#17]: https://github.com/oceanforge/spaces-gallery/issues/17`). Pure
docs/typo fixes don't need an entry.

## Good first issues

Look for issues labeled [`good first issue`](https://github.com/oceanforge/spaces-gallery/labels/good%20first%20issue).

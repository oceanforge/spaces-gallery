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
5. Make your change and test it locally.
6. Open a pull request describing what and why.

## Guidelines

- Keep it simple. The value of this repo is that it's small and easy to read.
- Match the existing style; keep functions short and commented where helpful.
- One logical change per pull request.

## Good first issues

Look for issues labeled [`good first issue`](https://github.com/oceanforge/spaces-gallery/labels/good%20first%20issue).

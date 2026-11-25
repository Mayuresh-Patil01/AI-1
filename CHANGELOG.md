# Changelog

All notable changes to SORTIFIED. Versions follow [semantic versioning](https://semver.org):
**MAJOR**.**MINOR**.**PATCH** — patch = bug fixes, minor = new features, major = big breaking changes.

Add new entries under **Unreleased** as you work; rename it to the version number when releasing.

## [Unreleased]

## [1.1.0] — 2026-11-25
### Added
- Database migrations: libraries from older versions upgrade automatically, with a backup first.
- `setup.cmd` (one-time setup, auto-detects NVIDIA GPU) and `dev.cmd` (starts engine + UI).
- Automated tests for the engine (21 tests; no AI model download needed).
- GitHub Actions CI: runs engine tests and the UI build on every push and pull request.
- Development workflow guide in `docs/DEVELOPMENT.md`.

## [1.0.0] — 2026-11-25 (commit 86323b7)
### Added
- AI albums with CLIP: auto-discover (k-means, auto-named) and custom categories (zero-shot).
- Album editing: rename, create, delete, multi-select, drag-and-drop to move.
- Export albums to folders (copy-only) with preview and undo.
### Fixed
- Thumbnails could show stale pictures after a folder was removed.

## [0.1.0] — 2026-11-25 (commit 8b17df1)
### Added
- Python engine that scans folders incrementally into SQLite and serves thumbnails.
- React UI with folder sidebar, photo grid and lightbox.

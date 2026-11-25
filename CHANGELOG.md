# Changelog

All notable changes to SORTIFIED. Versions follow [semantic versioning](https://semver.org):
**MAJOR**.**MINOR**.**PATCH** — patch = bug fixes, minor = new features, major = big breaking changes.

Add new entries under **Unreleased** as you work; rename it to the version number when releasing.

## [Unreleased]
### Fixed
- `setup.cmd` now uses `npm ci`, so it no longer rewrites `ui/package-lock.json` (which could break CI).

## [2.0.0] — 2026-11-25
### Added
- **Search** photos by describing them ("sunset over the sea", "receipts"), using the CLIP embeddings.
- **Cleanup** view:
  - Duplicates: identical files and look-alike copies (resized, re-compressed, blurred), with the best one suggested to keep.
  - Blurry and too-dark photos, with adjustable thresholds.
  - "Keep" hides photos from Cleanup; "Move to Recycle Bin" frees space (restorable from the Windows Recycle Bin).
- **Export folder templates**: `{year}/{album}`, `{year}/{month} - {month_name}/{album}`, or a custom pattern.
- Shared "Analyze library" pass (quality metrics + AI embeddings) used by organizing, search and Cleanup.
- Database migrations 2–4 (photo quality metrics). Existing libraries upgrade automatically.
### Changed
- Export undo now also removes empty parent folders it created (e.g. year folders).
### Fixed
- Different screenshots with the same layout are no longer reported as duplicates.
- Dark-mode screenshots and night photos are no longer reported as "too dark".

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

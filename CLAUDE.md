# SORTIFIED

AI-powered **local** photo organizer. Users point it at folders of images; it groups them into
albums with AI, finds duplicates/blurry shots, and writes organized folders — all offline.

## Owner context
- Owner knows **basic Python**, little/no JavaScript. Explain JS/TS/React changes briefly; keep Python readable.
- Works on two PCs, synced via GitHub (`main` branch). Always `git pull` before starting, push when done.
  - Office laptop: no GPU, 16 GB RAM → everything must work on CPU.
  - Personal laptop: RTX 3050 (CUDA) → use GPU when available, never require it.

## Architecture
- `engine/` — Python 3.13, FastAPI. Scans folders, runs AI models, stores results in SQLite.
  Serves a JSON API on `http://127.0.0.1:8000`.
- `ui/` — React + TypeScript + Vite + Tailwind. Dev server on `http://localhost:5173`, calls the engine API.
- `docs/` — roadmap and design notes. Later: GitHub Pages showcase site.
- Later: package as a desktop app (Tauri), installer via GitHub Releases.

## Running locally
- `setup.cmd` — one-time/after-pull setup (venv, CUDA torch if NVIDIA, npm install).
- `dev.cmd` — starts engine (with reload) + UI and opens the browser.
- Full workflow for the owner: `docs/DEVELOPMENT.md`.

## Change workflow (follow for every change)
- `git pull` first. Small fixes may go straight to `main`; features go on `feature/<name>` or `fix/<name>`
  branches and merge via Pull Request once CI is green.
- Run `engine\.venv\Scripts\python -m pytest` (from `engine/`) and `npm run build` (from `ui/`) before committing.
  Add or update tests in `engine/tests/` for engine behaviour changes. Tests use `fake_ai`; never download models in tests.
- **Database changes: append a new entry to `MIGRATIONS` in `engine/sortified/db.py`. Never edit an existing one.**
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for user-visible changes.
- Releases: bump version in both `engine/sortified/__init__.py` and `ui/package.json` (+ `npm install --package-lock-only`),
  move changelog notes under the version, commit, `git tag vX.Y.Z`, `git push --follow-tags`.

## Ground rules
- **Never modify or delete the user's original photos** without an explicit preview + confirmation.
  Default is copy or virtual albums. Every file operation must be logged so it can be undone.
- The engine only reads files inside folders the user has added (no arbitrary path access).
- No secrets in the repo; use `.env` (git-ignored).
- Large files (models, caches, thumbnails, databases) never go in git.

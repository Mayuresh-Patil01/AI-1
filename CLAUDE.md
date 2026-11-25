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
```powershell
# engine (first time: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt)
cd engine; .venv\Scripts\python -m uvicorn sortified.main:app --reload --port 8000
# ui (first time: npm install)
cd ui; npm run dev
```

## Ground rules
- **Never modify or delete the user's original photos** without an explicit preview + confirmation.
  Default is copy or virtual albums. Every file operation must be logged so it can be undone.
- The engine only reads files inside folders the user has added (no arbitrary path access).
- No secrets in the repo; use `.env` (git-ignored).
- Large files (models, caches, thumbnails, databases) never go in git.

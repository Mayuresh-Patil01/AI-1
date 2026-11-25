# SORTIFIED

**AI-powered photo organizer that runs entirely on your own PC.**
Point it at your messy photo folders and it sorts them into albums, finds duplicates and blurry shots,
and writes neatly organized folders — your photos never leave your machine.

> 🚧 Early development — see [docs/ROADMAP.md](docs/ROADMAP.md).

## Stack
- **Engine:** Python · FastAPI · SQLite · Pillow (AI: CLIP/SigLIP, coming in v1)
- **UI:** React · TypeScript · Vite · Tailwind CSS

## Run it locally

**1. Engine** (first time only: create the virtual environment and install packages)
```powershell
cd engine
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Start it:
```powershell
cd engine
.venv\Scripts\python -m uvicorn sortified.main:app --reload --port 8000
```

**2. UI** (in a second terminal; first time only: `npm install`)
```powershell
cd ui
npm run dev
```
Open http://localhost:5173 and paste a folder path into the sidebar.

## Working across PCs
- **Before starting:** `git pull`
- **When done:** `git add .` → `git commit -m "describe change"` → `git push`

App data (database, thumbnail cache) lives in `~/.sortified`, separately on each PC, and is never committed.

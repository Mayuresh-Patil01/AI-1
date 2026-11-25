# SORTIFIED

**AI-powered photo organizer that runs entirely on your own PC.**
Point it at your messy photo folders and it sorts them into albums, finds duplicates and blurry shots,
and writes neatly organized folders — your photos never leave your machine.

> 🚧 Early development — see [docs/ROADMAP.md](docs/ROADMAP.md).

## Features (v1)
- **Organize with AI — auto-discover:** groups similar photos and names each album ("Sunsets", "Documents", …)
- **Organize with AI — your categories:** type "Family, Food, Receipts" and the AI fills them; unclear photos go to *Unsorted*
- Rename, create and delete albums; select photos (Ctrl/Shift-click) and drag them onto any album
- **Export** albums as real folders — copies only, with a preview first and one-click **undo**
- Runs offline on CPU; uses an NVIDIA GPU automatically when available

## How the AI works
SORTIFIED uses [CLIP](https://github.com/mlfoundations/open_clip), a model that maps images and text
into the same vector space. Similar photos get similar vectors, so **k-means clustering** finds natural
groups, and comparing a group's centre with ~120 label phrases ("a photo of sunsets") names it.
For custom categories, each photo is matched to the category text it's most similar to (zero-shot classification).

## Stack
- **Engine:** Python · FastAPI · SQLite · PyTorch · OpenCLIP · scikit-learn
- **UI:** React · TypeScript · Vite · Tailwind CSS

## Run it locally
Requires Python 3.12+, Node 20+ and Git (Windows).

```powershell
.\setup.cmd    # first time (and after pulling dependency changes)
.\dev.cmd      # starts the engine + UI and opens http://localhost:5173
```
`setup.cmd` installs the GPU build of PyTorch automatically if the PC has an NVIDIA card.
The first "Organize with AI" downloads the CLIP model (~600 MB, once per PC).

App data (database, thumbnail cache) lives in `~/.sortified`, separately on each PC, and is never committed.

## Development
- Workflow, branches, tests and releases: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- What changed: [CHANGELOG.md](CHANGELOG.md) · What's next: [docs/ROADMAP.md](docs/ROADMAP.md)
- Tests: `cd engine; .venv\Scripts\python -m pytest` — also run automatically by GitHub Actions on every push.

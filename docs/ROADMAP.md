# SORTIFIED Roadmap

## v0.1 — Foundation ✅
- [x] Repo, engine + UI skeletons
- [x] Add a folder → list its images with thumbnails in a grid

## v1 — First working product ✅
- [x] AI image embeddings (CLIP ViT-B/32, CPU or CUDA)
- [x] Auto-discover albums (k-means clustering) with AI-suggested names
- [x] Custom categories ("pets, receipts, cars") via zero-shot matching + strictness
- [x] Album view, rename/delete/create albums, multi-select, drag-and-drop to move
- [x] Export albums to folders (copy) with a preview step + undo log
- [x] Incremental rescans (only new/changed files, stale embeddings dropped)

### v1 polish ideas
- [ ] Progress for model download, cancel button for long jobs
- [ ] Native folder picker (comes with the Tauri desktop app)
- [ ] Keep hand-moved photos when re-organizing

## v2 — Cleanup & control ✅
- [x] Exact + near-duplicate detection, keep-the-best suggestion
- [x] Blurry / dark photo detection, Keep or move to Recycle Bin
- [x] Natural-language search ("red car at night")
- [x] Folder naming templates: `{year}/{month}/{album}`

### Moved to later
- [ ] Screenshots, memes, documents separated from photos (custom categories cover most of this today)
- [ ] Move mode for export (copy-only for now, which is safer)

## v3 — Smart albums
- [ ] People albums (face clustering, name once)
- [ ] Events from date + GPS ("Goa Trip, Dec 2025")
- [ ] Map view, timeline, "On this day"
- [ ] Learns from user corrections

## v4 — Ship it
- [ ] Google Drive import/export (OAuth)
- [ ] Watch folder auto-sort + rules
- [ ] Desktop app (Tauri) + installer on GitHub Releases
- [ ] GitHub Pages showcase site with screenshots + demo video

## Stretch
- [ ] Local AI captions/tags (small vision model)
- [ ] Shareable web gallery / slideshow export
- [ ] Google Photos via Picker API

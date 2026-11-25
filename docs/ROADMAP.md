# SORTIFIED Roadmap

## v0.1 — Foundation ✅ (in progress)
- [x] Repo, engine + UI skeletons
- [x] Add a folder → list its images with thumbnails in a grid

## v1 — First working product
- [ ] AI image embeddings (CLIP/SigLIP, CPU or CUDA)
- [ ] Auto-discover albums (clustering) with AI-suggested names
- [ ] Custom categories ("pets, receipts, cars") via zero-shot matching
- [ ] Album view in the UI, move photos between albums by drag-and-drop
- [ ] Export albums to folders (copy) with a preview step + undo log
- [ ] Incremental rescans (only new/changed files)

## v2 — Cleanup & control
- [ ] Exact + near-duplicate detection, keep-the-best suggestion
- [ ] Blurry / dark / accidental photo detection
- [ ] Screenshots, memes, documents separated from photos
- [ ] Natural-language search ("red car at night")
- [ ] Folder naming templates: `{year}/{month}/{album}`
- [ ] Copy / move / virtual-album modes

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

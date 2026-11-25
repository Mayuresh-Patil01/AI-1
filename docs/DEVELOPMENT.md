# Developing SORTIFIED

How to make changes cleanly, on either PC, without breaking anything.

## First time on a PC
```powershell
git clone https://github.com/Mayuresh-Patil01/AI-1.git
cd AI-1
git config user.name "Mayuresh Patil"
git config user.email "<your email>"
.\setup.cmd
```
`setup.cmd` creates the Python environment, installs the GPU build of PyTorch if the PC has an
NVIDIA card, and installs the UI packages. It's safe to run again any time.

## Every session
```powershell
git pull          # 1. get changes made on the other PC
.\setup.cmd       # 2. only if requirements.txt or package.json changed
.\dev.cmd         # 3. starts engine + UI and opens the browser
```
When you're done, commit and push (see below) so the other PC can pick it up.

## Small change vs. new feature

**Small fix or tweak** (a typo, a colour, a one-file bug fix) → commit straight to `main`:
```powershell
git add .
git commit -m "Fix album count after delete"
git push
```

**New feature or anything risky** (e.g. duplicate detection) → use a branch, so `main` always works:
```powershell
git switch -c feature/duplicates      # create the branch
# ...work, commit, and push as often as you like:
git push -u origin feature/duplicates
```
- Switching PCs mid-feature: on the other PC run `git fetch` then `git switch feature/duplicates`.
- When it's finished: open a Pull Request on GitHub (`feature/duplicates` → `main`).
  CI runs the tests automatically; merge when it's green ✅, then delete the branch.
- Back on each PC: `git switch main` and `git pull`.

Branch names: `feature/...` for new things, `fix/...` for bug fixes.

## Before every commit
```powershell
cd engine; .venv\Scripts\python -m pytest     # engine tests (a few seconds)
cd ..\ui; npm run build                        # UI type-check + build
```
CI runs the same two checks on GitHub after every push. A red ❌ next to a commit means something broke.

## Changing the database
Never edit an existing migration. Append a new one to `MIGRATIONS` in `engine/sortified/db.py`,
for example `"ALTER TABLE images ADD COLUMN blur_score REAL;"`, and add a test in `engine/tests/test_db.py`.
On startup, every PC's library upgrades itself and keeps a backup (`library.v1.bak`) first.

## Releasing a version
1. Move the **Unreleased** notes in `CHANGELOG.md` under a new version heading.
2. Update the version in **both** `engine/sortified/__init__.py` and `ui/package.json`
   (a test fails if they differ).
3. Commit, then tag and push:
   ```powershell
   git commit -am "Release v1.2.0"
   git tag -a v1.2.0 -m "SORTIFIED v1.2.0"
   git push --follow-tags
   ```
Tags show up under *Releases* on GitHub, so you can always go back to any version.

## Where things live
| Path | What |
|---|---|
| `engine/sortified/` | Python engine (API, scanner, AI, albums, export) |
| `engine/tests/` | Engine tests (`pytest`) |
| `ui/src/` | React UI |
| `docs/ROADMAP.md` | What's planned |
| `CHANGELOG.md` | What changed in each version |
| `~/.sortified/` | Your library database + thumbnail cache (per PC, never in git) |

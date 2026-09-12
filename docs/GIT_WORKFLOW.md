# Git Workflow — 3 people, ~13 hours, zero merge drama

The whole strategy rests on one fact from `ARCHITECTURE.md`: **each person owns whole folders.** So we do not need a clever branching model. We need a simple one that nobody can get wrong at 1 AM.

---

## Branches

| Branch | Purpose | Who pushes |
|---|---|---|
| `main` | **Always demoable.** Only ever receives merges from `dev` that have been run locally. Tagged at each checkpoint. | Saheb only |
| `dev` | Integration. Feature branches PR into here. May briefly be broken. | anyone, via PR |
| `feat/core-security` | Part A | Saheb |
| `feat/geo-ai` | Part B | Person B |
| `feat/frontend-map` | Part C | Person C |

Three feature branches. That is the entire model. **Do not create more branches.** Do not create per-task branches — you will spend more time on git than on code.

---

## One-time setup (do this TONIGHT, 12 Sep)

**Saheb, on your machine:**

```bash
# 1. Create the repo on GitHub first (empty, private, no README, no .gitignore)
cd "D:/BWB Project file"
git init
git branch -M main

# 2. Drop in the skeleton + docs, then:
git add .
git commit -m "initial project skeleton and docs"
git remote add origin https://github.com/DebanganMALI/TerraPulse.git
git push -u origin main

# 3. Create dev off main
git checkout -b dev
git push -u origin dev

# 4. Create your own feature branch
git checkout -b feat/core-security
git push -u origin feat/core-security
```

Then on GitHub: **Settings → Collaborators → add both teammates** with write access.

**B and C, once added:**

```bash
git clone https://github.com/DebanganMALI/TerraPulse.git
cd terrapulse
git checkout dev
git pull

# B runs:
git checkout -b feat/geo-ai && git push -u origin feat/geo-ai
# C runs:
git checkout -b feat/frontend-map && git push -u origin feat/frontend-map
```

### Branch protection (2 minutes, worth it)

GitHub → Settings → Branches → Add rule for `main`:
- ✅ Require a pull request before merging
- ✅ Require approval: 1
- ❌ Leave everything else off (status checks will slow you down at 1 AM)

Skip protection on `dev`. You need speed there.

---

## The loop everyone runs, all day

Commit small and often. Every 20–30 minutes, or whenever something works.

```bash
# before you start a chunk of work
git checkout feat/<yours>
git pull origin dev --no-rebase      # take everyone else's latest
# ...write code...
git add -A
git commit -m "add ndwi threshold tuning"
git push
```

That `git pull origin dev` at the *start* of each chunk is the whole trick. It means you are never more than 30 minutes behind, so integration is never a big-bang merge.

---

## Merging into `dev`

Two options. Use whichever the moment calls for.

**Fast path (default, use this most of the day):**

```bash
git checkout dev
git pull
git merge feat/<yours> --no-ff -m "merge <part>: <what landed>"
git push origin dev
git checkout feat/<yours>
git merge dev            # keep your branch current
```

**PR path (use for anything that touches `schemas/` or before a checkpoint):**

```bash
git push
# then open a PR on GitHub: feat/<yours> -> dev, tag the others, merge
```

---

## Promoting to `main` — only at checkpoints

Saheb does this, and only after running the app and confirming the demo works:

```bash
git checkout main
git pull
git merge dev --no-ff -m "checkpoint: mentor round 1 build"
git tag -a demo-r1 -m "vertical slice: auth + map + mock analysis"
git push origin main --tags
```

Tags to create, in order: `demo-r1`, `demo-r2`, `demo-final`.

**Why this matters:** if something catastrophically breaks at 09:30 on Day 2, you run `git checkout demo-r2` and you have a working demo in 20 seconds. This has saved more hackathon teams than any clever code.

---

## Conflict resolution

Because of folder ownership, conflicts should only ever happen in three places:

| File | Rule |
|---|---|
| `backend/app/schemas/*` | **A always wins.** B/C: `git checkout --theirs` on a pull from dev, or just ask A. Never edit these yourself. |
| `requirements.txt` | Keep both lines. Alphabetise. Pin versions. |
| `README.md` | A owns it. Don't edit during the hack. |

If you hit a conflict anywhere else, someone worked outside their folder. Stop, tell the group, fix the ownership — do not just resolve it and move on.

**Emergency abort:**
```bash
git merge --abort        # back out of a bad merge
git stash                # park uncommitted work
git reset --hard origin/feat/<yours>   # nuke local, match remote (LOSES WORK)
```

---

## `.gitignore` — commit this before anything else

```gitignore
# python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.ruff_cache/

# env & secrets
.env
.env.local
*.pem
*.key

# data & models (too big for git)
data/scenes/**/*.tif
data/scenes/**/*.tiff
data/scenes/**/*.jp2
data/models/*.joblib
backend/app/static/overlays/**/*.png

# keep folder structure + metadata
!data/scenes/**/meta.json
!data/env/*.csv
!**/.gitkeep

# db
*.db
*.sqlite3

# node
node_modules/
dist/
.vite/

# editors / tooling
.vscode/
.idea/
.antigravity/
.aider*
.cursor/
.claude/
*.log
.DS_Story
Thumbs.db
```

**Note the `data/scenes/**/*.tif` line.** GeoTIFFs are 50–800 MB. If you commit one, the repo becomes unusable for your teammates on venue wifi. Share scenes over a **USB stick or a shared Google Drive folder**, and commit only `meta.json`.

---

## Commit hygiene — and the AI question

You asked that the work not read as AI-generated. Git history is where that shows most, so:

**Do:**
- Short, lowercase, specific, imperative: `add ndwi threshold tuning`, `fix cors origin for vite dev port`, `handle empty polygon list in vectorize`
- Commit *partial* work with honest messages: `wip: risk grid, cells not aligned yet`
- Let the history be messy in a human way — a revert, a `fix typo`, a `oops wrong path`. Real history has those.

**Don't:**
- No `Co-Authored-By:` trailers, no `Generated with` lines, no AI tool links in commit bodies. Strip them if your IDE adds them.
- No 400-word commit bodies. Nobody writes those at 2 AM.
- Don't commit 40 files in one commit at 01:00 with the message `implement complete backend`. That is the single biggest tell. Spread work across many small commits with plausible timestamps.
- Don't let all three of you commit in identical style. You naturally won't — don't standardise it.

**Antigravity IDE specifically:** check `.antigravity/`, `.aider*`, and any agent rules/config file are git-ignored (they're in the list above) and that the IDE isn't appending attribution to commit messages. Run `git log -1 --format=%B` after your first commit and read it.

**Code comments** (this is a `CONTRIBUTING`-level rule, apply it everywhere):
- No docstrings on self-explanatory functions. `def get_user(username): ...` needs nothing.
- No narration comments: `# loop over events`, `# return the result`, `# Step 3: classify`.
- Comment **only** non-obvious *decisions*: a magic threshold, a CRS gotcha, a security rationale, a workaround for a library bug.
- Good: `# NDWI > 0.2 is the standard open-water cut for Sentinel-2 L2A; lower picks up wet soil`
- Good: `# resolve() before the containment check — a symlink in DATA_DIR would escape otherwise`
- Bad: `# This function computes the NDWI index from the green and NIR bands and returns an array`
- Type hints instead of describing types in prose.

---

## Emergency: "the demo is broken and judging is in 20 minutes"

```bash
git checkout demo-r2          # last known-good tag
# demo from there. Do not try to fix main.
```

Have this written on paper. At 11:00 on Day 2 nobody will remember it.

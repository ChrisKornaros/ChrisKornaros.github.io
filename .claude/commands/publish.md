---
description: Convert a vault draft to a site .qmd and ship it through the branch→PR→merge→deploy flow.
argument-hint: <vault-draft-path> | --all
allowed-tools: Bash, Read, AskUserQuestion
---

You are running the **publish** workflow for ChrisKornaros.github.io: take a
ready Obsidian draft from `~/vault/writing/`, convert it to Quarto, render, and
deploy it through the canonical git-flow (branch → PR → merge = deploy).

Arguments: `$ARGUMENTS` (a vault draft path, or `--all`; may include `--force`).

Do all of this from the repo root (`~/vault/projects/ChrisKornaros.github.io`).

## 1. Convert (deterministic — the Python CLI does the transform, no git)

Run: `uv run publish $ARGUMENTS`

- Publishing **is** the act of un-drafting: a single-file publish converts the
  file regardless of its draft flag and clears `draft: true` from the vault
  source (prints "un-drafted vault source"). `--all` still skips anything still
  tagged `draft: true`.
- On success it prints the `.qmd` (and any copied images / new category
  `index.qmd`) it wrote under `source/pages/`. Note the section + slug from the
  output — you need them for the branch name.
- The vault `.md` edit is just the one-line draft removal; mention it but you do
  not commit the vault (separate repo) — it stays as Chris's canonical source.

## 2. Render (verification + regenerates the tracked `docs/`)

Run: `uv run quarto render source`

- It must finish with `Output created:`. The two pre-existing `WARN` lines about
  the `../docs` output path are expected — ignore them. Any real error: stop and
  report it; the draft is not publishable yet.

## 3. Ship it via the canonical git-flow-session-end loop

Follow [modules/git-flow-session-end/index.md](../../modules/git-flow-session-end/index.md)
(short form in [CLAUDE.md](../../CLAUDE.md)). Never push to `main` directly.

1. Branch: `publish/<section>-<slug>` (single file) or `publish/sync-<YYYY-MM-DD>`
   (`--all`). Create it with `git switch -c`.
2. `git add` the new/changed **`source/`** files (the `.qmd`, copied
   `images/`, any new category `index.qmd`) **and** the regenerated **`docs/`**
   (it's tracked — keep it in sync with source).
3. Commit (describe what was published), `git push -u origin <branch>`,
   then `gh pr create` with a *Delivered + Verified* footer. Print the PR URL.
4. **AskUserQuestion** merge popup: "PR is up: `<url>`. Merging it in the GitHub
   UI deploys to GitHub Pages. Has it been merged?" — options **Merged** /
   **Not yet** / **Changes requested / closed**. Don't end the turn waiting.
5. Verify: `gh pr view <N> --json state,mergedAt`. Only if `state == "MERGED"`
   proceed to cleanup; otherwise re-pop / stop.
6. Cleanup: `git switch main && git pull --ff-only && git branch -d <branch> &&
   git fetch --prune`.
7. Print the fixed-format **Session end** summary from CLAUDE.md.

## Notes

- The vault `.md` stays canonical and is **not** modified here; re-running
  `/publish` on an edited draft overwrites the `.qmd` (idempotent).
- The CLI reads from `~/vault/writing` and writes only into this repo's
  `source/`. It never runs git — that's this skill's job.

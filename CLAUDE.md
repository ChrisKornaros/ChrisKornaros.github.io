# ChrisKornaros.github.io — agent contract

Chris Kornaros's personal website: a [Quarto](https://quarto.org) website
(guides, projects, blogs) whose source `.qmd` lives in [source/](source/),
renders to [docs/](docs/), and is deployed to GitHub Pages by
[.github/workflows/publish.yml](.github/workflows/publish.yml) on every push to
`main`. Python tooling is managed with [uv](https://docs.astral.sh/uv/)
(`pyproject.toml` + `uv.lock`, Python 3.13).

## Composed modules

Vendored from
[agentic_optimization_research/modules/](https://github.com/ChrisKornaros/agentic_optimization_research/tree/main/modules)
— see [MODULES.md](MODULES.md) for versions and source commits. The link is the
load-bearing thing: when a module's canonical version bumps, re-vendor and this
repo inherits the update. Project-local rules below override a vendored module
on conflict.

| Module | Type | Why it's here |
|---|---|---|
| [git-flow-no-direct-main](modules/git-flow-no-direct-main/index.md) | guardrail | Work happens on a branch + PR; never commit or push straight to `main`. `main` auto-deploys to GitHub Pages, so a direct push publishes unreviewed. |
| [git-flow-session-end](modules/git-flow-session-end/index.md) | workflow | The commit → PR → merge-popup → verify-before-cleanup session-end loop. Short form below. |
| [stay-in-project-tree](modules/stay-in-project-tree/index.md) | guardrail | Keep filesystem writes inside this repo; don't touch system dirs, credential stores, shell rc files, or the global Claude config. |
| [no-sudo-as-shortcut](modules/no-sudo-as-shortcut/index.md) | guardrail | No `sudo`/`su`/`chmod 777`/privileged-container escalation as a workaround — fix the actual problem instead. |
| [no-cat-head-via-bash](modules/no-cat-head-via-bash/index.md) | guardrail | Use the Read/Edit/Write tools, not `cat`/`head`/`sed` through Bash, to inspect files. Ships the `pre_read_guard.py` PreToolUse hook wired in [.claude/settings.json](.claude/settings.json). |
| [python-uv-only](modules/python-uv-only/index.md) | guardrail | All Python ops go through `uv` (`uv run`, `uv sync`, `uv add`) — no bare `pip`/`poetry`/`conda`. Matches the existing `uv.lock` + `.venv`. |

### Session-end loop — short form

Canonical rule: [modules/git-flow-session-end/index.md](modules/git-flow-session-end/index.md).
When the branch's scope is met and verified, run these **in one response**:

1. **Sync tracking docs to reality** — update any requirements/roadmap notes
   *and* this `CLAUDE.md` (status lines, the Composed-modules ledger if a module
   was vendored/bumped). If nothing meaningful changed, say so in the commit body.
2. **Commit → push → open PR in one response** — `git add` → `git commit` →
   `git push -u origin <branch>` → `gh pr create` with a *Delivered + Verified*
   footer. Print the PR URL.
3. **Pop the merge question via `AskUserQuestion`** — "PR is up: `<url>`. Merge
   it in the GitHub UI when ready. Has it been merged?" Options: **Merged** ·
   **Not yet** · **Changes requested / closed**. Don't end the turn waiting.
4. **Verify before cleanup** — run `gh pr view <N> --json state,mergedAt`. If
   `state != "MERGED"`, say so and re-pop the question; do **not** run the
   cleanup sequence on an unverified claim.
5. **Sync and clean up** (only after `MERGED` confirmed):
   `git switch main && git pull --ff-only && git branch -d <branch> && git fetch --prune`.
6. **Print the fixed-format Session end summary:**

   ```markdown
   ## Session end

   - **Branch merged:** `<branch>` → `main` (PR #<n>)
   - **Delivered:** <one-line outcome>
   - **Verified:** <how — render check, manual review>
   - **Docs synced:** <files touched, or "no status changes">
   - **Local state:** `main` up to date, `<branch>` deleted

   Session done.
   ```

If "Not yet" comes back, re-pop after a pause. If "Changes requested", stop the
cleanup and wait for review notes — the branch is still live work.

## Project-specific

- **`source/` is the source of truth; `docs/` is generated.** Edit `.qmd` files
  (and `_quarto.yml`, `_brand.yml`, `brand/`) under [source/](source/). Never
  hand-edit the rendered HTML/JSON under [docs/](docs/) — it's overwritten on
  the next render. Regenerate with `quarto render` from `source/` (or
  `uv run quarto render source` from the repo root).
- **Publishing is automatic.** Pushing to `main` triggers the publish workflow,
  which renders `source/` and deploys `docs/` to GitHub Pages. Chris merges PRs
  in the GitHub UI — that merge *is* the deploy. Don't run `quarto publish`
  without asking.
- **Branch slugs:** `feat/<slug>`, `docs/<slug>`, `chore/<slug>`, and
  `publish/<section>-<slug>` (content published from the vault). `main` is the
  only long-lived branch.
- **Verification = a local render.** There's no test suite; confirm a change by
  rendering `source/` cleanly and (when it matters) previewing with
  `quarto preview source`.

## Publishing pipeline (vault → site)

Long-form content is **drafted in Obsidian** under `~/vault/writing/<section>/`
(sections: `guides`, `research`, `blogs`, `recipes`) and tagged `draft: true`.
A draft is the canonical source; the site `.qmd` is generated from it.

- **Scaffold a draft:** `uv run new <section> "<Title>" [--category <Cat>]`
  (recipes require `--category`, mirrored as a subfolder). Pre-fills frontmatter.
- **Publish one (or all):** the **`/publish`** skill
  ([.claude/commands/publish.md](.claude/commands/publish.md)) runs the
  deterministic converter (`uv run publish <draft>` / `--all`), then
  `quarto render`, then the canonical session-end loop on a
  `publish/<section>-<slug>` branch. Merge = deploy. A single-file publish
  **un-drafts the vault source** (clears `draft: true`); `--all` skips anything
  still tagged draft.
- **The converter** lives in [site_publish/](site_publish/) and does the
  transform only — never git. It maps Obsidian → Quarto (wikilinks, `![[embeds]]`
  → copied `images/`, callouts, strips `#tags`/`draft`), routes by section
  (recipes → `recipes/<Category>/`, others → `<section>/posts/`), generates the
  Substack embed for blogs (normalizing a "Share"-link `open.substack.com/pub/…`
  URL with tracking params to the canonical `<pub>.substack.com/p/<slug>` form)
  and the `video:` embed for recipes, and is idempotent (re-publish overwrites
  the `.qmd`).
- **No `_quarto.yml` edits per publish:** the navbar links to listing pages, the
  guides/blogs sidebars auto-list their `posts/` directory, and the recipes
  sidebar lists category index pages, so a newly published post appears
  automatically. The one exception is adding a brand-new recipe *category*
  folder — that needs a one-line entry under the recipes sidebar `contents`
  (Quarto 1.9 renders bare globs as literal text and crashes on the `auto:` glob
  form, so categories are listed explicitly to keep each page's sidebar slim
  rather than embedding the whole recipe tree).
- **`docs/` is committed alongside `source/`** in a publish PR (it's tracked and
  re-rendered on every render). CI re-renders on merge.

## Verify changes to this contract

No build. Relative links in this file resolve, each vendored module has an
`index.md`, and [MODULES.md](MODULES.md) has one row per installed module.

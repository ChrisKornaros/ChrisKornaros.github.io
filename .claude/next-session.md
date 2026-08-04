# Next session kickoff

**Context:** The Pages source gap is closed (2026-08-04, session after PR
#22): GitHub Pages now serves the **`gh-pages` branch** (CI render from
publish.yml) instead of `main:/docs`. Settings-only change via the Pages
API — verified live (all pages 200, paidakia video embed intact). CM
pushes that touch only a `.qmd` now deploy automatically via the CI
render; no local re-render needed.

**Queued follow-ups:**

1. **CM emission config (content_manager repo, not here):** CM PR #137
   finalized `CM_WEBSITE_REPO_PATH: /data/website/source` +
   `CM_WEBSITE_RECIPES_DIR: recipes`; Chris may still need to
   `git pull && docker compose up -d --build` on ms01. Remaining CM work:
   `site/git_repo.py` should `git pull --ff-only` the clone before
   resolving (stale clone → terminal `skipped_no_match`).
   **Constraint from PR #21:** CM must never emit a recipe title matching
   `^\d+\. ` — it blanks the whole listing (see CLAUDE.md publishing
   section).
2. **Untrack `docs/` (this repo, optional):** with Pages serving
   `gh-pages`, the committed `docs/` no longer drives the live site —
   it's kept for local preview parity. Deciding to untrack it would
   shrink publish PRs to just the `.qmd` diff; it's a contract change
   (CLAUDE.md documents `docs/` as committed), so it's its own
   decision/PR, not a drive-by.
3. **Guides migration step 4** (republish live guides) — still open per
   MIGRATION.md / memory.

**Open question:** old recipe URLs inside Plane work-item descriptions
still point at `/pages/recipes/...`; redirects cover humans, and CM
still parses them, so rewriting them is optional cleanup, not required.

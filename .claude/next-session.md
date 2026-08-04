# Next session kickoff

**Context:** PR #20 (flat recipe slugs) merged 2026-08-03. PR #21
(`chore/fix-recipes-listing-titles`) then repaired its fallout: recipe
titles starting `NN. ` parsed as markdown ordered lists in the grid
listing, corrupting the card anchors so List.js rendered an **empty**
/recipes listing. Fix: retitle the 8 canning chapters to `NN — Title`
(same slug via `slugify_recipe`), restore category browsing to the left
recipes sidebar as `#category=` hash links, document the `NN.`-title
rule in CLAUDE.md. The re-render also shipped CM's paidakia video embed
(commit 3a09cdb had touched only the `.qmd`).

**Queued follow-ups:**

1. **CM emission config (content_manager repo, not here):** point CM's
   emission at the new layout — `website_repo_path` → the clone's
   `source/` dir, `website_recipes_dir: recipes` (default). File lookup
   becomes `source/recipes/<slug>.qmd`, emitted URLs
   `https://chriskornaros.dev/recipes/<slug>.html`. Recognition regex
   already matches. Drop any `website_slug` overrides that only bridged
   the old capitalized paths. Own branch/PR in that repo.
   **New constraint from PR #21:** CM must never emit a recipe title
   matching `^\d+\. ` — it blanks the whole listing (see CLAUDE.md
   publishing section).
2. **Pages source gap (this repo):** Pages serves `main:/docs` while
   publish.yml deploys to `gh-pages` (JamesIves action) — the CI render
   is dead weight, so a CM push that touches only a `.qmd` never goes
   live until someone re-renders locally. Either switch Pages to
   `gh-pages` or make the workflow commit `docs/` back to `main`.
   Suggested branch: `chore/pages-deploy-alignment`.
3. **Guides migration step 4** (republish live guides) — still open per
   memory.

**Open question:** old recipe URLs inside Plane work-item descriptions
still point at `/pages/recipes/...`; redirects cover humans, and CM
still parses them, so rewriting them is optional cleanup, not required.

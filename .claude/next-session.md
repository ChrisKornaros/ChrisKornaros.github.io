# Next session kickoff

**Context:** PR #20 (`chore/recipes-flat-slugs`) flattened all 123 recipe
pages to `source/recipes/<slug>.qmd` with slug = content_manager's
`slugify(title)`, added redirect aliases for every old
`/pages/recipes/<Category>/<Title>.html` URL, and updated the
`site_publish` converter (`config.slugify_recipe`, flat routing).

**Queued follow-up (lives in the content_manager repo, not here):**
point CM's *emission* at the new layout. `website_recipes_dir` doubles as
the filesystem dir under `website_repo_path` *and* the public URL path
segment, so the working combo is:

- `website_repo_path` → the clone's `source/` directory
- `website_recipes_dir: recipes` (the default)

That yields file lookup `source/recipes/<slug>.qmd` and emitted URLs
`https://chriskornaros.dev/recipes/<slug>.html`. Recognition (the Plane
recipe-URL regex) already matches the flat form — no change needed there.
Any `website_slug` overrides that existed only to bridge the old
capitalized paths can be dropped. Do this in a content_manager session on
its own branch/PR.

**In this repo, nothing is queued.** If starting fresh here: guides
migration step 4 (republish live guides) is still the only open item per
memory — otherwise pick from requirements/roadmap.

**Open question:** old recipe URLs inside Plane work-item descriptions
still point at `/pages/recipes/...`; redirects cover humans, and CM still
parses them, so rewriting them is optional cleanup, not required.

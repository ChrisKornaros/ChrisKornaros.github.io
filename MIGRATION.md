# Migrating the existing guides into the vault

> **Status (2026-06-02):** Steps 1–3 executed. The four guides now live in
> `~/vault/writing/guides/` as the canonical `.md` source (`quarto.md`/`uv.md`
> carry `draft: true`; `raspberry-pi-server.md` has the `aliases` redirect), and
> `quarto.qmd`/`uv.qmd` are removed from the live site in this PR. **Step 4
> (re-homing the live `docker` and Pi guides through `/publish`) is deferred** —
> the existing `raspberry_pi_server.qmd`/`docker.qmd` keep serving the site until
> republished.

One-time runbook to move the four guide `.qmd` files that currently live in
[source/pages/guides/posts/](source/pages/guides/posts/) into the vault
(`~/vault/writing/guides/`), so the vault `.md` becomes the **canonical source**
and future edits flow through `/publish` like everything else.

After this, the loop for a guide is identical to recipes/blogs: edit the vault
`.md` → `/publish` → it regenerates the `.qmd` and deploys.

## How publishing treats migrated content (why this is low-risk)

The Obsidian→Quarto converter (`site_publish/`) only rewrites *Obsidian* syntax.
Anything already in plain/Quarto form **passes through untouched**:

- `![](images/foo.png)` image links → left as-is (only `![[foo.png]]` embeds are
  rewritten). So **keep the existing `images/` links and the
  `source/pages/guides/posts/images/` folder** and images keep working with zero
  copying.
- `::: {.callout-note}` fenced divs → left as-is (only Obsidian `> [!note]`
  callouts are converted). The Pi guide's existing callouts are already valid.
- Inline `#word` hashtags in body text **are stripped** on publish. Guides use
  `#` only for Markdown headings (`# Heading`, with a space — safe) and in code
  blocks (protected), so this is a non-issue — but eyeball the first render.

You only need real Obsidian conversion if you *want* a guide to look native in
Obsidian (preview images, native callouts). That's optional polish, not required
to publish.

## Slugs & URLs (one gotcha)

`/publish` lowercases the vault filename and turns non-alphanumerics into `-`:

| Vault file | Published `.qmd` | URL changes? |
|---|---|---|
| `docker.md` | `docker.qmd` | no — overwrites in place |
| `quarto.md` | `quarto.qmd` | n/a (kept as draft) |
| `uv.md` | `uv.qmd` | n/a (kept as draft) |
| `raspberry_pi_server.md` | `raspberry-pi-server.qmd` | **yes** — `_` → `-` |

Only the Pi guide's URL moves. To preserve the old link, add an alias to the
vault draft's frontmatter so Quarto emits a redirect:

```yaml
aliases:
  - /pages/guides/posts/raspberry_pi_server.html
```

## Per-guide plan

| Guide | State | Plan |
|---|---|---|
| **raspberry_pi_server** (Ubuntu Pi) | live, done | Migrate to `raspberry-pi-server.md` (no `draft`). Republish → new `raspberry-pi-server.qmd`; delete the old underscore file; add the `aliases` redirect above. |
| **docker** | live, WIP | Migrate to `docker.md` (no `draft` → stays live). Finish in Obsidian; `/publish` regenerates the same `docker.qmd` (same URL). |
| **quarto** | not wanted live | Migrate to `quarto.md` with `draft: true`. Delete `source/.../quarto.qmd`. Render drops it from the site. |
| **uv** | not wanted live | Migrate to `uv.md` with `draft: true`. Delete `source/.../uv.qmd`. Render drops it from the site. |

## Steps

All paths relative to the repo root (`~/vault/projects/ChrisKornaros.github.io`).

### 1. Copy each guide into the vault (`.qmd` → `.md`)

```sh
W=~/vault/writing/guides
cp source/pages/guides/posts/docker.qmd              "$W/docker.md"
cp source/pages/guides/posts/raspberry_pi_server.qmd "$W/raspberry-pi-server.md"
cp source/pages/guides/posts/quarto.qmd              "$W/quarto.md"
cp source/pages/guides/posts/uv.qmd                  "$W/uv.md"
```

### 2. Set draft flags in the vault copies

- `quarto.md` and `uv.md`: add `draft: true` to frontmatter (keeps them off the
  site; they're still scaffolded for future work).
- `docker.md` and `raspberry-pi-server.md`: **no** `draft` (they stay live).
- `raspberry-pi-server.md`: also add the `aliases:` block from above.

### 3. Remove the two unwanted guides from the live site

```sh
rm source/pages/guides/posts/quarto.qmd source/pages/guides/posts/uv.qmd
```

This is a normal website change → branch + PR (a render drops them from `docs/`).
The vault keeps them as drafts.

### 4. Re-home the live guides through the pipeline (when ready)

- **docker:** once it's finished, `/publish ~/vault/writing/guides/docker.md`
  (regenerates `docker.qmd`, same URL).
- **Pi guide:** `/publish ~/vault/writing/guides/raspberry-pi-server.md`, then
  `rm source/pages/guides/posts/raspberry_pi_server.qmd` (old slug) in the same
  PR. Verify the `aliases` redirect works.

You don't have to do step 4 immediately — the live `.qmd` files keep serving the
site until you republish. Migrate the *source of truth* now (steps 1–3); reissue
the live ones from the vault whenever you next touch them.

## Two-repo reminder

The vault `.md` files (steps 1–2) are committed in the **vault** repo via its own
flow. The `source/` deletions and any republished `.qmd` (steps 3–4) are
**website** PRs. Never mix the two in one commit.

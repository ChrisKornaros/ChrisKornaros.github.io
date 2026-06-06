---
description: Post a Bluesky announcement for a just-published post. Reads the app password from Bitwarden (bw) at run time.
argument-hint: <vault-draft-path> [--url <link>] [--tag <t>] [--dry-run]
allowed-tools: Bash, Read
---

You are running the **announce** step: post a short Bluesky update linking to a
post that was *already published* via `/publish`. This is a runtime action, not
a code change — it creates **no git branch, commit, or PR**. (The `announce`
command itself was added to the repo in its own PR; running it just posts.)

Arguments: `$ARGUMENTS` — a published vault draft path (supplies title + link),
and/or `--url`, `--tag`, `--text`, `--item`, `--dry-run`.

Run everything from the repo root (`~/vault/projects/ChrisKornaros.github.io`).

## 1. Compose and preview first — always dry-run

Run: `uv run announce $ARGUMENTS --dry-run`

- This composes the post and prints it plus the detected facets (clickable link
  + any `#tags`). It does **not** touch Bitwarden or the network.
- For a blog draft the link comes from the draft's `substack:` frontmatter; for
  anything else pass `--url`. Override the whole text with `--text`, and add
  hashtags with `--tag` (lowercase, few).
- Show Chris the composed post and confirm it reads right before sending.

## 2. Bitwarden vault — unlock is handled for you (on a terminal)

The send step reads the Bluesky **app password** (not the account password)
from a Bitwarden item via the `bw` CLI. If the vault is locked **and you're at a
terminal**, `announce` runs `bw unlock` itself — the master-password prompt
shows inline, you type it, and it proceeds. The session key is captured, never
printed. So no pre-export is required for interactive use; you *can* still
pre-unlock if you prefer:

```sh
export BW_SESSION="$(bw unlock --raw)"
```

- With **no tty** (CI, or a captured subprocess — e.g. an agent's Bash tool),
  there's no way to prompt, so it fails with the manual-unlock hint instead of
  hanging. In that case run the pre-export above first.
- Config (non-secret) is env-driven: `BLUESKY_BW_ITEM` (default `Bluesky`) names
  the vault item; its username is the handle and its password is the app
  password. `BLUESKY_HANDLE` overrides the identifier if needed.
- Never print, echo, or log the password. If `bw` reports it's not logged in,
  surface that and stop — don't work around it.

## 3. Send

Run the same command **without** `--dry-run`:

`uv run announce $ARGUMENTS`

On success it prints the posting handle and the `bsky.app` URL of the new post.
Report that URL back. On failure (locked vault, missing item, API error) it
prints the reason and exits non-zero — relay it, don't retry blindly.

## Notes

- One post per publish; re-running posts again (the API has no dedupe).
- Eventually this folds into `content_manager`'s multi-platform poster behind
  its `core/secrets.py` Bitwarden boundary; the `bw`-CLI shape here is the
  documented bridge until then.

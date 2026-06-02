---
name: git-flow-session-end
type: workflow
scope: repo
lifecycle: stable
dependencies:
  - git-flow-no-direct-main
evidence:
  - case-studies/product-use-tracker/playbook.md#141-workflow-rules-codified-mid-cycle
  - templates/_shared/git-workflow.md#the-session-end-loop
  - playbook/02-workflow-patterns.md#1-auto-commit--auto-pr-at-end-of-branch-session
  - playbook/02-workflow-patterns.md#3-askuserquestion-answer--merge-confirmation-not-a-request-to-wait
applies_when:
  - host follows GitHub Flow (sessions = one branch = one PR)
  - human is available to merge during the session
version: 2
---

# Git Flow — session-end loop

## Rule

A coding session ends with the PR merged into `main`, the local
`main` updated, and a fixed-format **Session end** summary
printed to the human. When the branch's scope is met and
verified, the agent's next response runs, in one turn:

1. sync the project's tracking docs to reality (human-readable
   requirements/roadmap/bug docs *and* the AI-facing
   `CLAUDE.md` status lines)
2. commit → push → `gh pr create`
3. pop the merge question via `AskUserQuestion`

No "ready to commit?" stall. The merge confirmation arrives via
the popup; the sync + branch-delete sequence and the closing
**Session end** summary run in the response after that.

## Why

The "ready to commit?" turn was a round-trip with no information
in it — the agent had everything it needed to proceed, and the
human's "yes" was reflexive. The product-use-tracker v3 cycle
([case study §1.4.1](../../case-studies/product-use-tracker/playbook.md#141-workflow-rules-codified-mid-cycle))
counted the cost and made the auto-shape a rule:
[[git-flow-no-direct-main]] is the safety net, so sitting on
uncommitted work is friction, not safety. The popup-for-merge
half exists for the same reason: a turn that ends with the
agent waiting for "merged" forces a session restart and burns
the prompt cache; a popup keeps the session warm and gives the
human a one-click answer.

Folding the doc-sync step *into* the session-end sequence
(rather than letting it drift into the next session) keeps the
human-readable requirements doc and the AI-facing `CLAUDE.md`
honest: status flips, test notes, and "what changed" land in the
same PR as the code. Future-you reading the PR a quarter later
gets a faithful snapshot, not a code diff plus archaeology.

The fixed-format **Session end** summary at the close exists
because the previous freeform "Done." gave the human no
consistent place to look for what just happened. A stable shape
is scannable and survives across repos without retraining.

## How to apply

When the branch goal is met and verified (smoke green, tests
passing, acceptance criteria observable), execute these steps
**in one response**:

1. **Sync the tracking docs to reality — before committing.**
   Update both layers in the same diff as the code:
   - **Human-readable tracking** — the requirements / roadmap /
     enhancements / bugfixes doc(s) the host repo uses (common
     names: `REQUIREMENTS.md`, `ROADMAP.md`, `ENHANCEMENTS.md`,
     `BUGFIXES.md`, `playbook.md`). Flip statuses (🔴/🟡/🟢,
     `in-progress` → `done`), add a one-line outcome, and note
     any *important* observation from testing/development that
     would otherwise be lost (a surprise, a deferred sub-task,
     a constraint discovered mid-branch). Skip mechanical
     play-by-play.
   - **`CLAUDE.md` status lines** — the root `CLAUDE.md` (and
     any subdir `CLAUDE.md` that touches changed folders).
     Update the Layout / Status tables, the "Composed modules"
     ledger if a module was vendored or bumped, and any rule
     whose wording is now stale.

   If nothing meaningful changed in either layer, say so in the
   commit body (`Docs: no status changes — pure code refactor`)
   rather than silently skipping. The check happened.
2. **Commit + push + open PR in one response.** `git add` →
   `git commit` → `git push -u origin <branch>` →
   `gh pr create` with title, body, and the
   *Delivered + Verified* footer (see
   [templates/_shared/git-workflow.md](../../templates/_shared/git-workflow.md#the-delivered--verified-footer)).
   Print the PR URL.
3. **Pop the merge question via `AskUserQuestion`, not by
   ending the turn.** Phrasing:

   > PR is up: `<url>`. Merge it in the GitHub UI when you're
   > ready. Has it been merged?
   >
   > Options: **Merged** · **Not yet** · **Changes requested /
   > closed without merge**

   The popup answer *is* the merge confirmation — no
   intermediate "waiting on your merge" turn. The third option
   covers "I'm going to review and request changes" — the agent
   stays on the branch and awaits the human's notes rather than
   running cleanup.
4. **Verify before syncing — always, regardless of channel.**
   Whether the answer came in via the popup or via free-text
   ("merged" / "approved" / "go ahead"), run
   `gh pr view <N> --json state,mergedAt` *before* the destructive
   sync sequence. If `state != "MERGED"`:
   - say so in one line and re-pop `AskUserQuestion`
   - do **not** run `git switch main && git pull && git branch
     -d <branch>` on an unverified claim
   - the cost of one extra `gh` call is trivial; the cost of
     deleting the branch + pulling a `main` without the work
     requires force-push to recover, and force-push is on the
     deny list
5. **Sync and clean up** (only after `state == "MERGED"`
   confirmed):
   ```sh
   git switch main
   git pull --ff-only
   git branch -d <branch>     # safe delete — refuses if unmerged
   git fetch --prune
   ```
6. **Print the fixed-format Session end summary.** Always emit
   it, in this exact shape:

   ```markdown
   ## Session end

   - **Branch merged:** `<branch>` → `main` (PR #<n>)
   - **Delivered:** <one-line outcome — what shipped>
   - **Verified:** <how — smoke, tests, manual check>
   - **Docs synced:** <files touched, or "no status changes">
   - **Local state:** `main` up to date, `<branch>` deleted

   Session done.
   ```

   No "recommended next step" or runnable next-prompt block —
   the next session's work is driven by the host's
   version-planning / phase doc, not by the agent guessing
   from context.

If "Not yet" comes back from the popup, re-pop the same
question after a short pause rather than ending the turn. If
"Changes requested" comes back, stop the cleanup sequence
entirely and wait for the human's review notes — the branch is
still live work.

## Anti-patterns

- Committing the code first and "doing the docs in a follow-up
  PR." The doc sync belongs in the same diff; a follow-up PR
  almost never happens, and the requirements doc rots.
- Skipping the doc-sync step on the grounds that "the diff is
  self-documenting." The human-readable tracking doc is for the
  human reading six months later, not for the agent reading the
  diff today.
- Ending the turn with uncommitted work and a "ready to commit?"
  question. The branch is done; commit it.
- Ending the turn waiting for a free-text "merged" reply instead
  of popping `AskUserQuestion`.
- Acting on a "merged" answer (from either channel) without
  first running `gh pr view --json state,mergedAt`. The popup
  click and the chat reply are equally fallible.
- Running the sync sequence on an unverified "merged" claim,
  losing the branch's work in the process.
- Pushing to `main` directly to "save a step" when the PR
  workflow feels heavyweight for a small change.
- Replacing the fixed **Session end** block with freeform prose,
  or appending a "recommended next prompt" — the human drives
  next-step selection from the version-planning doc.

## Related

- [[git-flow-no-direct-main]]
- [[ask-merged-via-popup]]
- [[auto-commit-on-branch-done]]
- [[smoke-before-commit]]
- [[docs-sync-before-commit]]

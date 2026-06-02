#!/usr/bin/env python3
"""PreToolUse re-read guard — vendored companion for no-cat-head-via-bash.

This is the portable copy of the H2 re-read-collapse hook, bundled with
the module so a host repo that vendors `no-cat-head-via-bash` gets a
runnable hook (not just prose). Wire it from the host's
`.claude/settings.json` per the module's index.md "Companion files"
section — the shape is shipped in
`templates/_shared/claude-settings.example.json`.

    Canonical source (kept in sync; edit there first, then re-copy):
    case-studies/agentic-optimization-research/experiments/
    h2-re-read-collapse/tool/pre_read_guard.py

Why it lives here too: a host vendors the module directory only, never
the experiment scaffolding, so the script has to travel with the module
to be usable. This mirrors how stay-in-project-tree and no-sudo-as-shortcut
ship a `settings-snippet.json` companion.

---

Tracks per-session Read calls and blocks redundant re-reads of files the
session has already read and not modified since. Edit/Write/MultiEdit
calls mark a file as "modified", so the *next* Read of that file is
allowed (legitimate post-edit re-read).

State is per-session JSON at:

    $H2_STATE_DIR/<session_id>.json
    (default: ~/.cache/agentic_metrics/h2-re-read-tracker/)

The hook fails open: any unexpected condition (malformed payload, I/O
error, exception in decision logic) returns exit 0 so the tool call
proceeds. The block path is reserved for the *intended* case — a
redundant re-read of an unmodified file.

Disable for one session by setting H2_REREAD_GUARD_DISABLED=1 in the
shell that launches Claude Code.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


STATE_DIR = Path(
    os.environ.get(
        "H2_STATE_DIR",
        os.path.expanduser("~/.cache/agentic_metrics/h2-re-read-tracker"),
    )
)

_DISABLED_TRUTHY = {"1", "true", "yes", "on"}
DISABLED = os.environ.get("H2_REREAD_GUARD_DISABLED", "").lower() in _DISABLED_TRUTHY


def _state_path(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in session_id)
    return STATE_DIR / f"{safe}.json"


def load_state(session_id: str) -> dict:
    path = _state_path(session_id)
    if not path.exists():
        return {"files": {}}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"files": {}}


def save_state(session_id: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(session_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")))
    tmp.replace(path)


def decide(payload: dict) -> tuple[int, str]:
    """Pure decision function.

    Returns (exit_code, stderr_message). Exit 0 = allow; exit 2 = block.
    """
    session_id = payload.get("session_id") or "unknown"
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""

    if not file_path or tool_name not in {"Read", "Edit", "Write", "MultiEdit"}:
        return 0, ""

    state = load_state(session_id)
    files = state.setdefault("files", {})
    entry = files.get(file_path)

    if tool_name == "Read":
        if entry is not None and not entry.get("modified_since_read", False):
            # Redundant re-read of an unmodified file → block.
            msg = (
                f"[h2-re-read-guard] BLOCKED: '{file_path}' was already read "
                f"earlier in this session and has not been modified by "
                f"Edit/Write/MultiEdit since. The prior content is still in "
                f"your context — refer to it instead of re-reading.\n"
                f"\n"
                f"If you have a specific reason to re-read (e.g. the file "
                f"was changed by an external process), set "
                f"H2_REREAD_GUARD_DISABLED=1 in the shell that launched "
                f"Claude Code, or see the module's index.md for context."
            )
            return 2, msg
        # First read OR re-read after an intervening modification.
        prev_reads = entry.get("reads", 0) if entry else 0
        files[file_path] = {
            "reads": prev_reads + 1,
            "modified_since_read": False,
        }
        save_state(session_id, state)
        return 0, ""

    # Edit / Write / MultiEdit: mark file as modified, always allow.
    if entry is None:
        files[file_path] = {"reads": 0, "modified_since_read": True}
    else:
        entry["modified_since_read"] = True
    save_state(session_id, state)
    return 0, ""


def main() -> int:
    if DISABLED:
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # malformed payload → fail open

    try:
        exit_code, stderr_msg = decide(payload)
    except Exception:
        return 0  # any unexpected error → fail open

    if stderr_msg:
        print(stderr_msg, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

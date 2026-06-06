"""The one boundary between the app and the secret store (Bitwarden CLI).

Per the canonical ``secrets-no-plaintext`` convention, secret access funnels
through a single module so the backend is swappable and the audit surface is
one file. Here the backend is the Bitwarden ``bw`` CLI vault: the Bluesky app
password lives in a vault item and is read at run time -- never written to a
file, never echoed.

Two narrow reads do the work -- ``bw get username`` and ``bw get password`` --
rather than fetching the whole item as JSON. That sidesteps a brittle failure
mode (a ``bw`` update notice or a "more than one result" message prepended to
stdout makes ``json.loads`` blow up with no useful error) and uses exactly the
commands that return the raw value.

Unlock is handled here too: if the vault is locked and we're on a terminal,
``bw unlock`` is run interactively -- the master-password prompt shows on the
tty, the session key is captured (never printed) and stashed in the environment
for the ``bw get`` calls that follow. With no tty (CI, a captured subprocess)
we fail with the manual-unlock hint instead of hanging on an invisible prompt.

Prereqs at call time:

- ``bw`` installed and logged in (``bw login`` once).
- Either the vault already unlocked for this shell
  (``export BW_SESSION="$(bw unlock --raw)"``) or an interactive terminal so we
  can unlock it for you. ``bw`` reads ``BW_SESSION`` from the environment.

Configuration (non-secret) via env:

- ``BLUESKY_BW_ITEM`` -- name or id of the Bitwarden item holding the Bluesky
  login (default ``"Bluesky"``). Its ``username`` is the handle/identifier and
  its ``password`` is the app password.
- ``BLUESKY_HANDLE`` -- optional override for the identifier if it isn't stored
  as the item's username.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

DEFAULT_ITEM = "Bluesky"


class SecretError(RuntimeError):
    """The secret could not be read (CLI missing, vault locked, item absent)."""


def _require_bw() -> None:
    if shutil.which("bw") is None:
        raise SecretError(
            "Bitwarden CLI ('bw') not found. Install it and run `bw login`."
        )


def _bw(*args: str) -> str:
    """Run a ``bw`` subcommand with output captured (so secrets never print)."""
    _require_bw()
    proc = subprocess.run(
        ["bw", *args],
        capture_output=True,
        text=True,
        env=os.environ,  # bw reads BW_SESSION from here.
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        hint = ""
        if "locked" in err.lower() or "logged in" in err.lower():
            hint = '  Unlock first: export BW_SESSION="$(bw unlock --raw)"'
        raise SecretError(f"`bw {' '.join(args)}` failed: {err}{hint}")
    return proc.stdout


def _vault_status() -> str:
    """Return the vault status: ``unlocked`` | ``locked`` | ``unauthenticated``.

    ``bw status`` prints a JSON blob to stdout in every state. Tolerate a notice
    line prepended to it; if it's unreadable, treat the vault as locked and let
    the unlock path take over.
    """
    _require_bw()
    proc = subprocess.run(
        ["bw", "status"], capture_output=True, text=True, env=os.environ
    )
    out = proc.stdout or ""
    start = out.find("{")
    if start == -1:
        return "locked"
    try:
        data = json.loads(out[start:])
    except json.JSONDecodeError:
        return "locked"
    return data.get("status", "locked")


def _ensure_unlocked() -> None:
    """Make sure the vault is usable for this process.

    No-op if already unlocked. If locked and we're attached to a terminal, run
    ``bw unlock`` interactively: the prompt is visible on stderr, the session
    key is captured from stdout (never printed) and stored in the environment so
    the following ``bw get`` calls authenticate. With no tty, raise the manual
    hint rather than block on an invisible prompt.
    """
    status = _vault_status()
    if status == "unlocked":
        return
    if status == "unauthenticated":
        raise SecretError("Bitwarden is not logged in. Run `bw login` first.")

    # status == "locked" (or unreadable, treated as locked).
    if not sys.stdin.isatty():
        raise SecretError(
            "Bitwarden vault is locked. Unlock first: "
            'export BW_SESSION="$(bw unlock --raw)"'
        )

    # Interactive unlock: stdout captured (the raw session key), stderr/stdin
    # inherited so the master-password prompt shows and you can type it.
    proc = subprocess.run(
        ["bw", "unlock", "--raw"],
        stdout=subprocess.PIPE,
        text=True,
        env=os.environ,
    )
    session = (proc.stdout or "").strip()
    if proc.returncode != 0 or not session:
        raise SecretError("Bitwarden unlock failed or was cancelled.")
    os.environ["BW_SESSION"] = session


def bluesky_credentials(item_ref: str | None = None) -> tuple[str, str]:
    """Return ``(identifier, app_password)`` for Bluesky from the vault.

    Reads two narrow values (``bw get username`` / ``bw get password``); the
    password is never returned to the shell, logged, or printed -- only handed
    to the API client.
    """
    item_ref = item_ref or os.environ.get("BLUESKY_BW_ITEM", DEFAULT_ITEM)
    _ensure_unlocked()

    password = _bw("get", "password", item_ref).strip()
    identifier = os.environ.get("BLUESKY_HANDLE") or _bw(
        "get", "username", item_ref
    ).strip()

    if not identifier:
        raise SecretError(
            f"No identifier for Bluesky: set the username on item '{item_ref}' "
            "or export BLUESKY_HANDLE."
        )
    if not password:
        raise SecretError(
            f"Item '{item_ref}' has no password (the Bluesky app password)."
        )
    return identifier, password

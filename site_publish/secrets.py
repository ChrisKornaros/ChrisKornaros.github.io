"""The one boundary between the app and the secret store (Bitwarden CLI).

Per the canonical ``secrets-no-plaintext`` convention, secret access funnels
through a single module so the backend is swappable and the audit surface is
one file. Here the backend is the Bitwarden ``bw`` CLI vault: the Bluesky app
password lives in a vault item and is read at run time -- never written to a
file, never echoed.

Prereqs at call time (the documented bootstrap exception is the one env var
that unlocks the store itself):

- ``bw`` installed and logged in (``bw login`` once).
- The vault unlocked for this shell: ``export BW_SESSION="$(bw unlock --raw)"``.
  ``bw`` reads ``BW_SESSION`` from the environment automatically.

Configuration (non-secret) via env:

- ``BLUESKY_BW_ITEM`` -- name or id of the Bitwarden item holding the Bluesky
  login (default ``"Bluesky"``). Its ``login.username`` is the handle/identifier
  and ``login.password`` is the app password.
- ``BLUESKY_HANDLE`` -- optional override for the identifier if it isn't stored
  as the item's username.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

DEFAULT_ITEM = "Bluesky"


class SecretError(RuntimeError):
    """The secret could not be read (CLI missing, vault locked, item absent)."""


def _bw(*args: str) -> str:
    if shutil.which("bw") is None:
        raise SecretError(
            "Bitwarden CLI ('bw') not found. Install it and run `bw login`."
        )
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
            hint = (
                "  Unlock first: export BW_SESSION=\"$(bw unlock --raw)\""
            )
        raise SecretError(f"`bw {' '.join(args)}` failed: {err}{hint}")
    return proc.stdout


def bluesky_credentials(item_ref: str | None = None) -> tuple[str, str]:
    """Return ``(identifier, app_password)`` for Bluesky from the vault.

    Reads one Bitwarden item; the password is never returned to the shell,
    logged, or printed -- only handed to the API client.
    """
    item_ref = item_ref or os.environ.get("BLUESKY_BW_ITEM", DEFAULT_ITEM)
    try:
        item = json.loads(_bw("get", "item", item_ref))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SecretError(f"`bw get item {item_ref}` did not return JSON.") from exc

    login = item.get("login") or {}
    identifier = os.environ.get("BLUESKY_HANDLE") or login.get("username")
    password = login.get("password")

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

"""Path + section configuration for the publishing pipeline.

Roots are resolved relative to this repo so the tooling works on any machine
(Mac/Pi) without hardcoded home paths, but both are env-overridable:

- ``VAULT_WRITING``  -- where Obsidian drafts live (default ``<repo>/../../writing``
  which resolves to ``~/vault/writing`` in the normal vault layout).
- ``SITE_SOURCE``    -- this site's Quarto source dir (default ``<repo>/source``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# <repo>/site_publish/config.py -> repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parent.parent


def vault_writing() -> Path:
    """Root of the vault drafting area (``writing/``)."""
    env = os.environ.get("VAULT_WRITING")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO_ROOT / ".." / ".." / "writing").resolve()


def site_source() -> Path:
    """Root of the Quarto site source (``source/``)."""
    env = os.environ.get("SITE_SOURCE")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO_ROOT / "source").resolve()


def site_pages() -> Path:
    return site_source() / "pages"


# Sections a draft can belong to. ``recipes`` is special-cased (category folders,
# full content on-site); the rest are post-listing sections.
SECTIONS = ("guides", "research", "blogs", "recipes")
POST_SECTIONS = ("guides", "research", "blogs")


def slugify(value: str) -> str:
    """Kebab-case slug used for filenames and branch names."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "untitled"

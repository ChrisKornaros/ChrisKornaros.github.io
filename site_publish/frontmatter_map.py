"""Per-section frontmatter mapping from Obsidian draft -> Quarto post.

Rules common to every section:
- strip the ``draft`` flag (publishing is the act of clearing it),
- default ``author`` to "Chris Kornaros",
- ensure a ``date`` (fall back to today),
- stamp ``published`` with today's date,
- drop vault-only keys (``aliases``, ``cssclasses``, ``publish``).

Section extras:
- recipes keep ``categories`` (required) and an optional ``video`` URL,
- blogs require a ``substack`` URL (used to build the embed; see convert.py).

A library recipe page (``library/food/recipes/<category>/<slug>.md``) is first
reshaped into a ``writing/`` recipe draft by :func:`library_recipe_meta`: its
vault-only keys are dropped, ``author`` is always the site author, and
``categories`` comes from its folder.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

AUTHOR_DEFAULT = "Chris Kornaros"

# Vault-only frontmatter that should never reach the site.
_DROP_KEYS = {"draft", "publish", "aliases", "cssclasses", "cssclass"}


class FrontmatterError(ValueError):
    """Raised when a draft is missing frontmatter the section requires."""


def _today() -> str:
    return _dt.date.today().isoformat()


# Stable, readable key order for the emitted frontmatter.
_ORDER = ("title", "author", "date", "categories", "tags", "video", "published")


def map_metadata(section: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Return the cleaned, ordered frontmatter dict for the rendered ``.qmd``."""
    cleaned: dict[str, Any] = {k: v for k, v in meta.items() if k not in _DROP_KEYS}

    cleaned.setdefault("author", AUTHOR_DEFAULT)
    if not cleaned.get("date"):
        cleaned["date"] = _today()
    cleaned["published"] = _today()

    if not cleaned.get("title"):
        raise FrontmatterError(f"{section} draft is missing a 'title'.")

    if section == "recipes":
        if not cleaned.get("categories"):
            raise FrontmatterError(
                "Recipe draft is missing 'categories' (e.g. categories: [Beef])."
            )
        if "video" in cleaned and not cleaned["video"]:
            cleaned.pop("video")

    if section == "blogs":
        if not meta.get("substack"):
            raise FrontmatterError(
                "Blog draft is missing a 'substack' URL to embed."
            )
        # substack drives the embed body, not the visible frontmatter.
        cleaned.pop("substack", None)

    # Emit known keys first in a stable order, then any remaining extras.
    out: dict[str, Any] = {k: cleaned[k] for k in _ORDER if k in cleaned}
    for k, v in cleaned.items():
        out.setdefault(k, v)
    return out


def is_draft(meta: dict[str, Any]) -> bool:
    return bool(meta.get("draft"))


# Vault-only keys of a library recipe page; ``draft`` is in _DROP_KEYS already.
# Its ``author`` (agent | chris) is provenance in the vault, not a byline.
_LIBRARY_DROP_KEYS = {
    "type", "category", "yield", "prep_minutes", "cook_minutes", "source",
    "updated", "author",
}

# Kept lower-case inside a category name, as in the site's "Sauces and Condiments".
_MINOR_WORDS = {"a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to", "with"}


def category_name(folder: str) -> str:
    """The site ``categories`` value for a kebab-case category folder.

    ``sauces-and-condiments`` -> ``Sauces and Condiments``: the form the site's
    existing recipes carry, so the listing's category filter groups a library
    recipe with them.
    """
    words = [w.lower() for w in folder.split("-") if w]
    return " ".join(
        w if i and w in _MINOR_WORDS else w.capitalize() for i, w in enumerate(words)
    )


def library_recipe_meta(meta: dict[str, Any], *, folder: str) -> dict[str, Any]:
    """Reshape a library recipe page's frontmatter into a writing/ recipe draft's.

    The result then goes through :func:`map_metadata` like any recipe draft.
    """
    category = meta.get("category")
    if category and str(category) != folder:
        raise FrontmatterError(
            f"Recipe page says 'category: {category}' but lives in the "
            f"'{folder}' folder."
        )
    out = {k: v for k, v in meta.items() if k not in _LIBRARY_DROP_KEYS}
    out["author"] = AUTHOR_DEFAULT
    out["categories"] = [category_name(folder)]
    return out

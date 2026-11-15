"""Map a vault draft path to its section and target ``.qmd`` path.

Layout mirrored between vault and site:

    writing/guides/foo.md        -> source/pages/guides/posts/foo.qmd
    writing/research/foo.md      -> source/pages/research/posts/foo.qmd
    writing/blogs/foo.md         -> source/pages/blogs/posts/foo.qmd
    library/food/recipes/beef/foo.md -> source/recipes/<cm-slug-of-title>.qmd

Recipes live in the vault library only (the ``writing/recipes/`` ones moved
there on 2026-11-15) and land in the flat ``source/recipes/``; a draft found
under ``writing/recipes/`` is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Target:
    section: str
    category: str | None  # recipes only
    qmd_path: Path
    assets_dir: Path  # where embedded images are copied


def _library_rel(draft: Path) -> Path | None:
    """The draft's path under the library recipes root, or None if not there."""
    try:
        return draft.resolve().relative_to(config.library_recipes())
    except ValueError:
        return None


def is_library_recipe(draft: Path) -> bool:
    """True when the draft is under ``library/food/recipes/``."""
    return _library_rel(draft) is not None


def library_category(draft: Path) -> str:
    """A library recipe's category: its folder under ``food/recipes/``."""
    rel = _library_rel(draft)
    if rel is None or len(rel.parts) < 2:
        raise ValueError(
            f"Library recipe {draft} must live in a category folder, e.g. "
            f"library/food/recipes/vegetables/{draft.name}."
        )
    return rel.parts[0]


def section_for(draft: Path) -> str:
    """The section a draft belongs to: ``recipes`` for a library recipe page,
    else its first path part under writing/."""
    if is_library_recipe(draft):
        return "recipes"
    writing = config.vault_writing()
    try:
        rel = draft.resolve().relative_to(writing)
    except ValueError as exc:  # pragma: no cover - guarded by caller
        raise ValueError(
            f"{draft} is not under the vault writing root ({writing}) or the "
            f"library recipes root ({config.library_recipes()})."
        ) from exc
    section = rel.parts[0] if rel.parts else ""
    if section == "recipes":
        raise ValueError(
            f"{draft} is under writing/recipes/, but recipes live in the vault "
            f"library: move it to library/food/recipes/<category>/<slug>.md."
        )
    if section not in config.POST_SECTIONS:
        raise ValueError(
            f"{draft} is in '{section or '<root>'}', not a known section "
            f"({', '.join(config.POST_SECTIONS)})."
        )
    return section


def _recipe_target(category: str, title: str) -> Target:
    # The site file is flat: source/recipes/<slug>.qmd with slug =
    # content_manager's slugify(title), so CM's slug->file lookup resolves it
    # directly. The category folder only names the `categories:` front matter.
    dest_dir = config.site_source() / "recipes"
    return Target(
        section="recipes",
        category=category,
        qmd_path=dest_dir / f"{config.slugify_recipe(title)}.qmd",
        assets_dir=dest_dir / "images",
    )


def resolve(draft: Path, *, title: str) -> Target:
    """Compute the target paths for a draft given its (mapped) title."""
    if is_library_recipe(draft):
        # library/food/recipes/<category>/<slug>.md -> the same flat site file.
        return _recipe_target(library_category(draft), title)

    section = section_for(draft)
    writing = config.vault_writing()
    rel = draft.resolve().relative_to(writing)
    slug = config.slugify(draft.stem)
    pages = config.site_pages()

    dest_dir = pages / section / "posts"
    return Target(
        section=section,
        category=None,
        qmd_path=dest_dir / f"{slug}.qmd",
        assets_dir=dest_dir / "images",
    )

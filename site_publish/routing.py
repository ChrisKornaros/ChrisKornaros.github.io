"""Map a vault draft path to its section and target ``.qmd`` path.

Layout mirrored between vault and site:

    writing/guides/foo.md        -> source/pages/guides/posts/foo.qmd
    writing/research/foo.md      -> source/pages/research/posts/foo.qmd
    writing/blogs/foo.md         -> source/pages/blogs/posts/foo.qmd
    writing/recipes/Beef/foo.md  -> source/recipes/<cm-slug-of-title>.qmd
    library/food/recipes/beef/foo.md -> source/recipes/<cm-slug-of-title>.qmd

Recipes are read from both vault places until the ``writing/recipes/`` ones
move into the library; both land in the same flat ``source/recipes/``.
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
    if section not in config.SECTIONS:
        raise ValueError(
            f"{draft} is in '{section or '<root>'}', not a known section "
            f"({', '.join(config.SECTIONS)})."
        )
    return section


def _recipe_target(category: str, title: str) -> Target:
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

    if section == "recipes":
        # writing/recipes/<Category>/<file>.md -- the category subfolder still
        # names the `categories:` front matter, but the site file is FLAT:
        # source/recipes/<slug>.qmd with slug = content_manager's
        # slugify(title), so CM's slug->file lookup resolves it directly.
        if len(rel.parts) < 3:
            raise ValueError(
                f"Recipe draft {draft} must live in a category subfolder, e.g. "
                f"writing/recipes/Beef/{draft.name}."
            )
        return _recipe_target(rel.parts[1], title)

    dest_dir = pages / section / "posts"
    return Target(
        section=section,
        category=None,
        qmd_path=dest_dir / f"{slug}.qmd",
        assets_dir=dest_dir / "images",
    )

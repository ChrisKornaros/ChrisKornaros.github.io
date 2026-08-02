"""Map a vault draft path to its section and target ``.qmd`` path.

Layout mirrored between vault and site:

    writing/guides/foo.md        -> source/pages/guides/posts/foo.qmd
    writing/research/foo.md      -> source/pages/research/posts/foo.qmd
    writing/blogs/foo.md         -> source/pages/blogs/posts/foo.qmd
    writing/recipes/Beef/foo.md  -> source/recipes/<cm-slug-of-title>.qmd
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


def section_for(draft: Path) -> str:
    """The section a draft belongs to, from its first path part under writing/."""
    writing = config.vault_writing()
    try:
        rel = draft.resolve().relative_to(writing)
    except ValueError as exc:  # pragma: no cover - guarded by caller
        raise ValueError(
            f"{draft} is not under the vault writing root ({writing})."
        ) from exc
    section = rel.parts[0] if rel.parts else ""
    if section not in config.SECTIONS:
        raise ValueError(
            f"{draft} is in '{section or '<root>'}', not a known section "
            f"({', '.join(config.SECTIONS)})."
        )
    return section


def resolve(draft: Path, *, title: str) -> Target:
    """Compute the target paths for a draft given its (mapped) title."""
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
        category = rel.parts[1]
        dest_dir = config.site_source() / "recipes"
        return Target(
            section=section,
            category=category,
            qmd_path=dest_dir / f"{config.slugify_recipe(title)}.qmd",
            assets_dir=dest_dir / "images",
        )

    dest_dir = pages / section / "posts"
    return Target(
        section=section,
        category=None,
        qmd_path=dest_dir / f"{slug}.qmd",
        assets_dir=dest_dir / "images",
    )

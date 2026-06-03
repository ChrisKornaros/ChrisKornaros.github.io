"""Convert a single vault draft into a site ``.qmd``.

Pure-ish: reads the draft + (for embeds) copies image assets, writes the target
``.qmd`` and, for recipes, a category ``index.qmd`` if one is missing. Never
touches git.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
import yaml

from . import config, embeds, frontmatter_map, obsidian, routing

# Image extensions we resolve for ![[embeds]].
_IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}
_TEMPLATES = Path(__file__).resolve().parent / "templates"


@dataclass
class Result:
    draft: Path
    qmd_path: Path
    section: str
    category: str | None
    written: list[Path] = field(default_factory=list)  # all files created/updated


class ConvertError(Exception):
    pass


def _find_asset(name: str, draft: Path) -> Path | None:
    """Locate an embedded asset by name, draft folder first then attachments."""
    candidates = [
        draft.parent / name,
        config.vault_writing() / "attachments" / name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    # Fall back to a recursive search under writing/ (handles nested attachments).
    matches = list(config.vault_writing().rglob(name))
    return matches[0] if matches else None


def _ensure_category_index(target: routing.Target, result: Result) -> None:
    if target.section != "recipes" or target.category is None:
        return
    index = target.qmd_path.parent / "index.qmd"
    if index.exists():
        return
    text = (_TEMPLATES / "category_index.qmd").read_text(encoding="utf-8")
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(text.format(category=target.category), encoding="utf-8")
    result.written.append(index)


_FM_BLOCK = re.compile(r"\A---\r?\n.*?\r?\n---", re.DOTALL)
_DRAFT_TRUE = re.compile(r"(?mi)^[ \t]*draft:[ \t]*true[ \t]*\r?\n")


def clear_source_draft(draft: Path) -> bool:
    """Remove a ``draft: true`` line from the vault source's frontmatter.

    Publishing un-drafts the canonical source so future ``--all`` syncs include
    it. Surgical line removal within the frontmatter block only (not a full
    round-trip) to avoid churning the author's file formatting or touching the
    body. Returns True if a change was made.
    """
    text = draft.read_text(encoding="utf-8")
    m = _FM_BLOCK.match(text)
    if not m:
        return False
    new_block, n = _DRAFT_TRUE.subn("", m.group(0))
    if not n:
        return False
    draft.write_text(new_block + text[m.end():], encoding="utf-8")
    return True


def _dump_qmd(meta: dict, body: str) -> str:
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip("\n")
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


def convert(draft: Path) -> Result:
    draft = draft.resolve()
    if not draft.is_file():
        raise ConvertError(f"Draft not found: {draft}")

    post = frontmatter.load(str(draft))
    meta = dict(post.metadata)
    section = routing.section_for(draft)

    # Publishing is the act of un-drafting: the draft flag is stripped from the
    # output here (see frontmatter_map._DROP_KEYS) and cleared from the vault
    # source by the caller. An explicit publish always proceeds; --all decides
    # what to touch via the draft flag before reaching this function.
    mapped = frontmatter_map.map_metadata(section, meta)
    target = routing.resolve(draft, title=str(mapped["title"]))
    result = Result(
        draft=draft, qmd_path=target.qmd_path, section=section,
        category=target.category,
    )

    if section == "blogs":
        body = embeds.substack_embed(str(mapped["title"]), str(meta["substack"]))
    else:
        copied: list[Path] = []

        def _resolver(name: str) -> str | None:
            stem_ext = Path(name)
            if stem_ext.suffix.lower() not in _IMG_EXTS:
                return None
            src = _find_asset(name, draft)
            if src is None:
                return None
            target.assets_dir.mkdir(parents=True, exist_ok=True)
            dest = target.assets_dir / src.name
            shutil.copy2(src, dest)
            copied.append(dest)
            return f"images/{src.name}"

        body = obsidian.transform_body(post.content, _resolver)
        result.written.extend(copied)

        if section == "recipes" and mapped.get("video"):
            body = embeds.video_embed(str(mapped["video"])) + "\n" + body
            mapped.pop("video")  # rendered into the body, not shown as metadata

    _ensure_category_index(target, result)
    target.qmd_path.parent.mkdir(parents=True, exist_ok=True)
    target.qmd_path.write_text(_dump_qmd(mapped, body), encoding="utf-8")
    result.written.append(target.qmd_path)
    return result

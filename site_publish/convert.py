"""Convert a single vault draft into a site ``.qmd``.

Pure-ish: reads the draft + (for embeds) copies image assets, writes the target
``.qmd``. Never touches git.

A library recipe page (``library/food/recipes/<category>/<slug>.md``) is
reshaped into a ``writing/`` recipe draft first: its frontmatter by
``frontmatter_map.library_recipe_meta``, its body by :func:`_library_body`
(``Up:`` line and HTML comments with text dropped, a yield/prep/cook line
added). From there it converts like any other draft.

A re-publish keeps what only the site file holds (:func:`_existing_page`): its
``aliases`` (the redirects from a page's old address), its ``published`` date
(or the lack of one, on a page from before the stamp), and the video block
content_manager writes between ``cm:video`` markers. None of these is in the
vault, so regenerating the file from the vault alone would drop them.
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


_FM_BLOCK = re.compile(r"\A---\r?\n.*?\r?\n---", re.DOTALL)
_DRAFT_TRUE = re.compile(
    r"(?mi)^[ \t]*draft:[ \t]*true(?:[ \t]+#[^\r\n]*)?[ \t]*\r?\n"
)


def clear_source_draft(draft: Path) -> bool:
    """Remove a ``draft: true`` line from the vault source's frontmatter.

    Publishing un-drafts the canonical source so future ``--all`` syncs include
    it. Surgical line removal within the frontmatter block only (not a full
    round-trip) to avoid churning the author's file formatting or touching the
    body. The line may carry a trailing YAML comment (the library recipe
    template's does). Returns True if a change was made.
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


# Library recipe body lines that stay in the vault: the first ``Up:`` line and
# HTML comments. Where one fills whole lines, one blank line after it goes too,
# so it leaves no gap behind.
_UP_LINE = re.compile(r"^Up:.*(?:\n|\Z)(?:[ \t]*\n)?", re.MULTILINE)
_COMMENT_LINES = re.compile(
    r"^[ \t]*<!--((?:(?!-->).)*)-->[ \t]*(?:\n|\Z)(?:[ \t]*\n)?",
    re.MULTILINE | re.DOTALL,
)
_COMMENT = re.compile(r"[ \t]*<!--(.*?)-->", re.DOTALL)
_ADAPTED_LINE = re.compile(r"^Adapted from .*$", re.MULTILINE)
_YIELD_PARTS = (("yield", "Yield", ""), ("prep_minutes", "Prep", " min"),
                ("cook_minutes", "Cook", " min"))


def _drop_comment(m: re.Match[str]) -> str:
    # An empty ``<!-- -->`` is pandoc's list separator, not text: keep it.
    return m.group(0) if not m.group(1).strip() else ""


def _library_body(body: str, meta: dict) -> str:
    """A library recipe page's body in a ``writing/`` recipe's shape."""
    body = _UP_LINE.sub("", body, count=1)
    body = _COMMENT.sub(_drop_comment, _COMMENT_LINES.sub(_drop_comment, body))
    parts = [
        f"**{label}:** {str(meta[key]).strip()}{unit}"
        for key, label, unit in _YIELD_PARTS
        if meta.get(key) is not None and str(meta[key]).strip()
    ]
    if not parts:
        return body
    line = " · ".join(parts)
    adapted = _ADAPTED_LINE.search(body)
    if adapted is None:
        return f"{line}\n\n{body}"
    return f"{body[:adapted.end()]}\n\n{line}{body[adapted.end():]}"


# content_manager writes a recipe's video embed (and its JSON-LD) into the site
# file itself, between these markers.
_CM_BLOCK = re.compile(r"<!-- cm:video:start -->.*?<!-- cm:video:end -->", re.DOTALL)


@dataclass(frozen=True)
class _Existing:
    """What the site file at a target path already holds."""

    meta: dict
    cm_block: str | None


def _existing_page(qmd_path: Path) -> _Existing | None:
    """The page already on the site at ``qmd_path``, or None on a first publish."""
    if not qmd_path.is_file():
        return None
    post = frontmatter.load(str(qmd_path))
    block = _CM_BLOCK.search(post.content)
    return _Existing(dict(post.metadata), block.group(0) if block else None)


def _keep_site_frontmatter(mapped: dict, existing: _Existing) -> None:
    """Carry the site-only frontmatter of an existing page into ``mapped``.

    ``aliases`` are the redirects from the page's old address. ``published`` is
    the day the page first went out: a re-publish keeps it, and a page that was
    on the site before the stamp existed gets none rather than today's date.
    """
    if existing.meta.get("aliases"):
        mapped["aliases"] = existing.meta["aliases"]
    if "published" in existing.meta:
        mapped["published"] = existing.meta["published"]
    else:
        mapped.pop("published", None)


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
    content = post.content

    if routing.is_library_recipe(draft):
        if meta.get("type") != "recipe":
            raise ConvertError(
                f"{draft} is under the library recipes root but is not a "
                f"recipe page (type: {meta.get('type')!r})."
            )
        content = _library_body(content, meta)
        meta = frontmatter_map.library_recipe_meta(
            meta, folder=routing.library_category(draft)
        )

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
    existing = _existing_page(target.qmd_path)
    if existing is not None:
        _keep_site_frontmatter(mapped, existing)

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

        body = obsidian.transform_body(content, _resolver)
        result.written.extend(copied)

        if section == "recipes" and existing is not None and existing.cm_block:
            # content_manager's block already carries the video; it stays where
            # it was, at the top of the body, and no second embed is added.
            body = f"{existing.cm_block}\n\n{body.lstrip()}"
            mapped.pop("video", None)
        elif section == "recipes" and mapped.get("video"):
            body = embeds.video_embed(str(mapped["video"])) + "\n" + body
            mapped.pop("video")  # rendered into the body, not shown as metadata

    target.qmd_path.parent.mkdir(parents=True, exist_ok=True)
    target.qmd_path.write_text(_dump_qmd(mapped, body), encoding="utf-8")
    result.written.append(target.qmd_path)
    return result

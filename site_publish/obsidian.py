"""Obsidian-flavoured Markdown -> Quarto Markdown body transforms.

Pure text in, pure text out -- the one impure edge (copying embedded images)
is handled via an injected ``resolver`` callback so this module stays testable
and never touches the filesystem itself.

Transforms (applied outside of fenced/inline code, which is preserved verbatim):
- callouts:  ``> [!note] Title`` blocks -> ``::: {.callout-note title="Title"}``
- wikilinks: ``[[Note|alias]]`` -> ``alias`` (plain text; v1 doesn't cross-link)
- embeds:    ``![[img.png]]``   -> ``![](images/img.png)`` (via resolver)
- inline tags: ``#tag`` -> removed
"""

from __future__ import annotations

import re
from typing import Callable

# Obsidian callout type -> Quarto callout class suffix.
_CALLOUT_MAP = {
    "note": "note",
    "info": "note",
    "abstract": "note",
    "summary": "note",
    "quote": "note",
    "example": "note",
    "tip": "tip",
    "hint": "tip",
    "success": "tip",
    "question": "tip",
    "faq": "tip",
    "warning": "warning",
    "caution": "warning",
    "attention": "warning",
    "important": "important",
    "danger": "important",
    "error": "important",
    "bug": "caution",
    "failure": "caution",
    "todo": "caution",
}

_CALLOUT_HEAD = re.compile(r"^>\s*\[!(?P<type>\w+)\][+-]?\s*(?P<title>.*?)\s*$")
_WIKILINK = re.compile(r"!?\[\[([^\]]+)\]\]")
_IMAGE_EMBED = re.compile(r"!\[\[([^\]]+)\]\]")
# A hashtag tag: # immediately followed by a word char (so "# Heading" is safe).
_INLINE_TAG = re.compile(r"(?<!\w)#(?=[A-Za-z])[A-Za-z0-9_/-]+")


# --------------------------------------------------------------------------- #
# Code protection
# --------------------------------------------------------------------------- #
_FENCE = re.compile(r"^(\s*)(```+|~~~+)(.*)$")


def _protect_code(text: str) -> tuple[str, list[str]]:
    """Replace fenced + inline code with placeholders; return (text, blocks)."""
    blocks: list[str] = []
    out_lines: list[str] = []
    fence: str | None = None
    buf: list[str] = []

    for line in text.splitlines():
        m = _FENCE.match(line)
        if fence is None and m:
            fence = m.group(2)[0] * len(m.group(2).rstrip())
            buf = [line]
            continue
        if fence is not None:
            buf.append(line)
            stripped = line.strip()
            if stripped.startswith(fence[0]) and set(stripped) <= {fence[0]}:
                blocks.append("\n".join(buf))
                out_lines.append(f"\x00CODE{len(blocks) - 1}\x00")
                fence = None
            continue
        out_lines.append(line)

    if fence is not None:  # unterminated fence -- keep as-is
        blocks.append("\n".join(buf))
        out_lines.append(f"\x00CODE{len(blocks) - 1}\x00")

    text = "\n".join(out_lines)

    def _stash_inline(m: re.Match[str]) -> str:
        blocks.append(m.group(0))
        return f"\x00CODE{len(blocks) - 1}\x00"

    text = re.sub(r"`[^`\n]+`", _stash_inline, text)
    return text, blocks


def _restore_code(text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(f"\x00CODE{i}\x00", block)
    return text


# --------------------------------------------------------------------------- #
# Individual transforms
# --------------------------------------------------------------------------- #
def convert_callouts(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        head = _CALLOUT_HEAD.match(lines[i])
        if not head:
            out.append(lines[i])
            i += 1
            continue
        ctype = _CALLOUT_MAP.get(head.group("type").lower(), "note")
        title = head.group("title").strip()
        body: list[str] = []
        i += 1
        while i < len(lines) and lines[i].lstrip().startswith(">"):
            stripped = re.sub(r"^\s*>\s?", "", lines[i])
            body.append(stripped)
            i += 1
        attrs = f".callout-{ctype}"
        if title:
            attrs += f' title="{title}"'
        out.append(f"::: {{{attrs}}}")
        out.extend(body)
        out.append(":::")
    return "\n".join(out)


def rewrite_image_embeds(text: str, resolver: Callable[[str], str | None]) -> str:
    """Rewrite ``![[name]]`` using ``resolver(name) -> relative path | None``."""

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1).split("|")[0].strip()
        rel = resolver(name)
        if rel is None:
            return f"<!-- missing embed: {name} -->"
        return f"![]({rel})"

    return _IMAGE_EMBED.sub(_sub, text)


def convert_wikilinks(text: str) -> str:
    """Drop note-embeds to nothing useful; turn links into their display text."""

    def _sub(m: re.Match[str]) -> str:
        if m.group(0).startswith("!"):
            # A leftover ![[note]] note-embed (non-image): flatten to a note.
            target = m.group(1).split("|")[0].strip()
            return f"<!-- TODO: embedded note '{target}' not inlined -->"
        inner = m.group(1)
        display = inner.split("|", 1)[1] if "|" in inner else inner.split("#")[0]
        return display.strip()

    return _WIKILINK.sub(_sub, text)


def strip_inline_tags(text: str) -> str:
    return _INLINE_TAG.sub("", text)


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def transform_body(text: str, resolver: Callable[[str], str | None]) -> str:
    protected, blocks = _protect_code(text)
    protected = convert_callouts(protected)
    protected = rewrite_image_embeds(protected, resolver)
    protected = convert_wikilinks(protected)
    protected = strip_inline_tags(protected)
    return _restore_code(protected, blocks)

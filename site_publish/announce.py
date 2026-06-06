"""Compose a Bluesky announcement from a published vault draft.

The blog track publishes as a Substack embed, so a blog draft already carries
the canonical ``substack:`` URL to point the announcement at. For other
sections (or to point somewhere else) pass an explicit ``--url``.

Composition is deliberately thin: a headline + the link, with hashtags only if
asked for. ``bluesky.detect_facets`` makes the link (and any ``#tags``)
clickable, so the text we build here is just plain prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Announcement:
    text: str
    url: str | None


def _draft_meta(draft: Path) -> dict[str, Any]:
    import frontmatter

    if not draft.exists():
        raise ValueError(f"Draft not found: {draft}")
    return frontmatter.load(str(draft)).metadata


def compose(
    *,
    draft: Path | None = None,
    title: str | None = None,
    url: str | None = None,
    tags: list[str] | None = None,
    lead: str = "New post",
) -> Announcement:
    """Build the announcement text from a draft and/or explicit overrides."""
    meta = _draft_meta(draft) if draft else {}
    title = title or meta.get("title")
    # Blogs store the canonical link in `substack:`; --url overrides anything.
    url = url or meta.get("substack")

    if not title:
        raise ValueError("No title: pass --title or a draft with a 'title'.")
    if not url:
        raise ValueError(
            "No link: pass --url (or publish a blog draft that has a "
            "'substack:' URL)."
        )

    text = f"{lead} — {title}\n\n{url}"
    if tags:
        cleaned = [t.lstrip("#").strip() for t in tags if t.strip()]
        if cleaned:
            text += "\n\n" + " ".join(f"#{t}" for t in cleaned)
    return Announcement(text=text, url=url)

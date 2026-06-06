"""Compose a Bluesky announcement from a published vault draft.

The blog track publishes as a Substack embed, so a blog draft already carries
the canonical ``substack:`` URL to point the announcement at. For other
sections (or to point somewhere else) pass an explicit ``--url``.

Composition is deliberately thin: a fixed invitation line + the link, with
hashtags only if asked for. ``bluesky.detect_facets`` makes the link (and any
``#tags``) clickable, so the text we build here is just plain prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import embeds


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
    url: str | None = None,
    tags: list[str] | None = None,
) -> Announcement:
    """Build the announcement text from a draft and/or explicit overrides."""
    meta = _draft_meta(draft) if draft else {}
    # An explicit --url is posted verbatim; a blog draft's `substack:` link is
    # normalized to the canonical post URL via the same transform the embed
    # uses, so we announce the clean link rather than the tracking-param
    # "Share" form.
    if url is None:
        share = meta.get("substack")
        url = embeds.canonical_substack_url(share) if share else None

    if not url:
        raise ValueError(
            "No link: pass --url (or publish a blog draft that has a "
            "'substack:' URL)."
        )

    text = (
        "I just posted a new blog to substack, check it out and let me know "
        f"what you think! {url}"
    )
    if tags:
        cleaned = [t.lstrip("#").strip() for t in tags if t.strip()]
        if cleaned:
            text += "\n\n" + " ".join(f"#{t}" for t in cleaned)
    return Announcement(text=text, url=url)

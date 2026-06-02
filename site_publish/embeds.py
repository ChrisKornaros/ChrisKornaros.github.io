"""HTML embed snippets generated from frontmatter (blogs, recipe videos).

Emitted as Quarto raw-HTML blocks (```` ```{=html} ````), matching the existing
Substack pattern in source/pages/blogs/posts/test.qmd.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def substack_embed(title: str, url: str) -> str:
    """Substack post embed stub (verbatim shape of the existing test.qmd)."""
    return (
        "```{=html}\n"
        f'<div class="substack-post-embed"><p lang="en">{title} by '
        f'Chris Kornaros</p><p></p><a data-post-link href="{url}">Read on '
        'Substack</a></div><script async src="https://substack.com/embedjs/'
        'embed.js" charset="utf-8"></script>\n'
        "```\n"
    )


def _youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid if _YT_ID.match(vid) else None
    if "youtube.com" in host:
        if parsed.path.startswith(("/embed/", "/shorts/")):
            vid = parsed.path.split("/")[2]
            return vid if _YT_ID.match(vid) else None
        vid = parse_qs(parsed.query).get("v", [""])[0]
        return vid if _YT_ID.match(vid) else None
    return None


def video_embed(url: str) -> str:
    """Responsive video embed for a recipe.

    YouTube URLs become a proper iframe embed. Other platforms
    (Instagram/TikTok) fall back to a generic responsive iframe -- refine per
    platform once the recipe content strategy settles on one.
    """
    yt = _youtube_id(url)
    if yt:
        src = f"https://www.youtube.com/embed/{yt}"
    else:
        src = url
    return (
        "```{=html}\n"
        '<div class="ratio ratio-16x9 my-3">\n'
        f'  <iframe src="{src}" title="Recipe video" loading="lazy" '
        'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
        'encrypted-media; gyroscope; picture-in-picture; web-share" '
        "allowfullscreen></iframe>\n"
        "</div>\n"
        "```\n"
    )

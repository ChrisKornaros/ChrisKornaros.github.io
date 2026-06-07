"""Minimal Bluesky (AT Protocol) post client -- stdlib only, no SDK.

Implements the two-call flow from https://docs.bsky.app/blog/create-post:

1. ``com.atproto.server.createSession`` with an identifier + app password to
   get a short-lived ``accessJwt`` and the account ``did``.
2. ``com.atproto.repo.createRecord`` to write an ``app.bsky.feed.post`` record.

Rich-text **facets** (clickable links and hashtags) are byte-indexed into the
UTF-8 text, so we detect them on the encoded bytes -- the indices the API
expects are byte offsets, not character offsets.

This module knows nothing about where the password comes from; the caller
passes it in (see ``secrets.py`` for the Bitwarden boundary).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

DEFAULT_SERVICE = "https://bsky.social"

# A descriptive UA -- some hosts (Substack included) serve thin/blocked HTML to
# the bare urllib default.
_UA = "ChrisKornaros-site-publish/1.0 (+https://chriskornaros.github.io)"
# Only read the head-ish portion of a page; OG tags live up top.
_MAX_HTML_BYTES = 600_000
# Bluesky caps a blob at ~1 MB; stay safely under so uploadBlob doesn't 413.
_MAX_THUMB_BYTES = 976_560

# Detected on the UTF-8 *bytes* so match offsets are byte offsets (what facets
# need). Trailing punctuation is trimmed from links so a sentence-final URL
# doesn't swallow the period.
_URL_RE = re.compile(rb"https?://[^\s\]\)>]+")
_TAG_RE = re.compile(rb"(?:^|\s)(#[A-Za-z][A-Za-z0-9_]*)")
_URL_TRAILING = b".,;:!?)\"'"


class BlueskyError(RuntimeError):
    """A createSession / createRecord call failed."""


def detect_facets(text: str) -> list[dict[str, Any]]:
    """Build the ``facets`` array (link + hashtag features) for ``text``.

    Indices are UTF-8 byte offsets, per the AT Protocol spec.
    """
    raw = text.encode("utf-8")
    facets: list[dict[str, Any]] = []

    for m in _URL_RE.finditer(raw):
        start, end = m.start(), m.end()
        # Trim trailing punctuation that isn't really part of the URL.
        # raw[i] is an int; `int in bytes` tests the byte value.
        while end > start and raw[end - 1] in _URL_TRAILING:
            end -= 1
        uri = raw[start:end].decode("utf-8")
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#link", "uri": uri}
                ],
            }
        )

    for m in _TAG_RE.finditer(raw):
        start, end = m.start(1), m.end(1)  # group 1 excludes the leading space
        tag = raw[start:end].decode("utf-8").lstrip("#")
        facets.append(
            {
                "index": {"byteStart": start, "byteEnd": end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#tag", "tag": tag}
                ],
            }
        )

    facets.sort(key=lambda f: f["index"]["byteStart"])
    return facets


def _post_json(
    url: str, payload: dict[str, Any], *, token: str | None = None
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        # The body may name the error (e.g. AuthenticationRequired) but never
        # echoes the password back, so it's safe to surface.
        raise BlueskyError(f"{url} -> HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise BlueskyError(f"{url} unreachable: {exc.reason}") from exc


def create_session(
    identifier: str, password: str, *, service: str = DEFAULT_SERVICE
) -> dict[str, Any]:
    """Exchange an identifier + app password for a session (accessJwt, did)."""
    return _post_json(
        f"{service}/xrpc/com.atproto.server.createSession",
        {"identifier": identifier, "password": password},
    )


def _now_iso() -> str:
    # Trailing 'Z' is preferred over '+00:00' per the docs.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def create_post(
    session: dict[str, Any],
    text: str,
    *,
    langs: tuple[str, ...] = ("en",),
    embed: dict[str, Any] | None = None,
    service: str = DEFAULT_SERVICE,
) -> dict[str, Any]:
    """Create an ``app.bsky.feed.post`` record; returns the API response (uri, cid).

    Pass ``embed`` (e.g. from :func:`build_external_embed`) to attach a link card.
    """
    record: dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": _now_iso(),
        "langs": list(langs),
    }
    facets = detect_facets(text)
    if facets:
        record["facets"] = facets
    if embed:
        record["embed"] = embed

    return _post_json(
        f"{service}/xrpc/com.atproto.repo.createRecord",
        {
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        token=session["accessJwt"],
    )


class _OGParser(HTMLParser):
    """Collect ``<meta property|name=… content=…>`` pairs (first wins)."""

    def __init__(self) -> None:
        super().__init__()
        self.props: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        a = {k: v for k, v in attrs}
        key = a.get("property") or a.get("name")
        content = a.get("content")
        if key and content and key not in self.props:
            self.props[key] = content


def _get(url: str, *, timeout: float = 10.0) -> tuple[bytes, str] | None:
    """GET ``url`` with a real UA; return ``(body, content_type)`` or None."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read(_MAX_HTML_BYTES)
    except (urllib.error.URLError, OSError):
        return None
    return body, ctype


def fetch_external_card(url: str) -> dict[str, str] | None:
    """Fetch a page's Open Graph card data.

    Returns ``{"uri", "title", "description", "image_url"}`` (any of the last
    three may be empty), or None if the page can't be fetched / isn't HTML.
    """
    got = _get(url)
    if got is None:
        return None
    body, ctype = got
    if "html" not in ctype.lower():
        return None
    text = body.decode("utf-8", "replace")
    parser = _OGParser()
    try:
        parser.feed(text)
    except Exception:  # pragma: no cover - defensive against malformed HTML
        pass
    p = parser.props
    return {
        "uri": url,
        "title": p.get("og:title") or p.get("twitter:title") or "",
        "description": p.get("og:description") or p.get("twitter:description") or "",
        "image_url": p.get("og:image") or p.get("twitter:image") or "",
    }


def upload_blob(
    session: dict[str, Any], data: bytes, mime: str, *, service: str = DEFAULT_SERVICE
) -> dict[str, Any]:
    """Upload raw bytes via ``com.atproto.repo.uploadBlob``; returns the response.

    The blob ref the caller wants is ``response["blob"]``.
    """
    req = urllib.request.Request(
        f"{service}/xrpc/com.atproto.repo.uploadBlob", data=data, method="POST"
    )
    req.add_header("Content-Type", mime or "application/octet-stream")
    req.add_header("Authorization", f"Bearer {session['accessJwt']}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise BlueskyError(f"uploadBlob -> HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise BlueskyError(f"uploadBlob unreachable: {exc.reason}") from exc


def _thumb_blob(
    session: dict[str, Any], image_url: str, *, service: str
) -> dict[str, Any] | None:
    """Download an OG image and upload it as a blob; None if anything's off.

    Image problems never sink the post -- a card without a thumb still beats a
    bare link.
    """
    got = _get(image_url)
    if got is None:
        return None
    data, ctype = got
    mime = ctype.split(";")[0].strip().lower()
    if not data or len(data) > _MAX_THUMB_BYTES or not mime.startswith("image/"):
        return None
    try:
        resp = upload_blob(session, data, mime, service=service)
    except BlueskyError:
        return None
    return resp.get("blob")


def build_external_embed(
    session: dict[str, Any], url: str, *, service: str = DEFAULT_SERVICE
) -> dict[str, Any] | None:
    """Build an ``app.bsky.embed.external`` link card for ``url``.

    Degrades gracefully: no usable card data -> None; image missing / too big /
    upload fails -> a card with title + description but no thumbnail.
    """
    card = fetch_external_card(url)
    if not card or not (card["title"] or card["description"]):
        return None
    external: dict[str, Any] = {
        "uri": card["uri"],
        "title": card["title"],
        "description": card["description"],
    }
    if card["image_url"]:
        thumb = _thumb_blob(session, card["image_url"], service=service)
        if thumb:
            external["thumb"] = thumb
    return {"$type": "app.bsky.embed.external", "external": external}


def post_web_url(handle: str, at_uri: str) -> str | None:
    """Turn an ``at://did/app.bsky.feed.post/<rkey>`` URI into a bsky.app link."""
    rkey = at_uri.rsplit("/", 1)[-1] if at_uri else ""
    if not rkey:
        return None
    return f"https://bsky.app/profile/{handle}/post/{rkey}"

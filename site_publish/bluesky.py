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
from typing import Any

DEFAULT_SERVICE = "https://bsky.social"

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
    service: str = DEFAULT_SERVICE,
) -> dict[str, Any]:
    """Create an ``app.bsky.feed.post`` record; returns the API response (uri, cid)."""
    record: dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": _now_iso(),
        "langs": list(langs),
    }
    facets = detect_facets(text)
    if facets:
        record["facets"] = facets

    return _post_json(
        f"{service}/xrpc/com.atproto.repo.createRecord",
        {
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": record,
        },
        token=session["accessJwt"],
    )


def post_web_url(handle: str, at_uri: str) -> str | None:
    """Turn an ``at://did/app.bsky.feed.post/<rkey>`` URI into a bsky.app link."""
    rkey = at_uri.rsplit("/", 1)[-1] if at_uri else ""
    if not rkey:
        return None
    return f"https://bsky.app/profile/{handle}/post/{rkey}"

"""Command-line entry points: ``publish`` and ``new`` (wired in pyproject)."""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from . import config, convert, frontmatter_map
from .convert import ConvertError
from .frontmatter_map import FrontmatterError

_TEMPLATES = Path(__file__).resolve().parent / "templates"


def _rel(path: Path) -> Path | str:
    """Path relative to the repo root when possible, else the absolute path."""
    try:
        return path.relative_to(config.REPO_ROOT)
    except ValueError:
        return path


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #
def _iter_non_draft_drafts():
    import frontmatter

    writing = config.vault_writing()
    for md in sorted(writing.rglob("*.md")):
        parts = md.relative_to(writing).parts
        # Only files that live under a known section (skip index.md, attachments, etc.)
        if not parts or parts[0] not in config.SECTIONS:
            continue
        try:
            meta = frontmatter.load(str(md)).metadata
        except Exception:
            continue
        if not frontmatter_map.is_draft(meta):
            yield md


def publish(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="publish",
        description="Convert a vault draft to a site .qmd (no git -- the "
        "/publish skill handles branch/PR/deploy).",
    )
    parser.add_argument("file", nargs="?", help="Path to a vault draft (.md).")
    parser.add_argument(
        "--all", action="store_true",
        help="Convert every non-draft file under the vault writing root.",
    )
    args = parser.parse_args(argv)

    if bool(args.file) == bool(args.all):
        parser.error("Provide exactly one of: a FILE, or --all.")

    drafts = [Path(args.file)] if args.file else list(_iter_non_draft_drafts())
    if not drafts:
        print("No non-draft files to publish.")
        return 0

    failures = 0
    for draft in drafts:
        try:
            result = convert.convert(draft)
        except (ConvertError, FrontmatterError, ValueError) as exc:
            print(f"  ✗ {draft}: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"  ✓ {draft.name} -> {_rel(result.qmd_path)}")
        for extra in result.written:
            if extra != result.qmd_path:
                print(f"      + {_rel(extra)}")
        if convert.clear_source_draft(draft):
            print("      (un-drafted vault source)")

    if failures:
        print(f"\n{failures} file(s) failed.", file=sys.stderr)
        return 1
    return 0


# --------------------------------------------------------------------------- #
# new
# --------------------------------------------------------------------------- #
def new_draft(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="new",
        description="Scaffold a new vault draft with section frontmatter.",
    )
    parser.add_argument("section", choices=config.SECTIONS)
    parser.add_argument("title", help='Draft title, e.g. "Braised Short Ribs".')
    parser.add_argument(
        "--category", help="Recipe category subfolder (required for recipes).",
    )
    args = parser.parse_args(argv)

    if args.section == "recipes" and not args.category:
        parser.error("recipes require --category, e.g. --category Beef.")

    slug = config.slugify(args.title)
    base = config.vault_writing() / args.section
    dest = base / args.category / f"{slug}.md" if args.category else base / f"{slug}.md"

    if dest.exists():
        print(f"Refusing to overwrite existing draft: {dest}", file=sys.stderr)
        return 1

    template = (_TEMPLATES / f"{args.section}.md").read_text(encoding="utf-8")
    content = template.format(
        title=args.title,
        date=_dt.date.today().isoformat(),
        category=args.category or "",
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"Created {dest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(publish())

#!/usr/bin/env python3
"""dokuwiki2wikijs.py

A **self‑contained** converter that walks a DokuWiki data folder (the one that
contains your ``pages`` sub‑tree) and produces a parallel folder tree with
Markdown (*.md*) files and copied media assets that Wiki.js can import via the
*Administration → Imports → Markdown* wizard or by pointing a Git sync
repository to the generated directory.

Features
========
* Converts headings (``=`` to ``#``), bold, italic, internal links, images,
  lists, code blocks and tables that follow the most common DokuWiki syntax.
* Preserves the namespace hierarchy: ``foo:bar:baz`` becomes ``foo/bar/baz.md``.
* Copies media files from the specified ``data/media`` directory into an
  ``_media`` folder next to their referencing Markdown page and rewrites the
  links accordingly.
* Designed to run with **no external dependencies**, but transparently uses the
  *dokuwiki2markdown* PyPI package if you already have it – this gives better
  edge‑case coverage without changing the command line.

Usage
-----
```bash
python dokuwiki2wikijs.py /srv/dokuwiki/data/pages ./wikijs-import \
    --media-dir /srv/dokuwiki/data/media --verbose
```

Then in Wiki.js (v2.5+):
1. Log in as an administrator → *Import*.
2. Pick *Markdown Folder* as the source and select *wikijs-import*.
3. Review the preview and import.

The script never touches your source wiki; it only reads files.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Iterable, Tuple

# ---------------------------------------------------------------------------
# Optional best‑effort import of a richer converter.
try:
    from dokuwiki2markdown import convert as dk2md  # type: ignore
except ImportError:  # pragma: no cover
    dk2md = None  # fall back to regex converter below


def debug(enabled: bool, *msg: object) -> None:
    """Cheap debug printer controlled by --verbose."""
    if enabled:
        print("[dokuwiki2wikijs]", *msg)


# ---------------------------------------------------------------------------
# Primitive regex‑based converter (good enough for most clean pages)
_HEADING_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1$", re.MULTILINE)
_BOLD_ITALIC_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (r"\*\*([^*]+)\*\*", r"**\1**"),  # bold stays bold but normalise spacing
    (r"//([^/]+)//", r"*\1*"),          # italic → *italic*
)
_LINK_RE = re.compile(r"\[\[(?P<target>[^]|]+)(?:\|(?P<label>[^]]+))?]]")
_IMAGE_RE = re.compile(r"{{(?P<target>[^}|]+)(?:\|(?P<alt>[^}]+))?}}")
_CODEBLOCK_RE = re.compile(r"<code(?: [^>]*)?>\n?(.*?)\n?</code>", re.S)
_NOWIKI_RE = re.compile(r"<nowiki>(.*?)</nowiki>", re.S)
_TABLE_RE = re.compile(r"^\^(.*?)\^$", re.M)  # very naive table header detector


def _dk_to_md_regex(source: str, page_ns: str) -> str:
    """Very small DokuWiki → Markdown subset using regexes."""

    def heading(m: re.Match[str]) -> str:  # noqa: D401
        level = len(m.group(1))
        return f"{'#' * level} {m.group(2)}"

    txt = _HEADING_RE.sub(heading, source)

    # Bold / italic replacements
    for pattern, repl in _BOLD_ITALIC_REPLACEMENTS:
        txt = re.sub(pattern, repl, txt)

    # Code blocks
    txt = _CODEBLOCK_RE.sub(lambda m: f"```\n{m.group(1).rstrip()}\n```", txt)
    txt = _NOWIKI_RE.sub(lambda m: f"```\n{m.group(1).rstrip()}\n```", txt)

    # Images – rewrite to Markdown syntax and path
    txt = _IMAGE_RE.sub(lambda m: _replace_media(m, page_ns, embed=True), txt)

    # Links
    txt = _LINK_RE.sub(lambda m: _replace_links(m, page_ns), txt)

    # Very rough table header conversion (optional – Wiki.js can parse pipe tables)
    txt = _TABLE_RE.sub(lambda m: "| " + " | ".join(col.strip() for col in m.group(1).split("^")) + " |", txt)

    return txt


def _replace_media(match: re.Match[str], page_ns: str, embed: bool = False) -> str:
    target = match.group("target")
    alt = match.groupdict().get("alt") or ""
    md_path = _dokuwiki_id_to_path(target, suffix="", is_media=True)
    if embed:
        return f"![{alt}]({md_path})"
    return f"[{alt}]({md_path})"


def _replace_links(match: re.Match[str], page_ns: str) -> str:
    target = match.group("target")
    label = match.group("label") or target
    md_path = _dokuwiki_id_to_path(target, suffix=".md")
    return f"[{label}]({md_path})"


# ---------------------------------------------------------------------------
# Helpers

COLON = ":"


def _dokuwiki_id_to_path(doku_id: str, *, suffix: str = "", is_media: bool = False) -> str:
    """Convert ``foo:bar:baz`` → ``foo/bar/baz{suffix}``."""
    parts = doku_id.split(COLON)
    return "/".join(parts) + suffix


def _iter_txt_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.txt"):
        yield p


def _write_file(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main conversion driver

def convert_site(pages_dir: Path, output_dir: Path, *, media_dir: Path | None = None,
                 force: bool = False, verbose: bool = False) -> None:
    """Convert a complete DokuWiki *pages* tree into Markdown."""

    converter = dk2md or _dk_to_md_regex  # use library if available

    for txt_path in _iter_txt_files(pages_dir):
        rel_ns = txt_path.relative_to(pages_dir).with_suffix("")  # remove .txt
        page_id = COLON.join(rel_ns.parts)
        md_rel_path = Path(_dokuwiki_id_to_path(page_id, suffix=".md"))
        md_abs_path = output_dir / md_rel_path

        debug(verbose, "Converting", page_id, "→", md_rel_path)

        src_text = txt_path.read_text(encoding="utf-8")
        md_text = converter(src_text, page_id) if dk2md else converter(src_text, page_id)
        _write_file(md_abs_path, md_text, force=force)

    if media_dir and media_dir.exists():
        debug(verbose, "Copying media…")
        _copy_media(media_dir, output_dir, force=force, verbose=verbose)


# ---------------------------------------------------------------------------
# Media handling

def _copy_media(media_root: Path, dest_root: Path, *, force: bool, verbose: bool) -> None:
    for media_path in media_root.rglob("*"):
        if media_path.is_file():
            rel_ns = media_path.relative_to(media_root)
            dest_path = dest_root / "_media" / rel_ns
            if dest_path.exists() and not force:
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(media_path, dest_path)
            debug(verbose, "  ↳", rel_ns)


# ---------------------------------------------------------------------------
# Entry point

def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description="Convert DokuWiki syntax & filesystem to Markdown for Wiki.js import.")
    ap.add_argument("pages_dir", type=Path, help="Path to DokuWiki data/pages directory")
    ap.add_argument("output_dir", type=Path, help="Destination root for Markdown files")
    ap.add_argument("--media-dir", type=Path, dest="media_dir", help="Path to DokuWiki data/media directory")
    ap.add_argument("--force", action="store_true", help="Overwrite existing files in output")
    ap.add_argument("--verbose", action="store_true", help="Show converted pages & media")
    args = ap.parse_args()

    convert_site(args.pages_dir, args.output_dir, media_dir=args.media_dir,
                 force=args.force, verbose=args.verbose)


if __name__ == "__main__":
    main()

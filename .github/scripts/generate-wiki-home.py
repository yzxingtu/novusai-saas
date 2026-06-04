#!/usr/bin/env python3
"""Prepare GitHub Wiki content from .qoder/repowiki/zh/content/.

For every markdown file the script:
  1. Strips ``<cite>…</cite>`` blocks (source-reference metadata).
  2. Rewrites ``file://`` links to GitHub repository blob URLs so they
     are clickable inside the wiki.

It also generates:
  • Home.md     – wiki landing page with section overview.
  • _Sidebar.md – persistent sidebar for in-wiki navigation.

All output is written to OUTPUT_DIR (default: ``.wiki-staging/``).
The CI workflow copies that directory into the wiki git repo.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

CONTENT_DIR = Path(".qoder/repowiki/zh/content")
OUTPUT_DIR = Path(".wiki-staging")

# Resolved at runtime from $GITHUB_SERVER_URL / $GITHUB_REPOSITORY, with
# a sensible default for local testing.
REPO_BASE_URL = (
    f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}"
    f"/{os.environ.get('GITHUB_REPOSITORY', 'yzxingtu/novusai-saas')}"
)
DEFAULT_BRANCH = "main"

# ── cite stripping ────────────────────────────────────────────────────────────

_CITE_RE = re.compile(
    r"<cite\b[^>]*>.*?</cite>",
    re.DOTALL,
)


def strip_cite_blocks(text: str) -> str:
    """Remove all ``<cite>…</cite>`` blocks (including multi-line ones)."""
    return _CITE_RE.sub("", text).strip()


# ── file:// link rewriting ────────────────────────────────────────────────────

# Matches:  [anything](file://path)  or  [anything](file://path#L1-L10)
_FILE_LINK_RE = re.compile(
    r"\[([^\]]+)\]\(file://([^)#]+)(#[^)]+)?\)"
)


def rewrite_file_links(text: str) -> str:
    """Replace ``file://…`` links with GitHub blob URLs.

    Example
    -------
    ``[backend/app/core/security.py:431-468](file://backend/app/core/security.py#L431-L468)``
    → ``[backend/app/core/security.py:431-468](https://github.com/owner/repo/blob/main/backend/app/core/security.py#L431-L468)``
    """

    def _replace(m: re.Match) -> str:
        label = m.group(1)
        filepath = m.group(2)
        fragment = m.group(3) or ""  # e.g. "#L431-L468"
        url = f"{REPO_BASE_URL}/blob/{DEFAULT_BRANCH}/{filepath}{fragment}"
        return f"[{label}]({url})"

    return _FILE_LINK_RE.sub(_replace, text)


# ── helpers ──────────────────────────────────────────────────────────────────

def process_md(text: str) -> str:
    """Apply all content transformations to a markdown string."""
    text = strip_cite_blocks(text)
    text = rewrite_file_links(text)
    return text


def extract_first_paragraph(text: str) -> str:
    """Return the first real paragraph from processed markdown text."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        # Skip TOC entries, links, list items, tables, blockquotes
        if re.match(r"^(\d+\.\s+\[|[-*|>])", stripped):
            continue
        if stripped.startswith("[") or stripped.startswith("*"):
            continue
        return stripped.rstrip("。，,.")
    return ""


def wiki_link(rel_path: Path) -> str:
    """Convert a relative content path to a GitHub Wiki page name.

    GitHub Wiki flattens subdirectories into dash-separated names.
    e.g. ``AI能力系统/AI网关系统.md`` → ``AI能力系统-AI网关系统``
    """
    return str(rel_path.with_suffix("")).replace(os.sep, "-")


def wiki_url(page_name: str) -> str:
    return page_name.replace(" ", "-")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # Clean output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    sections: list[dict] = []

    # ── Process & copy all markdown files ─────────────────────────────────────
    for entry in sorted(CONTENT_DIR.iterdir()):
        if not entry.is_dir():
            # Copy loose .md files at root level
            if entry.suffix == ".md":
                out = OUTPUT_DIR / entry.name
                out.write_text(process_md(entry.read_text(encoding="utf-8")),
                               encoding="utf-8")
            continue

        overview_file = entry / f"{entry.name}.md"
        sub_pages: list[Path] = []

        for md_file in sorted(entry.rglob("*.md")):
            raw = md_file.read_text(encoding="utf-8")
            processed = process_md(raw)

            # Mirror directory structure in output
            rel = md_file.relative_to(CONTENT_DIR)
            out_path = OUTPUT_DIR / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(processed, encoding="utf-8")

            if md_file != overview_file:
                sub_pages.append(md_file)

        desc = ""
        if overview_file.exists():
            processed_overview = (OUTPUT_DIR / overview_file.relative_to(CONTENT_DIR)
                                  ).read_text(encoding="utf-8")
            desc = extract_first_paragraph(processed_overview)

        sections.append({
            "title": entry.name,
            "overview": overview_file if overview_file.exists() else None,
            "desc": desc,
            "pages": sub_pages,
        })

    # ── Build Home.md ─────────────────────────────────────────────────────────
    overview_md = CONTENT_DIR / "项目概述" / "项目概述.md"
    intro = ""
    if overview_md.exists():
        intro = extract_first_paragraph(
            process_md(overview_md.read_text(encoding="utf-8"))
        )
    if not intro:
        intro = "NovusAI SaaS 是一个面向二次开发的多租户 AI 原生 SaaS 开发框架。"

    lines = [
        "# NovusAI SaaS 技术文档",
        "",
        f"> {intro}",
        "",
        "---",
        "",
        "## 📚 文档目录",
        "",
    ]

    for sec in sections:
        title = sec["title"]
        overview_page = wiki_link(sec["overview"].relative_to(CONTENT_DIR)) if sec["overview"] else None
        desc = sec["desc"]

        if overview_page:
            lines.append(f"### [{title}]({wiki_url(overview_page)})")
        else:
            lines.append(f"### {title}")

        if desc:
            lines.append(f"\n{desc}\n")

        if sec["pages"]:
            sub_items = []
            for p in sec["pages"][:8]:
                page_name = wiki_link(p.relative_to(CONTENT_DIR))
                sub_items.append(f"[{p.stem}]({wiki_url(page_name)})")
            lines.append(" | ".join(sub_items))
            remaining = len(sec["pages"]) - 8
            if remaining > 0:
                lines.append(f"\n*…另有 {remaining} 篇文档*")

        lines.append("")

    lines.extend([
        "---",
        "",
        "*本 Wiki 由 CI 自动同步，源文件位于 `.qoder/repowiki/zh/content/`*",
        "",
    ])

    (OUTPUT_DIR / "Home.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Generated Home.md ({len(lines)} lines)")

    # ── Build _Sidebar.md ─────────────────────────────────────────────────────
    sidebar_lines = [
        "**[🏠 首页](Home)**",
        "",
        "---",
        "",
    ]

    for sec in sections:
        title = sec["title"]
        overview_page = wiki_link(sec["overview"].relative_to(CONTENT_DIR)) if sec["overview"] else None

        if overview_page:
            sidebar_lines.append(f"**[{title}]({wiki_url(overview_page)})**")
        else:
            sidebar_lines.append(f"**{title}**")

        for p in sec["pages"][:10]:
            page_name = wiki_link(p.relative_to(CONTENT_DIR))
            indent = "  " if p.parent.name == sec["title"] else "    "
            sidebar_lines.append(f"{indent}- [{p.stem}]({wiki_url(page_name)})")

        sidebar_lines.append("")

    (OUTPUT_DIR / "_Sidebar.md").write_text("\n".join(sidebar_lines), encoding="utf-8")
    print(f"✓ Generated _Sidebar.md ({len(sidebar_lines)} lines)")

    # Summary
    total_files = sum(1 for _ in OUTPUT_DIR.rglob("*.md"))
    print(f"✓ Staged {total_files} wiki pages → {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

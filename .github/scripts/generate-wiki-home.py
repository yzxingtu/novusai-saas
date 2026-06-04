#!/usr/bin/env python3
"""Generate Home.md for GitHub Wiki from .qoder/repowiki/zh/content/ structure.

Produces a landing page with:
- Project title & one-line description (from 项目概述/项目概述.md)
- Section cards linking to each top-level category
- Auto-generated sidebar (_Sidebar.md) for in-wiki navigation
"""

from __future__ import annotations

import os
import re
from pathlib import Path

CONTENT_DIR = Path(".qoder/repowiki/zh/content")
HOME_OUT = Path("Home.md")
SIDEBAR_OUT = Path("_Sidebar.md")

# ── helpers ──────────────────────────────────────────────────────────────────

def extract_first_paragraph(md_path: Path) -> str:
    """Return the first non-empty, non-heading paragraph from a markdown file."""
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8")
    in_cite = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<cite"):
            in_cite = True
            continue
        if stripped.startswith("</cite"):
            in_cite = False
            continue
        if in_cite:
            continue
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        # Skip TOC entries, links, list items, tables
        if re.match(r'^(\d+\.\s+\[|[-*|>])', stripped):
            continue
        if stripped.startswith("[") or stripped.startswith("*"):
            continue
        return stripped.rstrip("。，,.")
    return ""


def section_title(dirname: str) -> str:
    """Directory name is already the Chinese section title."""
    return dirname


def section_files(section_dir: Path) -> list[Path]:
    """Return all .md files in a section (sorted), excluding the overview file."""
    overview = section_dir / f"{section_dir.name}.md"
    files = sorted(section_dir.rglob("*.md"))
    return [f for f in files if f != overview]


def wiki_link(md_path: Path) -> str:
    """Convert a content path to a GitHub Wiki page link.

    GitHub Wiki flattens subdirectories into dash-separated page names.
    e.g. AI能力系统/AI网关系统.md  →  AI能力系统-AI网关系统
    """
    rel = md_path.relative_to(CONTENT_DIR)
    # Remove .md and replace path separators with dashes
    page_name = str(rel.with_suffix("")).replace(os.sep, "-")
    return page_name


def wiki_url(page_name: str) -> str:
    return page_name.replace(" ", "-")


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    sections: list[dict] = []

    for entry in sorted(CONTENT_DIR.iterdir()):
        if not entry.is_dir():
            continue
        overview_file = entry / f"{entry.name}.md"
        desc = extract_first_paragraph(overview_file)
        sub_pages = section_files(entry)

        sections.append({
            "title": section_title(entry.name),
            "overview": overview_file if overview_file.exists() else None,
            "desc": desc,
            "pages": sub_pages,
        })

    # ── Build Home.md ─────────────────────────────────────────────────────────
    overview_md = CONTENT_DIR / "项目概述" / "项目概述.md"
    intro = extract_first_paragraph(overview_md) or (
        "NovusAI SaaS 是一个面向二次开发的多租户 AI 原生 SaaS 开发框架。"
    )

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
        overview_page = wiki_link(sec["overview"]) if sec["overview"] else None
        desc = sec["desc"]

        if overview_page:
            lines.append(f"### [{title}]({wiki_url(overview_page)})")
        else:
            lines.append(f"### {title}")

        if desc:
            lines.append(f"\n{desc}\n")

        if sec["pages"]:
            sub_items = []
            for p in sec["pages"][:8]:  # Show up to 8 sub-pages
                page_name = wiki_link(p)
                sub_items.append(f"[{p.stem}]({wiki_url(page_name)})")
            lines.append(" | ".join(sub_items))
            remaining = len(sec["pages"]) - 8
            if remaining > 0:
                lines.append(f"\n*…另有 {remaining} 篇文档*")

        lines.append("")

    lines.extend([
        "---",
        "",
        "*本 Wiki 由 [sync-wiki.yml](.github/workflows/sync-wiki.yml) 自动同步，"
        "源文件位于 `.qoder/repowiki/zh/content/`*",
        "",
    ])

    HOME_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Generated {HOME_OUT} ({len(lines)} lines)")

    # ── Build _Sidebar.md ─────────────────────────────────────────────────────
    sidebar_lines = [
        "**[🏠 首页](Home)**",
        "",
        "---",
        "",
    ]

    for sec in sections:
        title = sec["title"]
        overview_page = wiki_link(sec["overview"]) if sec["overview"] else None

        if overview_page:
            sidebar_lines.append(f"**[{title}]({wiki_url(overview_page)})**")
        else:
            sidebar_lines.append(f"**{title}**")

        for p in sec["pages"][:10]:
            page_name = wiki_link(p)
            indent = "  " if p.parent.name == sec["title"] else "    "
            sidebar_lines.append(f"{indent}- [{p.stem}]({wiki_url(page_name)})")

        sidebar_lines.append("")

    SIDEBAR_OUT.write_text("\n".join(sidebar_lines), encoding="utf-8")
    print(f"✓ Generated {SIDEBAR_OUT} ({len(sidebar_lines)} lines)")


if __name__ == "__main__":
    main()

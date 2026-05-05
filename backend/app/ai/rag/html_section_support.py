"""
HTML section extraction support for RAG parsers.
"""

from __future__ import annotations

from typing import Any


def build_html_sections(
    html_text: str,
    *,
    source: str,
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    """Split HTML body text into heading-aware sections."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_text, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    sections: list[dict[str, Any]] = []
    body = soup.find("body") or soup
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    current_heading: str | None = title
    current_content: list[str] = []

    def flush() -> None:
        if not current_content:
            return
        metadata: dict[str, Any] = {
            "heading": current_heading,
            "source": source,
        }
        if source_url:
            metadata["source_url"] = source_url
        sections.append(
            {
                "content": "\n".join(current_content),
                "metadata": metadata,
            }
        )

    for element in body.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
        text = element.get_text(strip=True)
        if not text:
            continue

        if element.name and element.name.startswith("h"):
            flush()
            current_content = []
            current_heading = text
            continue

        current_content.append(text)

    flush()
    return sections


__all__ = ["build_html_sections"]

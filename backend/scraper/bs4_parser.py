from __future__ import annotations

import re
from bs4 import BeautifulSoup


def extract_visible_text(html: str) -> str:
    """Convert HTML into cleaned, readable text preserving paragraph structure."""
    soup = BeautifulSoup(html, "lxml")

    # Prefer main/article regions when available to reduce chrome/nav noise.
    main_node = (
        soup.select_one("main")
        or soup.select_one("article")
        or soup.select_one("[role='main']")
        or soup.select_one(".post-content")
        or soup.select_one(".article-body")
        or soup.select_one("#content")
    )
    if main_node is not None:
        soup = BeautifulSoup(str(main_node), "lxml")

    # Remove non-content elements
    for tag_name in [
        "script", "style", "noscript", "header", "footer", "nav", "aside",
        "iframe", "svg", "form", "button", "input", "select", "textarea",
        "figure", "figcaption",
    ]:
        for node in soup.find_all(tag_name):
            node.decompose()

    # Remove hidden elements
    for node in soup.find_all(attrs={"aria-hidden": "true"}):
        node.decompose()
    for node in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
        node.decompose()

    # Extract text from content-bearing tags, preserving structure
    content_tags = soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "blockquote", "pre", "dd", "dt"])

    if content_tags:
        paragraphs: list[str] = []
        for tag in content_tags:
            text = tag.get_text(separator=" ").strip()
            text = re.sub(r"\s+", " ", text)
            if text and len(text) > 15:
                paragraphs.append(text)
        result = "\n\n".join(paragraphs)
    else:
        # Fallback: get all text
        result = soup.get_text(separator=" ")
        result = re.sub(r"\s+", " ", result)

    # Remove common boilerplate — only filter very short fragments matching noise exactly
    lines = result.split("\n\n")
    noise_markers = [
        "skip to content", "jump to content", "open in app",
        "sign in to your account", "create an account",
    ]
    cleaned_lines: list[str] = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        lowered = line_stripped.lower()
        # Only drop if the line is SHORT and matches noise
        if len(line_stripped) < 60 and any(marker in lowered for marker in noise_markers):
            continue
        # Drop breadcrumb-style navigation paths
        if re.match(r"^[\w\s]+(\s*[>›»/|]\s*[\w\s]+){2,}$", line_stripped) and len(line_stripped) < 120:
            continue
        cleaned_lines.append(line_stripped)

    candidate = "\n\n".join(cleaned_lines).strip()
    return candidate if candidate else result.strip()

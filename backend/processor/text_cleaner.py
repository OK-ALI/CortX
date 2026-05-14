from __future__ import annotations

import re


def clean_text(text: str) -> str:
    """Apply cleaning to scraped text before ranking/synthesis."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    # Remove exact duplicate lines (common with boilerplate)
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    lines = deduped

    cleaned: list[str] = []
    for line in lines:
        # Remove breadcrumb-style navigation paths
        if re.match(r"^[\w\s]+(\s*[>›»/|]\s*[\w\s]+){2,}$", line) and len(line) < 120:
            continue

        # Remove social media share fragments
        lowered = line.lower()
        if len(line) < 50 and any(
            marker in lowered
            for marker in [
                "share on twitter", "share on facebook", "share on linkedin",
                "share this article", "follow us on", "tweet this",
                "share via email", "copy link",
            ]
        ):
            continue

        # Remove very short standalone lines that are usually UI noise
        if len(line) < 12 and not re.search(r"[.!?]$", line):
            continue

        cleaned.append(line)

    result = "\n".join(cleaned)

    # Normalize unicode whitespace artifacts
    result = re.sub(r"[\u00a0\u200b\u200c\u200d\ufeff]", " ", result)
    result = re.sub(r" {3,}", " ", result)

    return result.strip()

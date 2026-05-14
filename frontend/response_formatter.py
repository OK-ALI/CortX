"""Format pipeline results for chat display."""
from __future__ import annotations

import re


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\s*{re.escape(heading)}:\s*\n(.*?)(?=^\s*[A-Za-z][A-Za-z ]+:\s*\n|\Z)"
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _clean_findings(findings: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in findings.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        if re.match(r"^\[\d+\]\s*URL:\s*", line, flags=re.IGNORECASE):
            continue
        if re.match(r"^URL:\s*", line, flags=re.IGNORECASE):
            continue
        if re.match(r"^Tier:\s*", line, flags=re.IGNORECASE):
            continue

        excerpt_match = re.match(r"^Excerpt:\s*(.*)$", line, flags=re.IGNORECASE)
        if excerpt_match:
            line = excerpt_match.group(1).strip()

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def format_chat_result(raw: str) -> str:
    """Extract user-facing acknowledgement and findings from structured output."""
    text = raw.strip()
    if not text:
        return "I couldn't generate an answer for this query."

    ack = _extract_section(text, "LLM Acknowledgement")
    if not ack:
        ack = _extract_section(text, "Acknowledgement")

    findings = _extract_section(text, "Scraped Findings")
    cleaned_findings = _clean_findings(findings) if findings else ""

    parts = [part for part in [ack, cleaned_findings] if part]
    if not parts:
        # Fallback to general header cleanup for free-form model output.
        text = re.sub(
            r"^(Acknowledgement|LLM Acknowledgement|User Query|Refined Search Queries|Scraped Findings|Sources):\s*$",
            "",
            text,
            flags=re.MULTILINE,
        )
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() or "I couldn't generate an answer for this query."

    return "\n\n".join(parts).strip()


def format_chat_answer(answer: str) -> str:
    """UI helper that normalizes structured pipeline output for display."""
    return format_chat_result(answer)


def format_sources(sources: list[str]) -> list[str]:
    """Clean source strings for display."""
    cleaned: list[str] = []
    for src in sources:
        src = src.strip()
        if src and re.search(r"https?://", src):
            cleaned.append(src)
    return cleaned

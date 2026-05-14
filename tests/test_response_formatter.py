from __future__ import annotations

from frontend.response_formatter import format_chat_result


def test_format_chat_result_structured_output() -> None:
    raw = (
        "Acknowledgement:\n"
        "Scrape-grounded response only.\n\n"
        "LLM Acknowledgement:\n"
        "Here is what I found from scraped excerpts only.\n\n"
        "User Query:\n"
        "What is RAG?\n\n"
        "Refined Search Queries:\n"
        "- rag architecture\n\n"
        "Scraped Findings:\n"
        "RAG combines retrieval with generation to improve grounded responses.\n\n"
        "Sources:\n"
        "- https://example.com/rag"
    )

    output = format_chat_result(raw)

    assert output.startswith("Here is what I found from scraped excerpts only.")
    assert "RAG combines retrieval with generation" in output
    assert "Acknowledgement:" not in output
    assert "User Query:" not in output
    assert "Sources:" not in output


def test_format_chat_result_strips_raw_excerpt_blocks() -> None:
    raw = (
        "LLM Acknowledgement:\n"
        "Validation fallback used.\n\n"
        "Scraped Findings:\n"
        "[1] URL: https://a.example\n"
        "Tier: 0.80 relevance\n"
        "Excerpt: First refined excerpt text...\n\n"
        "[2] URL: https://b.example\n"
        "Tier: 0.60 relevance\n"
        "Excerpt: Second refined excerpt text...\n\n"
        "Sources:\n"
        "[1] https://a.example\n"
        "[2] https://b.example"
    )

    output = format_chat_result(raw)

    assert "Validation fallback used." in output
    assert "First refined excerpt text" in output
    assert "Second refined excerpt text" in output
    assert "URL:" not in output
    assert "Tier:" not in output

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object from potentially noisy model output."""
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty model output")

    # Strip markdown fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model output")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON is not an object")
    return parsed

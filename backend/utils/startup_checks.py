from __future__ import annotations

import sys
import subprocess
from dataclasses import dataclass

import httpx

from backend.utils.config import Settings


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


def _check_playwright_cli() -> CheckResult:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "playwright", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return CheckResult("playwright_cli", True, completed.stdout.strip())
    except Exception as exc:  # noqa: BLE001
        return CheckResult("playwright_cli", False, f"Playwright CLI check failed: {exc}")


def _check_ollama(url: str) -> CheckResult:
    tags_url = f"{url.rstrip('/')}/api/tags"
    try:
        response = httpx.get(tags_url, timeout=3.0)
        if response.status_code == 200:
            return CheckResult("ollama_service", True, "Ollama is reachable")
        return CheckResult("ollama_service", False, f"Unexpected status: {response.status_code}")
    except Exception as exc:  # noqa: BLE001
        return CheckResult("ollama_service", False, f"Unable to reach Ollama: {exc}")


def run_startup_checks(settings: Settings) -> list[CheckResult]:
    """Run lightweight environment checks before handling requests."""
    return [
        _check_playwright_cli(),
        _check_ollama(settings.ollama_url),
    ]

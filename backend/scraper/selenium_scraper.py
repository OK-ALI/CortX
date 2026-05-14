from __future__ import annotations

import contextlib
import html
import re
import time


def _create_driver():
    try:
        import undetected_chromedriver as uc  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001
        return None

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.set_page_load_timeout(20)
        return driver
    except Exception:  # noqa: BLE001
        return None


def _extract_best_effort_html(driver) -> str:
    """Prefer rendered body text wrapped as HTML for downstream parsing."""
    try:
        body_text = driver.execute_script("return document.body ? document.body.innerText : '';")
        body_text = str(body_text or "").strip()
        if body_text:
            safe_text = html.escape(re.sub(r"\s+", " ", body_text))
            return f"<html><body><main>{safe_text}</main></body></html>"
    except Exception:  # noqa: BLE001
        pass

    try:
        page_source = str(driver.page_source or "").strip()
        return page_source
    except Exception:  # noqa: BLE001
        return ""


def scrape_with_selenium_fallback(urls: list[str]) -> list[tuple[str, str]]:
    """Best-effort browser fallback for pages blocked in earlier tiers."""
    if not urls:
        return []

    driver = _create_driver()
    if driver is None:
        return []

    rendered: list[tuple[str, str]] = []
    try:
        for url in urls:
            if not (url.startswith("http://") or url.startswith("https://")):
                continue

            try:
                driver.get(url)
                time.sleep(1.0)
            except Exception:  # noqa: BLE001
                continue

            html_content = _extract_best_effort_html(driver)
            if html_content:
                rendered.append((url, html_content))
    finally:
        with contextlib.suppress(Exception):
            driver.quit()
        # Prevent __del__ from calling quit() again (causes OSError on Windows)
        try:
            driver.__class__.__del__ = lambda self: None
        except Exception:
            pass

    return rendered

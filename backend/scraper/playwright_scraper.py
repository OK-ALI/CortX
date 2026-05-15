from __future__ import annotations

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def scrape_with_playwright(
    urls: list[str], timeout_seconds: int, user_agent: str
) -> list[tuple[str, str]]:
    """Render pages in a real browser when static HTTP scraping is insufficient."""
    if not urls:
        return []

    rendered: list[tuple[str, str]] = []
    timeout_ms = max(timeout_seconds, 1) * 1000

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        try:
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False
            )
            page = await context.new_page()

            # Apply anti-bot stealth scripts (Webgl spoof, navigator.webdriver strip, etc)
            await stealth_async(page)

            for url in urls:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    await page.wait_for_timeout(300)
                    html = await page.content()
                    rendered.append((url, html))
                except Exception:  # noqa: BLE001
                    continue

            await context.close()
        finally:
            await browser.close()

    return rendered

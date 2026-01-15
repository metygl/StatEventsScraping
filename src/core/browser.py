"""
Playwright browser management for async web scraping.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser instances for scraping."""

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: int = 30000,
    ):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by this many milliseconds
            timeout: Default timeout for operations in milliseconds
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def start(self):
        """Initialize Playwright and launch browser."""
        logger.info("Starting browser...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )
        logger.info(f"Browser started (headless={self.headless})")

    async def stop(self):
        """Clean up browser and Playwright."""
        logger.info("Stopping browser...")
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser stopped")

    @asynccontextmanager
    async def new_page(self) -> Page:
        """
        Create a new browser page with default settings.

        Usage:
            async with browser_manager.new_page() as page:
                await page.goto(url)
        """
        context: BrowserContext = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        context.set_default_timeout(self.timeout)

        page = await context.new_page()
        try:
            yield page
        finally:
            await context.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

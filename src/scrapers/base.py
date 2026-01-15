"""
Abstract base class for all site-specific scrapers.
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from playwright.async_api import Page, ElementHandle

from src.models.event import Event, LocationType
from src.core.exceptions import SiteUnreachableError
from src.utils.retry import async_retry

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all site-specific scrapers."""

    # Subclasses must define these
    SOURCE_NAME: str = ""  # e.g., "Harvard HSPH"
    BASE_URL: str = ""  # e.g., "https://www.hsph.harvard.edu/..."

    def __init__(self, page: Page):
        """
        Initialize scraper with a Playwright page.

        Args:
            page: Playwright page instance
        """
        self.page = page
        self.events: List[Event] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def scrape(self) -> List[Event]:
        """
        Main scraping method. Must be implemented by each subclass.

        Returns:
            List of Event objects extracted from the site
        """
        pass

    @async_retry(max_attempts=3, delay=2.0, backoff=2.0)
    async def navigate_to_page(self, url: Optional[str] = None) -> None:
        """Navigate to the target URL with retry logic."""
        target_url = url or self.BASE_URL
        self.logger.info(f"Navigating to {target_url}")

        try:
            response = await self.page.goto(
                target_url,
                wait_until="networkidle",
                timeout=30000,
            )
            if response and response.status >= 400:
                raise SiteUnreachableError(f"HTTP {response.status} for {target_url}")
        except Exception as e:
            self.logger.error(f"Failed to navigate to {target_url}: {e}")
            raise SiteUnreachableError(str(e))

    async def wait_for_content(self, selector: str, timeout: int = 10000) -> bool:
        """
        Wait for specific content to be rendered.

        Args:
            selector: CSS selector to wait for
            timeout: Maximum wait time in milliseconds

        Returns:
            True if element found, False otherwise
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            self.logger.warning(f"Timeout waiting for selector '{selector}': {e}")
            return False

    async def get_text(self, selector: str) -> Optional[str]:
        """Safely extract text from a selector."""
        try:
            element = await self.page.query_selector(selector)
            if element:
                text = await element.text_content()
                return text.strip() if text else None
        except Exception as e:
            self.logger.debug(f"Could not get text for '{selector}': {e}")
        return None

    async def get_element_text(self, element: ElementHandle) -> Optional[str]:
        """Safely extract text from an element."""
        try:
            text = await element.text_content()
            return text.strip() if text else None
        except Exception as e:
            self.logger.debug(f"Could not get element text: {e}")
        return None

    async def get_all_elements(self, selector: str) -> List[ElementHandle]:
        """Get all elements matching a selector."""
        return await self.page.query_selector_all(selector)

    async def get_attribute(
        self, element: ElementHandle, attr: str
    ) -> Optional[str]:
        """Safely get an attribute from an element."""
        try:
            value = await element.get_attribute(attr)
            return value.strip() if value else None
        except Exception:
            return None

    async def get_href(self, element: ElementHandle) -> Optional[str]:
        """Get href attribute from a link element."""
        href = await self.get_attribute(element, "href")
        if href and not href.startswith("http"):
            # Make relative URL absolute
            from urllib.parse import urljoin
            href = urljoin(self.BASE_URL, href)
        return href

    def create_event(self, **kwargs) -> Event:
        """Factory method to create Event with source pre-filled."""
        return Event(source=self.SOURCE_NAME, **kwargs)

    def parse_speakers(self, text: str) -> List[str]:
        """
        Extract speaker names from text.
        Handles common formats like "John Doe, Jane Smith" or "John Doe & Jane Smith"
        """
        if not text:
            return []
        # Replace common separators
        text = text.replace(" and ", ", ").replace(" & ", ", ")
        # Split and clean
        speakers = [s.strip() for s in text.split(",") if s.strip()]
        return speakers

    def normalize_cost(self, text: str) -> str:
        """Normalize cost text to standard format."""
        if not text:
            return "free"
        text = text.strip().lower()
        if "free" in text or text in ["0", "$0", "$0.00", "no cost", "no charge"]:
            return "free"
        # Try to extract price pattern
        match = re.search(r"\$[\d,]+(?:\s*[-\u2013]\s*\$[\d,]+)?", text, re.IGNORECASE)
        if match:
            return match.group(0)
        return text

    def detect_location_type(self, text: str) -> LocationType:
        """Detect location type from text."""
        if not text:
            return LocationType.UNKNOWN
        text = text.lower()
        if "virtual" in text or "online" in text or "webinar" in text or "zoom" in text:
            if "hybrid" in text or ("in-person" in text) or ("in person" in text):
                return LocationType.HYBRID
            return LocationType.VIRTUAL
        if "in-person" in text or "in person" in text or "onsite" in text:
            return LocationType.IN_PERSON
        return LocationType.UNKNOWN

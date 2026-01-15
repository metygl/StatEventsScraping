"""
Scraper for ASA (American Statistical Association) Webinars.
Site: https://www.amstat.org/ASA/Education/Web-Based-Lectures.aspx
"""

from typing import List

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASAWebinarsScraper(BaseScraper):
    """Scraper for ASA web-based lectures and webinars."""

    SOURCE_NAME = "ASA Webinar"
    BASE_URL = "https://www.amstat.org/ASA/Education/Web-Based-Lectures.aspx"

    async def scrape(self) -> List[Event]:
        """Scrape ASA webinar listings."""
        await self.navigate_to_page()

        # Wait for content
        await self.wait_for_content(".content, main", timeout=10000)

        # ASA uses various formats - try multiple approaches
        await self._scrape_event_items()
        await self._scrape_links()

        return self.events

    async def _scrape_event_items(self):
        """Scrape structured event items."""
        # Look for common event item patterns
        items = await self.get_all_elements(
            ".event-item, .webinar-item, .lecture-item, article"
        )

        for item in items:
            try:
                event = await self._parse_event_item(item)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse event item: {e}")

    async def _parse_event_item(self, item) -> Event:
        """Parse a single event item."""
        # Get title
        title_elem = await item.query_selector("h2, h3, h4, .title, a")
        if not title_elem:
            return None

        title = await self.get_element_text(title_elem)

        # Get link
        link = await item.query_selector("a")
        url = await self.get_href(link) if link else self.BASE_URL

        # Get date
        date_elem = await item.query_selector(".date, time, [class*='date']")
        date_text = await self.get_element_text(date_elem) if date_elem else None

        # If no date element, try full text
        if not date_text:
            full_text = await self.get_element_text(item)
            date_text = full_text

        if not title or not date_text:
            return None

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        # Extract speakers and cost
        full_text = await self.get_element_text(item) or ""
        speakers = self._extract_speakers(full_text)
        cost = self._extract_cost(full_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost=cost,
            raw_date_text=date_text,
        )

    async def _scrape_links(self):
        """Scrape from link-based format."""
        # Get all links that might be events
        links = await self.get_all_elements("a")

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title:
                    continue

                # Skip short titles (likely navigation)
                if len(title) < 20:
                    continue

                # Skip if already scraped
                if any(e.title == title for e in self.events):
                    continue

                # Get surrounding context
                parent = await link.evaluate_handle(
                    "el => el.parentElement?.parentElement"
                )
                if parent:
                    context = await parent.evaluate("el => el?.textContent || ''")
                else:
                    context = title

                # Try to find date
                try:
                    start_dt, end_dt = DateParser.parse_datetime_range(context)
                except Exception:
                    continue

                speakers = self._extract_speakers(context)
                cost = self._extract_cost(context)

                event = self.create_event(
                    title=title,
                    url=href,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    speakers=speakers,
                    location_type=LocationType.VIRTUAL,
                    cost=cost,
                )
                self.events.append(event)

            except Exception as e:
                self.logger.debug(f"Failed to parse link: {e}")

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        import re

        # Look for presenter/speaker patterns
        patterns = [
            r"(?:presented by|speaker[s]?:?|instructor[s]?:?)\s*([^.]+?)(?:\.|$)",
            r"\(([^)]+)\)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                potential = match.group(1)
                # Validate it looks like names
                if len(potential) < 100 and any(c.isupper() for c in potential):
                    return self.parse_speakers(potential)

        return []

    def _extract_cost(self, text: str) -> str:
        """Extract cost from text."""
        import re

        text_lower = text.lower()

        # Check for free indicators
        if "free" in text_lower or "no cost" in text_lower:
            return "free"

        # Check for member pricing
        match = re.search(r"\$\d+(?:\s*[-–]\s*\$\d+)?", text)
        if match:
            return match.group(0)

        return "free"  # Default for ASA webinars

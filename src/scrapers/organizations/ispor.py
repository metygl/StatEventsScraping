"""
Scraper for ISPOR (International Society for Pharmacoeconomics and Outcomes Research) Events.
Site: https://www.ispor.org/conferences-education/conferences/upcoming-conferences
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ISPORScraper(BaseScraper):
    """Scraper for ISPOR conferences and events (Sitefinity CMS, server-rendered)."""

    SOURCE_NAME = "ISPOR"
    BASE_URL = "https://www.ispor.org/conferences-education/conferences/upcoming-conferences"

    async def scrape(self) -> List[Event]:
        """Scrape ISPOR upcoming conferences listing."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .content, body", timeout=10000)

        # Collect conference links from listing page
        event_data = await self._collect_conference_links()
        self.logger.info(f"Found {len(event_data)} ISPOR conferences to process")

        # Visit each conference page for full details
        for data in event_data[:10]:
            try:
                event = await self._scrape_conference_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse ISPOR conference {data.get('url')}: {e}")

        return self.events

    async def _collect_conference_links(self) -> List[Dict]:
        """Collect conference links from the listing page."""
        event_data = []
        seen_urls = set()

        # ISPOR conference links follow pattern: /upcoming-conferences/ispor-YYYY
        links = await self.get_all_elements(
            "a[href*='/upcoming-conferences/'], a[href*='/conferences/']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link) or ""

                if not href:
                    continue

                # Only follow detail page links
                if "/upcoming-conferences/" not in href:
                    continue

                # Skip the listing page itself
                if href.rstrip("/") == self.BASE_URL.rstrip("/"):
                    continue

                # Only top-level conference pages (e.g. /upcoming-conferences/ispor-2026)
                # Skip sub-pages like /upcoming-conferences/ispor-2026/about/registration
                path_after = href.split("/upcoming-conferences/")[-1].strip("/")
                if "/" in path_after:
                    continue

                if href in seen_urls:
                    continue

                # Skip nav-like links
                if len(text) < 3 or any(skip in text.lower() for skip in [
                    "view all", "back", "home", "menu"
                ]):
                    continue

                seen_urls.add(href)
                event_data.append({"url": href, "link_title": text.strip()})

            except Exception as e:
                self.logger.debug(f"Failed to collect ISPOR link: {e}")

        # Also try extracting from page text if no links found
        if not event_data:
            event_data = await self._extract_from_text()

        return event_data

    async def _extract_from_text(self) -> List[Dict]:
        """Extract conference info directly from page text."""
        body_text = await self.page.text_content("body") or ""
        events = []

        # Look for patterns like "ISPOR 2026" with dates
        matches = re.finditer(
            r"(ISPOR\s+(?:Europe\s+)?\d{4})\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}[-–]\d{1,2},?\s+\d{4})?",
            body_text, re.IGNORECASE
        )

        for match in matches:
            title = match.group(1)
            if title not in [e.get("link_title") for e in events]:
                events.append({
                    "link_title": title,
                    "url": self.BASE_URL,
                    "date_text": match.group(2) if match.group(2) else None,
                })

        return events

    async def _scrape_conference_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual conference page for details."""
        url = data["url"]

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get title from h1
        h1_text = await self.get_text("h1")
        title = h1_text if h1_text and len(h1_text) > 3 else data.get("link_title", "")

        if not title:
            return None

        # Extract date range from page text
        date_text = data.get("date_text") or self._extract_dates(body_text)
        if not date_text:
            return None

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract location
        location = self._extract_location(body_text)
        location_type = LocationType.IN_PERSON
        if location and ("virtual" in location.lower() or "online" in location.lower()):
            location_type = LocationType.VIRTUAL

        # Extract cost
        cost = self._extract_cost(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=location_type,
            location_details=location,
            cost=cost,
            raw_date_text=date_text,
        )

    def _extract_dates(self, text: str) -> Optional[str]:
        """Extract date range from page text."""
        # Pattern: "May 17-20, 2026" or "November 8-11, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}\s*[-–]\s*\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Pattern: "May 17, 2026" single date
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract venue/location from text."""
        # Pattern: "City, State, Country" or "City, Country"
        match = re.search(
            r"(?:Pennsylvania Convention Center|Convention Center|"
            r"Hotel|Conference Center|Centre)\s*[,\n]\s*"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z]{2})?(?:,\s*[A-Z]+)?)",
            text
        )
        if match:
            return match.group(0).strip()

        # Simpler: look for "City, ST, USA" or "City, Country"
        match = re.search(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:[A-Z]{2},\s*)?(?:USA|UK|Canada|Germany|France|Spain|Italy|Netherlands))",
            text
        )
        if match:
            return match.group(1).strip()

        return None

    def _extract_cost(self, text: str) -> str:
        """Extract cost from text."""
        match = re.search(r"\$\s*[\d,]+(?:\s*[-–]\s*\$\s*[\d,]+)?", text)
        if match:
            return match.group(0)
        return ""

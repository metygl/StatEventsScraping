"""
Scraper for RSS (Royal Statistical Society) Events.
Site: https://rss.org.uk/training-events/events/
ASP.NET WebForms with postback-based pagination.
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class RSSScraper(BaseScraper):
    """Scraper for Royal Statistical Society events (list+detail pattern)."""

    SOURCE_NAME = "RSS"
    BASE_URL = "https://rss.org.uk/training-events/events/"

    async def scrape(self) -> List[Event]:
        """Scrape RSS event listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, body", timeout=15000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} RSS events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse RSS event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # RSS events listing uses links with event URLs
        links = await self.get_all_elements(
            "a[href*='/training-events/events/events-']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link) or ""

                if not href or href in seen_urls:
                    continue

                # Skip the listing page itself and non-event links
                if href.rstrip("/") == self.BASE_URL.rstrip("/"):
                    continue

                if any(skip in text.lower() for skip in [
                    "load more", "view all", "menu", "back"
                ]):
                    continue

                # Only follow detail page links (not year landing pages)
                # Pattern: /events-2026/rss-events/event-slug/
                if not re.search(r"/events-\d{4}/[^/]+/[^/]+/?$", href):
                    continue

                seen_urls.add(href)
                event_data.append({
                    "url": href,
                    "link_title": text.strip(),
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect RSS event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get title from h1
        h1_text = await self.get_text("h1")
        title = h1_text if h1_text and len(h1_text) > 5 else data.get("link_title", "")

        if not title:
            return None

        # Clean "(In person)" or "(Online)" from title
        location_hint = ""
        loc_match = re.search(r"\(([^)]*(?:person|online|virtual|hybrid)[^)]*)\)", title, re.IGNORECASE)
        if loc_match:
            location_hint = loc_match.group(1)
            title = title[:loc_match.start()].strip()

        # Extract date: "Tuesday 24 March 2026, 2.15PM - 3.15PM"
        date_text = self._extract_date(body_text)
        if not date_text:
            return None

        # UK time format uses dots: "2.15PM" -> "2:15PM"
        date_text = re.sub(r"(\d{1,2})\.(\d{2})\s*(AM|PM|am|pm)", r"\1:\2\3", date_text)

        # Add GMT timezone if none present
        if not re.search(r"\b(?:GMT|BST|UTC|CET)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} GMT"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Detect location type
        full_text = f"{title} {location_hint} {body_text}"
        location_type = self.detect_location_type(full_text)
        if location_type == LocationType.UNKNOWN:
            if "in person" in location_hint.lower():
                location_type = LocationType.IN_PERSON
            elif "online" in location_hint.lower():
                location_type = LocationType.VIRTUAL
            else:
                location_type = LocationType.IN_PERSON

        # Extract location details
        location_details = self._extract_location(body_text)

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        # Extract cost
        cost = self._extract_cost(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost=cost,
            raw_date_text=date_text,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from page text.

        RSS format: "Date: Tuesday 24 March 2026, 2.15PM - 3.15PM"
        """
        # Pattern: "Date:" label followed by full date/time
        match = re.search(
            r"Date[:\s]+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*,?\s*"
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}[.:]\d{2}\s*(?:AM|PM|am|pm)\s*[-–]\s*\d{1,2}[.:]\d{2}\s*(?:AM|PM|am|pm)))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str}".strip()

        # Simpler pattern: just date
        match = re.search(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text."""
        match = re.search(
            r"Location[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            location = match.group(1).strip()
            if len(location) > 5:
                return location[:100]
        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names."""
        speakers = []

        match = re.search(
            r"(?:Speaker|Presenter|Chair)[s]?[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

    def _extract_cost(self, text: str) -> str:
        """Extract cost from text."""
        if "free" in text.lower():
            return "free"
        match = re.search(r"[£]\s*\d+(?:\s*[-–]\s*[£]?\s*\d+)?", text)
        if match:
            return match.group(0)
        return ""

"""
Scraper for PSI (Statisticians in the Pharmaceutical Industry) Events.
Site: https://www.psiweb.org/events/psi-events
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class PSIScraper(BaseScraper):
    """Scraper for PSI webinars and events."""

    SOURCE_NAME = "PSI"
    BASE_URL = "https://www.psiweb.org/events/psi-events"

    async def scrape(self) -> List[Event]:
        """Scrape PSI event listings using list+detail pattern."""
        await self.navigate_to_page()

        # Wait for content to load
        await self.wait_for_content(".event, article, .content", timeout=10000)

        # Collect event URLs first
        event_urls = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_urls)} PSI event URLs")

        # Visit each event page for full details including times
        for url, title in event_urls:
            try:
                event = await self._scrape_event_page(url, title)
                if event:
                    # Avoid duplicates
                    if not any(e.url == event.url for e in self.events):
                        self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to scrape PSI event {url}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[tuple]:
        """Collect event URLs and titles from listing page."""
        seen_urls = set()
        event_urls = []

        # Find event articles
        items = await self.get_all_elements("article")

        for item in items:
            try:
                # Get title from heading
                title = None
                url = None

                heading = await item.query_selector("h2, h3")
                if heading:
                    title = await self.get_element_text(heading)

                if not title or len(title) < 5:
                    continue

                # Get URL from "Find out more" link or any event-item link
                links = await item.query_selector_all("a[href*='event-item']")
                for link in links:
                    href = await self.get_href(link)
                    if href and "event-item" in href:
                        url = href
                        break

                if title and url and url not in seen_urls:
                    seen_urls.add(url)
                    event_urls.append((url, self._clean_title(title)))

            except Exception as e:
                self.logger.debug(f"Failed to collect PSI URL: {e}")

        return event_urls

    async def _scrape_event_page(self, url: str, title: str) -> Optional[Event]:
        """Scrape individual event page for full details including time."""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await self.page.wait_for_timeout(1000)

        body_text = await self.page.text_content("body") or ""

        # Extract date - first try page content, then URL
        date_text = self._extract_date(body_text)
        if not date_text:
            # Try to extract date from URL (format: /2026/01/14/)
            date_text = self._extract_date_from_url(url)

        if not date_text:
            return None

        # Extract time - PSI uses GMT/CET times
        time_info = self._extract_time(body_text)

        # Build full date string with timezone
        if time_info:
            start_time, end_time, timezone = time_info
            full_date = f"{date_text} {start_time}-{end_time} {timezone}"
        else:
            full_date = date_text

        # Parse datetime
        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception:
            return None

        # Extract other info
        location_type = self.detect_location_type(body_text)
        speakers = self._extract_speakers(title, body_text)
        cost = self._extract_cost(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost=cost,
            raw_date_text=full_date,
        )

    def _extract_date_from_url(self, url: str) -> Optional[str]:
        """Extract date from URL path like /2026/01/14/."""
        match = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        if match:
            year, month, day = match.groups()
            from datetime import datetime
            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%B %d, %Y")
            except ValueError:
                pass
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from page text."""
        # Look for date patterns like "14 January 2026" or "January 14, 2026"
        patterns = [
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_time(self, text: str) -> Optional[tuple]:
        """Extract time from page text. Returns (start_time, end_time, timezone)."""
        # PSI format: "16:00-17:00 GMT/BST | 17:00-18:00 CET/CEST"
        # We prefer GMT for consistent conversion

        # Try to find GMT time first
        gmt_match = re.search(
            r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*GMT",
            text,
            re.IGNORECASE
        )
        if gmt_match:
            return (gmt_match.group(1), gmt_match.group(2), "GMT")

        # Try CET if no GMT
        cet_match = re.search(
            r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})\s*CET",
            text,
            re.IGNORECASE
        )
        if cet_match:
            return (cet_match.group(1), cet_match.group(2), "CET")

        # Try generic time patterns with am/pm
        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm))\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:am|pm))",
            text,
            re.IGNORECASE
        )
        if time_match:
            return (time_match.group(1), time_match.group(2), "GMT")

        return None

    def _extract_speakers(self, title: str, description: str) -> List[str]:
        """Extract speaker names."""
        # Look for "Presenters:" line in PSI format
        # Example: "Presenters: Bodo Kirsch, Alexander Schacht, Mark Baillie..."
        presenters_match = re.search(
            r"Presenters?:\s*([A-Z][^,\n]+(?:,\s*[A-Z][^,\n]+)*)",
            description
        )
        if presenters_match:
            speakers_text = presenters_match.group(1)
            # Limit to reasonable length (avoid grabbing navigation text)
            if len(speakers_text) < 500:
                return self.parse_speakers(speakers_text)

        return []

    def _extract_cost(self, text: str) -> str:
        """Extract cost information."""
        text_lower = text.lower()
        if "free" in text_lower:
            return "free"

        # Look for price patterns
        match = re.search(r"[£€\$]\s*\d+(?:\s*[-–]\s*[£€\$]?\s*\d+)?", text)
        if match:
            return match.group(0)

        return "free"

    def _clean_title(self, title: str) -> str:
        """Clean up title."""
        title = re.sub(r"\s*\([^)]+\)\s*$", "", title)
        return title.strip()

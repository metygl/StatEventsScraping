"""
Scraper for Cambridge MRC Biostatistics Unit Events.
Site: https://www.mrc-bsu.cam.ac.uk/events/
Note: DNS may be unreliable - site might be accessed via alternate URLs.
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class CambridgeMRCScraper(BaseScraper):
    """Scraper for Cambridge MRC Biostatistics Unit seminars and events."""

    SOURCE_NAME = "Cambridge MRC BSU"
    BASE_URL = "https://www.mrc-bsu.cam.ac.uk/events/"

    async def scrape(self) -> List[Event]:
        """Scrape Cambridge MRC BSU event listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .content, body", timeout=15000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} Cambridge MRC events to process")

        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse MRC event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # Try various event listing selectors (WordPress-based site)
        items = await self.get_all_elements(
            "article, .event-item, .views-row, .post, .hentry"
        )

        for item in items:
            try:
                link = await item.query_selector("h2 a, h3 a, .entry-title a, a")
                if not link:
                    continue

                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 5:
                    continue

                if href in seen_urls:
                    continue

                if any(skip in title.lower() for skip in ["menu", "back", "home"]):
                    continue

                seen_urls.add(href)

                # Try to get date
                date_elem = await item.query_selector("time, .date, .event-date")
                date_text = await self.get_element_text(date_elem) if date_elem else None

                event_data.append({
                    "title": title.strip(),
                    "url": href,
                    "date_text": date_text,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event data: {e}")

        # Fallback: extract events from page text
        if not event_data:
            event_data = await self._extract_from_text()

        return event_data

    async def _extract_from_text(self) -> List[Dict]:
        """Extract events from page text when DOM scraping fails."""
        body_text = await self.page.text_content("body") or ""
        events = []

        # Look for date + title patterns
        pattern = re.compile(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"
            r"\s*[-–:]\s*(.+?)(?:\n|$)",
            re.IGNORECASE
        )

        for match in pattern.finditer(body_text):
            title = match.group(2).strip()
            if len(title) > 10:
                events.append({
                    "title": title,
                    "url": self.BASE_URL,
                    "date_text": match.group(1),
                })

        return events

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]
        title = data["title"]

        if url != self.BASE_URL:
            await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get title from h1 if on detail page
        if url != self.BASE_URL:
            h1_text = await self.get_text("h1, .entry-title")
            if h1_text and len(h1_text) > 10:
                title = h1_text.strip()

        # Extract date
        date_text = data.get("date_text") or self._extract_date(body_text)
        if not date_text:
            return None

        # Extract time
        time_text = self._extract_time(body_text)
        full_date = f"{date_text} {time_text}".strip()

        # Cambridge is GMT/BST timezone
        if not re.search(r"\b(?:GMT|BST|UTC|CET)\b", full_date, re.IGNORECASE):
            full_date = f"{full_date} GMT"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date}': {e}")
            return None

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.IN_PERSON,
            cost="free",
            raw_date_text=full_date,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from page text."""
        # European format: "14 January 2026"
        match = re.search(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # American format: "January 14, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from page text."""
        # Pattern: "14:00-15:00" or "2:00pm-3:00pm"
        match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm)?\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm)?)",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return ""

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        match = re.search(
            r"(?:Speaker|Presenter|Talk by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

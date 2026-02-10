"""
Scraper for UCSF Biostatistics and Bioinformatics Seminars.
Site: https://epibiostat.ucsf.edu/events
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class UCSFScraper(BaseScraper):
    """Scraper for UCSF Biostatistics and Bioinformatics seminars."""

    SOURCE_NAME = "UCSF Biostatistics and Bioinformatics Seminar"
    BASE_URL = "https://epibiostat.ucsf.edu/events"

    async def scrape(self) -> List[Event]:
        """Scrape UCSF event listings."""
        await self.navigate_to_page()

        await self.wait_for_content(".view-content, main", timeout=10000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} UCSF events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse UCSF event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # UCSF Drupal site uses /content/ paths for event detail pages
        links = await self.get_all_elements(
            "a[href*='/content/'], .views-row a, .views-field-title a"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 10:
                    continue

                if href in seen_urls:
                    continue

                # Only follow detail page links
                if "/content/" not in href and "/events/" not in href:
                    continue

                # Skip navigation-like links
                if any(skip in title.lower() for skip in ["menu", "back", "home", "view all", "more events"]):
                    continue

                seen_urls.add(href)
                event_data.append({"title": title, "url": href})

            except Exception as e:
                self.logger.debug(f"Failed to collect event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]
        title = data["title"]

        await self.navigate_to_page(url)

        # Get page text
        body_text = await self.page.text_content("body") or ""

        # Try to get a better title from h1
        h1_title = await self.get_text("h1")
        if h1_title and len(h1_title) > 10:
            title = h1_title.strip()

        # Extract date from body text
        date_text = self._extract_date(body_text)

        # Extract time from body text
        time_text = self._extract_time(body_text)

        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        full_date = f"{date_text} {time_text}".strip()

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date}': {e}")
            return None

        # Extract speaker
        speakers = self._extract_speakers(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost="free",
            raw_date_text=full_date,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from page text using various patterns."""
        # Pattern: "Date: February 5, 2026" or "Date February 5, 2026"
        match = re.search(
            r"Date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Pattern: "Wednesday, February 5, 2026"
        match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Pattern: standalone "February 5, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from page text, normalizing formats like '1 to 2 p.m.'."""
        # Pattern: "Time: 1:00pm-2:00pm" or "Time: 1:00 PM - 2:00 PM"
        match = re.search(
            r"Time[:\s]+(\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*[-–to]+\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?)",
            text, re.IGNORECASE
        )
        if match:
            return self._normalize_time(match.group(1))

        # Pattern: "Time: 1 to 2 p.m." or "1 to 2 pm"
        match = re.search(
            r"Time[:\s]+(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?\s*(?:to|-|–)\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)",
            text, re.IGNORECASE
        )
        if match:
            return self._normalize_time(match.group(1))

        # Pattern: standalone time range "1:00pm-2:00pm"
        match = re.search(
            r"(\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*[-–]\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?)",
            text, re.IGNORECASE
        )
        if match:
            return self._normalize_time(match.group(1))

        # Pattern: "1 to 2 p.m." or "1-2 p.m."
        match = re.search(
            r"(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?\s*(?:to|-|–)\s*\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)",
            text, re.IGNORECASE
        )
        if match:
            return self._normalize_time(match.group(1))

        return ""

    def _normalize_time(self, time_str: str) -> str:
        """Normalize time strings like '1 to 2 p.m.' to '1:00pm-2:00pm'."""
        # Remove periods from am/pm
        time_str = re.sub(r"([ap])\.m\.", r"\1m", time_str, flags=re.IGNORECASE)
        # Replace "to" with "-"
        time_str = re.sub(r"\s+to\s+", "-", time_str)
        # Normalize dashes
        time_str = time_str.replace("–", "-")

        # Add :00 to bare hours like "1pm" -> "1:00pm"
        time_str = re.sub(r"\b(\d{1,2})\s*(am|pm)", r"\1:00\2", time_str, flags=re.IGNORECASE)
        # Handle start time without am/pm: "1:00-2:00pm" -> "1:00pm-2:00pm" (infer from end)
        time_str = re.sub(r"(\d{1,2}:\d{2})\s*-\s*", r"\1-", time_str)

        # Clean up spaces
        time_str = re.sub(r"\s+", "", time_str)

        return time_str

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from page text."""
        speakers = []

        # Pattern: "Speaker: Name" or "Presenter: Name"
        match = re.search(
            r"(?:Speaker|Presenter)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())
            return speakers

        # Pattern: "by Name" near title
        match = re.search(
            r"(?:^|\n)\s*(?:by|presented by)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)",
            text, re.IGNORECASE | re.MULTILINE
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

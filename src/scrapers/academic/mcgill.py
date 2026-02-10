"""
Scraper for McGill University Biostatistics Seminars.
Site: https://www.mcgill.ca/epi-biostat-occh/seminars-events/seminars/biostatistics
"""

import re
import asyncio
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class McGillScraper(BaseScraper):
    """Scraper for McGill University Biostatistics seminars."""

    SOURCE_NAME = "McGill University Biostatistics Seminars"
    BASE_URL = "https://www.mcgill.ca/epi-biostat-occh/seminars-events/seminars/biostatistics"

    async def scrape(self) -> List[Event]:
        """Scrape McGill Biostatistics seminar listings."""
        await self.navigate_to_page()

        await self.wait_for_content(".view-content, main, body", timeout=10000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} McGill events to process")

        # Visit each event page with rate limiting (McGill may return 429)
        for data in event_data[:10]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
                # Rate limit: wait between requests to avoid 429
                await asyncio.sleep(3)
            except Exception as e:
                self.logger.warning(f"Failed to parse McGill event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # McGill Drupal views - try multiple selectors
        links = await self.get_all_elements(
            ".views-row a, a[href*='/channels/event/'], "
            ".views-field-title a, a[href*='/epi-biostat-occh/']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 10:
                    continue

                if href in seen_urls:
                    continue

                # Only follow event detail links
                if not any(p in href for p in ["/channels/event/", "/seminars/", "/epi-biostat-occh/"]):
                    continue

                # Skip the listing page itself and navigation
                if href.rstrip("/") == self.BASE_URL.rstrip("/"):
                    continue

                if any(skip in title.lower() for skip in [
                    "menu", "back", "home", "view all", "biostatistics seminar",
                    "seminars & events"
                ]):
                    continue

                seen_urls.add(href)

                # Try to get date from listing page context
                parent = await link.evaluate_handle("el => el.closest('.views-row')")
                date_text = None
                if parent:
                    date_elem_text = await parent.evaluate("el => el?.textContent || ''")
                    date_text = self._extract_date(date_elem_text)

                event_data.append({
                    "title": title.strip(),
                    "url": href,
                    "date_text": date_text,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]
        title = data["title"]
        date_text = data.get("date_text")

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Try to get a better title from h1
        h1_title = await self.get_text("h1, .page-title, #page-title")
        if h1_title and len(h1_title) > 10:
            title = h1_title.strip()

        # Extract date from detail page if not from listing
        if not date_text:
            # Try date-display-single first (Drupal)
            date_elem = await self.get_text(".date-display-single, .field-name-field-date, time")
            if date_elem:
                date_text = date_elem
            else:
                date_text = self._extract_date(body_text)

        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        # Add ET timezone if none detected (McGill is in Eastern)
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT|CST|CDT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract speaker - often in parentheses in title or in body
        speakers = self._extract_speakers(title, body_text)

        # Clean title (remove speaker parenthetical)
        clean_title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()

        return self.create_event(
            title=clean_title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.HYBRID,
            cost="free",
            raw_date_text=date_text,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from text."""
        # Pattern: "February 4, 2026" with optional time
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:\s+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:am|pm)(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm))?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str}".strip()

        # Pattern: "Tuesday, February 4, 2026 3:30 PM - 4:30 PM"
        match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:\s+(\d{1,2}:\d{2}\s*(?:am|pm)(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm))?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str}".strip()

        # Pattern: "4 February 2026" (European format)
        match = re.search(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_speakers(self, title: str, body_text: str) -> List[str]:
        """Extract speaker names from title parenthetical or body text."""
        speakers = []

        # Check title for parenthetical speaker name: "Title (Speaker Name)"
        match = re.search(r"\(([^)]+)\)\s*$", title)
        if match:
            potential = match.group(1)
            if len(potential) < 80 and any(c.isupper() for c in potential):
                return self.parse_speakers(potential)

        # Check body for "Speaker:" or "Presenter:" patterns
        match = re.search(
            r"(?:Speaker|Presenter|Presented by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            body_text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

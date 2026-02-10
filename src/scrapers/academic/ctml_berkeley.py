"""
Scraper for CTML Berkeley Seminars and Events.
Site: https://ctml.berkeley.edu/
Drupal (OpenBerkeley) with event listings and seminar series pages.
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class CTMLBerkeleyScraper(BaseScraper):
    """Scraper for CTML Berkeley seminars and events."""

    SOURCE_NAME = "CTML Berkeley"
    BASE_URL = "https://ctml.berkeley.edu/ctml-events"

    async def scrape(self) -> List[Event]:
        """Scrape CTML Berkeley event listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .content, body", timeout=10000)

        # Collect event URLs from the events page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} CTML Berkeley events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse CTML event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # Drupal uses h3 links with event titles, also try broader link selectors
        links = await self.get_all_elements(
            "h3 a, h2 a, .views-row a, .panopoly-spotlight a, "
            "a[href*='/seminar'], a[href*='/workshop'], a[href*='/event']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link) or ""

                if not href or not text or len(text) < 10:
                    continue

                if href in seen_urls:
                    continue

                # Only follow internal detail pages
                if "ctml.berkeley.edu" not in href and not href.startswith("/"):
                    continue

                # Skip non-event pages (people, about, join, etc.)
                if re.search(r"/people/|/about|/join|/donate|/contact|/news/", href, re.IGNORECASE):
                    continue

                # Skip navigation and category links
                if any(skip in text.lower() for skip in [
                    "menu", "back", "home", "read more", "more events",
                    "view all", "pause", "next", "previous", "join us",
                    "big give", "donate"
                ]):
                    continue

                seen_urls.add(href)

                # Event titles often include date prefix: "2/11/26 Seminar: ..."
                title = text.strip()
                date_text = None
                date_match = re.match(r"(\d{1,2}/\d{1,2}/\d{2,4})\s+", title)
                if date_match:
                    date_text = date_match.group(1)
                    title = title[date_match.end():].strip()

                event_data.append({
                    "title": title,
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

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get better title from h1
        h1_text = await self.get_text("h1")
        if h1_text and len(h1_text) > 10:
            title = h1_text.strip()
            # Remove date prefix if present
            title = re.sub(r"^\d{1,2}/\d{1,2}/\d{2,4}\s+", "", title)

        # Remove "Seminar:" or "Workshop:" prefix for cleaner title
        title = re.sub(r'^(?:Seminar|Workshop|Talk|Lecture)[:\s]+', '', title, flags=re.IGNORECASE)
        title = title.strip('" ')

        # Extract date
        date_text = data.get("date_text") or self._extract_date(body_text)
        if not date_text:
            return None

        # Extract time
        time_text = self._extract_time(body_text)
        full_date = f"{date_text} {time_text}".strip()

        # Add PT timezone
        if not re.search(r"\b(?:PT|PST|PDT|ET|EST|EDT)\b", full_date, re.IGNORECASE):
            full_date = f"{full_date} PT"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date}': {e}")
            return None

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        return self.create_event(
            title=title if title else data["title"],
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
        # Pattern: "February 11, 2026" or "Feb 11, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Pattern: MM/DD/YYYY or MM/DD/YY
        match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", text)
        if match:
            return match.group(1)

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from page text."""
        # Pattern: "3:30 PM - 5:00 PM" or "3:30pm-5:00pm"
        match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))",
            text
        )
        if match:
            return match.group(1)

        # Pattern: "3:30-5:00 PM"
        match = re.search(
            r"(\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))",
            text
        )
        if match:
            return match.group(1)

        return ""

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        # Pattern: "Speaker: Name" or "Presenter: Name"
        match = re.search(
            r"(?:Speaker|Presenter|Presented by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())
            return speakers

        # Pattern: "by Name, Institution"
        match = re.search(
            r"\bby\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)(?:,|\s+\()",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

"""
Scraper for Dana Farber Data Science Events.
Site: https://ds.dfci.harvard.edu/events/
Uses WordPress with "The Events Calendar" plugin (tribe-events).
"""

import re
import asyncio
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class DanaFarberScraper(BaseScraper):
    """Scraper for Dana Farber Cancer Institute Data Science events."""

    SOURCE_NAME = "Dana Farber Data Science"
    BASE_URL = "https://ds.dfci.harvard.edu/events/"

    async def scrape(self) -> List[Event]:
        """Scrape Dana Farber Data Science events."""
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        await self.wait_for_content(
            ".tribe-events-calendar-list__event-row, .tribe-events-view, main",
            timeout=15000
        )

        # The Events Calendar plugin uses list view by default
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} Dana Farber events to process")

        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse Dana Farber event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # tribe-events uses article or list-item containers
        items = await self.get_all_elements(
            ".tribe-events-calendar-list__event-row, "
            "article.tribe-events-calendar-list__event, "
            ".tribe-events-calendar-list__event-details, "
            "article"
        )

        for item in items:
            try:
                # Get event link
                link = await item.query_selector(
                    "a[href*='/event/'], h3 a, h2 a, .tribe-events-calendar-list__event-title a"
                )
                if not link:
                    continue

                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 5:
                    continue
                if href in seen_urls:
                    continue

                # Skip navigation links
                if any(skip in title.lower() for skip in ["next", "previous", "view", "menu"]):
                    continue

                seen_urls.add(href)

                # Try to get date from listing
                time_elem = await item.query_selector("time, .tribe-events-calendar-list__event-datetime")
                date_text = await self.get_element_text(time_elem) if time_elem else None

                event_data.append({
                    "title": title.strip(),
                    "url": href,
                    "date_text": date_text,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event data: {e}")

        # Fallback: extract links from whole page
        if not event_data:
            links = await self.get_all_elements("a[href*='/event/']")
            for link in links:
                try:
                    href = await self.get_href(link)
                    text = await self.get_element_text(link) or ""
                    if href and text and len(text) > 10 and href not in seen_urls:
                        seen_urls.add(href)
                        event_data.append({"title": text.strip(), "url": href})
                except Exception:
                    pass

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]
        title = data["title"]

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get better title from h1
        h1_text = await self.get_text("h1, .tribe-events-single-event-title")
        if h1_text and len(h1_text) > 10:
            title = h1_text.strip()

        # Extract date/time - tribe-events format: "February 12 @ 4:00 pm - 5:00 pm EST"
        date_text = data.get("date_text") or ""
        if not date_text:
            date_text = self._extract_date_time(body_text)

        if not date_text:
            return None

        # Clean up tribe-events date format: "February 12 @ 4:00 pm - 5:00 pm EST"
        date_text = date_text.replace("@", "").replace("  ", " ")

        # Add ET timezone if none present
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT|GMT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract speaker
        speakers = self._extract_speakers(body_text)

        # Detect location type
        location_type = self.detect_location_type(body_text)
        if location_type == LocationType.UNKNOWN:
            # Check for "Zoominar" in the event type
            if "zoom" in body_text.lower() or "zoominar" in body_text.lower():
                location_type = LocationType.VIRTUAL
            elif "seminar" in body_text.lower():
                location_type = LocationType.IN_PERSON

        # Extract location details
        location_details = self._extract_location(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost="free",
            raw_date_text=date_text,
        )

    def _extract_date_time(self, text: str) -> Optional[str]:
        """Extract date/time from The Events Calendar format."""
        # Pattern: "February 12 @ 4:00 pm - 5:00 pm EST"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:,?\s+\d{4})?)"
            r"\s*@?\s*"
            r"(\d{1,2}:\d{2}\s*(?:am|pm)\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm))"
            r"(?:\s*(EST|EDT|ET|PST|PDT|CT|CST|CDT))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            tz = match.group(3) or "ET"
            # Ensure year is present
            if not re.search(r"\d{4}", date_str):
                from datetime import datetime
                date_str = f"{date_str}, {datetime.now().year}"
            return f"{date_str} {time_str} {tz}"

        # Simpler pattern: just date
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from event text."""
        speakers = []

        # Pattern: "Speaker: Name" or "Presenter: Name"
        match = re.search(
            r"(?:Speaker|Presenter|Featuring)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())
            return speakers

        # Pattern: "Name, Institution" near top of page
        match = re.search(
            r"(?:^|\n)\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s+"
            r"(?:Harvard|MIT|Stanford|Duke|DFCI|Dana.?Farber|Boston)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location details from text."""
        # Pattern: "Venue: Location" or building name
        match = re.search(
            r"(?:Venue|Location|Room|Building)[:\s]+([A-Z][^\n]{5,50})",
            text
        )
        if match:
            return match.group(1).strip()
        return None

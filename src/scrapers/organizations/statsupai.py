"""
Scraper for Stats-Up-AI-Alliance Webinars.
Site: https://statsupai.org/events/webinars/
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class StatsUpAIScraper(BaseScraper):
    """Scraper for Stats-Up-AI-Alliance webinar events."""

    SOURCE_NAME = "Stats-Up-AI-Alliance Webinar"
    BASE_URL = "https://statsupai.org/events/webinars/"

    async def scrape(self) -> List[Event]:
        """Scrape Stats-Up-AI-Alliance webinar listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, body", timeout=10000)

        # Extract events from the structured page
        await self._extract_events()

        return self.events

    async def _extract_events(self):
        """Extract events from the page using links and surrounding text.

        The page structure has webinar series sections with:
        - A heading for the series name
        - Individual event entries with title, date, speaker, and registration link
        - Links whose text contains "date · time · speaker" info
        - Separate "Register!" links to Zoom
        """
        body_text = await self.page.text_content("body") or ""

        # Collect all zoom registration links with their text
        links = await self.get_all_elements("a[href*='zoom']")

        for link in links:
            try:
                href = await self.get_href(link)
                link_text = await self.get_element_text(link) or ""

                if not href or "register" not in href.lower():
                    continue

                # Skip if link text is just "Register!"
                if link_text.strip().lower().startswith("register"):
                    continue

                # Link text format: "Feb 11, 2026\n· 1:00 PM ET\n· James Zou (Stanford University)"
                event = self._parse_link_event(link_text, href, body_text)
                if event and not any(e.url == event.url for e in self.events):
                    self.events.append(event)

            except Exception as e:
                self.logger.debug(f"Failed to parse link event: {e}")

    def _parse_link_event(self, link_text: str, url: str, full_text: str) -> Optional[Event]:
        """Parse event from a zoom registration link and its text."""
        # Extract date from link text: "Feb 11, 2026"
        date_match = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
            r"\s+\d{1,2},?\s+\d{4})",
            link_text, re.IGNORECASE
        )
        if not date_match:
            return None

        date_str = date_match.group(1)

        # Extract time: "1:00 PM ET" or "12:00 PM ET"
        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))"
            r"(?:\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)))?"
            r"(?:\s*(ET|EST|EDT|PT|PST|PDT|CT|CST|CDT))?",
            link_text, re.IGNORECASE
        )
        time_str = ""
        tz = "ET"
        if time_match:
            time_str = time_match.group(1)
            if time_match.group(2):
                time_str = f"{time_str}-{time_match.group(2)}"
            tz = time_match.group(3) or "ET"

        full_date = f"{date_str} {time_str} {tz}".strip()

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date}': {e}")
            return None

        # Extract speaker: "· James Zou (Stanford University)"
        speaker_match = re.search(
            r"·\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)"
            r"(?:\s+\(([^)]+)\))?",
            link_text
        )
        speakers = []
        if speaker_match:
            speakers = [speaker_match.group(1).strip()]

        # Find the event title by looking in the full text near this date
        title = self._find_title_for_date(date_str, full_text)
        if not title:
            return None

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

    def _find_title_for_date(self, date_str: str, full_text: str) -> Optional[str]:
        """Find the event title associated with a date in the full page text."""
        # Split text into lines
        lines = full_text.split("\n")

        # Find the line with this date
        date_idx = None
        for i, line in enumerate(lines):
            if date_str in line:
                date_idx = i
                break

        if date_idx is None:
            return None

        # Look backwards from the date line for the title
        # Title is typically a heading/bold text above the date
        for i in range(date_idx - 1, max(0, date_idx - 10), -1):
            line = lines[i].strip()
            if len(line) > 15 and not line.startswith("·") and not line.startswith("http"):
                # Skip series headers and metadata
                skip = [
                    "ongoing webinar", "webinars 2026", "series", "last updated",
                    "community news", "register", "read more", "visit statsupai",
                    "bridging the gap", "empowering health",
                    "health data science", "genai", "generative ai and statistics",
                ]
                if not any(s in line.lower() for s in skip):
                    return line

        return None

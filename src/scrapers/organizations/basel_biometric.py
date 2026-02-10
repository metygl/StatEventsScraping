"""
Scraper for Basel Biometric Society Events.
Site: https://baselbiometrics.github.io/home/docs/
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class BaselBiometricScraper(BaseScraper):
    """Scraper for Basel Biometric Society events (Quarto static site on GitHub Pages)."""

    SOURCE_NAME = "Basel Biometric Society"
    BASE_URL = "https://baselbiometrics.github.io/home/docs/events_upcoming.html"

    async def scrape(self) -> List[Event]:
        """Scrape Basel Biometric Society upcoming events table."""
        await self.navigate_to_page()

        await self.wait_for_content("table, main", timeout=10000)

        # Events are in an HTML table with columns: Date, Event, Type, Agenda, Registration, Comment
        rows = await self.get_all_elements("table tbody tr")
        self.logger.info(f"Found {len(rows)} Basel Biometric table rows")

        for row in rows:
            try:
                event = await self._parse_table_row(row)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse Basel Biometric row: {e}")

        # Also check h2 headings on the page (format: "DD.MM.YYYY: Event Title")
        if not self.events:
            await self._parse_heading_events()

        return self.events

    async def _parse_table_row(self, row) -> Optional[Event]:
        """Parse a table row into an Event."""
        cells = await row.query_selector_all("td")
        if len(cells) < 2:
            return None

        # Column 0: Date (format: DD.MM.YYYY)
        date_text = await self.get_element_text(cells[0])
        if not date_text:
            return None

        # Column 1: Event title
        title_text = await self.get_element_text(cells[1])
        if not title_text or len(title_text) < 5:
            return None

        # Try to get link from event cell
        link = await cells[1].query_selector("a")
        url = await self.get_href(link) if link else self.BASE_URL

        # Column 4: Registration link (if exists)
        reg_url = None
        if len(cells) > 4:
            reg_link = await cells[4].query_selector("a")
            if reg_link:
                reg_url = await self.get_href(reg_link)

        # Parse Swiss date format DD.MM.YYYY
        date_str = self._parse_swiss_date(date_text)
        if not date_str:
            return None

        # Add CET timezone
        date_str = f"{date_str} CET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_str)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_str}': {e}")
            return None

        # Column 2: Type (Training, Seminar, etc.)
        event_type = ""
        if len(cells) > 2:
            event_type = await self.get_element_text(cells[2]) or ""

        location_type = LocationType.HYBRID if "hybrid" in event_type.lower() else LocationType.IN_PERSON

        return self.create_event(
            title=title_text.strip(),
            url=reg_url or url or self.BASE_URL,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=location_type,
            cost="free",
            raw_date_text=date_text,
        )

    async def _parse_heading_events(self):
        """Parse events from h2 headings (format: DD.MM.YYYY: Event Title)."""
        headings = await self.get_all_elements("h2")
        for heading in headings:
            try:
                text = await self.get_element_text(heading)
                if not text:
                    continue

                # Format: "25.03.2026: Event Title"
                match = re.match(r"(\d{2}\.\d{2}\.\d{4}):\s*(.+)", text)
                if not match:
                    continue

                date_text = match.group(1)
                title = match.group(2).strip()

                date_str = self._parse_swiss_date(date_text)
                if not date_str:
                    continue

                date_str = f"{date_str} CET"

                start_dt, end_dt = DateParser.parse_datetime_range(date_str)

                self.events.append(self.create_event(
                    title=title,
                    url=self.BASE_URL,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    speakers=[],
                    location_type=LocationType.IN_PERSON,
                    cost="free",
                    raw_date_text=date_text,
                ))
            except Exception as e:
                self.logger.debug(f"Failed to parse heading event: {e}")

    def _parse_swiss_date(self, text: str) -> Optional[str]:
        """Convert Swiss date DD.MM.YYYY to standard format."""
        match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if match:
            day, month, year = match.groups()
            from datetime import datetime
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime("%B %d, %Y")
            except ValueError:
                pass
        return None

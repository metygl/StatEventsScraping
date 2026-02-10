"""
Scraper for Washington Statistical Society Events.
Site: https://washstat.org/
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class WashingtonStatScraper(BaseScraper):
    """Scraper for Washington Statistical Society (WSS) events and seminars."""

    SOURCE_NAME = "Washington Statistical Society"
    BASE_URL = "https://washstat.org/seminars"

    async def scrape(self) -> List[Event]:
        """Scrape WSS events from main page and seminars page."""
        # Try seminars page first (has more structured data)
        await self.navigate_to_page(self.BASE_URL)
        await self.wait_for_content("main, body", timeout=10000)

        await self._extract_events_from_page()

        # Also check events page
        try:
            await self.navigate_to_page("https://washstat.org/events")
            await self.wait_for_content("main, body", timeout=10000)
            await self._extract_events_from_page()
        except Exception as e:
            self.logger.debug(f"Failed to load WSS events page: {e}")

        return self.events

    async def _extract_events_from_page(self):
        """Extract events from the current page."""
        body_text = await self.page.text_content("body") or ""

        # WSS lists events with dates as headings and linked titles
        # Format: "10 February 2026" heading followed by event title link to PDF
        links = await self.get_all_elements("a[href*='/seminars/'], a[href*='.pdf']")

        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link)

                if not href or not text or len(text) < 10:
                    continue

                # Skip navigation links
                if any(skip in text.lower() for skip in [
                    "menu", "home", "back", "view all", "seminars page",
                    "meetup", "join", "contact", "about"
                ]):
                    continue

                event = self._parse_event(text, href, body_text)
                if event and not any(e.url == event.url for e in self.events):
                    self.events.append(event)

            except Exception as e:
                self.logger.debug(f"Failed to parse WSS event: {e}")

        # Also try parsing from text structure
        if not self.events:
            self._parse_text_events(body_text)

    def _parse_event(self, title: str, url: str, body_text: str) -> Optional[Event]:
        """Parse an event from link text and surrounding context."""
        # Find the date near this title in the body text
        date_text = self._find_date_near_text(title, body_text)

        if not date_text:
            return None

        # Add ET timezone (Washington DC is Eastern Time)
        if not re.search(r"\b(?:ET|EST|EDT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        return self.create_event(
            title=title.strip(),
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=LocationType.VIRTUAL,
            cost="free",
            raw_date_text=date_text,
        )

    def _find_date_near_text(self, title: str, body_text: str) -> Optional[str]:
        """Find the date associated with an event title in the body text."""
        lines = body_text.split("\n")

        # Find the line with this title
        title_idx = None
        for i, line in enumerate(lines):
            if title[:30] in line:
                title_idx = i
                break

        if title_idx is None:
            return None

        # Look nearby (before and after) for a date
        for i in range(max(0, title_idx - 5), min(len(lines), title_idx + 5)):
            line = lines[i].strip()
            # Pattern: "10 February 2026" or "February 10, 2026"
            match = re.search(
                r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
                line, re.IGNORECASE
            )
            if match:
                return match.group(1)

            match = re.search(
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
                line, re.IGNORECASE
            )
            if match:
                return match.group(1)

        return None

    def _parse_text_events(self, body_text: str):
        """Parse events from unstructured text when links aren't available."""
        # Pattern: date followed by event title
        pattern = re.compile(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"
            r"\s*\n\s*(.+?)(?:\n|$)",
            re.IGNORECASE
        )

        for match in pattern.finditer(body_text):
            date_text = match.group(1)
            title = match.group(2).strip()

            if len(title) < 10:
                continue

            date_with_tz = f"{date_text} ET"

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(date_with_tz)
            except Exception:
                continue

            self.events.append(self.create_event(
                title=title,
                url=self.BASE_URL,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=LocationType.VIRTUAL,
                cost="free",
                raw_date_text=date_text,
            ))

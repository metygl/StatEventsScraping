"""
Scraper for IBS (International Biometric Society) Events.
Site: https://www.biometricsociety.org/meetings/events
React SPA on HigherLogic Connected Community platform.
"""

import re
import asyncio
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class IBSScraper(BaseScraper):
    """Scraper for IBS meetings and events (React SPA with wait)."""

    SOURCE_NAME = "IBS"
    BASE_URL = "https://www.biometricsociety.org/meetings/events"

    async def scrape(self) -> List[Event]:
        """Scrape IBS event listings from React SPA."""
        # Use domcontentloaded since React SPAs may never reach networkidle
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for React to render event items
        await asyncio.sleep(8)

        await self.wait_for_content(".event-item, main, body", timeout=15000)

        # Extract events from the rendered page
        await self._extract_events()

        return self.events

    async def _extract_events(self):
        """Extract events from the rendered React page."""
        # Try structured event items first
        items = await self.get_all_elements(".event-item")

        if items:
            for item in items:
                try:
                    event = await self._parse_event_item(item)
                    if event and not any(e.title == event.title for e in self.events):
                        self.events.append(event)
                except Exception as e:
                    self.logger.debug(f"Failed to parse IBS event item: {e}")
        else:
            # Fall back to extracting from page text
            await self._extract_from_text()

    async def _parse_event_item(self, item) -> Optional[Event]:
        """Parse a structured event item element."""
        # Get title and URL from link
        link = await item.query_selector("h3 a, h2 a, a")
        if not link:
            return None

        title = await self.get_element_text(link)
        url = await self.get_href(link) or self.BASE_URL

        if not title or len(title) < 5:
            return None

        # Get date/time text
        date_elem = await item.query_selector(".event-datetime, .event-date, time")
        date_text = await self.get_element_text(date_elem) if date_elem else None

        if not date_text:
            # Try to get date from item text
            item_text = await self.get_element_text(item) or ""
            date_text = self._extract_date(item_text)

        if not date_text:
            return None

        # Add ET timezone if none present
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT|GMT|CET)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        # Get event type/meta
        meta_elem = await item.query_selector(".event-meta, .event-type")
        meta_text = await self.get_element_text(meta_elem) if meta_elem else ""

        # Detect location type
        item_text = await self.get_element_text(item) or ""
        location_type = self.detect_location_type(item_text)

        # Extract location details
        location_details = None
        loc_match = re.search(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*|[A-Z]{2,}))",
            item_text
        )
        if loc_match:
            location_details = loc_match.group(1)

        # Determine cost from meta
        cost = "free" if "free" in item_text.lower() or "no payment" in item_text.lower() else ""

        return self.create_event(
            title=title.strip(),
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=location_type,
            location_details=location_details,
            cost=cost,
            raw_date_text=date_text,
        )

    async def _extract_from_text(self):
        """Extract events from unstructured page text."""
        body_text = await self.page.text_content("body") or ""

        # Look for event links
        links = await self.get_all_elements("a[href*='event-description'], a[href*='CalendarEventKey']")

        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link)

                if not href or not text or len(text) < 5:
                    continue

                # Find date near this link text
                date_text = self._find_date_near_text(text, body_text)
                if not date_text:
                    continue

                if not re.search(r"\b(?:ET|EST|EDT)\b", date_text, re.IGNORECASE):
                    date_text = f"{date_text} ET"

                start_dt, end_dt = DateParser.parse_datetime_range(date_text)

                self.events.append(self.create_event(
                    title=text.strip(),
                    url=href,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    speakers=[],
                    location_type=LocationType.UNKNOWN,
                    cost="",
                    raw_date_text=date_text,
                ))

            except Exception as e:
                self.logger.debug(f"Failed to parse IBS text event: {e}")

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Pattern: "Friday, February 13, 2026, 11:00 - 12:00 ET"
        match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}))?",
            text, re.IGNORECASE
        )
        if match:
            result = match.group(1)
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result

        # Pattern: date range "February 13-15, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}\s*[-–]\s*\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _find_date_near_text(self, title: str, body_text: str) -> Optional[str]:
        """Find date near an event title in body text."""
        lines = body_text.split("\n")
        for i, line in enumerate(lines):
            if title[:20] in line:
                for j in range(max(0, i - 3), min(len(lines), i + 5)):
                    date = self._extract_date(lines[j])
                    if date:
                        return date
        return None

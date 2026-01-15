"""
Scraper for DahShu Events.
Site: https://dahshu.wildapricot.org/events
Uses Wild Apricot platform for event management.
"""

import re
from typing import List, Optional
import asyncio

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class DahShuScraper(BaseScraper):
    """Scraper for DahShu webinars and seminars."""

    SOURCE_NAME = "DahShu"
    BASE_URL = "https://dahshu.wildapricot.org/events"

    async def scrape(self) -> List[Event]:
        """Scrape DahShu event listings."""
        await self.navigate_to_page()

        # Wild Apricot uses React - wait for content
        await asyncio.sleep(2)

        # Collect unique event URLs from the calendar/list view
        seen_event_ids = set()
        event_urls = []

        # Find all event links - Wild Apricot uses event-NNNNNN pattern
        all_links = await self.get_all_elements('a[href*="event-"]')

        for link in all_links:
            href = await self.get_href(link)
            if not href:
                continue

            # Extract event ID to deduplicate
            match = re.search(r"event-(\d+)", href)
            if match:
                event_id = match.group(1)
                if event_id not in seen_event_ids:
                    seen_event_ids.add(event_id)
                    # Clean URL - remove calendar view parameters
                    clean_url = re.sub(r"\?CalendarViewType.*$", "", href)
                    event_urls.append(clean_url)

        self.logger.info(f"Found {len(event_urls)} unique DahShu events")

        # Scrape each event page for full details
        for url in event_urls[:20]:  # Limit to avoid timeout
            try:
                event = await self._scrape_event_page(url)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse DahShu event {url}: {e}")

        return self.events

    async def _scrape_event_page(self, url: str) -> Optional[Event]:
        """Scrape individual event page for details."""
        await self.navigate_to_page(url)
        await asyncio.sleep(1)

        # Get title
        title = None
        for selector in ["h1", ".eventName", ".wa-event-title", "h2"]:
            title = await self.get_text(selector)
            if title and len(title) > 5:
                break

        if not title:
            return None

        # Get date and time - Wild Apricot has specific fields
        date_text = None
        time_text = ""

        # Try various date selectors
        for selector in [".eventDate", ".wa-event-date", ".date", "time"]:
            elem = await self.page.query_selector(selector)
            if elem:
                text = await self.get_element_text(elem)
                if text:
                    date_text = text
                    break

        # Also look for time
        for selector in [".eventTime", ".wa-event-time", ".time"]:
            elem = await self.page.query_selector(selector)
            if elem:
                text = await self.get_element_text(elem)
                if text:
                    time_text = text
                    break

        # If still no date, try to extract from page body
        if not date_text:
            body = await self.page.query_selector("body")
            if body:
                body_text = await self.get_element_text(body)
                # Look for date patterns
                date_match = re.search(
                    r"(\w+day,?\s+\w+\s+\d{1,2},?\s+\d{4})", body_text, re.IGNORECASE
                )
                if date_match:
                    date_text = date_match.group(1)

                # Look for time patterns
                time_match = re.search(r"(\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2})", body_text)
                if time_match:
                    time_text = time_match.group(1)

        if not date_text:
            return None

        # Combine date and time
        full_date_text = f"{date_text} {time_text}".strip()

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date_text}': {e}")
            return None

        # Get speakers from title or page
        speakers = self._extract_speakers_from_title(title)

        if not speakers:
            # Try to find speaker info on page
            for selector in [".speaker", ".presenter", ".eventSpeaker"]:
                elem = await self.page.query_selector(selector)
                if elem:
                    text = await self.get_element_text(elem)
                    if text:
                        speakers = self.parse_speakers(text)
                        break

        # DahShu events are typically virtual
        location_type = LocationType.VIRTUAL

        return self.create_event(
            title=self._clean_title(title),
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost="free",
            raw_date_text=full_date_text,
        )

    def _extract_speakers_from_title(self, title: str) -> List[str]:
        """Extract speaker names from title (usually in parentheses)."""
        match = re.search(r"\(([^)]+)\)\s*$", title)
        if match:
            return self.parse_speakers(match.group(1))
        return []

    def _clean_title(self, title: str) -> str:
        """Remove speaker info from title."""
        # Remove trailing parenthetical with speakers
        title = re.sub(r"\s*\([^)]+\)\s*$", "", title)
        return title.strip()

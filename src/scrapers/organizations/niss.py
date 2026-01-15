"""
Scraper for NISS (National Institute of Statistical Sciences) Events.
Site: https://www.niss.org/events
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class NISSScraper(BaseScraper):
    """Scraper for NISS events and webinars."""

    SOURCE_NAME = "NISS"
    BASE_URL = "https://www.niss.org/events"

    async def scrape(self) -> List[Event]:
        """Scrape NISS event listings."""
        await self.navigate_to_page()

        # Wait for content
        await self.wait_for_content(".view-content", timeout=10000)

        # First pass: collect all event URLs and basic info from the listing page
        # This avoids DOM context issues when navigating
        event_data = await self._collect_event_urls()

        self.logger.info(f"Found {len(event_data)} NISS events to process")

        # Second pass: scrape each event page
        for data in event_data:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse NISS event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs and basic data from listing page."""
        event_data = []

        # Find event items - NISS uses Drupal views
        event_items = await self.get_all_elements(".views-row, .event-item, article")

        for item in event_items:
            try:
                # Get title and link
                title_link = await item.query_selector(
                    "h2 a, h3 a, .views-field-title a, a[href*='/events/']"
                )
                if not title_link:
                    continue

                title = await self.get_element_text(title_link)
                url = await self.get_href(title_link)

                if not title or not url:
                    continue

                # Skip if not an event URL
                if "/events/" not in url:
                    continue

                # Get date if available on listing
                date_elem = await item.query_selector(
                    ".date-display-single, .views-field-field-event-date, .event-date, time"
                )
                date_text = await self.get_element_text(date_elem) if date_elem else None

                event_data.append({
                    "title": title,
                    "url": url,
                    "date_text": date_text,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event data: {e}")
                continue

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details."""
        url = data["url"]
        title = data["title"]
        date_text = data.get("date_text")

        await self.navigate_to_page(url)

        # Get date from event page if not already available
        if not date_text:
            for selector in [
                ".date-display-single",
                ".field--name-field-event-date",
                ".event-date",
                "time",
                ".date",
            ]:
                date_elem = await self.page.query_selector(selector)
                if date_elem:
                    date_text = await self.get_element_text(date_elem)
                    if date_text:
                        break

        # Also look for time information
        time_elem = await self.page.query_selector(".field--name-field-event-time, .time")
        time_text = await self.get_element_text(time_elem) if time_elem else ""

        # Combine date and time
        full_date_text = f"{date_text or ''} {time_text}".strip()

        if not full_date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date_text}': {e}")
            return None

        # Get speakers
        speakers = []
        for selector in [".field--name-field-speakers", ".speakers", ".presenter"]:
            speaker_elem = await self.page.query_selector(selector)
            if speaker_elem:
                speaker_text = await self.get_element_text(speaker_elem)
                if speaker_text:
                    speakers = self.parse_speakers(speaker_text)
                    break

        # Also check for speakers in parentheses in title
        if not speakers:
            speakers = self._extract_speakers(title)

        # Get body for location detection
        body_elem = await self.page.query_selector(".field--name-body, .body, main")
        body_text = await self.get_element_text(body_elem) if body_elem else ""

        location_type = self.detect_location_type(f"{title} {body_text}")
        if location_type == LocationType.UNKNOWN:
            # NISS events are typically webinars
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

    def _extract_speakers(self, title: str) -> List[str]:
        """Extract speaker names from title."""
        # Check for parenthetical in title
        match = re.search(r"\(([^)]+)\)", title)
        if match:
            potential = match.group(1)
            # Check if it looks like names (contains capital letters, not too long)
            if len(potential) < 100 and any(c.isupper() for c in potential):
                return self.parse_speakers(potential)
        return []

    def _clean_title(self, title: str) -> str:
        """Clean up event title."""
        # Remove trailing dates
        title = re.sub(r"\s*[-|]\s*\w+\s+\d{1,2},?\s+\d{4}\s*$", "", title)
        return title.strip()

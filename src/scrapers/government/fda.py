"""
Scraper for FDA Events.
Site: https://www.fda.gov/news-events/fda-meetings-conferences-and-workshops
Uses JSON API endpoint for event listing, then visits pages for times.
"""

import re
import json
from typing import List, Optional, Tuple
from datetime import datetime
import pytz

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class FDAScraper(BaseScraper):
    """Scraper for FDA meetings, conferences, and workshops."""

    SOURCE_NAME = "FDA"
    BASE_URL = "https://www.fda.gov/news-events/fda-meetings-conferences-and-workshops"
    JSON_URL = "https://www.fda.gov/datatables-json/events-meetings.json"
    PST = pytz.timezone("America/Los_Angeles")
    ET = pytz.timezone("America/New_York")

    async def scrape(self) -> List[Event]:
        """Fetch FDA events from JSON API, then visit pages for times."""
        # Navigate to JSON endpoint
        response = await self.page.goto(self.JSON_URL, timeout=30000)

        if not response or response.status != 200:
            self.logger.error(f"Failed to fetch FDA JSON: status {response.status if response else 'no response'}")
            return self.events

        # Get JSON content
        content = await self.page.content()

        # Extract JSON from page (it's wrapped in HTML tags by browser)
        json_match = re.search(r'<pre[^>]*>(.*?)</pre>', content, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            json_text = await self.page.evaluate("() => document.body.innerText")

        try:
            events_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse FDA JSON: {e}")
            return self.events

        self.logger.info(f"Found {len(events_data)} FDA events in JSON")

        # Parse events from JSON and collect URLs for detail pages
        events_to_process = []
        for event_data in events_data:
            try:
                event_info = self._parse_event_basic(event_data)
                if event_info:
                    events_to_process.append(event_info)
            except Exception as e:
                self.logger.warning(f"Failed to parse FDA event: {e}")

        # Visit each event page to get accurate times
        for title, url, date_str, source_name, location_type in events_to_process:
            try:
                event = await self._scrape_event_page(title, url, date_str, source_name, location_type)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to scrape FDA event page {url}: {e}")

        return self.events

    def _parse_event_basic(self, data: dict) -> Optional[Tuple]:
        """Parse basic event info from JSON. Returns tuple for further processing."""
        # Extract title and URL from HTML field
        title_html = data.get("field_event_title", "")
        if not title_html:
            return None

        # Parse title and URL from HTML: <a href="/path">Title</a>
        title_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', title_html)
        if not title_match:
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            url = self.BASE_URL
        else:
            url_path = title_match.group(1)
            title = title_match.group(2).strip()
            if url_path.startswith("/"):
                url = f"https://www.fda.gov{url_path}"
            else:
                url = url_path

        if not title or len(title) < 10:
            return None

        # Get date string
        date_str = data.get("field_start_date", "")
        if not date_str:
            return None

        # Determine event type for source name
        event_type = data.get("field_event_type", "")

        if "grand rounds" in title.lower() or "grand rounds" in event_type.lower():
            source_name = "FDA Grand Rounds"
        elif "webcast" in event_type.lower():
            source_name = "FDA Webcast"
        elif "workshop" in event_type.lower():
            source_name = "FDA Workshop"
        elif "town hall" in event_type.lower():
            source_name = "FDA Town Hall"
        elif "advisory committee" in event_type.lower():
            source_name = "FDA Advisory Committee Meeting"
        else:
            source_name = f"FDA {event_type}" if event_type else "FDA"

        # Determine location type
        location_type = LocationType.VIRTUAL
        if "in-person" in title.lower() or "hybrid" in title.lower():
            location_type = LocationType.HYBRID

        return (title, url, date_str, source_name, location_type)

    async def _scrape_event_page(
        self,
        title: str,
        url: str,
        date_str: str,
        source_name: str,
        location_type: LocationType
    ) -> Optional[Event]:
        """Visit event page to get accurate time information."""
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await self.page.wait_for_timeout(1000)

            body_text = await self.page.text_content("body") or ""

            # Extract time from page - FDA uses "12:00 p.m. - 1:00 p.m. ET" format
            time_info = self._extract_time(body_text)

            # Build full datetime
            if time_info:
                start_time, end_time = time_info
                # Parse date and add time with ET timezone
                try:
                    # FDA date format: MM/DD/YYYY
                    date_obj = datetime.strptime(date_str, "%m/%d/%Y")
                    full_date = f"{date_obj.strftime('%B %d, %Y')} {start_time}-{end_time} ET"
                    start_dt, end_dt = DateParser.parse_datetime_range(full_date)
                except Exception:
                    # Fallback: use date with default time
                    start_dt = self._parse_date_with_default_time(date_str)
                    end_dt = None
            else:
                # No time found, use default
                start_dt = self._parse_date_with_default_time(date_str)
                end_dt = None

            if not start_dt:
                return None

            return Event(
                source=source_name,
                title=title,
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=[],
                location_type=location_type,
                cost="free",
            )

        except Exception as e:
            self.logger.debug(f"Error fetching FDA event page: {e}")
            # Fallback to basic event without time
            start_dt = self._parse_date_with_default_time(date_str)
            if start_dt:
                return Event(
                    source=source_name,
                    title=title,
                    url=url,
                    start_datetime=start_dt,
                    speakers=[],
                    location_type=location_type,
                    cost="free",
                )
            return None

    def _extract_time(self, text: str) -> Optional[Tuple[str, str]]:
        """Extract time from FDA page. Returns (start_time, end_time)."""
        # FDA format: "12:00 p.m. - 1:00 p.m. ET" or "12:00 p.m.\n- 1:00 p.m.\nET"

        # Normalize text for matching
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text)

        # Pattern for FDA time format: "12:00 p.m. - 1:00 p.m."
        match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?))\s*[-–]\s*(\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?))",
            text,
            re.IGNORECASE
        )

        if match:
            start_time = match.group(1).replace('.', '').replace(' ', '')
            end_time = match.group(2).replace('.', '').replace(' ', '')
            # Normalize to "12:00pm" format
            start_time = re.sub(r'(\d+:\d+)\s*(am|pm)', r'\1\2', start_time, flags=re.IGNORECASE)
            end_time = re.sub(r'(\d+:\d+)\s*(am|pm)', r'\1\2', end_time, flags=re.IGNORECASE)
            return (start_time, end_time)

        return None

    def _parse_date_with_default_time(self, date_str: str) -> Optional[datetime]:
        """Parse date string and add default time (9am PST = noon ET)."""
        try:
            # FDA date format: MM/DD/YYYY
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
            # Default to noon ET (9am PST) - common FDA time
            return self.ET.localize(date_obj.replace(hour=12, minute=0)).astimezone(self.PST)
        except ValueError:
            try:
                start_dt, _ = DateParser.parse_datetime_range(date_str)
                return start_dt
            except Exception:
                return None

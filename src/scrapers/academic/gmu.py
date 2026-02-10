"""
Scraper for George Mason University Statistics Seminar Series.
Site: https://statistics.gmu.edu/about/events
Uses 25Live/Trumba JSON API (bypasses JS widget rendering).
"""

import re
import json
from datetime import datetime
from typing import List, Optional
import pytz

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class GMUScraper(BaseScraper):
    """Scraper for GMU R. Clifton Bailey Statistics Seminar Series."""

    SOURCE_NAME = "George Mason University R. Clifton Bailey Statistics Seminar Series"
    BASE_URL = "https://statistics.gmu.edu/about/events"
    API_URL = "https://25livepub.collegenet.com/calendars/cec-statistics.json"
    ET = pytz.timezone("America/New_York")
    PST = pytz.timezone("America/Los_Angeles")

    async def scrape(self) -> List[Event]:
        """Scrape GMU seminar listings from 25Live JSON API."""
        response = await self.page.goto(
            self.API_URL, wait_until="domcontentloaded", timeout=30000
        )

        if not response or response.status != 200:
            self.logger.error(
                f"Failed to fetch GMU JSON: status "
                f"{response.status if response else 'no response'}"
            )
            return self.events

        # Get JSON content from page
        body_text = await self.page.text_content("body") or ""

        try:
            events_data = json.loads(body_text)
        except json.JSONDecodeError:
            # Browser may wrap JSON in <pre> tags
            pre_elem = await self.page.query_selector("pre")
            if pre_elem:
                body_text = await self.get_element_text(pre_elem) or ""
                events_data = json.loads(body_text)
            else:
                self.logger.error("Could not parse GMU JSON response")
                return self.events

        if not isinstance(events_data, list):
            self.logger.error("GMU API response is not a list")
            return self.events

        self.logger.info(f"Found {len(events_data)} GMU events from API")

        for event_obj in events_data:
            try:
                if event_obj.get("canceled", False):
                    continue
                event = self._parse_event(event_obj)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse GMU event: {e}")

        return self.events

    def _parse_event(self, data: dict) -> Optional[Event]:
        """Parse a single event from the JSON API response."""
        event_id = data.get("eventID")
        description_html = data.get("description", "")
        start_str = data.get("startDateTime", "")
        end_str = data.get("endDateTime", "")
        tz_offset = data.get("startTimeZoneOffset", "-0500")

        if not start_str or not event_id:
            return None

        # Parse datetimes with timezone offset
        start_dt = self._parse_iso_with_offset(start_str, tz_offset)
        end_dt = self._parse_iso_with_offset(end_str, tz_offset) if end_str else None

        if not start_dt:
            return None

        # Extract talk title and speaker from HTML description
        description_text = self._strip_html(description_html)
        talk_title = self._extract_talk_title(description_text)
        speakers = self._extract_speakers_from_description(description_text)

        # Build the event title
        if talk_title:
            title = talk_title
        else:
            title = data.get("title", "Statistics Seminar")

        # Build GMU canonical URL
        url = (
            f"https://statistics.gmu.edu/about/events"
            f"?trumbaEmbed=view%3Devent%26eventid%3D{event_id}"
        )

        # Detect location type from description
        location_type = LocationType.HYBRID  # GMU seminars are live-streamed
        if "virtual" in description_text.lower() and "in-person" not in description_text.lower():
            location_type = LocationType.VIRTUAL

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost="free",
        )

    def _parse_iso_with_offset(self, dt_str: str, offset: str) -> Optional[datetime]:
        """Parse ISO datetime string with timezone offset, convert to PST."""
        try:
            # Parse the ISO datetime (e.g., "2026-02-13T11:00:00")
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")

            # Apply timezone offset (e.g., "-0500" for EST)
            hours = int(offset[:3])
            minutes = int(offset[0] + offset[3:5])
            from datetime import timedelta, timezone
            tz = timezone(timedelta(hours=hours, minutes=minutes))
            dt = dt.replace(tzinfo=tz)

            # Convert to PST
            return dt.astimezone(self.PST)
        except Exception as e:
            self.logger.debug(f"Could not parse datetime '{dt_str}': {e}")
            return None

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags and decode entities."""
        if not html:
            return ""
        # Convert block-level tags to newlines
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        # Strip remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&nbsp;", " ")
        text = text.replace("&#160;", " ")
        text = text.replace("&#39;", "'")
        text = text.replace("&#8217;", "'")
        text = text.replace("&#8211;", "-")
        text = text.replace("&quot;", '"')
        # Collapse whitespace but preserve newlines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)
        return text.strip()

    def _extract_talk_title(self, text: str) -> Optional[str]:
        """Extract talk title from description text.

        Typical format:
        Talk Title Here
        Dr. Speaker Name, Position, Department, University
        Location: ...
        """
        if not text:
            return None

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        # The talk title is typically the first line(s) before a line starting with
        # "Dr.", "Prof.", "Speaker:", "Location:", or a name pattern
        title_parts = []
        for line in lines:
            # Stop at speaker/location/meta lines
            if re.match(
                r"^(?:Dr\.|Prof\.|Professor |Speaker|Location|"
                r"This seminar|Abstract|Bio|Register|REGISTER|"
                r"Please |Join us|Zoom|https?://)",
                line, re.IGNORECASE
            ):
                break
            # Stop if line looks like "Name, Position, Department"
            if re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+,\s+", line) and len(title_parts) > 0:
                break
            title_parts.append(line)

        if title_parts:
            title = " ".join(title_parts)
            # Clean up
            title = re.sub(r"\s+", " ", title).strip()
            if len(title) > 10:
                return title

        return None

    def _extract_speakers_from_description(self, text: str) -> List[str]:
        """Extract speaker names from description text."""
        speakers = []

        if not text:
            return speakers

        # Pattern: "Dr. FirstName LastName" or "Prof. FirstName LastName"
        match = re.search(
            r"(?:Dr\.|Prof\.|Professor )\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())
            return speakers

        # Pattern: "Speaker: Name" or "Presented by Name"
        match = re.search(
            r"(?:Speaker|Presenter|Presented by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

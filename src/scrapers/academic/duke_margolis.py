"""
Scraper for Duke-Margolis Center for Health Policy Events.
Site: https://healthpolicy.duke.edu/events
Drupal with Views module and AJAX-enabled filtering.
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class DukeMargolisScraper(BaseScraper):
    """Scraper for Duke-Margolis health policy events."""

    SOURCE_NAME = "Duke-Margolis"
    BASE_URL = "https://healthpolicy.duke.edu/events"

    async def scrape(self) -> List[Event]:
        """Scrape Duke-Margolis event listings."""
        await self.navigate_to_page()

        await self.wait_for_content(".view-content, main, body", timeout=15000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} Duke-Margolis events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse Duke-Margolis event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # Drupal views typically use article elements or views-row divs
        items = await self.get_all_elements(
            ".views-row, article, .node--type-event"
        )

        for item in items:
            try:
                # Get title link
                link = await item.query_selector(
                    "h2 a, h3 a, .field--name-title a, a[href*='/events/']"
                )
                if not link:
                    continue

                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 5:
                    continue

                if href in seen_urls:
                    continue

                # Skip non-event links
                if any(skip in title.lower() for skip in [
                    "read more", "view all", "menu", "back"
                ]):
                    continue

                seen_urls.add(href)

                # Try to get date from listing
                date_elem = await item.query_selector(
                    ".datetime, .date, time, .field--name-field-event-date"
                )
                date_text = await self.get_element_text(date_elem) if date_elem else None

                # Try to get category
                cat_elem = await item.query_selector(
                    ".field--name-field-event-type, .category, .tag"
                )
                category = await self.get_element_text(cat_elem) if cat_elem else None

                event_data.append({
                    "title": title.strip(),
                    "url": href,
                    "date_text": date_text,
                    "category": category,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event data: {e}")

        # Fallback: extract any event-like links
        if not event_data:
            links = await self.get_all_elements("a")
            for link in links:
                try:
                    href = await self.get_href(link)
                    text = await self.get_element_text(link) or ""
                    if (href and "healthpolicy.duke.edu" in href and
                            "/events/" in href and len(text) > 10 and
                            href not in seen_urls):
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
        h1_text = await self.get_text("h1")
        if h1_text and len(h1_text) > 10:
            title = h1_text.strip()

        # Extract date
        date_text = data.get("date_text") or self._extract_date(body_text)
        if not date_text:
            return None

        # Extract time
        time_text = self._extract_time(body_text)
        full_date = f"{date_text} {time_text}".strip()

        # Add ET timezone if none present
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT)\b", full_date, re.IGNORECASE):
            full_date = f"{full_date} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{full_date}': {e}")
            return None

        # Detect location type
        location_type = self.detect_location_type(body_text)
        if location_type == LocationType.UNKNOWN:
            if "webinar" in body_text.lower() or "virtual" in body_text.lower():
                location_type = LocationType.VIRTUAL
            else:
                location_type = LocationType.IN_PERSON

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost="free",
            raw_date_text=full_date,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from page text."""
        # Pattern: "February 19, 2026"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from page text."""
        # Pattern: "1:00 PM - 2:30 PM ET"
        match = re.search(
            r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))"
            r"(?:\s*(ET|EST|EDT|PT|PST|PDT|CT))?",
            text
        )
        if match:
            result = match.group(1)
            tz = match.group(2)
            if tz:
                result = f"{result} {tz}"
            return result

        return ""

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        # Pattern: "Speaker(s):" or "Presenter(s):" or "Panelist(s):"
        match = re.search(
            r"(?:Speaker|Presenter|Panelist|Featuring)[s]?[:\s]+(.+?)(?:\n|$)",
            text, re.IGNORECASE
        )
        if match:
            speaker_text = match.group(1).strip()
            if len(speaker_text) < 200:
                return self.parse_speakers(speaker_text)

        return speakers

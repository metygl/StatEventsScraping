"""
Scraper for Posit (formerly RStudio) Events.
Site: https://posit.co/events/
"""

import asyncio
from typing import List

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class PositScraper(BaseScraper):
    """Scraper for Posit conferences, meetups, and webinars."""

    SOURCE_NAME = "Posit"
    BASE_URL = "https://posit.co/events/"

    async def scrape(self) -> List[Event]:
        """Scrape Posit event listings."""
        await self.navigate_to_page()

        # Wait for JavaScript to render event cards
        await asyncio.sleep(3)

        # Wait for card content to appear
        try:
            await self.page.wait_for_selector(".posit-card", timeout=10000)
        except Exception:
            self.logger.warning("No .posit-card elements found")
            return self.events

        # Get all event cards
        cards = await self.get_all_elements(".posit-card")
        self.logger.info(f"Found {len(cards)} Posit event cards")

        for card in cards:
            try:
                event = await self._parse_card(card)
                if event:
                    # Avoid duplicates
                    if not any(e.url == event.url for e in self.events):
                        self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse Posit card: {e}")

        return self.events

    async def _parse_card(self, card) -> Event | None:
        """Parse a single event card."""
        # Get title
        title_elem = await card.query_selector("h3.card-title")
        if not title_elem:
            return None

        title = await self.get_element_text(title_elem)
        if not title or len(title) < 5:
            return None

        # Get event URL from card footer link
        link_elem = await card.query_selector("a.card-button")
        url = await self.get_href(link_elem) if link_elem else self.BASE_URL

        # Get date components
        day_elem = await card.query_selector(".card-date-day")
        month_elem = await card.query_selector(".card-date-month--start")
        year_elem = await card.query_selector(".card-date-year-container span")
        time_elem = await card.query_selector(".card-date-time span")

        day_text = await self.get_element_text(day_elem) if day_elem else ""
        month_text = await self.get_element_text(month_elem) if month_elem else ""
        year_text = await self.get_element_text(year_elem) if year_elem else ""
        time_text = await self.get_element_text(time_elem) if time_elem else ""

        # Build date string
        if day_text and month_text and year_text:
            date_str = f"{month_text} {day_text}, {year_text}"
            if time_text:
                date_str = f"{date_str} {time_text}"
        else:
            # Fallback: try to get date from card text
            card_text = await self.get_element_text(card)
            date_str = card_text

        if not date_str:
            return None

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_str)
        except Exception:
            self.logger.debug(f"Could not parse date from: {date_str[:50]}")
            return None

        # Get event type from kicker
        kicker_elem = await card.query_selector("p.card-kicker")
        event_type = await self.get_element_text(kicker_elem) if kicker_elem else ""

        # Get description
        desc_elem = await card.query_selector("p.card-description")
        description = await self.get_element_text(desc_elem) if desc_elem else ""

        # Detect location type
        full_text = f"{title} {description} {event_type}"
        location_type = self.detect_location_type(full_text)

        # Determine location from event type and description
        if "webinar" in title.lower() or "webinar" in event_type.lower():
            location_type = LocationType.VIRTUAL
        elif "in-person" in description.lower():
            location_type = LocationType.IN_PERSON
        elif "hangout" in event_type.lower():
            location_type = LocationType.VIRTUAL

        # Determine source name based on event type
        if event_type:
            source_name = f"Posit {event_type}"
        else:
            source_name = "Posit"

        # Extract cost
        cost = self._extract_cost(full_text)

        return self.create_event(
            title=title,
            url=url or self.BASE_URL,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=[],
            location_type=location_type,
            cost=cost,
            raw_date_text=date_str,
        )

    def _extract_cost(self, text: str) -> str:
        """Extract cost information."""
        import re

        text_lower = text.lower()

        if "free" in text_lower:
            return "free"

        # Look for price patterns
        match = re.search(r"\$\s*\d+(?:\s*[-–]\s*\$?\s*\d+)?", text)
        if match:
            return match.group(0)

        # Check for registration required
        if "register" in text_lower or "registration" in text_lower:
            if "free" not in text_lower:
                return "registration required"

        return "free"

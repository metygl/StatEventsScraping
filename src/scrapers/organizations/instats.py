"""
Scraper for Instats Seminars.
Site: https://instats.org/results?view=Seminars

This is a Bubble.io SPA that loads content dynamically via JavaScript.
We extract titles from the listing page, then visit individual event pages for times.
"""

import re
from typing import List, Optional, Tuple
import asyncio

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class InstatsScraper(BaseScraper):
    """Scraper for Instats seminars and courses."""

    SOURCE_NAME = "Instats Seminar"
    BASE_URL = "https://instats.org/results?view=Seminars"

    async def scrape(self) -> List[Event]:
        """Scrape Instats seminar listings."""
        await self.navigate_to_page()

        # Bubble.io apps need significant time to render content
        await asyncio.sleep(8)

        # Extract event info from cards, then visit each page for times
        event_info = await self._extract_events_from_cards()
        self.logger.info(f"Found {len(event_info)} seminars on listing page")

        # Visit each event page to get accurate times
        for title, url, raw_date, speakers, cost in event_info[:20]:  # Limit to 20
            try:
                event = await self._scrape_event_page(title, url, raw_date, speakers, cost)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to scrape {url}: {e}")

        return self.events

    async def _extract_events_from_cards(self) -> List[Tuple[str, str, str, List[str], str]]:
        """Extract event info from Bubble.io cards on listing page.

        Returns list of (title, url, raw_date, speakers, cost) tuples.
        """
        events = []

        cards = await self.get_all_elements('.clickable-element.bubble-element.Group')
        self.logger.info(f"Extracted {len(cards)} seminars using selector '.clickable-element.bubble-element.Group'")

        for card in cards:
            try:
                card_text = await self.get_element_text(card)
                if not card_text or len(card_text) < 30:
                    continue

                # Extract title - text before "Livestream:"
                title_match = re.search(r'^(.+?)(?:Livestream|Online|Live)', card_text, re.IGNORECASE)
                if not title_match:
                    continue

                title = title_match.group(1).strip()
                if len(title) < 10:
                    continue

                # Extract date - after "Livestream:"
                date_match = re.search(
                    r'(?:Livestream|Online|Live)[:\s]*([A-Z][a-z]{2}\s+\d{1,2}(?:th|st|nd|rd)?)',
                    card_text,
                    re.IGNORECASE
                )
                raw_date = date_match.group(1).strip() if date_match else ""

                # Extract instructor name
                instructor_match = re.search(
                    r'(?:\d(?:th|st|nd|rd)?)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    card_text
                )
                speakers = []
                if instructor_match:
                    name = instructor_match.group(1).strip()
                    # Filter out organization names
                    if name.lower() not in {"american statistical association", "statistical association", "free seminar"}:
                        speakers = [name]

                # Check for free in title
                cost = "free" if "free" in title.lower() else "paid"

                # Construct URL from title
                url = self._title_to_url(title)

                events.append((title, url, raw_date, speakers, cost))

            except Exception as e:
                self.logger.debug(f"Failed to parse card: {e}")

        return events

    def _title_to_url(self, title: str) -> str:
        """Convert event title to Instats URL slug."""
        # Remove parenthetical content like "(Free Seminar)"
        slug = re.sub(r'\s*\([^)]*\)\s*', '', title)
        # Convert to lowercase
        slug = slug.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        # Handle multiple hyphens
        slug = re.sub(r'-+', '-', slug)

        return f"https://instats.org/seminar/{slug}"

    async def _scrape_event_page(
        self,
        title: str,
        url: str,
        raw_date: str,
        speakers: List[str],
        cost: str
    ) -> Optional[Event]:
        """Visit individual event page to get accurate date/time."""
        try:
            await self.navigate_to_page(url)
            await asyncio.sleep(3)  # Wait for Bubble.io to render

            body_text = await self.page.inner_text("body")

            # Extract time from page - format: "12:00 pm to 1:00 pm"
            time_match = re.search(
                r'(\d{1,2}:\d{2}\s*(?:am|pm))\s*to\s*(\d{1,2}:\d{2}\s*(?:am|pm))',
                body_text,
                re.IGNORECASE
            )

            # Extract date from page - format: "Jan 14th 2026"
            date_match = re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})',
                body_text,
                re.IGNORECASE
            )

            if date_match:
                date_str = date_match.group(1)
                if time_match:
                    start_time = time_match.group(1)
                    end_time = time_match.group(2)
                    date_str = f"{date_str} {start_time}-{end_time}"
            else:
                # Fallback to raw_date from listing
                date_str = f"{raw_date} 2026" if raw_date else None

            if not date_str:
                return None

            # Parse datetime
            try:
                start_dt, end_dt = DateParser.parse_datetime_range(date_str)
            except Exception:
                return None

            # Extract speakers from page if not already found
            if not speakers:
                speakers = self._extract_speakers_from_text(body_text)

            # Extract cost from page
            page_cost = self._extract_cost_from_text(body_text)
            if page_cost != "free":
                cost = page_cost

            return self.create_event(
                title=title,
                url=url,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=speakers[:5],
                location_type=LocationType.VIRTUAL,
                cost=cost,
                raw_date_text=date_str,
            )

        except Exception as e:
            self.logger.debug(f"Error scraping {url}: {e}")
            return None

    def _extract_speakers_from_text(self, text: str) -> List[str]:
        """Extract speaker names from page text."""
        speakers = []

        # Organization names to exclude (not actual speakers)
        org_names = {
            "american statistical association", "statistical association",
            "free seminar", "instats", "online course", "livestream",
        }

        # Look for names after common patterns
        patterns = [
            r"(?:instructor|speaker|by|presented by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Filter out organization names
                if match.lower().strip() not in org_names:
                    speakers.extend(self.parse_speakers(match))

        return list(dict.fromkeys(speakers))

    def _extract_cost_from_text(self, text: str) -> str:
        """Extract cost from page text."""
        text_lower = text.lower()

        if "free" in text_lower:
            return "free"

        # Look for price patterns like "$384-$548"
        price_match = re.search(r"\$(\d+(?:,\d+)?(?:\s*[-–]\s*\$?\d+(?:,\d+)?)?)", text)
        if price_match:
            return f"${price_match.group(1)}"

        return "paid"

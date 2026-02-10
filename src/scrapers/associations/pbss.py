"""
Scraper for PBSS (Pacific Bridge Statistical Society) Events.
Site: https://www.pbss.org/chapter/SF-Bay
React SPA that requires JavaScript rendering.
"""

import re
import asyncio
from typing import List, Optional, Dict
from urllib.parse import urljoin

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class PBSSScraper(BaseScraper):
    """Scraper for PBSS webcasts and events."""

    SOURCE_NAME = "PBSS Webcast"
    BASE_URL = "https://www.pbss.org/chapter/SF-Bay"

    async def _goto(self, url: str) -> None:
        """Navigate using domcontentloaded (PBSS React SPA never reaches networkidle)."""
        self.logger.info(f"Navigating to {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            self.logger.warning(f"Navigation to {url} had issues: {e}")

    async def scrape(self) -> List[Event]:
        """Scrape PBSS event listings from React SPA."""
        await self._goto(self.BASE_URL)

        # React SPA needs time to render
        await asyncio.sleep(8)

        # Wait for event links to appear
        found = await self.wait_for_content(
            "a[href*='eventDetails']",
            timeout=15000,
        )

        if not found:
            self.logger.warning("PBSS React app may not have fully rendered")
            await asyncio.sleep(5)

        # Collect event data from listing page links
        event_data = await self._collect_events()
        self.logger.info(f"Found {len(event_data)} PBSS events to process")

        # Visit each event detail page
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse PBSS event {data.get('url')}: {e}")

        return self.events

    async def _collect_events(self) -> List[Dict]:
        """Collect events from the React-rendered listing page."""
        event_data = []
        seen_urls = set()

        # PBSS listing page has links like /eventDetails/1018
        links = await self.get_all_elements("a[href*='eventDetails']")

        for link in links:
            try:
                href = await self.get_href(link)
                link_text = await self.get_element_text(link) or ""

                if not href or href in seen_urls:
                    continue

                # Skip if doesn't contain eventDetails
                if "eventDetails" not in href:
                    continue

                seen_urls.add(href)

                # The link text on PBSS contains structured info like:
                # "San Francisco Bay WebcastFebruary 10, 202608:30 AM - 12:00 PM PTWebcastBiopharm..."
                event_data.append({
                    "url": href,
                    "link_text": link_text.strip(),
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event detail page."""
        url = data["url"]

        await self._goto(url)
        await asyncio.sleep(5)  # Wait for React to render detail page

        body_text = await self.page.text_content("body") or ""

        if "404" in body_text[:200] or "page you visited" in body_text[:300].lower():
            self.logger.debug(f"404 on PBSS event page: {url}")
            return None

        # Extract title - appears after the date/type header
        title = self._extract_title(body_text)
        if not title:
            self.logger.debug(f"No title found for {url}")
            return None

        # Extract date and time
        date_text = self._extract_date(body_text)
        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        # Extract cost
        cost = self._extract_cost(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost=cost,
            raw_date_text=date_text,
        )

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract event title from PBSS detail page text.

        React SPA renders all text on one line (no newlines), so we use
        keyword boundaries instead. Two page layouts:
        - Closed: ...Registration is closed[TITLE]Speakers:...
        - Active: ...Registration Fee:...Event Description[TITLE]Speakers:...
        """
        # 1. Text between "Event Description" and "Speakers:" (active registration pages)
        match = re.search(
            r"Event Description\s*(.{15,}?)(?=Speakers?:|Organizer|Location)",
            text
        )
        if match:
            title = self._clean_title(match.group(1))
            if title and len(title) > 15:
                return title

        # 2. Text between "Registration is closed" and "Speakers:" (closed registration)
        match = re.search(
            r"Registration is closed\s*(.{15,}?)(?=Speakers?:|Event Description|Organizer)",
            text
        )
        if match:
            title = self._clean_title(match.group(1))
            if title and len(title) > 15:
                return title

        # 3. Fallback: text between timezone marker and next section
        match = re.search(
            r"(?:AM|PM)\s+(?:PT|ET|CT|PST|EST|CST)\s*(.{15,}?)"
            r"(?=Speakers?:|Event Description|Registration|Organizer)",
            text
        )
        if match:
            title = self._clean_title(match.group(1))
            if title and len(title) > 15:
                return title

        return None

    def _clean_title(self, raw: str) -> str:
        """Remove UI artifacts from extracted title text."""
        title = raw.strip()
        # Remove button/link text and bracketed prefixes from React rendering
        title = re.sub(r"^(?:Register Now|Sign Up|Learn More|View Details)\s*", "", title)
        title = re.sub(r"^\[(?:Free Online|Virtual|In-Person|Webcast)\]\s*", "", title, flags=re.IGNORECASE)
        return title.strip()

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from PBSS detail page."""
        # Pattern: "February 10, 2026 |08:30 AM - 12:00 PM PT"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"[|\s]+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\s*[-–]\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))"
            r"(?:\s*(PT|ET|CT|PST|EST|CST|PDT|EDT|CDT))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            tz = match.group(3) or "PT"
            return f"{date_str} {time_str} {tz}"

        # Simpler pattern: date with time
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:[,|\s]+(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str} PT".strip()

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from PBSS detail page.

        Format: 'Speakers: Lucy Li, PhD (VP, One Medicines)Nick Mordwinkin (CBO)...'
        Names run together without newlines; parenthesized content has titles/orgs.
        """
        match = re.search(
            r"Speakers?:\s*(.+?)(?:Organizer|Registration|Event Description|Location)",
            text, re.IGNORECASE | re.DOTALL
        )
        if not match:
            return []

        speaker_block = match.group(1).strip()

        # Replace parenthesized content (job titles, orgs) with separators
        cleaned = re.sub(r"\([^)]*\)", ";", speaker_block)
        # Remove degree suffixes
        cleaned = re.sub(
            r",?\s*(?:PhD|MD|MBA|JD|MS|MSc|MSE|MPH|DrPH|BSc|DSc|PharmD|CEO|CSO)\.?",
            "", cleaned, flags=re.IGNORECASE
        )
        # Split by semicolons and commas, filter to name-like patterns
        parts = re.split(r"[;,]+", cleaned)
        # Common company/org name suffixes to exclude
        org_words = {
            "Therapeutics", "Biosciences", "Pharmaceuticals", "Consulting",
            "Sciences", "University", "Biotherapeutics", "Medicines",
        }
        names = []
        for part in parts:
            part = part.strip()
            # Names are 2-4 capitalized words
            if re.match(
                r"^[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$",
                part
            ):
                # Skip company/org names
                if any(word in part for word in org_words):
                    continue
                if part not in names:
                    names.append(part)
        return names[:8]

    def _extract_cost(self, text: str) -> str:
        """Extract cost from PBSS detail page."""
        text_lower = text.lower()

        if "free" in text_lower or "$0" in text_lower or "no cost" in text_lower:
            return "free"

        # Look for "Registration Fee:" section
        match = re.search(r"Registration Fee[:\s]+(.+?)(?:\n|Location|Event)", text, re.IGNORECASE)
        if match:
            fee_text = match.group(1)
            if "free" in fee_text.lower() or "$0" in fee_text:
                return "free"
            price_match = re.search(r"\$(\d+(?:\.\d{2})?)", fee_text)
            if price_match:
                return f"${price_match.group(1)}"

        return "free"

"""
Scraper for ASA North Texas Chapter Events.
Site: https://www.amstat-nt.org/
Google Sites page — same platform as SFASA.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASANorthTexasScraper(BaseScraper):
    """Scraper for ASA North Texas chapter events from Google Sites."""

    SOURCE_NAME = "ASA North Texas"
    BASE_URL = "https://www.amstat-nt.org/"

    async def scrape(self) -> List[Event]:
        """Scrape ASA North Texas event listings."""
        await self.navigate_to_page()
        await self.wait_for_content('[role="main"], main, body', timeout=10000)

        main_el = await self.page.query_selector('[role="main"]')
        body_text = await main_el.inner_text() if main_el else await self.page.inner_text("body")

        self._parse_events(body_text)

        # Check for events sub-page
        event_urls = await self._find_event_links()
        for url in event_urls[:10]:
            try:
                await self.navigate_to_page(url)
                main_el = await self.page.query_selector('[role="main"]')
                page_text = await main_el.inner_text() if main_el else await self.page.inner_text("body")
                self._parse_events(page_text, source_url=url)
            except Exception as e:
                self.logger.debug(f"Failed to scrape sub-page {url}: {e}")

        return self.events

    async def _find_event_links(self) -> List[str]:
        """Find links to event sub-pages."""
        urls = []
        seen = set()
        links = await self.get_all_elements("a[href]")
        for link in links:
            href = await self.get_href(link)
            text = await self.get_element_text(link) or ""
            if not href or href in seen:
                continue
            text_lower = text.lower()
            if any(kw in text_lower for kw in ["event", "meeting", "seminar", "workshop", "datafest"]):
                if href != self.BASE_URL and "amstat-nt.org" in href:
                    seen.add(href)
                    urls.append(href)
        return urls

    def _parse_events(self, text: str, source_url: Optional[str] = None):
        """Parse events from page text."""
        # Find dates to anchor events
        date_matches = list(re.finditer(
            r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}"
            r"[^\n]*)",
            text, re.IGNORECASE
        ))

        if not date_matches:
            # Try labeled dates
            date_matches = list(re.finditer(
                r"(?:Date|When)[:\s]+"
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}[^\n]*)",
                text, re.IGNORECASE
            ))

        for match in date_matches:
            date_text = match.group(1).strip()
            # Remove ordinal suffixes
            date_text = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", date_text)

            start_pos = max(0, match.start() - 500)
            end_pos = min(len(text), match.end() + 500)
            before_text = text[start_pos:match.start()]
            after_text = text[match.end():end_pos]

            # Add CT timezone (North Texas)
            if not re.search(r"\b(?:CT|CST|CDT|ET|PT)\b", date_text, re.IGNORECASE):
                date_text = f"{date_text} CT"

            try:
                start_dt, end_dt = DateParser.parse_datetime_range(date_text)
            except Exception:
                continue

            title = self._extract_title(before_text)
            if not title:
                continue
            if any(e.title == title for e in self.events):
                continue

            full_context = before_text + match.group(0) + after_text
            location_type = self.detect_location_type(full_context)
            location_details = self._extract_location(full_context)
            if location_type == LocationType.UNKNOWN:
                location_type = LocationType.IN_PERSON
            speakers = self._extract_speakers(full_context)
            cost = self._extract_cost(full_context)

            self.events.append(self.create_event(
                title=title,
                url=source_url or self.BASE_URL,
                start_datetime=start_dt,
                end_datetime=end_dt,
                speakers=speakers,
                location_type=location_type,
                location_details=location_details,
                cost=cost,
                raw_date_text=date_text,
            ))

    def _extract_title(self, before_text: str) -> Optional[str]:
        """Extract event title from text before the date."""
        lines = [l.strip() for l in before_text.split("\n") if l.strip()]
        for line in reversed(lines):
            if re.match(r"^(?:Speaker|Date|Time|Location|Place|Cost|Register|When|Where)[:\s]",
                        line, re.IGNORECASE):
                continue
            if len(line) < 10:
                continue
            if re.match(r"^(?:Home|About|Events|Contact|Menu|Navigation|Officers|Newsletter)",
                        line, re.IGNORECASE):
                continue
            return line[:300]
        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names."""
        speakers = []
        match = re.search(r"(?:Speaker|Presenter)[s]?[:\s]+([^\n]+)", text, re.IGNORECASE)
        if match:
            speaker_text = match.group(1).strip()
            speaker_text = re.sub(r"\s*\([^)]+\)", "", speaker_text)
            speaker_text = re.sub(r",?\s*(?:PhD|MD|MBA|JD|MS|MSc|MPH|DrPH|PharmD)\.?", "", speaker_text)
            names = re.split(r"\s*[;,&]\s*(?:and\s+)?|\s+and\s+", speaker_text)
            for name in names:
                name = name.strip()
                if name and len(name) > 3 and any(c.isupper() for c in name):
                    speakers.append(name)
        return speakers

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location details."""
        match = re.search(r"(?:Place|Location|Where|Venue)[:\s]+([^\n]+)", text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            if len(location) > 3:
                return location[:150]
        return None

    def _extract_cost(self, text: str) -> str:
        """Extract cost information."""
        match = re.search(r"(?:Cost|Price|Fee)[:\s]+([^\n]+)", text, re.IGNORECASE)
        if match:
            return self.normalize_cost(match.group(1))
        if "free" in text.lower():
            return "free"
        return ""

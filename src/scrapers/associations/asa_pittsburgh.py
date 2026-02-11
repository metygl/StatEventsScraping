"""
Scraper for ASA Pittsburgh Chapter Events.
Site: https://amstatpgh.com/
WordPress blog with events posted as blog posts.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASAPittsburghScraper(BaseScraper):
    """Scraper for ASA Pittsburgh chapter events from WordPress blog."""

    SOURCE_NAME = "ASA Pittsburgh"
    BASE_URL = "https://amstatpgh.com/"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Pittsburgh event listings."""
        await self.navigate_to_page()
        await self.wait_for_content("article, .post, .entry-content, main, body", timeout=10000)

        # Try to get article/post elements first
        articles = await self.get_all_elements("article, .post, .entry-content")

        if articles:
            for article in articles[:15]:
                try:
                    text = await article.inner_text()
                    # Get the article link if available
                    link_el = await article.query_selector("a[href]")
                    url = await self.get_href(link_el) if link_el else self.BASE_URL
                    self._parse_event_from_text(text, url or self.BASE_URL)
                except Exception as e:
                    self.logger.debug(f"Failed to parse article: {e}")
        else:
            # Fallback to full page text
            body_text = await self.page.inner_text("body")
            self._parse_events_from_body(body_text)

        return self.events

    def _parse_events_from_body(self, text: str):
        """Parse events from full page body text."""
        date_matches = list(re.finditer(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})",
            text, re.IGNORECASE
        ))
        for match in date_matches:
            start_pos = max(0, match.start() - 500)
            end_pos = min(len(text), match.end() + 500)
            before = text[start_pos:match.start()]
            after = text[match.end():end_pos]
            date_text = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(1))
            self._try_create_event(date_text, before, after, self.BASE_URL)

    def _parse_event_from_text(self, text: str, url: str):
        """Parse an event from article/post text."""
        date_matches = list(re.finditer(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}[^\n]*)",
            text, re.IGNORECASE
        ))
        for match in date_matches:
            date_text = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(1))
            start_pos = max(0, match.start() - 500)
            end_pos = min(len(text), match.end() + 500)
            before = text[start_pos:match.start()]
            after = text[match.end():end_pos]
            self._try_create_event(date_text, before, after, url)

    def _try_create_event(self, date_text: str, before: str, after: str, url: str):
        """Try to create an event from date text and context."""
        if not re.search(r"\b(?:ET|EST|EDT|CT|CST|CDT|PT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return

        title = self._extract_title(before)
        if not title:
            return
        if any(e.title == title for e in self.events):
            return

        full_context = before + date_text + after
        location_type = self.detect_location_type(full_context)
        if location_type == LocationType.UNKNOWN:
            location_type = LocationType.IN_PERSON
        location_details = self._extract_location(full_context)
        speakers = self._extract_speakers(full_context)

        self.events.append(self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost="",
            raw_date_text=date_text,
        ))

    def _extract_title(self, before_text: str) -> Optional[str]:
        """Extract event title from text before the date."""
        lines = [l.strip() for l in before_text.split("\n") if l.strip()]
        for line in reversed(lines):
            if re.match(r"^(?:Speaker|Date|Time|Location|Place|Cost|Register|When|Where|Posted)[:\s]",
                        line, re.IGNORECASE):
                continue
            if len(line) < 10:
                continue
            if re.match(r"^(?:Home|About|Events|Contact|Menu|Navigation|Archives|Categories|Search)",
                        line, re.IGNORECASE):
                continue
            return line[:300]
        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names."""
        speakers = []
        match = re.search(r"(?:Speaker|Presenter|Keynote)[s]?[:\s]+([^\n]+)", text, re.IGNORECASE)
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

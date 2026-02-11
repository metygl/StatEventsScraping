"""
Scraper for SFASA (San Francisco Bay Area ASA) Events.
Site: https://sites.google.com/view/sfasa-org/events
Google Sites page with event sub-pages.
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class SFASAScraper(BaseScraper):
    """Scraper for SFASA events."""

    SOURCE_NAME = "SFASA"
    BASE_URL = "https://sites.google.com/view/sfasa-org/events"

    async def scrape(self) -> List[Event]:
        """Scrape SFASA event listings from Google Sites."""
        await self.navigate_to_page()

        await self.wait_for_content("main, body", timeout=10000)

        # Collect event sub-page URLs from the events index
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} SFASA event sub-pages to process")

        # Visit each event sub-page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event sub-page URLs from the events index page."""
        event_data = []
        seen_urls = set()

        # Google Sites uses internal navigation links
        links = await self.get_all_elements("a[href*='/events/']")

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href:
                    continue

                # Skip links back to the events index itself
                if href.rstrip("/").endswith("/events"):
                    continue

                if href in seen_urls:
                    continue

                # Skip navigation/menu links
                if title and any(skip in title.lower() for skip in [
                    "home", "about", "contact", "menu", "back",
                    "officers", "newsletter", "membership",
                ]):
                    continue

                seen_urls.add(href)

                event_data.append({
                    "url": href,
                    "link_title": (title or "").strip(),
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape an individual event sub-page for details."""
        url = data["url"]

        await self.navigate_to_page(url)

        # Use inner_text on [role="main"] to skip navigation
        # (Google Sites renders all text_content on one line; inner_text preserves visual breaks)
        main_el = await self.page.query_selector('[role="main"]')
        body_text = await main_el.inner_text() if main_el else await self.page.inner_text("body")

        # Extract date
        date_text = self._extract_date(body_text)
        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        # Add PT timezone (San Francisco chapter)
        if not re.search(r"\b(?:PT|PST|PDT|ET|EST|EDT|CT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} PT"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Correct year if URL or title contains a different year than parsed date
        # (handles typos like "February 22nd, 2025" on a page titled "2026 Annual...")
        start_dt, end_dt = self._correct_year(start_dt, end_dt, url, body_text)

        # Extract title
        title = self._extract_title(body_text, data.get("link_title", ""))
        if not title:
            self.logger.debug(f"No title found for {url}")
            return None

        # Extract speakers
        speakers = self._extract_speakers(body_text)

        # Extract location
        location_type = self.detect_location_type(body_text)
        location_details = self._extract_location(body_text)
        if location_type == LocationType.UNKNOWN and location_details:
            location_type = LocationType.IN_PERSON

        # Extract cost
        cost = self._extract_cost(body_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost=cost,
            raw_date_text=date_text,
        )

    def _correct_year(self, start_dt, end_dt, url: str, body_text: str):
        """Correct year if URL or page title contains a different year.

        Handles cases where the page text has a typo (e.g. "2025" instead of
        "2026") but the URL slug or page heading contains the correct year.
        """
        # Look for a 4-digit year in the URL slug (e.g. /2026-annual-event)
        url_year_match = re.search(r"/(\d{4})-", url)
        if not url_year_match:
            return start_dt, end_dt

        url_year = int(url_year_match.group(1))
        if url_year == start_dt.year:
            return start_dt, end_dt

        # Also check first line of body text for the same year
        first_line = body_text.split("\n")[0] if body_text else ""
        if str(url_year) in first_line:
            # URL year matches title — correct the parsed date
            start_dt = start_dt.replace(year=url_year)
            if end_dt:
                end_dt = end_dt.replace(year=url_year)

        return start_dt, end_dt

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from page text.

        Handles formats like:
        - "Sunday, February 22nd, 2025, 1:30-8:00 PM"
        - "Time: 1:30 – 8:00 pm, Sunday, February 22nd, 2025"
        - "Date: February 22, 2026"
        """
        # Pattern 1: "Time: H:MM – H:MM pm, Day, Month DD, YYYY"
        # Time comes BEFORE date (Google Sites format)
        match = re.search(
            r"(?:Time)[:\s]+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))"
            r"[,\s]+(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)?,?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            time_part = match.group(1)
            date_part = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(2))
            return f"{date_part} {time_part}"

        # Pattern 2: "Day, Month DDth, YYYY, H:MM-H:MM PM"
        match = re.search(
            r"(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)))?",
            text, re.IGNORECASE
        )
        if match:
            result = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(1))
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result

        # Pattern 3: Labeled "Date:/When:" with date
        match = re.search(
            r"(?:Date|When)[:\s]+"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)))?",
            text, re.IGNORECASE
        )
        if match:
            result = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(1))
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result

        # Pattern 4: Standalone date with month name
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            result = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", match.group(1))
            # Look for time nearby (before or after)
            before_text = text[max(0, match.start() - 100):match.start()]
            after_text = text[match.end():match.end() + 100]
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))",
                before_text + " " + after_text, re.IGNORECASE
            )
            if time_match:
                result = f"{result} {time_match.group(1)}"
            return result

        return None

    def _extract_title(self, body_text: str, link_title: str) -> Optional[str]:
        """Extract event title from page text or link title."""
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]

        # Skip navigation/header lines, find first substantial content line
        skip_prefixes = (
            "Home", "About", "Contact", "Events", "SFASA", "Menu",
            "Navigation", "Skip to", "Search", "Embedded", "DOCS_timing",
        )
        skip_patterns = re.compile(
            r"^(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)"
            r"|^(?:Time|Date|Location|Parking|Food|Registration|Fees|Sponsor)[:\s]"
            r"|^(?:Get in touch)|google\.com|sfasa\.usa",
            re.IGNORECASE
        )

        for line in lines:
            if len(line) < 15 or len(line) > 300:
                continue
            if any(line.startswith(p) for p in skip_prefixes):
                continue
            if skip_patterns.search(line):
                continue
            # Skip lines that are mostly navigation items concatenated
            if line.count("  ") > 3:
                continue
            return line

        # Fall back to link title from the index page
        if link_title and len(link_title) > 5:
            return link_title

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        # Pattern: "Speaker: Dr. Jane Smith" or "Keynote Speaker: ..."
        match = re.search(
            r"(?:Speaker|Presenter|Keynote)[s]?[:\s]+"
            r"((?:Dr\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            name = match.group(1).strip()
            # Remove degree suffixes
            name = re.sub(r",?\s*(?:PhD|MD|MBA|MS|MPH|DrPH|PharmD)\.?", "", name).strip()
            if name and len(name) > 3:
                speakers.append(name)

        return speakers

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location details from text."""
        # Pattern: "Location: <address>" — capture up to next labeled field or sentence end
        match = re.search(
            r"(?:Location|Where|Venue|Place)[:\s]+(.+?)(?=(?:Parking|Food|Registration|Fees|Sponsor|Time|Date|Cost|Speaker)[:\s]|\n\n|$)",
            text, re.IGNORECASE | re.DOTALL
        )
        if match:
            location = match.group(1).strip()
            # Clean non-breaking spaces
            location = location.replace("\xa0", " ").strip()
            if len(location) > 3:
                return location[:150]

        return None

    def _extract_cost(self, text: str) -> str:
        """Extract cost information from text."""
        text_lower = text.lower()

        # Look for labeled cost/fees field
        match = re.search(
            r"(?:Cost|Price|Fees?)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            return self.normalize_cost(match.group(1))

        if "free" in text_lower:
            return "free"

        # Look for dollar amounts
        match = re.search(r"\$\d+(?:\s*[-–]\s*\$\d+)?", text)
        if match:
            return match.group(0)

        return ""

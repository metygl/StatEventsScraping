"""
Scraper for ASA Philadelphia Chapter Webinars.
Site: https://community.amstat.org/philadelphia/webinar
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASAPhiladelphiaScraper(BaseScraper):
    """Scraper for ASA Philadelphia Chapter webinars."""

    SOURCE_NAME = "ASA Philadelphia Chapter Webinar"
    BASE_URL = "https://community.amstat.org/philadelphia/webinar"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Philadelphia webinar listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .content, body", timeout=10000)

        # Collect event URLs from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} ASA Philadelphia events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect event URLs from the listing page."""
        event_data = []
        seen_urls = set()

        # ASA community sites use /philadelphia/webinar/ paths for individual webinars
        links = await self.get_all_elements(
            "a[href*='/philadelphia/webinar/']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 3:
                    continue

                if href in seen_urls:
                    continue

                # Skip navigation and non-person pages
                if any(skip in title.lower() for skip in [
                    "menu", "back", "home", "view all", "webinar archive",
                    "past webinar", "upcoming", "press enter"
                ]):
                    continue

                # Skip if title is just a year
                if re.match(r"^\d{4}$", title.strip()):
                    continue

                # Skip the listing page itself
                if href.rstrip("/") == self.BASE_URL.rstrip("/"):
                    continue

                seen_urls.add(href)

                event_data.append({
                    "url": href,
                    "link_title": title.strip(),
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual event page for details.

        ASA Philadelphia event pages have:
        - H1: Speaker name (e.g., "Yang Han, PhD")
        - Body: "February 5, 2026 Webinar"
        - Body: Event title text
        - Body: Speaker bio
        """
        url = data["url"]

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Extract date from body text (format: "February 5, 2026 Webinar")
        date_text = self._extract_date(body_text)
        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        # Add ET timezone (Philadelphia is Eastern Time)
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT|CST|CDT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract title from body (not H1, which is the speaker name)
        title = self._extract_title(body_text)
        if not title:
            self.logger.debug(f"No title found for {url}")
            return None

        # Extract speaker from H1 (format: "Yang Han, PhD")
        h1_text = await self.get_text("h1")
        speakers = self._extract_speaker_from_h1(h1_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost="free",
            raw_date_text=date_text,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from text."""
        # Pattern: "February 5, 2026 Webinar" - date followed by "Webinar"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})\s*(?:Webinar)?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)

            # Look for time pattern nearby
            time_match = re.search(
                r"(\d{1,2}:\d{2}\s*(?:am|pm)(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm))?)",
                text, re.IGNORECASE
            )
            time_str = time_match.group(1) if time_match else ""
            return f"{date_str} {time_str}".strip()

        return None

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract event title from body text.

        The title is a longer text line that appears after the date line,
        not the H1 (which is the speaker name).
        """
        lines = text.split("\n")

        # Find the date line first
        date_idx = None
        for i, line in enumerate(lines):
            line = line.strip()
            if re.search(r"\d{4}\s*Webinar", line, re.IGNORECASE):
                date_idx = i
                break

        if date_idx is not None:
            # Title is typically the next substantial line after the date
            for i in range(date_idx + 1, min(len(lines), date_idx + 10)):
                line = lines[i].strip()
                if len(line) > 20:
                    # Clean junk from title
                    line = re.sub(r"\s*\(Press Enter\)\s*", "", line)
                    line = re.sub(r"\s*Press Enter\s*$", "", line)
                    if len(line) > 20:
                        return line

        # Fallback: look for the longest line that looks like a title
        skip_patterns = [
            "webinar", "february", "january", "march", "april",
            "yang", "phd", "speaker", "department", "university",
            "research interests", "his main", "her main",
            "formtokenelement", "var ", "function ", "window.",
            "sys.webforms", "document.", "jquery", "script",
        ]
        for line in lines:
            line = line.strip()
            if (len(line) > 30 and len(line) < 300
                    and not any(s in line.lower() for s in skip_patterns)):
                line = re.sub(r"\s*\(Press Enter\)\s*", "", line)
                if len(line) > 30:
                    return line

        return None

    def _extract_speaker_from_h1(self, h1_text: str) -> List[str]:
        """Extract speaker name from H1 text (format: 'Yang Han, PhD')."""
        if not h1_text:
            return []

        name = h1_text.strip()
        # Remove degree suffixes
        name = re.sub(r",?\s*(?:PhD|MD|MBA|MS|MPH|DrPH|BSc|MSc|DSc)\.?\s*$", "", name).strip()

        if name and len(name) > 3 and any(c.isupper() for c in name):
            return [name]

        return []

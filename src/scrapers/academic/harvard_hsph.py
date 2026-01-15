"""
Scraper for Harvard T.H. Chan School of Public Health Epidemiology Seminars.
Site: https://hsph.harvard.edu/department/epidemiology/seminar-series/
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class HarvardHSPHScraper(BaseScraper):
    """Scraper for Harvard HSPH Epidemiology Seminar Series."""

    SOURCE_NAME = "Harvard Department of Epidemiology Webinar"
    BASE_URL = "https://hsph.harvard.edu/department/epidemiology/seminar-series/"

    async def scrape(self) -> List[Event]:
        """Scrape Harvard HSPH seminar listings."""
        await self.navigate_to_page()

        # Wait for content
        await self.wait_for_content("article, .event, main", timeout=10000)

        # Collect all event URLs first (list + detail pattern)
        event_urls = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_urls)} event URLs to scrape")

        # Visit each event page to get accurate date
        for url, title in event_urls:
            try:
                event = await self._scrape_event_page(url, title)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to scrape event page {url}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[tuple]:
        """Collect event URLs and titles from listing page."""
        seen_urls = set()
        event_urls = []

        # Look for event links
        event_links = await self.get_all_elements(
            'a[href*="/epidemiology/events/"], a[href*="/events/"]'
        )

        for link in event_links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title:
                    continue

                # Skip if already seen or too short
                if href in seen_urls or len(title) < 15:
                    continue

                # Skip navigation links
                if any(skip in title.lower() for skip in ["menu", "navigation", "back", "home", "view all"]):
                    continue

                seen_urls.add(href)
                # Clean the title - remove extra whitespace and truncate at common junk
                clean_title = self._clean_title(title)
                event_urls.append((href, clean_title))

            except Exception as e:
                self.logger.debug(f"Failed to extract link: {e}")

        return event_urls

    async def _scrape_event_page(self, url: str, title: str) -> Optional[Event]:
        """Scrape individual event page for accurate date/time."""
        await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await self.page.wait_for_timeout(1000)

        # Get page content
        page_text = await self.page.text_content("body") or ""

        # Extract date and time from the event page
        date_info = self._extract_date_time(page_text)

        if not date_info:
            self.logger.debug(f"No date found on page: {url}")
            return None

        date_text, time_text = date_info

        # Parse date
        try:
            full_date = f"{date_text} {time_text} ET"  # Harvard is in Eastern Time
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text} {time_text}': {e}")
            return None

        # Extract speaker from page
        speakers = self._extract_speakers(page_text)

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost="free",
            raw_date_text=f"{date_text} {time_text}",
        )

    def _extract_date_time(self, text: str) -> Optional[tuple]:
        """Extract date and time from context text."""
        # Harvard pages show event date in two formats:
        # 1. "January 28" (without year) near top of page - this is the main event date
        # 2. "February 11, 2026 @ 1:00 pm – 1:50 pm" for related events (ignore these)

        # Look for time pattern first: "1:00 pm" followed by "1:50 pm"
        time_pattern = r"(\d{1,2}:\d{2}\s*(?:am|pm))\s*(?:[–-]|to)\s*(\d{1,2}:\d{2}\s*(?:am|pm))"
        time_match = re.search(time_pattern, text, re.IGNORECASE)

        # Strategy: Look for date WITHOUT year (the main event date)
        # This date appears on its own line, not as "Month DD, YYYY @ time" format
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Match "January 28" or "February 11" standalone (not followed by year)
            if re.match(
                r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}$",
                line,
                re.IGNORECASE
            ):
                date_text = f"{line}, 2026"
                if time_match:
                    time_text = f"{time_match.group(1)}-{time_match.group(2)}"
                else:
                    time_text = ""
                return date_text, time_text

        # Fallback: look for date WITH year but only in first 100 lines
        # (avoid the "related events" section at bottom)
        for line in lines[:100]:
            # Skip lines that look like related events (contain "@")
            if "@" in line:
                continue
            date_with_year = re.search(
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
                line,
                re.IGNORECASE
            )
            if date_with_year:
                date_text = date_with_year.group(1)
                if time_match:
                    time_text = f"{time_match.group(1)}-{time_match.group(2)}"
                else:
                    time_text = ""
                return date_text, time_text

        return None

    def _clean_title(self, title: str) -> str:
        """Clean up title text."""
        # Remove tabs, newlines, and multiple spaces
        title = re.sub(r'[\t\n\r]+', ' ', title)
        title = " ".join(title.split())

        # Truncate at common junk patterns (institutions, navigation, etc.)
        junk_patterns = [
            r"\s*,?\s*the National Institute.*$",
            r"\s*,?\s*National Institute.*$",
            r"\s*,?\s*Information\s*$",
            r"\s*,?\s*Harvard faculty.*$",
            r"\s*,?\s*Rishi Desai\s*$",  # Remove duplicate speaker in title
        ]
        for pattern in junk_patterns:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)

        return title.strip()

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from context text."""
        speakers = []

        # Organization/junk names to exclude
        exclude_names = {
            "the national institute", "national institute", "information",
            "sentinel innovation", "fda sentinel", "innovation center",
            "harvard faculty", "harvard t",
        }

        # Look for "Dr. FirstName LastName" pattern
        dr_pattern = r"Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
        matches = re.findall(dr_pattern, text)
        for match in matches:
            if match.lower() not in exclude_names:
                speakers.append(f"Dr. {match}")

        # Dedupe speakers by base name (e.g., "Dr. Rishi Desai" and "Rishi Desai" -> keep "Dr." version)
        unique_speakers = []
        seen_names = set()
        for speaker in speakers:
            # Extract the base name without title
            base_name = re.sub(r"^Dr\.\s*", "", speaker).lower()
            if base_name not in seen_names:
                seen_names.add(base_name)
                unique_speakers.append(speaker)

        return unique_speakers[:2]  # Limit to 2 speakers

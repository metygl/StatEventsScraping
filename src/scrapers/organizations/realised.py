"""
Scraper for RealiseD Webinar Series.
Site: https://realised-ihi.eu/webinars/
"""

import re
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class RealisedScraper(BaseScraper):
    """Scraper for RealiseD (IHI) webinar series."""

    SOURCE_NAME = "RealiseD Webinar Series"
    BASE_URL = "https://realised-ihi.eu/webinars/"

    # Known non-webinar paths to skip
    SKIP_PATHS = [
        "/about-us/", "/the-pilars/", "/partners/", "/publications/",
        "/contact", "/author/", "/category/", "/tag/", "/page/",
        "/wp-content/", "/wp-admin/", "/privacy-policy/", "/cookies/",
        "/scientific-advisory-board/", "/news/", "/webinars/",
    ]

    async def scrape(self) -> List[Event]:
        """Scrape RealiseD webinar listings."""
        await self.navigate_to_page()

        await self.wait_for_content("main, .post, body", timeout=10000)

        # Collect webinar links from listing page
        event_data = await self._collect_event_urls()
        self.logger.info(f"Found {len(event_data)} RealiseD events to process")

        # Visit each event page for details
        for data in event_data[:15]:
            try:
                event = await self._scrape_event_page(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse RealiseD event {data.get('url')}: {e}")

        return self.events

    async def _collect_event_urls(self) -> List[Dict]:
        """Collect webinar URLs from the listing page.

        RealiseD uses image-wrapped links (link around an <img>), so link text
        may be empty. We collect all realised-ihi.eu links and filter by path.
        """
        event_data = []
        seen_urls = set()

        # Get ALL links on the page
        links = await self.get_all_elements("a[href*='realised-ihi.eu']")

        for link in links:
            try:
                href = await self.get_href(link)
                if not href or href in seen_urls:
                    continue

                # Skip known non-webinar paths
                if any(skip in href for skip in self.SKIP_PATHS):
                    continue

                # Must be on realised-ihi.eu domain
                if "realised-ihi.eu" not in href:
                    continue

                # Skip the listing page itself
                if href.rstrip("/") == self.BASE_URL.rstrip("/"):
                    continue

                # Get link text (may be empty for image-wrapped links)
                text = await self.get_element_text(link) or ""

                # If text is empty, try to get alt text from child image
                if not text.strip():
                    img = await link.query_selector("img")
                    if img:
                        text = await self.get_attribute(img, "alt") or ""

                # If still no text, try to get title from nearby heading
                if not text.strip():
                    # Look for heading text near this link
                    parent = await link.evaluate_handle("el => el.parentElement")
                    if parent:
                        heading = await parent.evaluate(
                            "el => { const h = el.querySelector('h2, h3, h4, strong, b, p'); return h ? h.textContent : ''; }"
                        )
                        text = heading or ""

                seen_urls.add(href)
                event_data.append({"title": text.strip(), "url": href})

            except Exception as e:
                self.logger.debug(f"Failed to collect event URL: {e}")

        return event_data

    async def _scrape_event_page(self, data: Dict) -> Optional[Event]:
        """Scrape individual webinar page for details."""
        url = data["url"]
        title = data.get("title", "")

        await self.navigate_to_page(url)

        body_text = await self.page.text_content("body") or ""

        # Get title from h1 or entry-title on detail page
        h1_title = await self.get_text("h1, .entry-title, .post-title")
        if h1_title and len(h1_title) > 10:
            title = h1_title.strip()

        if not title or len(title) < 10:
            self.logger.debug(f"No title found for {url}")
            return None

        # Extract date - first try countdown timer data attribute
        date_text = await self._extract_date_from_countdown()
        # Fall back to body text parsing
        if not date_text:
            date_text = self._extract_date(body_text)
        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        # Add CET timezone if none detected
        if not re.search(r"\b(?:CET|CEST|ET|EST|EDT|PST|PDT|GMT|UTC)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} CET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract speakers
        speakers = self._extract_speakers(body_text)

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

    async def _extract_date_from_countdown(self) -> Optional[str]:
        """Extract date from Avada countdown widget data-timer attribute.

        Format: data-timer="2026-02-03-17-00-00" (CET timezone)
        """
        countdown = await self.page.query_selector("[data-timer]")
        if countdown:
            timer_val = await self.get_attribute(countdown, "data-timer")
            if timer_val:
                # Parse "2026-02-03-17-00-00" format
                match = re.match(
                    r"(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})", timer_val
                )
                if match:
                    year, month, day, hour, minute, second = match.groups()
                    # Convert 24-hour to 12-hour for DateParser
                    h = int(hour)
                    ampm = "am" if h < 12 else "pm"
                    if h > 12:
                        h -= 12
                    elif h == 0:
                        h = 12
                    return f"{year}-{month}-{day} {h}:{minute}{ampm} CET"
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from text, handling European formats."""
        # Pattern: "February 3, 2026" or "3 February 2026" with optional time
        # American format
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:[,\s]+(?:at\s+)?(\d{1,2}:\d{2}\s*(?:am|pm|[AP]M)?"
            r"(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm|[AP]M)?)?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str}".strip()

        # European format: "3 February 2026"
        match = re.search(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{4})"
            r"(?:[,\s]+(?:at\s+)?(\d{1,2}[:.]\d{2}\s*(?:am|pm|[AP]M|CET|CEST)?"
            r"(?:\s*[-–]\s*\d{1,2}[:.]\d{2}\s*(?:am|pm|[AP]M|CET|CEST)?)?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            # Replace period-based time separator with colon
            time_str = re.sub(r"(\d{1,2})\.(\d{2})", r"\1:\2", time_str)
            return f"{date_str} {time_str}".strip()

        # Pattern with 24-hour time: "17:00-18:30 CET" combined with a date
        date_match = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        time_match = re.search(
            r"(\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2})\s*(CET|CEST|GMT|UTC)?",
            text
        )
        if date_match and time_match:
            tz = time_match.group(2) or "CET"
            return f"{date_match.group(1)} {time_match.group(1)} {tz}"
        if date_match:
            return date_match.group(1)

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []

        # Pattern: "Speaker(s):" followed by names
        match = re.search(
            r"(?:Speaker|Presenter|Paneli)[s]?[:\s]+(.+?)(?:\n|$)",
            text, re.IGNORECASE
        )
        if match:
            speaker_text = match.group(1).strip()
            if len(speaker_text) < 200:
                return self.parse_speakers(speaker_text)

        # Pattern: "Presented by Name" or "Chaired by Name"
        match = re.search(
            r"(?:Presented by|Chaired by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

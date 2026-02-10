"""
Scraper for George Mason University Statistics Seminar Series.
Site: https://statistics.gmu.edu/about/events
Uses Trumba calendar widget (JavaScript-rendered).
"""

import re
import asyncio
from typing import List, Optional, Dict

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class GMUScraper(BaseScraper):
    """Scraper for GMU R. Clifton Bailey Statistics Seminar Series."""

    SOURCE_NAME = "George Mason University R. Clifton Bailey Statistics Seminar Series"
    BASE_URL = "https://statistics.gmu.edu/about/events"

    async def scrape(self) -> List[Event]:
        """Scrape GMU seminar listings from Trumba calendar widget."""
        await self.navigate_to_page()

        # Trumba JS widget needs time to render
        await asyncio.sleep(6)

        # Wait for Trumba content
        found = await self.wait_for_content(
            ".twSimpleTableEventRow, .trumba-events, .twEventTitle, "
            "a[href*='trumbaEmbed'], iframe[src*='trumba']",
            timeout=15000,
        )

        if not found:
            self.logger.warning("Trumba calendar widget did not render, trying iframe approach")
            # Check for Trumba iframe
            iframe = await self.page.query_selector("iframe[src*='trumba']")
            if iframe:
                src = await iframe.get_attribute("src")
                if src:
                    await self.navigate_to_page(src)
                    await asyncio.sleep(5)

        # Extract events from rendered Trumba content
        event_data = await self._collect_events()
        self.logger.info(f"Found {len(event_data)} GMU events to process")

        # Process event detail pages
        for data in event_data[:10]:
            try:
                event = await self._scrape_event_detail(data)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.warning(f"Failed to parse GMU event {data.get('url')}: {e}")

        return self.events

    async def _collect_events(self) -> List[Dict]:
        """Collect events from the Trumba calendar widget."""
        event_data = []
        seen_urls = set()

        # Try Trumba-specific selectors
        links = await self.get_all_elements(
            ".twSimpleTableEventRow a, .twEventTitle a, "
            "a[href*='eventid'], a[href*='trumbaEmbed'], "
            "a[href*='statistics.gmu.edu/about/events']"
        )

        for link in links:
            try:
                href = await self.get_href(link)
                title = await self.get_element_text(link)

                if not href or not title or len(title) < 10:
                    continue

                if href in seen_urls:
                    continue

                # Skip navigation links
                if any(skip in title.lower() for skip in [
                    "menu", "back", "home", "view all", "subscribe",
                    "add to calendar", "more info"
                ]):
                    continue

                seen_urls.add(href)

                # Try to get date from parent row
                parent = await link.evaluate_handle(
                    "el => el.closest('.twSimpleTableEventRow, tr, .event-row')"
                )
                date_text = None
                if parent:
                    parent_content = await parent.evaluate("el => el?.textContent || ''")
                    date_text = self._extract_date(parent_content)

                event_data.append({
                    "title": title.strip(),
                    "url": href,
                    "date_text": date_text,
                })

            except Exception as e:
                self.logger.debug(f"Failed to collect event: {e}")

        # Fallback: if no Trumba links found, try generic approach
        if not event_data:
            event_data = await self._collect_events_generic()

        return event_data

    async def _collect_events_generic(self) -> List[Dict]:
        """Fallback: collect events from generic page content."""
        event_data = []
        body_text = await self.page.text_content("body") or ""

        # Look for event-like patterns in the page text
        # Pattern: title followed by date
        blocks = re.split(r"\n{2,}", body_text)
        for block in blocks:
            block = block.strip()
            if len(block) < 20:
                continue

            date_match = re.search(
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},?\s+\d{4})",
                block, re.IGNORECASE
            )
            if date_match:
                # Find any link in this area
                links = await self.get_all_elements("a")
                for link in links:
                    link_text = await self.get_element_text(link) or ""
                    if any(word in link_text for word in block.split()[:3]):
                        href = await self.get_href(link)
                        if href:
                            event_data.append({
                                "title": block.split("\n")[0].strip()[:200],
                                "url": href,
                                "date_text": date_match.group(1),
                            })
                            break

        return event_data

    async def _scrape_event_detail(self, data: Dict) -> Optional[Event]:
        """Scrape event detail page (may also be Trumba-rendered)."""
        url = data["url"]
        title = data["title"]
        date_text = data.get("date_text")

        await self.navigate_to_page(url)
        await asyncio.sleep(3)  # Wait for Trumba to render detail view

        body_text = await self.page.text_content("body") or ""

        # Try to get title from detail page
        h1_title = await self.get_text(
            "h1, .twEventTitle, .trumba-event-title, .event-title"
        )
        if h1_title and len(h1_title) > 10:
            title = h1_title.strip()

        # Extract date from detail page if not from listing
        if not date_text:
            date_text = self._extract_date(body_text)

        if not date_text:
            self.logger.debug(f"No date found for {url}")
            return None

        # Add ET timezone if none detected (GMU is in Eastern Time)
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT|CST|CDT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception as e:
            self.logger.debug(f"Could not parse date '{date_text}': {e}")
            return None

        # Extract speaker
        speakers = self._extract_speakers(title, body_text)

        # Clean title (remove speaker parenthetical if extracted)
        clean_title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()

        return self.create_event(
            title=clean_title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.HYBRID,
            cost="free",
            raw_date_text=date_text,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date and time from text."""
        # Pattern: "February 6, 2026 11:00 AM - 12:00 PM ET"
        match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:[,\s]+(\d{1,2}:\d{2}\s*(?:am|pm)(?:\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm))?))?",
            text, re.IGNORECASE
        )
        if match:
            date_str = match.group(1)
            time_str = match.group(2) or ""
            return f"{date_str} {time_str}".strip()

        # Pattern: "Thu, Feb 6, 2026"
        match = re.search(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,?\s+"
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        # Trumba format: "February 6, 2026"
        match = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)

        return None

    def _extract_speakers(self, title: str, body_text: str) -> List[str]:
        """Extract speaker names from title or body."""
        speakers = []

        # Check title for parenthetical speaker: "Title (Speaker Name)"
        match = re.search(r"\(([^)]+)\)\s*$", title)
        if match:
            potential = match.group(1)
            if len(potential) < 80 and any(c.isupper() for c in potential):
                return self.parse_speakers(potential)

        # Check body for "Speaker:" patterns
        match = re.search(
            r"(?:Speaker|Presenter|Presented by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            body_text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

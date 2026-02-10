"""
Scraper for ENAR (Eastern North American Region of IBS) Webinars.
Site: https://www.enar.org/education/
Static ColdFusion-generated HTML with simple structure.
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ENARScraper(BaseScraper):
    """Scraper for ENAR webinars and education events."""

    SOURCE_NAME = "ENAR"
    BASE_URL = "https://www.enar.org/education/"

    async def scrape(self) -> List[Event]:
        """Scrape ENAR education/webinar page."""
        await self.navigate_to_page()

        await self.wait_for_content("main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""

        # ENAR lists webinars with h3 titles, bold dates, and speaker info
        await self._extract_events(body_text)

        return self.events

    async def _extract_events(self, body_text: str):
        """Extract events from the page text.

        ENAR structure:
        <h3>Event Title</h3>
        <p><strong>Wednesday, February 18, 2026</strong><br>3-5 pm</p>
        <p><strong>Speakers:</strong><br><strong>Name</strong>, Affiliation</p>
        <p>Description...</p>
        <p><a href="registration-url">Register</a></p>
        """
        # Get all h3 elements as event boundaries
        headings = await self.get_all_elements("h3")

        for heading in headings:
            try:
                title = await self.get_element_text(heading)
                if not title or len(title) < 10:
                    continue

                # Skip navigation headings
                if any(skip in title.lower() for skip in [
                    "menu", "navigation", "footer", "sidebar", "past webinar"
                ]):
                    continue

                # Get all following sibling elements until next h3
                event_text = await heading.evaluate("""
                    el => {
                        let text = '';
                        let sibling = el.nextElementSibling;
                        while (sibling && sibling.tagName !== 'H3') {
                            text += sibling.textContent + '\\n';
                            sibling = sibling.nextElementSibling;
                        }
                        return text;
                    }
                """)

                if not event_text:
                    continue

                # Get registration link
                reg_url = await heading.evaluate("""
                    el => {
                        let sibling = el.nextElementSibling;
                        while (sibling && sibling.tagName !== 'H3') {
                            const link = sibling.querySelector('a[href*="portal.enar.org"], a[href*="Register"], a[href*="register"]');
                            if (link) return link.href;
                            sibling = sibling.nextElementSibling;
                        }
                        return null;
                    }
                """)

                event = self._parse_event(title, event_text, reg_url or self.BASE_URL)
                if event and not any(e.title == event.title for e in self.events):
                    self.events.append(event)

            except Exception as e:
                self.logger.debug(f"Failed to parse ENAR event: {e}")

    def _parse_event(self, title: str, text: str, url: str) -> Optional[Event]:
        """Parse event details from title and surrounding text."""
        # Extract date: "Wednesday, February 18, 2026"
        date_text = self._extract_date(text)
        if not date_text:
            return None

        # Extract time: "3-5 pm" or "3:00-5:00 pm"
        time_text = self._extract_time(text)
        full_date = f"{date_text} {time_text}".strip()

        # Add ET timezone
        if not re.search(r"\b(?:ET|EST|EDT)\b", full_date, re.IGNORECASE):
            full_date = f"{full_date} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(full_date)
        except Exception:
            return None

        # Extract speakers
        speakers = self._extract_speakers(text)

        # Extract cost
        cost = self._extract_cost(text)

        return self.create_event(
            title=title.strip(),
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=LocationType.VIRTUAL,
            cost=cost,
            raw_date_text=full_date,
        )

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Pattern: "Wednesday, February 18, 2026" or "February 18, 2026"
        match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s+\d{4})",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from text."""
        # Pattern: "3-5 pm" or "3:00-5:00 pm" or "3:00 PM - 5:00 PM"
        match = re.search(
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm))",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return ""

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names."""
        speakers = []

        # Pattern: "Speakers:" followed by bold names
        match = re.search(
            r"Speaker[s]?[:\s]+(.+?)(?:Description|Abstract|Register|\n\n)",
            text, re.IGNORECASE | re.DOTALL
        )
        if match:
            speaker_block = match.group(1)
            # Extract names (capitalized words before comma+affiliation)
            name_pattern = re.finditer(
                r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)",
                speaker_block
            )
            for m in name_pattern:
                name = m.group(1).strip()
                if len(name) > 5 and name not in speakers:
                    speakers.append(name)

        return speakers[:5]  # Limit to 5 speakers

    def _extract_cost(self, text: str) -> str:
        """Extract cost from text."""
        if "free" in text.lower():
            return "free"
        match = re.search(r"\$\s*\d+", text)
        if match:
            return match.group(0)
        return "free"

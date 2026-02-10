"""
Scraper for ASA Calendar of Events (Dateline).
Site: https://ww2.amstat.org/dateline/index.cfm?fuseaction=main
ColdFusion application requiring click-through navigation and form POST.
Events displayed inline on results page (no detail pages).
"""

import re
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASACalendarScraper(BaseScraper):
    """Scraper for ASA national calendar of events (Dateline)."""

    SOURCE_NAME = "ASA Calendar"
    BASE_URL = "https://ww2.amstat.org/dateline/index.cfm?fuseaction=main"

    async def scrape(self) -> List[Event]:
        """Scrape ASA Calendar events via click-through navigation."""
        # Step 1: Navigate to main page
        await self.navigate_to_page(self.BASE_URL)
        await self.wait_for_content("body", timeout=10000)

        # Step 2: Click "Search Events" link to get to search form
        try:
            search_link = await self.page.query_selector(
                "a[href*='dateline_search']"
            )
            if search_link:
                await search_link.click()
                await self.page.wait_for_load_state("networkidle", timeout=15000)
            else:
                return self.events
        except Exception as e:
            self.logger.warning(f"Could not navigate to search: {e}")
            return self.events

        # Step 3: Submit the search form with defaults (returns all events)
        try:
            submit = await self.page.query_selector(
                "input[name='btnSubmit'], input[type='submit'], "
                "input[value*='Search']"
            )
            if submit:
                await submit.click()
                await self.page.wait_for_load_state("networkidle", timeout=15000)
            else:
                return self.events
        except Exception as e:
            self.logger.warning(f"Could not submit search form: {e}")
            return self.events

        # Step 4: Parse events from results page
        await self._parse_results_page()

        return self.events

    async def _parse_results_page(self):
        """Parse events from the search results page.

        Events are in a table. Each event block starts with a <td> containing
        style="padding-top:25px" and an <h3> title. Following rows contain
        dates, location, type, description, and external links.
        """
        # Find current year context from month headers
        year_map = {}
        headers = await self.get_all_elements("h3")
        for header in headers:
            text = await self.get_element_text(header) or ""
            # Month headers like "March 2026"
            match = re.match(
                r"(January|February|March|April|May|June|July|August|September|"
                r"October|November|December)\s+(\d{4})", text.strip()
            )
            if match:
                year_map[match.group(1)] = match.group(2)

        # Find event title cells (padding-top:25px marks event blocks)
        title_cells = await self.page.query_selector_all("td[style*='padding-top']")

        for cell in title_cells:
            try:
                # Get title from h3
                h3 = await cell.query_selector("h3")
                if not h3:
                    continue

                title = await self.get_element_text(h3)
                if not title or len(title) < 5:
                    continue

                title = title.strip()

                # Get the containing row, then siblings for date/location/link
                row = await cell.evaluate_handle("el => el.closest('tr')")
                block_text = await row.evaluate("""
                    el => {
                        let text = el.textContent || '';
                        let sibling = el.nextElementSibling;
                        // Collect next 6 rows (date, location, type, description, link, contact)
                        for (let i = 0; i < 6 && sibling; i++) {
                            text += '\\n' + (sibling.textContent || '');
                            sibling = sibling.nextElementSibling;
                        }
                        return text;
                    }
                """)

                # Extract dates: "Monday March 02 - Tuesday March 03"
                date_text = self._extract_event_dates(block_text, year_map)
                if not date_text:
                    continue

                try:
                    start_dt, end_dt = DateParser.parse_datetime_range(date_text)
                except Exception:
                    continue

                # Extract external URL
                url = self.BASE_URL
                try:
                    ext_url = await row.evaluate("""
                        el => {
                            let sibling = el;
                            for (let i = 0; i < 6 && sibling; i++) {
                                sibling = sibling.nextElementSibling;
                                if (sibling) {
                                    const link = sibling.querySelector('a[href^="http"]');
                                    if (link) return link.href;
                                }
                            }
                            return null;
                        }
                    """)
                    if ext_url:
                        url = ext_url
                except Exception:
                    pass

                # Extract location
                location = self._extract_location(block_text)
                location_type = self.detect_location_type(block_text)
                if location_type == LocationType.UNKNOWN:
                    location_type = LocationType.IN_PERSON

                if any(e.title == title for e in self.events):
                    continue

                self.events.append(self.create_event(
                    title=title,
                    url=url,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    speakers=[],
                    location_type=location_type,
                    location_details=location,
                    cost="",
                    raw_date_text=date_text,
                ))

            except Exception as e:
                self.logger.debug(f"Failed to parse ASA Calendar event: {e}")

    def _extract_event_dates(self, text: str, year_map: dict) -> Optional[str]:
        """Extract and normalize dates from event block text.

        Input format: "Monday March 02 - Tuesday March 03" (year from headers)
        Output format: "March 02-03, 2026"
        """
        # Pattern: "DayOfWeek Month DD - DayOfWeek Month DD"
        match = re.search(
            r"Event Dates?:\s*"
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*"
            r"(January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+(\d{1,2})\s*"
            r"(?:-\s*"
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*"
            r"(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)?\s*(\d{1,2}))?",
            text, re.IGNORECASE
        )

        if not match:
            return None

        month = match.group(1)
        start_day = match.group(2)
        end_day = match.group(3)

        year = year_map.get(month, "2026")

        if end_day and end_day != start_day:
            return f"{month} {start_day}-{end_day}, {year}"
        else:
            return f"{month} {start_day}, {year}"

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from event block text."""
        city_match = re.search(r"City:\s*(\S[^\n]*?)(?:\s{2,}|$)", text)
        state_match = re.search(r"State:\s*(\S[^\n]*?)(?:\s{2,}|$)", text)

        parts = []
        if city_match:
            city = city_match.group(1).strip()
            if city:
                parts.append(city)
        if state_match:
            state = state_match.group(1).strip()
            if state and state != "International":
                parts.append(state)

        return ", ".join(parts) if parts else None

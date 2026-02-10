"""
Scraper for ICSA (International Chinese Statistical Association) Events.
Site: https://www.icsa.org/category/events/
WordPress with REST API available.
"""

import re
import json
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ICSAScraper(BaseScraper):
    """Scraper for ICSA events using WordPress REST API."""

    SOURCE_NAME = "ICSA"
    BASE_URL = "https://www.icsa.org/category/events/"

    # WordPress REST API endpoint for events category (ID 4)
    API_URL = "https://www.icsa.org/wp-json/wp/v2/posts?categories=4&per_page=20&orderby=date&order=desc"

    async def scrape(self) -> List[Event]:
        """Scrape ICSA events via WordPress REST API."""
        # Try API first, fall back to page scraping
        try:
            await self._scrape_via_api()
        except Exception as e:
            self.logger.warning(f"API scraping failed, falling back to page: {e}")
            await self._scrape_via_page()

        return self.events

    async def _scrape_via_api(self):
        """Fetch events from WordPress REST API."""
        await self.page.goto(self.API_URL, wait_until="domcontentloaded", timeout=30000)

        # Get the JSON response
        body_text = await self.page.text_content("body") or ""

        try:
            posts = json.loads(body_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, the API might return HTML wrapper
            pre_elem = await self.page.query_selector("pre")
            if pre_elem:
                body_text = await self.get_element_text(pre_elem) or ""
                posts = json.loads(body_text)
            else:
                raise ValueError("Could not parse API response as JSON")

        if not isinstance(posts, list):
            raise ValueError("API response is not a list")

        self.logger.info(f"Found {len(posts)} ICSA posts from API")

        for post in posts:
            try:
                event = self._parse_api_post(post)
                if event:
                    self.events.append(event)
            except Exception as e:
                self.logger.debug(f"Failed to parse ICSA post: {e}")

    def _parse_api_post(self, post: dict) -> Optional[Event]:
        """Parse a WordPress API post into an Event."""
        title = post.get("title", {}).get("rendered", "").strip()
        url = post.get("link", "")
        content = post.get("content", {}).get("rendered", "")
        excerpt = post.get("excerpt", {}).get("rendered", "")

        if not title or not url:
            return None

        # Clean HTML from title
        title = re.sub(r"<[^>]+>", "", title).strip()

        # Extract date from content (event date, not post date)
        combined_text = re.sub(r"<[^>]+>", " ", content).strip()
        date_text = self._extract_event_date(combined_text)

        if not date_text:
            # Fall back to post publication date
            post_date = post.get("date", "")
            if post_date:
                date_text = post_date[:10]  # YYYY-MM-DD

        if not date_text:
            return None

        # Add ET timezone if not present
        if not re.search(r"\b(?:ET|EST|EDT|PST|PDT|CT)\b", date_text, re.IGNORECASE):
            date_text = f"{date_text} ET"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(date_text)
        except Exception:
            return None

        # Extract speakers from content
        speakers = self._extract_speakers(combined_text)

        # Detect location type
        location_type = self.detect_location_type(combined_text)
        if location_type == LocationType.UNKNOWN:
            location_type = LocationType.VIRTUAL

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            cost="free",
            raw_date_text=date_text,
        )

    def _extract_event_date(self, text: str) -> Optional[str]:
        """Extract event date from post content."""
        # Pattern: "Date: Feb 20th 3:00-4:00PM EST" or "Date Feb 20, 2026"
        match = re.search(
            r"Date[:\s]+(.+?)(?:\n|$|Speaker|Host|Register)",
            text, re.IGNORECASE
        )
        if match:
            date_part = match.group(1).strip()
            # Clean up ordinal suffixes
            date_part = re.sub(r"(\d+)(?:st|nd|rd|th)", r"\1", date_part)
            if len(date_part) > 5:
                return date_part

        # Pattern: "February 20, 2026" or "Feb 20, 2026"
        match = re.search(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*"
            r"\s+\d{1,2},?\s+\d{4})"
            r"(?:\s*,?\s*(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)\s*[-–]\s*\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)))?",
            text, re.IGNORECASE
        )
        if match:
            result = match.group(1)
            if match.group(2):
                result = f"{result} {match.group(2)}"
            return result

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from content."""
        speakers = []

        # Pattern: "Speaker: Name" or "Speaker(s): Name"
        match = re.search(
            r"Speaker[s]?[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)",
            text
        )
        if match:
            speakers.append(match.group(1).strip())

        return speakers

    async def _scrape_via_page(self):
        """Fallback: scrape events from the HTML page."""
        await self.navigate_to_page()
        await self.wait_for_content("main, .content, body", timeout=10000)

        # Look for event post links
        links = await self.get_all_elements("article a, .entry-title a, h2 a")

        seen_urls = set()
        for link in links:
            try:
                href = await self.get_href(link)
                text = await self.get_element_text(link)

                if not href or not text or len(text) < 10 or href in seen_urls:
                    continue

                if "icsa.org" not in href:
                    continue

                seen_urls.add(href)

                # Visit each event page
                await self.navigate_to_page(href)
                body_text = await self.page.text_content("body") or ""

                date_text = self._extract_event_date(body_text)
                if not date_text:
                    continue

                if not re.search(r"\b(?:ET|EST|EDT)\b", date_text, re.IGNORECASE):
                    date_text = f"{date_text} ET"

                start_dt, end_dt = DateParser.parse_datetime_range(date_text)
                speakers = self._extract_speakers(body_text)

                self.events.append(self.create_event(
                    title=text.strip(),
                    url=href,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    speakers=speakers,
                    location_type=LocationType.VIRTUAL,
                    cost="free",
                    raw_date_text=date_text,
                ))

            except Exception as e:
                self.logger.debug(f"Failed to parse ICSA page event: {e}")

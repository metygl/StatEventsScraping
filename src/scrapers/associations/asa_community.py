"""
Generic scraper for ASA chapter pages on community.amstat.org (Higher Logic platform).

All chapters share the same React SPA platform with announcement blocks containing
labeled fields (Date:, Speaker:, Place:, Cost:, etc.). Each subclass just sets
SOURCE_NAME, BASE_URL, and TIMEZONE.
"""

import re
import asyncio
from typing import List, Optional

from src.scrapers.base import BaseScraper
from src.models.event import Event, LocationType
from src.parsers.date_parser import DateParser


class ASACommunityGenericScraper(BaseScraper):
    """Generic scraper for ASA chapters on the Higher Logic community platform."""

    # Subclasses override these
    TIMEZONE = "ET"
    DEFAULT_LOCATION_TYPE = LocationType.VIRTUAL

    async def scrape(self) -> List[Event]:
        """Scrape event listings from a Higher Logic community homepage."""
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        await self.wait_for_content("#MPContentArea, main, body", timeout=10000)

        body_text = await self.page.text_content("body") or ""
        self._parse_events(body_text)
        return self.events

    def _parse_events(self, body_text: str):
        """Parse events from homepage announcement blocks."""
        # Strategy 1: labeled Date:/When: fields
        date_matches = list(re.finditer(
            r"(?:Date|When)[:\s]+"
            r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:\s*[-–]\s*\d{1,2})?,?\s+\d{4}"
            r"[^\n]*)",
            body_text, re.IGNORECASE
        ))

        # Strategy 2: day-name anchored dates (no label)
        if not date_matches:
            date_matches = list(re.finditer(
                r"((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
                r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},?\s+\d{4}"
                r"[^\n]*)",
                body_text, re.IGNORECASE
            ))

        # Strategy 3: standalone Month DD, YYYY
        if not date_matches:
            date_matches = list(re.finditer(
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},?\s+\d{4})",
                body_text, re.IGNORECASE
            ))

        for match in date_matches:
            date_text = match.group(1).strip()
            start_pos = max(0, match.start() - 1000)
            end_pos = min(len(body_text), match.end() + 500)
            before_text = body_text[start_pos:match.start()]
            after_text = body_text[match.end():end_pos]

            event = self._parse_event_block(date_text, before_text, after_text)
            if event and not any(e.title == event.title for e in self.events):
                self.events.append(event)

    def _parse_event_block(self, date_text: str, before_text: str, after_text: str) -> Optional[Event]:
        """Parse a single event from context around a date match."""
        normalized_date = self._normalize_time_words(date_text)

        # Add chapter timezone if not present
        if not re.search(r"\b(?:ET|EST|EDT|PT|PST|PDT|CT|CST|CDT|MT|MST|MDT|AKST|AKDT|AKT)\b",
                         normalized_date, re.IGNORECASE):
            normalized_date = f"{normalized_date} {self.TIMEZONE}"

        try:
            start_dt, end_dt = DateParser.parse_datetime_range(normalized_date)
        except Exception:
            return None

        title = self._extract_title(before_text)
        if not title:
            return None

        full_context = before_text + date_text + after_text
        speakers = self._extract_speakers(full_context)
        location_type = self.detect_location_type(full_context)
        location_details = self._extract_location(full_context)
        if location_type == LocationType.UNKNOWN:
            location_type = self.DEFAULT_LOCATION_TYPE
        cost = self._extract_cost(full_context)
        url = self._extract_url(full_context) or self.BASE_URL

        return self.create_event(
            title=title,
            url=url,
            start_datetime=start_dt,
            end_datetime=end_dt,
            speakers=speakers,
            location_type=location_type,
            location_details=location_details,
            cost=cost,
            raw_date_text=normalized_date,
        )

    def _normalize_time_words(self, text: str) -> str:
        """Convert Noon/Midnight to numeric times."""
        text = re.sub(
            r"\bNoon\s*[-–]\s*(\d{1,2}:\d{2})\b(?!\s*[ap]m)",
            r"12:00pm - \1pm",
            text, flags=re.IGNORECASE
        )
        text = re.sub(r"\bNoon\b", "12:00pm", text, flags=re.IGNORECASE)
        text = re.sub(r"\bMidnight\b", "12:00am", text, flags=re.IGNORECASE)
        return text

    def _extract_title(self, before_text: str) -> Optional[str]:
        """Extract event title from text before the date."""
        # Try explicit "Title:" label
        match = re.search(r"Title[:\s]+(.+)", before_text, re.IGNORECASE)
        if match:
            title = match.group(1).strip().replace("\xa0", " ").strip()
            if len(title) > 10:
                return title[:300]

        # Reverse-scan lines before the date
        lines = [l.strip() for l in before_text.split("\n") if l.strip()]
        for line in reversed(lines):
            if re.match(r"^(?:Speaker|Date|Time|Location|Place|Cost|Register|When|Where|Topic|Title)[:\s]",
                        line, re.IGNORECASE):
                continue
            if len(line) < 15:
                continue
            if re.match(r"^(?:Home|About|Events|Contact|Chapter|News|Upcoming|Menu|Navigation)",
                        line, re.IGNORECASE):
                continue
            return line[:300]

        return None

    def _extract_speakers(self, text: str) -> List[str]:
        """Extract speaker names from text."""
        speakers = []
        match = re.search(
            r"(?:Speaker|Presenter)[s]?[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            speaker_text = match.group(1).strip()
            speaker_text = re.sub(r"\s*\([^)]+\)", "", speaker_text)
            speaker_text = re.sub(r",?\s*(?:PhD|MD|MBA|JD|MS|MSc|MPH|DrPH|PharmD|CEO|CSO)\.?", "", speaker_text)
            names = re.split(r"\s*[;,&]\s*(?:and\s+)?|\s+and\s+", speaker_text)
            for name in names:
                name = name.strip()
                if name and len(name) > 3 and any(c.isupper() for c in name):
                    speakers.append(name)
        return speakers

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location details from text."""
        match = re.search(
            r"(?:Place|Location|Where|Venue)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            location = match.group(1).strip()
            if len(location) > 3:
                return location[:150]
        return None

    def _extract_cost(self, text: str) -> str:
        """Extract cost information from text."""
        match = re.search(
            r"(?:Cost|Price|Fee)[:\s]+([^\n]+)",
            text, re.IGNORECASE
        )
        if match:
            return self.normalize_cost(match.group(1))
        if "free" in text.lower():
            return "free"
        return ""

    def _extract_url(self, text: str) -> Optional[str]:
        """Extract registration or event URL from text."""
        match = re.search(r"(https?://[^\s]*zoom\.us/[^\s]+)", text)
        if match:
            return match.group(1)
        match = re.search(r"(https?://[^\s]+(?:register|registration|signup|rsvp)[^\s]*)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"(https?://(?:www\.)?eventbrite\.com/[^\s]+)", text)
        if match:
            return match.group(1)
        return None


# ---------------------------------------------------------------------------
# Lightweight subclasses (one per chapter)
# ---------------------------------------------------------------------------

class ASANYCMetroScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA NYC Metro"
    BASE_URL = "https://community.amstat.org/nycchapter/home"
    TIMEZONE = "ET"


class ASAChicagoScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Chicago"
    BASE_URL = "https://community.amstat.org/chicagochapter/home"
    TIMEZONE = "CT"


class ASANorthCarolinaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA North Carolina"
    BASE_URL = "https://community.amstat.org/northcarolina/home"
    TIMEZONE = "ET"


class ASAFloridaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Florida"
    BASE_URL = "https://community.amstat.org/floridachapter/home"
    TIMEZONE = "ET"


class ASAHoustonScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Houston Area"
    BASE_URL = "https://community.amstat.org/Houston/home"
    TIMEZONE = "CT"


class ASAColoradoWyomingScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Colorado-Wyoming"
    BASE_URL = "https://community.amstat.org/cwc/home"
    TIMEZONE = "MT"


class ASAWisconsinScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Wisconsin"
    BASE_URL = "https://community.amstat.org/wisconsinchapter/home"
    TIMEZONE = "CT"


class ASAAlabamaMississippiScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Alabama-Mississippi"
    BASE_URL = "https://community.amstat.org/alabamachapter/home"
    TIMEZONE = "CT"


class ASAKansasWesternMOScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Kansas/Western Missouri"
    BASE_URL = "https://community.amstat.org/KWMChapter/home"
    TIMEZONE = "CT"


class ASARochesterScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Rochester"
    BASE_URL = "https://community.amstat.org/Rochester/home"
    TIMEZONE = "ET"


class ASAIowaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Iowa"
    BASE_URL = "https://community.amstat.org/iowachapter/home"
    TIMEZONE = "CT"


class ASAMidMissouriScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Mid-Missouri"
    BASE_URL = "https://community.amstat.org/midmissouri/home"
    TIMEZONE = "CT"


class ASAStLouisScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA St. Louis"
    BASE_URL = "https://community.amstat.org/stlouischapter/home"
    TIMEZONE = "CT"


class ASAConnecticutScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Connecticut"
    BASE_URL = "https://community.amstat.org/connecticutchapter/home"
    TIMEZONE = "ET"


class ASAKentuckyScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Kentucky"
    BASE_URL = "https://community.amstat.org/kentucky/home"
    TIMEZONE = "ET"


class ASAAustinScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Austin"
    BASE_URL = "https://community.amstat.org/austinchapter/home"
    TIMEZONE = "CT"


class ASASanAntonioScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA San Antonio"
    BASE_URL = "https://community.amstat.org/sanantoniochapter/home"
    TIMEZONE = "CT"


class ASAWesternTennesseeScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Western Tennessee"
    BASE_URL = "https://community.amstat.org/westerntennesseechapter/home"
    TIMEZONE = "CT"


class ASAOregonScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Oregon"
    BASE_URL = "https://community.amstat.org/oregon/home"
    TIMEZONE = "PT"


class ASAUtahScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Utah"
    BASE_URL = "https://community.amstat.org/utahchapter/home"
    TIMEZONE = "MT"


class ASASouthFloridaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA South Florida"
    BASE_URL = "https://community.amstat.org/southflorida/home"
    TIMEZONE = "ET"


class ASANebraskaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Nebraska"
    BASE_URL = "https://community.amstat.org/amstatnebraska/home"
    TIMEZONE = "CT"


class ASAPrincetonTrentonScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Princeton-Trenton"
    BASE_URL = "https://community.amstat.org/princetontrenton/home"
    TIMEZONE = "ET"


class ASAAlbanyScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Albany"
    BASE_URL = "https://community.amstat.org/ac/home"
    TIMEZONE = "ET"


class ASAAlaskaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Alaska"
    BASE_URL = "https://community.amstat.org/AlaskaChapter/home"
    TIMEZONE = "AKST"


class ASACentralArkansasScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Central Arkansas"
    BASE_URL = "https://community.amstat.org/crc/home"
    TIMEZONE = "CT"


class ASAMidTennesseeScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Mid-Tennessee"
    BASE_URL = "https://community.amstat.org/midtennesseechapter/home"
    TIMEZONE = "CT"


class ASASouthernCaliforniaScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Southern California"
    BASE_URL = "https://community.amstat.org/SCASA/home"
    TIMEZONE = "PT"


class ASAOrangeCountyLBScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Orange County/Long Beach"
    BASE_URL = "https://community.amstat.org/OCLB/home"
    TIMEZONE = "PT"


class ASADelawareScraper(ASACommunityGenericScraper):
    SOURCE_NAME = "ASA Delaware"
    BASE_URL = "https://community.amstat.org/delawarechapter/home"
    TIMEZONE = "ET"

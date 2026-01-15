# Statistics Events Scraper - Implementation Plan

## Overview

A Python + Playwright system to scrape 31 statistics/biostatistics event sources, filter by date range, and generate a static HTML page for local viewing. Supports both manual and automatic (cron) execution.

## Project Structure

```
StatEventsScraping/
├── config/
│   ├── settings.yaml         # Date range, browser, output settings
│   └── sources.yaml          # Site definitions (31 sources)
├── src/
│   ├── main.py               # Entry point and orchestration
│   ├── core/
│   │   ├── browser.py        # Playwright browser management
│   │   └── exceptions.py     # Custom exceptions
│   ├── models/
│   │   └── event.py          # Event dataclass with PST normalization
│   ├── scrapers/
│   │   ├── base.py           # Abstract base scraper class
│   │   ├── academic/         # Harvard, UCSF, McGill, Duke, etc.
│   │   ├── associations/     # ASA chapters, ICSA, PSI, ENAR, etc.
│   │   ├── organizations/    # NISS, DahShu, Instats, ISPOR, etc.
│   │   ├── government/       # FDA
│   │   └── tech/             # Posit, R Conferences
│   ├── parsers/
│   │   └── date_parser.py    # Date extraction and PST normalization
│   └── output/
│       ├── html_generator.py # Static HTML generation
│       └── templates/
│           └── events.html.j2
├── output/                   # Generated HTML/text files
├── logs/                     # Rotating log files
├── tests/                    # Unit tests (pytest)
│   ├── conftest.py
│   ├── test_date_parser.py
│   └── test_event.py
├── scripts/
│   ├── run_scraper.sh        # Shell script for cron
│   └── serve_local.py        # Local HTTP server
├── requirements.txt
└── pyproject.toml
```

## Implementation Phases

### Phase 1: Core Infrastructure ✅
1. Create project structure - directories and `__init__.py` files
2. Set up config files - `settings.yaml` and `sources.yaml` with all 31 sources
3. Implement Event model (`src/models/event.py`)
   - Dataclass with title, url, source, datetime, speakers, location_type, cost
   - PST timezone normalization
   - Output formatting methods (to_display_string)
4. Implement DateParser (`src/parsers/date_parser.py`)
   - Handle multiple date formats (Jan 14 2026, 2026-01-14, 01/14/2026, etc.)
   - Time range extraction (12:00-1:00pm)
   - Timezone detection and PST conversion
5. Implement BrowserManager (`src/core/browser.py`)
   - Playwright async context manager
   - Page factory with viewport/user-agent settings

### Phase 2: Base Scraper Framework ✅
6. Implement BaseScraper (`src/scrapers/base.py`)
   - Abstract scrape() method
   - navigate_to_page() with retry logic
   - Helper methods: wait_for_content, get_text, get_all_elements
7. Implement scraper registry (`src/scrapers/__init__.py`)
   - Dynamic class lookup by module path
8. Implement retry decorator (`src/utils/retry.py`)
   - Exponential backoff for transient failures

### Phase 3: Site-Specific Scrapers (Initial 8, then expand) ✅

**Initial implementation (8 scrapers)** - chosen for variety of site structures:
1. **Instats** - Bubble.io SPA, heavy JS rendering
2. **FDA** - Government site, clean structure
3. **NISS** - Drupal CMS, standard selectors
4. **DahShu** - Wild Apricot calendar
5. **Harvard HSPH** - Academic institution
6. **ASA Webinars** - Professional association
7. **PSI** - European organization
8. **Posit** - Tech company events

**Future additions (23 remaining)** - add iteratively using base patterns:
- Academic: UCSF, McGill, Duke-Margolis, Cambridge MRC, GMU, Dana Farber, CTML Berkeley
- Associations: ASA chapters (5), ICSA, ENAR, IBS, RSS, NESTAT, PBSS, Washington Stat
- Organizations: ISPOR, Basel Biometric
- Tech: R Conferences

### Phase 4: Output Generation ✅
9. Implement HTMLGenerator (`src/output/html_generator.py`)
   - Sort events by date
   - Group by day for display
   - Render Jinja2 template
10. Create HTML template (`src/output/templates/events.html.j2`)
    - Clean, readable card-based layout
    - Date/time, location badges, cost indicators
11. Plain text output - Matching the example format

### Phase 5: Main Orchestration ✅
12. Implement main.py
    - Load config and sources
    - Initialize browser manager
    - Run scrapers concurrently (semaphore for rate limiting)
    - Filter by date range
    - Generate output files
    - Error tracking and logging

### Phase 6: Scheduling & Serving ✅
13. Create `run_scraper.sh` - Cron-compatible shell script
14. Create `serve_local.py` - Simple HTTP server on localhost:8000
15. Set up logging - Rotating file logs

### Phase 7: Testing ✅ (NEW)
16. Unit tests for DateParser (21 tests)
17. Unit tests for Event model (18 tests)
18. Test fixtures in conftest.py

## Key Technical Decisions

| Aspect | Decision |
|--------|----------|
| Async | Full async/await with asyncio for concurrent scraping |
| Concurrency | Semaphore-controlled (default 5 concurrent) |
| Browser | Playwright Chromium, headless by default |
| Timezone | All dates normalized to PST |
| Error handling | Site-level isolation, continue on failures |
| Output | HTML (styled) + optional plain text |
| Date range | Configurable in settings.yaml |

## Date Range Configuration

```yaml
date_range:
  # Option 1: Rolling window (days from today)
  mode: "rolling"
  days_ahead: 14

  # Option 2: Fixed dates
  # mode: "fixed"
  # start_date: "2026-01-14"
  # end_date: "2026-01-30"
```

## Dependencies

- playwright (JS rendering)
- pyyaml (config)
- jinja2 (templating)
- pytz (timezone)
- python-dateutil (date parsing)
- pytest (testing)
- pytest-asyncio (async test support)

## Verification Plan

1. **Unit tests** for DateParser with various formats ✅
2. **Unit tests** for Event model ✅
3. **Manual test** individual scrapers with --debug flag (non-headless)
4. **Integration test** full run with 2-3 sources enabled
5. **Visual check** generated HTML in browser
6. **Cron test** scheduled execution with log output

---

## Known Issues & Scraper Notes

### Working Scrapers

| Scraper | Events | Notes |
|---------|--------|-------|
| Instats | 20 | ✅ Bubble.io SPA - visits pages for accurate times |
| FDA | 11 (6 in range) | ✅ JSON API + page visits for times |
| NISS | 10 | Drupal site, list+detail pattern |
| DahShu | 1 | Wild Apricot, deduplicates by event ID |
| Harvard HSPH | 3 | ✅ List+detail, clean title/speaker extraction |
| ASA Webinars | 5 | Stable, standard HTML structure |
| PSI | 10 | ✅ List+detail with GMT→PST time conversion |
| Posit | 5 (3 in range) | ✅ Fixed card selectors for new site design |

**Latest Run:** 65 total events, 27 within date range

### Recently Fixed Scrapers

#### FDA (Government Site) ✅ FIXED
- **Previous Issue:** Timeouts, intermittent 404 errors
- **Root Cause:** HTML scraping was unreliable due to rate limiting
- **Solution:**
  - Discovered FDA provides JSON API at `/datatables-json/events-meetings.json`
  - Rewrote scraper to fetch JSON directly
  - JSON contains all event data: title, dates, URLs, event types
- **Result:** 6 events within date range (11 total)

### Recently Fixed Scrapers

#### Instats (Bubble.io SPA) ✅ FIXED
- **Previous Issue:** 0 events found
- **Root Cause:** Heavy JavaScript SPA built on Bubble.io framework
- **Solution:**
  - Increased wait time to 8 seconds for JS rendering
  - Used `.clickable-element.bubble-element.Group` selector for cards
  - Parse card text with regex to extract title (before "Livestream:") and date (after)
  - Bubble.io doesn't use URLs, so all events link to main listing page
- **Result:** 43 events found

#### PSI (European Organization) ✅ FIXED
- **Previous Issue:** Shows "Read more" instead of actual event titles
- **Root Cause:** Title selector fell back to generic `<a>` tags
- **Solution:**
  - Prioritize heading elements (`h2, h3, h4`) for title text
  - Filter out "Read more", "More info", "Learn more" text
  - Only use link text if length > 10 characters
- **Result:** Proper titles extracted

#### Harvard HSPH ✅ FIXED
- **Previous Issue:** All events show same date (Jan 27)
- **Root Cause:** Date extraction used regex on ancestor containing multiple events
- **Solution:**
  - Refactored to list+detail pattern
  - Visit each event page individually for accurate date
- **Result:** Correct per-event dates

#### Posit ✅ FIXED (2026-01-14 Night)
- **Previous Issue:** 0 events found
- **Root Cause:** Site redesign changed card element structure
- **Solution:**
  - Updated selectors to use `.posit-card` containers
  - Extract title from `.card-title`, date from `.card-date-day`/`.card-date-month`
- **Result:** 5 events found (3 within date range)

### Time Extraction Fixes (2026-01-14 Night)

Multiple scrapers were showing 12:00am instead of actual event times:

#### Instats Time Fix
- **Issue:** All events defaulting to 12:00am
- **Solution:** Visit individual event pages to extract "12:00 pm to 1:00 pm" format
- **Result:** Accurate times like "12:00-1:00pm PST"

#### PSI Time Fix
- **Issue:** 24-hour GMT times (16:00-17:00) not parsing
- **Solution:**
  - Visit each event page for accurate times
  - Extract "16:00-17:00 GMT" and convert to PST
  - Fixed DateParser regex to make am/pm optional
- **Result:** Correct times (8:00-9:00am PST)

#### FDA Time Fix
- **Issue:** Defaulting to 9am instead of actual meeting times
- **Solution:** Visit event pages to extract "12:00 p.m. - 1:00 p.m. ET"
- **Result:** Accurate times converted from ET to PST

### Text Cleanup Fixes (2026-01-14 Night)

#### PSI Speaker Cleanup
- **Issue:** Navigation menu text appearing in speaker lists
- **Solution:** Rewrote `_extract_speakers()` to only capture "Presenters:" line

#### Instats Speaker Cleanup
- **Issue:** "(American Statistical Association)" appearing as speaker name
- **Solution:** Added organization name blocklist filter

#### Harvard Title Cleanup
- **Issue:** Fragmented titles with "the National Institute, Information" junk
- **Solution:** Added `_clean_title()` method with pattern-based cleanup

### HTML Template Redesign (2026-01-14 Night)

Polished editorial design with:
- **Typography:** Syne (headings), DM Sans (body), JetBrains Mono (badges)
- **Colors:** Deep ink blues, coral accents, teal/violet badges
- **Features:** Date badges, animated hover effects, staggered animations
- **Responsive:** Mobile-optimized, print-friendly

---

## Source Sites (31 Total)

### Academic (7)
- Harvard HSPH Epidemiology Seminar Series ✅
- UCSF Department of Epidemiology & Biostatistics
- McGill Biostatistics Seminars
- Duke-Margolis Events
- Cambridge MRC Events
- GMU Statistics Seminars
- Dana Farber Data Science Events

### Professional Associations (14)
- ASA Webinars ✅
- ASA Calendar of Events
- ASA Boston Chapter
- ASA Georgia Chapter
- ASA New Jersey Chapter
- ASA San Diego Chapter
- ASA Philadelphia Chapter
- ICSA Events
- PSI Events ✅ (6 events)
- ENAR Webinar Series
- IBS Meetings Calendar
- RSS Events Calendar
- New England Statistical Society
- PBSS SF Bay

### Organizations (7)
- NISS-Merck Calendar ✅
- DahShu Webinars ✅
- Instats Seminars ✅ (43 events)
- ISPOR Events
- CTML Berkeley
- Basel Biometric Society
- Washington Statistical Society

### Government (1)
- FDA Events ✅ (JSON API)

### Tech (2)
- Posit Events ✅
- R Conferences

---

## Scraper Design Patterns

### Pattern 1: List + Detail Pages (Recommended)
Best for sites where listing page has limited info:
```python
async def scrape(self):
    await self.navigate_to_page()
    urls = await self._collect_event_urls()  # Get all URLs first
    for url in urls:
        event = await self._scrape_detail_page(url)
        if event:
            self.events.append(event)
```
**Used by:** NISS, DahShu, Harvard HSPH

### Pattern 2: Single Page Extraction
Best for sites with all info on listing page:
```python
async def scrape(self):
    await self.navigate_to_page()
    items = await self.get_all_elements(".event-item")
    for item in items:
        # Extract all data from item element
        event = await self._parse_item(item)
```
**Used by:** ASA Webinars, PSI

### Pattern 3: Bubble.io SPA with Card Extraction
For Bubble.io JavaScript-heavy sites that don't use traditional URLs:
```python
async def scrape(self):
    await self.navigate_to_page()
    await asyncio.sleep(8)  # Bubble.io needs longer to render

    # Find cards using Bubble.io class patterns
    cards = await self.get_all_elements('.clickable-element.bubble-element.Group')

    for card in cards:
        card_text = await self.get_element_text(card)
        # Parse title and date from card text using regex
        title = extract_title(card_text)  # Text before "Livestream:"
        date = extract_date(card_text)    # Text after "Livestream:"
```
**Used by:** Instats ✅

**Key insights for Bubble.io:**
- Content renders 5-8 seconds after initial page load
- Uses dynamic class names but consistent patterns (`.bubble-element`, `.clickable-element`)
- No traditional URLs - navigation via JavaScript click handlers
- Data embedded in card text, extract with regex

---

## Future Improvements

### High Priority
- [x] ~~Fix PSI title extraction~~ ✅
- [x] ~~Fix Harvard per-event date extraction~~ ✅
- [x] ~~Investigate Instats API/data source~~ ✅ (solved with card text extraction)
- [x] ~~Fix FDA scraper~~ ✅ (rewrote to use JSON API)
- [x] ~~Fix Posit scraper~~ ✅ (updated card selectors)
- [x] ~~Fix time extraction for all scrapers~~ ✅ (visit individual pages)
- [x] ~~Clean up extraneous text in output~~ ✅ (blocklists, pattern cleanup)
- [x] ~~Redesign HTML template~~ ✅ (polished editorial design)

### Medium Priority
- [ ] Add event deduplication across sources
- [ ] Add caching layer
- [ ] Add integration tests for scrapers
- [ ] Add pyproject.toml

### Low Priority
- [ ] Add RSS feed output
- [ ] Add email/Slack notifications
- [ ] Add web dashboard for monitoring
- [ ] Implement remaining 23 scrapers

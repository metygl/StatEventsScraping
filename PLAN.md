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
├── vercel.json              # Vercel deployment config
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

**Second wave (7 scrapers, 5 working):**
9. **UCSF** - Drupal list+detail, static HTML ✅
10. **ASA Philadelphia** - List+detail, speaker from H1 ✅
11. **StatsUpAI** (new source) - Zoom link extraction ✅
12. **RealiseD** (new source) - WordPress/Avada countdown timer ✅
13. **PBSS** - React SPA, domcontentloaded ✅
14. **McGill** - Disabled (bot protection) ❌
15. **GMU** - 25Live JSON API, bypasses Trumba widget ✅

**Third wave (18 scrapers, 17 working):**
16. **CTML Berkeley** - Drupal/OpenBerkeley, date prefix in titles ✅
17. **Duke-Margolis** - Drupal Views, list+detail ✅
18. **Dana Farber** - WordPress/TEC, domcontentloaded ✅
19. **Cambridge MRC** - Disabled (DNS resolution failure) ❌
20. **ASA Calendar** - ColdFusion form POST, click-through, inline results ✅
21. **ASA Boston** - Higher Logic/React SPA, rich text parsing ✅
22. **ASA Georgia** - Squarespace, h3 + sibling text ✅
23. **ASA New Jersey** - Basic static HTML ✅
24. **ASA San Diego** - Higher Logic/React SPA ✅
25. **ICSA** - WordPress REST API ✅
26. **NESTAT** - Static HTML, multi-page ✅
27. **ENAR** - Static ColdFusion ✅
28. **IBS** - React SPA (HigherLogic), intermittent ✅
29. **RSS** - ASP.NET WebForms, list+detail, GMT ✅
30. **Washington Stat** - Static HTML ✅
31. **ISPOR** - Sitefinity CMS, conference pages ✅
32. **Basel Biometric** - Quarto/GitHub Pages, Swiss dates ✅
33. **R Conferences** - Static HTML conference list ✅

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

### Phase 8: Deployment ✅ (NEW)
19. GitHub repository - https://github.com/metygl/StatEventsScraping
20. Vercel auto-deployment - serves `output/events.html` at root URL
21. Vercel config (`vercel.json`) - URL rewrite for clean paths

### Phase 9: Export Page ✅ (NEW)
22. Export HTML template (`src/output/templates/export.html.j2`)
    - Checkbox selection for individual events
    - Select All / Select None buttons
    - Source filter dropdown
    - Sticky controls bar and export footer
23. HTMLGenerator `generate_export_page()` method
    - JSON serialization for client-side JavaScript
    - Pre-formatted fields matching ExampleOutput.txt format
24. Copy to Clipboard functionality (navigator.clipboard API)
25. Download as .txt functionality (Blob + createObjectURL)
26. Navigation between events.html and export.html
27. Vercel `/export` route for clean URL
28. Unit tests for export functionality (15 tests)

### Phase 10: Expanded Scrapers ✅
29. 7 new scrapers implemented (5 working, 2 disabled due to technical limitations)
    - **UCSF** - Drupal list+detail, static HTML
    - **ASA Philadelphia** - List+detail, speaker from H1, title from body text
    - **StatsUpAI** (new source) - Single-page zoom link extraction
    - **RealiseD** (new source) - WordPress/Avada with countdown timer dates
    - **PBSS** - React SPA with domcontentloaded, keyword-boundary parsing
    - **McGill** - Disabled (Imperva/Distil bot protection)
    - **GMU** - Disabled (Trumba JS calendar widget doesn't render headless)
30. Updated `src/scrapers/__init__.py` with 2 new registry entries
31. Updated `config/sources.yaml` - 3 enabled, 2 new sources added, 2 disabled

### Phase 11: Complete All Scrapers ✅ (NEW)
32. 18 remaining scrapers implemented (17 enabled, 1 disabled)
    - **Academic**: CTML Berkeley, Duke-Margolis, Dana Farber, Cambridge MRC (disabled - DNS)
    - **Associations**: ASA Calendar, ASA Boston, ASA Georgia, ASA NJ, ASA SD, ICSA, NESTAT, ENAR, IBS, RSS, Washington Stat
    - **Organizations**: ISPOR, Basel Biometric
    - **Tech**: R Conferences
33. All 33 source scrapers now implemented
34. Updated `config/sources.yaml` - 30 sources enabled, 3 disabled
35. Full run: 172 total events, 47 within date range

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
| DahShu | 3 | Wild Apricot, deduplicates by event ID |
| Harvard HSPH | 3 | ✅ List+detail, clean title/speaker extraction |
| ASA Webinars | 5 | Stable, standard HTML structure |
| PSI | 10 | ✅ List+detail with GMT→PST time conversion |
| Posit | 5 (3 in range) | ✅ Fixed card selectors for new site design |
| UCSF | 1+ | ✅ Drupal list+detail, static HTML |
| ASA Philadelphia | 15 | ✅ List+detail, speaker from H1, title from body |
| StatsUpAI | 3 | ✅ Single-page zoom link extraction |
| RealiseD | 4 | ✅ WordPress/Avada, countdown timer dates (CET) |
| PBSS | 15 (3 in range) | ✅ React SPA, domcontentloaded, keyword-boundary parsing |
| GMU | 14 (3 in range) | ✅ 25Live JSON API, bypasses Trumba JS widget |

### Disabled Scrapers (Technical Limitations)

| Scraper | Issue |
|---------|-------|
| McGill | Imperva/Distil bot protection blocks headless browsers |
| Cambridge MRC | DNS resolution failure - site unreachable |

### Recently Fixed Scrapers

#### GMU Statistics ✅ FIXED
- **Previous Issue:** Trumba JS calendar widget doesn't render in headless Playwright
- **Solution:** Discovered 25Live/CollegeNET JSON API at `https://25livepub.collegenet.com/calendars/cec-statistics.json`
- **Result:** 14 events found (3 within date range), output matches expected format

**Latest Run:** 31 enabled sources, 2 disabled

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

## Source Sites (33 Total, 31 Enabled)

### Academic (8)
- Harvard HSPH Epidemiology Seminar Series ✅
- UCSF Department of Epidemiology & Biostatistics ✅
- McGill Biostatistics Seminars ❌ (bot protection)
- Duke-Margolis Events ✅
- Cambridge MRC Events ❌ (DNS failure)
- GMU Statistics Seminars ✅ (25Live JSON API)
- Dana Farber Data Science Events ✅
- CTML Berkeley ✅

### Professional Associations (14)
- ASA Webinars ✅
- ASA Calendar of Events ✅
- ASA Boston Chapter ✅
- ASA Georgia Chapter ✅
- ASA New Jersey Chapter ✅
- ASA San Diego Chapter ✅
- ASA Philadelphia Chapter ✅
- ICSA Events ✅
- PSI Events ✅
- ENAR Webinar Series ✅
- IBS Meetings Calendar ✅
- RSS Events Calendar ✅
- New England Statistical Society ✅
- PBSS SF Bay ✅

### Organizations (8)
- NISS-Merck Calendar ✅
- DahShu Webinars ✅
- Instats Seminars ✅
- ISPOR Events ✅
- Basel Biometric Society ✅
- Washington Statistical Society ✅
- Stats-Up-AI-Alliance ✅
- RealiseD Webinar Series ✅

### Government (1)
- FDA Events ✅ (JSON API)

### Tech (2)
- Posit Events ✅
- R Conferences ✅

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
**Used by:** NISS, DahShu, Harvard HSPH, UCSF, ASA Philadelphia, RealiseD

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
**Used by:** ASA Webinars, PSI, StatsUpAI

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

### Pattern 4: React SPA with domcontentloaded
For React SPAs that never reach `networkidle`:
```python
async def _goto(self, url):
    await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

async def scrape(self):
    await self._goto(self.BASE_URL)
    await asyncio.sleep(8)  # React needs time to render
    links = await self.get_all_elements("a[href*='eventDetails']")
    for link in links:
        # Visit each detail page
        event = await self._scrape_event_page(data)
```
**Used by:** PBSS ✅

**Key insights for React SPAs:**
- Must use `domcontentloaded` not `networkidle` (React SPAs never reach idle)
- Text renders on single line without newlines - use keyword boundaries (Speakers:, Event Description) instead of `\n`
- asyncio.sleep(5-8) needed for content to render

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
- [x] ~~Implement remaining 16 scrapers~~ ✅ All 33 scrapers implemented

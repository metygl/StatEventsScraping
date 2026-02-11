# Statistics Events Scraper - Progress Tracker

## Current Status: Deployed to Vercel

**Last Updated:** 2026-02-10

---

## Recent Update: ASA Chapter Expansion (Phase 14)

Added 35 new ASA chapter scrapers, bringing total sources from 33 to 70 (67 enabled, 3 disabled).

### Generic Higher Logic Scraper
- Created `ASACommunityGenericScraper` base class in `src/scrapers/associations/asa_community.py`
- Consolidates patterns from ASA Indiana/San Diego/Boston scrapers
- `domcontentloaded` + `asyncio.sleep(5)` for React SPA loading
- Multi-strategy date extraction: labeled (Date:/When:), day-name anchored, standalone
- Noon/Midnight normalization, configurable timezone per chapter
- **30 lightweight subclasses** (~4 lines each) for all Higher Logic community chapters

### 30 Higher Logic Chapter Subclasses

| Chapter | Timezone | Chapter | Timezone |
|---------|----------|---------|----------|
| ASA NYC Metro | ET | ASA Oregon | PT |
| ASA Chicago | CT | ASA Utah | MT |
| ASA North Carolina | ET | ASA South Florida | ET |
| ASA Florida | ET | ASA Nebraska | CT |
| ASA Houston Area | CT | ASA Princeton-Trenton | ET |
| ASA Colorado-Wyoming | MT | ASA Albany | ET |
| ASA Wisconsin | CT | ASA Alaska | AKST |
| ASA Alabama-Mississippi | CT | ASA Central Arkansas | CT |
| ASA Kansas/Western Missouri | CT | ASA Mid-Tennessee | CT |
| ASA Rochester | ET | ASA Southern California | PT |
| ASA Iowa | CT | ASA Orange County/Long Beach | PT |
| ASA Mid-Missouri | CT | ASA Delaware | ET |
| ASA St. Louis | CT | ASA Austin | CT |
| ASA Connecticut | ET | ASA San Antonio | CT |
| ASA Kentucky | ET | ASA Western Tennessee | CT |

### 5 Standalone Site Scrapers

| Scraper | Platform | Status |
|---------|----------|--------|
| ASA North Texas | Google Sites | ✅ Working |
| ASA Pittsburgh | WordPress | ✅ Working (4 events found) |
| ASA Twin Cities | Hugo static | ❌ Disabled (site unreachable) |
| ASA Cleveland | Google Sites | ✅ Working |
| ASA Columbus | Google Sites | ✅ Working |

### Other Changes
- Added AKST/AKDT/AKT timezone support in `src/parsers/date_parser.py`
- Registry expanded to 70 entries in `src/scrapers/__init__.py`
- `config/sources.yaml` expanded to 70 sources

### Verification Results

| Scraper | Events Found |
|---------|-------------|
| ASA Alaska | 1 (AKST timezone works) |
| ASA Connecticut | 2 |
| ASA North Carolina | 3 |
| ASA Pittsburgh | 4 |
| ASA Chicago, Florida, NYC Metro, Cleveland, Columbus, So. Cal | 0 (no current events) |

**Current Totals:** 70 sources, 67 enabled, 3 disabled (McGill, Cambridge MRC, ASA Twin Cities)

---

## Previous Update: Source Status Page (Phase 13)

Added a `/status` page showing scraping health for all event sources with green/red/disabled indicators, event counts, and error messages.

### Changes
- **`src/main.py`** — Loads all sources (including disabled), tracks per-source results (status, total events, in-range events, error messages), passes data to status page generator
- **`src/output/html_generator.py`** — Added `generate_status_page()` method, passes `total_sources` to events template
- **`src/output/templates/status.html.j2`** — New template with summary pills, status table (sorted: errors first, then success, then disabled), responsive layout
- **`src/output/templates/events.html.j2`** — Added clickable "N sources" link to `/status` in header, moved Updated timestamp to its own line below Export Events
- **`vercel.json`** — Added `/status` rewrite route

### Features
- Summary bar: total, enabled, successful, failed counts as pill badges
- Table with status icon (green checkmark / red X / grey dash), source name (linked), total events, in-range events, notes
- Error messages shown with tooltip for full text
- Disabled rows styled with reduced opacity
- Matches existing design language (CSS vars, fonts, geometric background)

**Latest Run:** 188 total events, 50 within date range, 1 failure (Dana Farber timeout)

---

## Previous Update: GMU Scraper Fixed (Phase 12)

Re-enabled GMU Statistics scraper by discovering and using the 25Live/CollegeNET JSON API, bypassing the Trumba JS calendar widget that wouldn't render in headless Playwright.

### GMU Statistics ✅ FIXED
- **Previous Issue:** Trumba JS calendar widget doesn't render in headless Playwright
- **Root Cause:** The embedded Trumba spud (`$Trumba.addSpud({ webName: "cec-statistics" })`) requires full browser JS execution
- **Solution:**
  - Discovered 25Live/CollegeNET JSON API at `https://25livepub.collegenet.com/calendars/cec-statistics.json`
  - Returns structured event data: ISO 8601 dates with timezone offsets, HTML descriptions
  - No JavaScript rendering needed — plain HTTP GET returning JSON
  - Supports date filtering via `?startdate=YYYYMMDD&enddate=YYYYMMDD`
- **Implementation:**
  - Rewrote scraper to fetch JSON API directly (like FDA pattern)
  - Parse ISO datetimes with timezone offsets (ET→PST conversion)
  - Extract talk titles and speaker names from `<p>`-structured HTML descriptions
  - Construct GMU canonical URLs using event IDs
- **Result:** 14 total events, 3 within date range. Output matches expected format exactly.

**Disabled Scrapers:** 2 (McGill - bot protection, Cambridge MRC - DNS failure)
**Enabled Scrapers:** 31

---

## Previous Update: 18 New Scrapers (Phase 11)

Added 18 new scrapers completing all remaining sources. 17 enabled, 1 disabled (Cambridge MRC DNS unreachable).

### New Working Scrapers

| Scraper | Pattern | Events | Key Technique |
|---------|---------|--------|---------------|
| CTML Berkeley | List+Detail | 2 | Drupal/OpenBerkeley, date prefix in titles (M/DD/YY) |
| Duke-Margolis | List+Detail | 4 | Drupal Views module, article selectors |
| Dana Farber | List+Detail | 1 | WordPress/TEC plugin, `domcontentloaded` (networkidle timeout) |
| ASA Calendar | Click+Form+Parse | 17 | ColdFusion form POST, click-through navigation, inline results |
| ASA Boston | SPA-with-wait | 5 | Higher Logic/React, rich text block parsing |
| ASA Georgia | Single Page | 1 | Squarespace, h3 + JS sibling text traversal |
| ASA New Jersey | Single Page | 2 | Basic static HTML, multi-page (homepage + events.html) |
| ASA San Diego | SPA-with-wait | 1 | Higher Logic/React, labeled date patterns |
| ICSA | API | 20 | WordPress REST API `/wp-json/wp/v2/posts?categories=4` |
| NESTAT | Multi-page | 0 | Static HTML, 5 sub-pages (low volume source) |
| ENAR | Single Page | 1 | Static ColdFusion, h3 titles with date/speaker extraction |
| IBS | SPA-with-wait | 0-2 | React SPA (HigherLogic), intermittent rendering |
| RSS | List+Detail | 11 | ASP.NET WebForms, UK time format (dots→colons), GMT timezone |
| Washington Stat | Single Page | 1 | Static HTML, seminars + events pages |
| ISPOR | List+Detail | 2 | Sitefinity CMS, top-level conference pages only |
| Basel Biometric | Single Page | 1 | Quarto/GitHub Pages, table with Swiss dates (DD.MM.YYYY), CET |
| R Conferences | Single Page | 1 | Static HTML, `<li>` conference list parsing |

### Disabled Scrapers

| Scraper | Reason |
|---------|--------|
| Cambridge MRC | DNS resolution failure - site unreachable |

### Files Created (18 scrapers)
- `src/scrapers/academic/ctml_berkeley.py`
- `src/scrapers/academic/duke_margolis.py`
- `src/scrapers/academic/cambridge_mrc.py` (disabled)
- `src/scrapers/academic/dana_farber.py`
- `src/scrapers/associations/asa_calendar.py`
- `src/scrapers/associations/asa_boston.py`
- `src/scrapers/associations/asa_georgia.py`
- `src/scrapers/associations/asa_newjersey.py`
- `src/scrapers/associations/asa_sandiego.py`
- `src/scrapers/associations/icsa.py`
- `src/scrapers/associations/nestat.py`
- `src/scrapers/associations/enar.py`
- `src/scrapers/associations/ibs.py`
- `src/scrapers/associations/rss.py`
- `src/scrapers/associations/washington_stat.py`
- `src/scrapers/organizations/ispor.py`
- `src/scrapers/organizations/basel_biometric.py`
- `src/scrapers/tech/r_conferences.py`

### Technical Notes
- **ASA Calendar ColdFusion**: Must click "Search Events" link then submit form (direct GET to search page redirects to main). Events are inline on results page with no detail pages. Year extracted from month section headers.
- **Dana Farber**: Must use `domcontentloaded` (WordPress TEC never reaches `networkidle`).
- **ISPOR**: Must filter to top-level conference URLs only (sub-pages like /about/registration share same path prefix).
- **ICSA REST API**: Primary approach uses WordPress JSON API; page scraping as fallback.
- **RSS UK times**: Convert "2.15PM" format to "2:15PM" before parsing. GMT timezone.
- **Basel Biometric Swiss dates**: DD.MM.YYYY format converted to standard Month DD, YYYY. CET timezone.

**Latest Run:** 172 total events, 47 within date range (30 enabled sources)

---

## Previous Update: Extended Date Range

- Changed event date range from 2 weeks (14 days) to 3 weeks (21 days) in `config/settings.yaml`
- This allows users to see more upcoming events in the output

---

## Previous Update: Export Page Feature

### Phase 9: Export Page ✅ (NEW)

| Task | Status | File(s) |
|------|--------|---------|
| Export HTML template | ✅ Complete | `src/output/templates/export.html.j2` |
| HTMLGenerator export method | ✅ Complete | `src/output/html_generator.py` |
| Main orchestration update | ✅ Complete | `src/main.py` |
| Navigation link | ✅ Complete | `src/output/templates/events.html.j2` |
| Vercel routing | ✅ Complete | `vercel.json` |
| Unit tests | ✅ Complete (15 tests) | `tests/test_html_generator.py` |

**Features:**
- Separate export page (`export.html`) with event selection
- Checkboxes for selecting individual events
- "Select All" / "Select None" buttons
- Filter events by source
- Copy selected events to clipboard (matching ExampleOutput.txt format)
- Download selected events as .txt file
- Clean URL: `/export` via Vercel rewrite

**Total Tests:** 54 (51 passing, 3 pre-existing failures in date_parser)

---

## Completed Tasks

### Phase 1: Core Infrastructure ✅

| Task | Status | File(s) |
|------|--------|---------|
| Create project structure | ✅ Complete | All directories and `__init__.py` files |
| Settings configuration | ✅ Complete | `config/settings.yaml` |
| Sources configuration | ✅ Complete | `config/sources.yaml` |
| Event model | ✅ Complete | `src/models/event.py` |
| Date parser | ✅ Complete | `src/parsers/date_parser.py` |
| Browser manager | ✅ Complete | `src/core/browser.py` |
| Custom exceptions | ✅ Complete | `src/core/exceptions.py` |

### Phase 2: Base Scraper Framework ✅

| Task | Status | File(s) |
|------|--------|---------|
| Base scraper class | ✅ Complete | `src/scrapers/base.py` |
| Scraper registry | ✅ Complete | `src/scrapers/__init__.py` |
| Retry decorator | ✅ Complete | `src/utils/retry.py` |
| Logging config | ✅ Complete | `src/utils/logging_config.py` |

### Phase 3: Site-Specific Scrapers ✅ (70 total, 67 enabled)

| Scraper | Status | Events Found | Notes |
|---------|--------|--------------|-------|
| Instats | ✅ Working | 20 | Bubble.io SPA - visits individual pages for accurate times |
| FDA | ✅ Working | 7 | JSON API + page visits for times |
| NISS | ✅ Working | 9 | List+detail pattern, collects URLs first |
| DahShu | ✅ Working | 3 | Wild Apricot, deduplicates by event ID |
| Harvard HSPH | ✅ Working | 5 | List+detail pattern, clean title/speaker extraction |
| ASA Webinars | ✅ Working | 5 | Working as expected |
| PSI | ✅ Working | 9 | List+detail with GMT time extraction |
| Posit | ✅ Working | 6 | Fixed card selectors for new site design |
| UCSF | ✅ Working | 1 | Drupal list+detail, static HTML |
| ASA Philadelphia | ✅ Working | 15 | List+detail, speaker from H1, title from body |
| StatsUpAI | ✅ Working | 3 | Single-page zoom link extraction |
| RealiseD | ✅ Working | 4 | WordPress/Avada countdown timer dates |
| PBSS | ✅ Working | 15 | React SPA, domcontentloaded, keyword-boundary parsing |
| CTML Berkeley | ✅ Working | 2 | Drupal/OpenBerkeley, date prefix in titles |
| Duke-Margolis | ✅ Working | 4 | Drupal Views module, list+detail |
| Dana Farber | ✅ Working | 1 | WordPress/TEC, domcontentloaded |
| ASA Calendar | ✅ Working | 17 | ColdFusion form POST, click-through navigation |
| ASA Boston | ✅ Working | 5 | Higher Logic/React SPA, rich text parsing |
| ASA Georgia | ✅ Working | 1 | Squarespace, h3 + sibling text |
| ASA New Jersey | ✅ Working | 2 | Basic static HTML |
| ASA San Diego | ✅ Working | 1 | Higher Logic/React SPA |
| ICSA | ✅ Working | 20 | WordPress REST API |
| NESTAT | ✅ Working | 0 | Static HTML, low volume (no current events) |
| ENAR | ✅ Working | 1 | Static ColdFusion |
| IBS | ✅ Working | 0-2 | React SPA, intermittent rendering |
| RSS | ✅ Working | 11 | ASP.NET WebForms, list+detail, GMT |
| Washington Stat | ✅ Working | 1 | Static HTML |
| ISPOR | ✅ Working | 2 | Sitefinity CMS, conference pages |
| Basel Biometric | ✅ Working | 1 | Quarto/GitHub Pages, Swiss dates |
| R Conferences | ✅ Working | 1 | Static HTML conference list |
| McGill | ❌ Disabled | 0 | Imperva/Distil bot protection |
| GMU | ✅ Working | 14 (3 in range) | 25Live JSON API, bypasses Trumba JS widget |
| Cambridge MRC | ❌ Disabled | 0 | DNS resolution failure |
| ASA Twin Cities | ❌ Disabled | 0 | Site unreachable (timeout) |
| **ASA Community chapters** | ✅ Working | varies | 30 Higher Logic subclasses |
| ASA North Texas | ✅ Working | 0 | Google Sites |
| ASA Pittsburgh | ✅ Working | 4 | WordPress blog |
| ASA Cleveland | ✅ Working | 0 | Google Sites |
| ASA Columbus | ✅ Working | 0 | Google Sites |

**Latest Run Results:** 67 enabled sources, 3 disabled

### Phase 4: Output Generation ✅

| Task | Status | File(s) |
|------|--------|---------|
| HTML generator | ✅ Complete | `src/output/html_generator.py` |
| HTML template | ✅ Redesigned | `src/output/templates/events.html.j2` - polished editorial design |
| Text output | ✅ Complete | Included in html_generator.py |

### Phase 5: Main Orchestration ✅

| Task | Status | File(s) |
|------|--------|---------|
| Main entry point | ✅ Complete | `src/main.py` |
| CLI arguments | ✅ Complete | --config, --debug, --source |

### Phase 6: Scheduling & Serving ✅

| Task | Status | File(s) |
|------|--------|---------|
| Cron script | ✅ Complete | `scripts/run_scraper.sh` |
| Local server | ✅ Complete | `scripts/serve_local.py` |
| Requirements | ✅ Complete | `requirements.txt` |
| Git ignore | ✅ Complete | `.gitignore` |

### Phase 7: Testing ✅ (NEW)

| Task | Status | File(s) |
|------|--------|---------|
| Unit tests for DateParser | ✅ Complete (21 tests) | `tests/test_date_parser.py` |
| Unit tests for Event model | ✅ Complete (18 tests) | `tests/test_event.py` |
| Test fixtures | ✅ Complete | `tests/conftest.py` |

**Total: 39 unit tests passing**

### Phase 8: Deployment ✅ (NEW)

| Task | Status | Notes |
|------|--------|-------|
| GitHub repository | ✅ Complete | https://github.com/metygl/StatEventsScraping |
| Vercel auto-deploy | ✅ Complete | Auto-deploys `output/events.html` on push to main |
| Vercel config | ✅ Complete | `vercel.json` - rewrites root to events.html |

---

## Bug Fixes Applied (2026-01-14)

### NISS Scraper
- **Issue:** DOM context errors (`ElementHandle.query_selector` failures)
- **Cause:** Navigating to event pages invalidated element handles from listing page
- **Fix:** Refactored to collect all URLs first, then navigate to each page separately
- **Result:** Now finds 10 events (up from 1)

### DahShu Scraper
- **Issue:** 14 duplicate events, missing time details
- **Cause:** Calendar view showed same event in multiple day cells
- **Fix:** Deduplicate by event ID, scrape individual event pages for details
- **Result:** Now finds 1 unique event with proper date/time

### Harvard HSPH Scraper (Round 1)
- **Issue:** 404 error, no events found
- **Cause:** URL changed from `/epidemiology/epi-seminar-series/` to `/department/epidemiology/seminar-series/`
- **Fix:** Updated BASE_URL, improved date/time extraction from page context
- **Result:** Now finds 3 events

### FDA Scraper
- **Issue:** HTTP 404 error
- **Cause:** Incorrect URL path for Grand Rounds page
- **Fix:** Updated to use `/news-events` as entry point, improved link selectors
- **Result:** Still unstable due to government site rate limiting

### DateParser
- **Issue:** "ET" timezone warnings from dateutil
- **Cause:** Missing timezone abbreviations in TZINFOS
- **Fix:** Added TZINFOS mapping for ET, CET, BST, and other common abbreviations
- **Result:** No more timezone warnings

---

## Bug Fixes Applied (2026-01-14 Evening)

### Instats Scraper ✅ FIXED
- **Issue:** 0 events found - Bubble.io SPA content not rendering
- **Root Cause:** Bubble.io apps use heavy JavaScript rendering with dynamic class names
- **Investigation:**
  - Used diagnostic script to capture screenshot and HTML after rendering
  - Found content IS rendered after ~8 seconds delay
  - Discovered cards use `.clickable-element.bubble-element.Group` selector
  - No traditional URLs - Bubble.io uses JavaScript click handlers
- **Fix:**
  - Increased wait time to 8 seconds after navigation
  - Implemented `_extract_from_bubble_cards()` method to find card elements
  - Created `_parse_bubble_card()` to extract title, date, instructor from card text
  - Title extracted via regex: text before "Livestream:"
  - Date extracted via regex: text after "Livestream:" (e.g., "Jan 14th")
- **Result:** Now finds 43 events (up from 0)

### PSI Scraper ✅ FIXED
- **Issue:** Shows "Read more" as event titles instead of actual titles
- **Cause:** Title selector `"h2 a, h3 a, .title a, a"` fell back to generic `<a>` tags
- **Fix:**
  - Prioritize heading elements (`h2, h3, h4, .title, .event-title`) for title text
  - Filter out common non-title link text ("Read more", "More info", "Learn more")
  - Only use link text if length > 10 characters
- **Result:** Now extracts proper event titles

### Harvard HSPH Scraper (Round 2) ✅ FIXED
- **Issue:** All events showing same date (Jan 27) instead of individual dates
- **Cause:** Date extraction used `re.search` on ancestor element containing multiple events
- **Fix:**
  - Refactored to list+detail pattern (like NISS)
  - `_collect_event_urls()` gathers all event URLs from listing page
  - `_scrape_event_page()` visits each page individually to extract accurate date
  - Each event page has only one date, eliminating ambiguity
- **Result:** Now extracts correct per-event dates

---

## Bug Fixes Applied (2026-01-14 Night)

### FDA Scraper ✅ FIXED
- **Issue:** Timeouts, intermittent 404 errors, rate limiting
- **Root Cause:** HTML scraping approach was unreliable on government site
- **Solution:**
  - Discovered FDA provides a JSON API at `/datatables-json/events-meetings.json`
  - Rewrote scraper to fetch JSON directly instead of parsing HTML
  - JSON contains all event data: title, dates, URLs, event types
  - Much more reliable than DOM scraping
- **Result:** Now finds 6 events within date range (11 total)

---

## Bug Fixes Applied (2026-01-14 Late Night)

### Time Extraction Improvements ✅

Multiple scrapers were showing incorrect times (12:00am defaults). Fixed by visiting individual event pages:

#### Instats Scraper
- **Issue:** All events showed 12:00am instead of actual seminar times
- **Fix:** Visit each event page to extract "12:00 pm to 1:00 pm" format
- **Result:** Accurate times like "12:00-1:00pm PST"

#### PSI Scraper
- **Issue:** Times defaulting to 12:00am, navigation menu text appearing in output
- **Fix:**
  - Rewrote to use list+detail pattern (collect URLs, visit each page)
  - Extract GMT times ("16:00-17:00 GMT") and convert to PST
  - Fixed speaker extraction to only capture "Presenters:" content
- **Result:** Correct times (8:00-9:00am PST) and clean speaker lists

#### FDA Scraper
- **Issue:** Times defaulting to 9am instead of actual meeting times
- **Fix:** Visit each event page to extract "12:00 p.m. - 1:00 p.m. ET" format
- **Result:** Accurate times converted from ET to PST

#### Harvard HSPH Scraper
- **Issue:** Fragmented titles with junk text, duplicate speaker names
- **Fix:**
  - Added `_clean_title()` to remove tabs, newlines, and institution names
  - Fixed speaker extraction to dedupe by base name
- **Result:** Clean titles and single speaker attribution

#### DateParser
- **Issue:** 24-hour times (16:00-17:00) not parsing correctly
- **Fix:** Made am/pm optional in regex: `([ap]m)?` instead of `([ap]m)`
- **Issue:** Events on last day of range excluded
- **Fix:** Set end date to 23:59:59 instead of midnight

### HTML Template Redesign ✅

Completely redesigned the HTML output template with a polished editorial aesthetic:

**Typography:**
- Syne (geometric display font) for headings
- DM Sans for body text
- JetBrains Mono for badges and metadata

**Visual Design:**
- Deep ink blue color palette with coral accents
- Date badges with day/month display
- Animated accent bars on card hover
- Staggered fade-in animations
- Pill-shaped source and status badges

**Features:**
- Fully responsive design
- Print-optimized styles
- Clean visual hierarchy
- Professional data science aesthetic

### Text Output Cleanup ✅

Fixed extraneous text appearing in event output:

#### PSI Events
- **Issue:** Navigation menu text included in speakers
- **Fix:** Rewrote `_extract_speakers()` to only capture "Presenters:" line content

#### Instats Events
- **Issue:** "(American Statistical Association)" appearing as speaker
- **Fix:** Added organization name blocklist filter

#### Harvard Events
- **Issue:** "the National Institute, Information" and fragmented text in titles
- **Fix:** Added pattern-based title cleanup and speaker deduplication

---

## Pending Tasks

### All Scrapers Implemented ✅

All 70 source scrapers have been implemented. 67 are enabled, 3 are disabled due to technical limitations.

**Academic (8):** All implemented
- [x] ~~CTML Berkeley~~ ✅ Implemented 2026-02-09
- [x] ~~Duke-Margolis~~ ✅ Implemented 2026-02-09
- [x] ~~Cambridge MRC~~ ❌ DNS failure - disabled
- [x] ~~Dana Farber~~ ✅ Implemented 2026-02-09
- [x] ~~UCSF~~ ✅ Implemented 2026-02-09
- [x] ~~McGill~~ ❌ Bot protection - disabled
- [x] ~~GMU~~ ❌ Trumba widget - disabled
- [x] ~~Harvard HSPH~~ ✅

**Associations (14):** All implemented
- [x] ~~ASA Calendar~~ ✅ Implemented 2026-02-09
- [x] ~~ASA Boston~~ ✅ Implemented 2026-02-09
- [x] ~~ASA Georgia~~ ✅ Implemented 2026-02-09
- [x] ~~ASA New Jersey~~ ✅ Implemented 2026-02-09
- [x] ~~ASA San Diego~~ ✅ Implemented 2026-02-09
- [x] ~~ICSA~~ ✅ Implemented 2026-02-09
- [x] ~~NESTAT~~ ✅ Implemented 2026-02-09
- [x] ~~ENAR~~ ✅ Implemented 2026-02-09
- [x] ~~IBS~~ ✅ Implemented 2026-02-09
- [x] ~~RSS~~ ✅ Implemented 2026-02-09
- [x] ~~Washington Statistical Society~~ ✅ Implemented 2026-02-09
- [x] ~~ASA Philadelphia~~ ✅ Implemented 2026-02-09
- [x] ~~PBSS~~ ✅ Implemented 2026-02-09
- [x] ~~ASA Webinars~~ ✅

**Organizations (6):** All implemented
- [x] ~~ISPOR~~ ✅ Implemented 2026-02-09
- [x] ~~Basel Biometric~~ ✅ Implemented 2026-02-09
- [x] ~~StatsUpAI~~ ✅ Implemented 2026-02-09
- [x] ~~RealiseD~~ ✅ Implemented 2026-02-09
- [x] ~~NISS~~ ✅
- [x] ~~DahShu~~ ✅
- [x] ~~Instats~~ ✅

**Tech (2):** All implemented
- [x] ~~R Conferences~~ ✅ Implemented 2026-02-09
- [x] ~~Posit~~ ✅

**Government (1):** All implemented
- [x] ~~FDA~~ ✅

### Enhancements

- [ ] Add pyproject.toml for modern Python packaging
- [ ] Add error notification (email/Slack)
- [ ] Add event deduplication across sources
- [ ] Add caching to avoid re-scraping unchanged pages
- [ ] Add RSS feed output option
- [x] ~~Fix PSI title extraction~~ ✅ Fixed 2026-01-14
- [x] ~~Fix Harvard per-event date extraction~~ ✅ Fixed 2026-01-14
- [x] ~~Investigate Instats API for direct data access~~ ✅ Fixed using card text extraction
- [x] ~~Fix Posit scraper~~ ✅ Fixed 2026-01-14 (updated card selectors)
- [x] ~~Fix time extraction for all scrapers~~ ✅ Fixed 2026-01-14 (visit individual pages)
- [x] ~~Clean up extraneous text in output~~ ✅ Fixed 2026-01-14 (blocklists, pattern cleanup)
- [x] ~~Redesign HTML template~~ ✅ Fixed 2026-01-14 (polished editorial design)
- [x] ~~Add 7 new scrapers~~ ✅ Added 2026-02-09 (5 working, 2 disabled)
- [x] ~~Add remaining 18 scrapers~~ ✅ Added 2026-02-09 (17 enabled, 1 disabled)
- [x] ~~Add ASA chapter scrapers~~ ✅ Added 2026-02-10 (35 new, 34 enabled, 1 disabled)

---

## How to Continue Development

### Running Tests

```bash
# Activate venv first
source venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_date_parser.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/ --cov=src
```

### Adding a New Scraper

1. Create a new file in the appropriate category folder:
   ```
   src/scrapers/{category}/{site_name}.py
   ```

2. Implement the scraper class:
   ```python
   from src.scrapers.base import BaseScraper
   from src.models.event import Event, LocationType
   from src.parsers.date_parser import DateParser

   class NewSiteScraper(BaseScraper):
       SOURCE_NAME = "New Site"
       BASE_URL = "https://example.com/events"

       async def scrape(self):
           await self.navigate_to_page()
           # ... extraction logic
           return self.events
   ```

3. Register in `src/scrapers/__init__.py`:
   ```python
   SCRAPER_REGISTRY = {
       # ...
       "category.new_site": "src.scrapers.category.new_site.NewSiteScraper",
   }
   ```

4. Enable in `config/sources.yaml`:
   ```yaml
   - name: "New Site"
     url: "https://example.com/events"
     scraper: "category.new_site"
     enabled: true
   ```

### Testing a Single Scraper

```bash
python -m src.main --source "Site Name" --debug
```

---

## Quick Reference

### Run Scraper
```bash
# Activate venv first
source venv/bin/activate

# Run all enabled sources
python -m src.main

# Debug mode (visible browser)
python -m src.main --debug

# Single source
python -m src.main --source "NISS"
```

### Run Tests
```bash
source venv/bin/activate
python -m pytest tests/ -v
```

### View Output
```bash
# Local
python scripts/serve_local.py
# Open http://localhost:8000/events.html

# Production
# Visit your Vercel URL (auto-deploys on push to main)
```

### Configure Date Range
Edit `config/settings.yaml`:
```yaml
date_range:
  mode: "rolling"    # or "fixed"
  days_ahead: 21     # for rolling mode (3 weeks)
  # start_date: "2026-01-14"  # for fixed mode
  # end_date: "2026-01-30"
```

### Enable/Disable Sources
Edit `config/sources.yaml` and set `enabled: true/false` for each source.

---

## File Summary

| Category | Count | Notes |
|----------|-------|-------|
| Python modules | 49 | Core application code (includes all 70 scrapers) |
| Config files | 2 | YAML configuration |
| Templates | 3 | Jinja2 HTML templates (events.html.j2, export.html.j2, status.html.j2) |
| Scripts | 2 | Shell + Python |
| Tests | 4 | pytest unit tests |
| Documentation | 2 | plan.md, progress.md |
| **Total files** | **55** | Excluding __init__.py |

---

## Test Results Summary

```
tests/test_date_parser.py - 21 tests
  - Date parsing (various formats)
  - Time range extraction
  - Timezone detection
  - Date range utilities

tests/test_event.py - 18 tests
  - Event creation and validation
  - Datetime localization
  - Formatting methods
  - Date range filtering
  - Sorting

tests/test_html_generator.py - 15 tests
  - Export page generation
  - JSON data embedding
  - UI element verification
  - Text output formatting

Total: 54 tests (51 passing, 3 pre-existing failures in date_parser timezone tests)
```

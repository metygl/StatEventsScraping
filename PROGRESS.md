# Statistics Events Scraper - Progress Tracker

## Current Status: Deployed to Vercel

**Last Updated:** 2026-01-21

---

## Recent Update: Export Page Feature

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

### Phase 3: Site-Specific Scrapers ✅ (8 of 31)

| Scraper | Status | Events Found | Notes |
|---------|--------|--------------|-------|
| Instats | ✅ Working | 20 | Bubble.io SPA - visits individual pages for accurate times |
| FDA | ✅ Working | 11 (6 in range) | JSON API + page visits for times |
| NISS | ✅ Working | 10 | List+detail pattern, collects URLs first |
| DahShu | ✅ Working | 1 | Wild Apricot, deduplicates by event ID |
| Harvard HSPH | ✅ Working | 3 | List+detail pattern, clean title/speaker extraction |
| ASA Webinars | ✅ Working | 5 | Working as expected |
| PSI | ✅ Working | 10 | List+detail with GMT time extraction |
| Posit | ✅ Working | 5 (3 in range) | Fixed card selectors for new site design |

**Latest Run Results:** 65 total events, 27 within date range

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

### Additional Scrapers (23 remaining)

These scrapers are defined in `sources.yaml` but set to `enabled: false`:

**Academic:**
- [ ] CTML Berkeley
- [ ] UCSF
- [ ] McGill
- [ ] Duke-Margolis
- [ ] Cambridge MRC
- [ ] GMU
- [ ] Dana Farber

**Associations:**
- [ ] ASA Calendar
- [ ] ASA Boston
- [ ] ASA Georgia
- [ ] ASA New Jersey
- [ ] ASA San Diego
- [ ] ASA Philadelphia
- [ ] ICSA
- [ ] NESTAT
- [ ] ENAR
- [ ] IBS
- [ ] RSS
- [ ] PBSS
- [ ] Washington Statistical Society

**Organizations:**
- [ ] ISPOR
- [ ] Basel Biometric

**Tech:**
- [ ] R Conferences

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
  days_ahead: 14     # for rolling mode
  # start_date: "2026-01-14"  # for fixed mode
  # end_date: "2026-01-30"
```

### Enable/Disable Sources
Edit `config/sources.yaml` and set `enabled: true/false` for each source.

---

## File Summary

| Category | Count | Notes |
|----------|-------|-------|
| Python modules | 18 | Core application code |
| Config files | 2 | YAML configuration |
| Templates | 2 | Jinja2 HTML templates (events.html.j2, export.html.j2) |
| Scripts | 2 | Shell + Python |
| Tests | 4 | pytest unit tests |
| Documentation | 2 | plan.md, progress.md |
| **Total files** | **30** | Excluding __init__.py |

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

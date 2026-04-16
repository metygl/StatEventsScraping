# Changelog

## v1.5.0 — 2026-04-16

### New: Feedback Page
- Added a feedback form at `/feedback` where users can suggest new sources, report bugs, or request features
- Submissions create GitHub Issues automatically for tracking
- Violet-themed button added to the events page header

### New: Rich Clipboard Copy
- Export page "Copy to Clipboard" now copies rich HTML with blue clickable links
- URLs and date lines are indented for cleaner formatting
- Pasting into email clients, Word, or Google Docs preserves blue hyperlinks

### New: Changelog Page
- Added version history page at `/changelog` accessible via gear icon in header

### Changed: Scraper Filters
- **Instats**: Now only includes free seminars (paid events filtered out)
- **Posit**: Hangout events excluded from results
- **Harvard**: Detects location type from page content; only includes virtual and hybrid events
- **DahShu**: Filters out past events, only shows upcoming seminars

### Changed: ASA Chapter Cleanup
- Disabled 27 ASA Higher Logic community chapter scrapers that produced generic redirect links
- Kept active chapters: SF ASA, ASA Boston, ASA Philadelphia, ASA Pittsburgh, ASA North Carolina, ASA Connecticut
- Improved URL extraction to prefer event detail pages over generic chapter homepages

### Changed: Global Filters
- In-person international conferences (congresses, symposiums, summits) are now automatically excluded
- Berkeley (CTML) scraper disabled — events are in-person only

### Fixed: RSS Scraper
- Normalized whitespace in event titles
- Improved speaker/organizer extraction

---

## v1.4.0 — 2026-02-10

### New: ASA Chapter Expansion
- Added 35 ASA chapter scrapers (30 Higher Logic + 5 standalone sites)
- Generic `ASACommunityGenericScraper` base class for Higher Logic chapters
- Added AKST/AKDT timezone support
- Total sources expanded from 33 to 70

---

## v1.3.0 — 2026-02-09

### New: Source Status Page
- Added `/status` page showing per-source scraping health
- Summary pills for total, enabled, successful, and failed sources
- Color-coded status indicators with error messages

### New: 18 Additional Scrapers
- Completed all remaining source scrapers (CTML Berkeley, Duke-Margolis, Dana Farber, ASA Calendar, ICSA, RSS, ISPOR, Basel Biometric, R Conferences, and more)
- Total: 33 sources implemented

### Fixed: GMU Scraper
- Discovered 25Live JSON API to bypass Trumba JS widget

---

## v1.2.0 — 2026-02-09

### New: Export Page
- Added `/export` page with event selection checkboxes
- Select All / Select None buttons and source filter dropdown
- Copy to clipboard and download as .txt functionality

### New: 7 More Scrapers
- UCSF, ASA Philadelphia, StatsUpAI, RealiseD, PBSS, McGill (disabled), GMU (disabled)

---

## v1.1.0 — 2026-01-14

### Fixed: Multiple Scraper Improvements
- Instats: Fixed Bubble.io SPA rendering (0 to 43 events)
- PSI: Fixed title extraction and GMT time conversion
- Harvard: Fixed per-event date extraction and title cleanup
- FDA: Rewrote to use JSON API for reliability
- Posit: Updated card selectors for site redesign

### New: HTML Template Redesign
- Polished editorial design with Syne, DM Sans, JetBrains Mono fonts
- Date badges, animated hover effects, staggered animations

---

## v1.0.0 — 2026-01-14

### Initial Release
- Core scraping infrastructure with Playwright async browser automation
- 8 initial scrapers: Instats, FDA, NISS, DahShu, Harvard HSPH, ASA Webinars, PSI, Posit
- Date parser with timezone normalization to PST
- HTML and plain text output generation
- Vercel deployment with auto-deploy on push

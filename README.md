# StatEventsScraping

A web scraper that aggregates statistics and biostatistics events from academic, professional, and government sources into a unified calendar view.

## Live Site

View upcoming events at: [https://stat-events-scraping.vercel.app](https://stat-events-scraping.vercel.app)

## Features

- **Automated scraping** of 8+ event sources (seminars, webinars, conferences)
- **Daily updates** via GitHub Actions
- **Date range filtering** (currently 3-week lookahead)
- **Timezone normalization** to PST
- **Export functionality** for copying/downloading selected events

## Event Sources

| Source | Type |
|--------|------|
| ASA Webinars | Professional association |
| FDA Biostatistics | Government |
| Harvard HSPH | Academic |
| Instats Seminar | Organization |
| NISS | Organization |
| DahShu | Organization |
| Posit | Tech |
| PSI | Professional association |

## Local Development

### Prerequisites

- Python 3.12+
- Playwright

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Run the scraper
python -m src.main

# Run with debug mode (visible browser)
python -m src.main --debug

# Scrape a single source
python -m src.main --source "FDA Biostatistics"
```

### Local Server

```bash
python scripts/serve_local.py
# Visit http://localhost:8000
```

## Configuration

- `config/settings.yaml` - Date range, browser settings, output options
- `config/sources.yaml` - Event source definitions (enable/disable sources here)

## Project Structure

```
├── src/
│   ├── main.py              # Entry point
│   ├── scrapers/            # Site-specific scrapers
│   ├── parsers/             # Date parsing utilities
│   ├── output/              # HTML generation
│   └── models/              # Event data model
├── config/                  # Configuration files
├── output/                  # Generated HTML files
├── tests/                   # Unit tests
└── .github/workflows/       # GitHub Actions automation
```

## Deployment

The site is deployed on Vercel and updates automatically when changes are pushed to the main branch. GitHub Actions runs the scraper daily at 6am UTC and commits any changes.

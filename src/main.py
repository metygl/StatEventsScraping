"""
Main entry point for the event scraping system.
Orchestrates the scraping process across all configured sources.
"""

import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import yaml
import pytz

from src.core.browser import BrowserManager
from src.core.exceptions import ScraperException
from src.models.event import Event
from src.parsers.date_parser import DateParser
from src.output.html_generator import HTMLGenerator
from src.utils.logging_config import setup_logging
from src.scrapers import get_scraper_class

logger = logging.getLogger(__name__)


class EventScraperApp:
    """Main application class orchestrating the scraping process."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        Initialize the scraper application.

        Args:
            config_path: Path to settings configuration file
        """
        self.config = self._load_config(config_path)
        self.all_sources = self._load_all_sources("config/sources.yaml")
        self.sources = [s for s in self.all_sources if s.get("enabled", True)]
        self.browser_manager = None
        self.events: List[Event] = []
        self.errors: Dict[str, str] = {}
        self.source_results: List[Dict[str, Any]] = []

        setup_logging(
            level=self.config["logging"]["level"],
            log_file=self.config["logging"]["file"],
        )

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load main configuration."""
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def _load_all_sources(self, path: str) -> List[Dict[str, Any]]:
        """Load all source definitions."""
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            return data["sources"]

    def _get_date_range(self) -> tuple:
        """Get the date range for filtering events."""
        config = self.config["date_range"]
        mode = config.get("mode", "rolling")

        if mode == "fixed":
            return DateParser.get_fixed_date_range(
                config["start_date"], config["end_date"]
            )
        else:
            # Rolling mode
            return DateParser.get_date_range(days=config.get("days_ahead", 14))

    async def run(self) -> List[Event]:
        """
        Main execution method.

        Returns:
            List of filtered events within the date range
        """
        logger.info("Starting event scraping process")

        date_range = self._get_date_range()
        logger.info(
            f"Date range: {date_range[0].strftime('%Y-%m-%d')} to "
            f"{date_range[1].strftime('%Y-%m-%d')}"
        )

        # Initialize browser
        self.browser_manager = BrowserManager(
            headless=self.config["browser"]["headless"],
            slow_mo=self.config["browser"]["slow_mo"],
            timeout=self.config["browser"]["timeout"],
        )
        await self.browser_manager.start()

        try:
            # Scrape all sources with concurrency control
            semaphore = asyncio.Semaphore(
                self.config["scraping"]["max_concurrent"]
            )

            tasks = [
                self._scrape_source(source, semaphore) for source in self.sources
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            source_events_map: Dict[str, List[Event]] = {}
            for source, result in zip(self.sources, results):
                if isinstance(result, Exception):
                    self.errors[source["name"]] = str(result)
                    logger.error(f"Failed to scrape {source['name']}: {result}")
                    source_events_map[source["name"]] = []
                elif result:
                    self.events.extend(result)
                    source_events_map[source["name"]] = result
                else:
                    source_events_map[source["name"]] = []

            # Filter by date range
            filtered_events = [
                e
                for e in self.events
                if e.is_within_date_range(date_range[0], date_range[1])
            ]

            # Build per-source results for status page
            for source in self.all_sources:
                name = source["name"]
                enabled = source.get("enabled", True)
                if not enabled:
                    self.source_results.append({
                        "name": name,
                        "url": source.get("url", ""),
                        "enabled": False,
                        "status": "disabled",
                        "total_events": 0,
                        "in_range_events": 0,
                        "error_message": None,
                    })
                elif name in self.errors:
                    self.source_results.append({
                        "name": name,
                        "url": source.get("url", ""),
                        "enabled": True,
                        "status": "error",
                        "total_events": 0,
                        "in_range_events": 0,
                        "error_message": self.errors[name],
                    })
                else:
                    src_events = source_events_map.get(name, [])
                    in_range = [
                        e for e in src_events
                        if e.is_within_date_range(date_range[0], date_range[1])
                    ]
                    self.source_results.append({
                        "name": name,
                        "url": source.get("url", ""),
                        "enabled": True,
                        "status": "success",
                        "total_events": len(src_events),
                        "in_range_events": len(in_range),
                        "error_message": None,
                    })

            logger.info(
                f"Scraped {len(self.events)} total events, "
                f"{len(filtered_events)} within date range"
            )

            # Generate output
            days_ahead = self.config["date_range"].get("days_ahead", 14)
            self._generate_output(filtered_events, date_range, days_ahead)

            return filtered_events

        finally:
            await self.browser_manager.stop()

    async def _scrape_source(
        self,
        source: Dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> List[Event]:
        """
        Scrape a single source with semaphore control.

        Args:
            source: Source configuration dict
            semaphore: Asyncio semaphore for concurrency control

        Returns:
            List of events from the source
        """
        async with semaphore:
            logger.info(f"Scraping {source['name']}")

            try:
                scraper_class = get_scraper_class(source["scraper"])

                async with self.browser_manager.new_page() as page:
                    scraper = scraper_class(page)
                    events = await scraper.scrape()

                logger.info(f"Found {len(events)} events from {source['name']}")
                return events

            except Exception as e:
                logger.error(f"Error scraping {source['name']}: {e}")
                raise

    def _generate_output(
        self, events: List[Event], date_range: tuple, days_ahead: int = 14
    ):
        """Generate all output files."""
        output_config = self.config["output"]
        output_dir = Path(output_config["directory"])
        output_dir.mkdir(parents=True, exist_ok=True)

        generator = HTMLGenerator()
        total_sources = len(self.all_sources)

        # Generate HTML
        html_path = output_dir / output_config["html_file"]
        generator.generate(events, str(html_path), date_range, total_sources=total_sources)
        logger.info(f"Generated HTML: {html_path}")

        # Generate export page
        export_path = output_dir / "export.html"
        generator.generate_export_page(events, str(export_path), date_range, days_ahead)
        logger.info(f"Generated export page: {export_path}")

        # Generate status page
        status_path = output_dir / "status.html"
        generator.generate_status_page(self.source_results, str(status_path), date_range)
        logger.info(f"Generated status page: {status_path}")

        # Generate text if configured
        if output_config.get("generate_text", False):
            text_path = output_dir / output_config["text_file"]
            text_content = generator.generate_text_output(events, date_range, days_ahead)
            text_path.write_text(text_content, encoding="utf-8")
            logger.info(f"Generated text: {text_path}")

        # Log any errors
        if self.errors:
            logger.warning(f"Errors occurred for {len(self.errors)} sources:")
            for source, error in self.errors.items():
                logger.warning(f"  {source}: {error}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape statistics events from multiple sources"
    )
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to configuration file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (non-headless browser)",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Only scrape a specific source (by name)",
    )

    args = parser.parse_args()

    app = EventScraperApp(config_path=args.config)

    if args.debug:
        app.config["browser"]["headless"] = False
        app.config["logging"]["level"] = "DEBUG"

    if args.source:
        # Filter to only the specified source
        app.sources = [s for s in app.sources if s["name"] == args.source]
        if not app.sources:
            print(f"Source '{args.source}' not found or not enabled")
            return

    asyncio.run(app.run())


if __name__ == "__main__":
    main()

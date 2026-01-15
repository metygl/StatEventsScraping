"""
Custom exceptions for the scraper application.
"""


class ScraperException(Exception):
    """Base exception for all scraper errors."""

    pass


class SiteUnreachableError(ScraperException):
    """Site could not be reached after retries."""

    pass


class ParsingError(ScraperException):
    """Failed to parse expected content from page."""

    pass


class DateParsingError(ScraperException):
    """Failed to parse date from extracted text."""

    pass


class ConfigurationError(ScraperException):
    """Invalid or missing configuration."""

    pass

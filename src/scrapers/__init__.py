"""
Scraper module registry.
Provides dynamic scraper class lookup by module path.
"""

import importlib
from typing import Type

from src.scrapers.base import BaseScraper

# Registry of all available scrapers
# Format: "category.name" -> "full.module.path.ClassName"
SCRAPER_REGISTRY = {
    # Organizations (initial 8)
    "organizations.instats": "src.scrapers.organizations.instats.InstatsScraper",
    "organizations.niss": "src.scrapers.organizations.niss.NISSScraper",
    "organizations.dahshu": "src.scrapers.organizations.dahshu.DahShuScraper",
    # Government
    "government.fda": "src.scrapers.government.fda.FDAScraper",
    # Academic
    "academic.harvard_hsph": "src.scrapers.academic.harvard_hsph.HarvardHSPHScraper",
    # Associations
    "associations.asa_webinars": "src.scrapers.associations.asa_webinars.ASAWebinarsScraper",
    "associations.psi": "src.scrapers.associations.psi.PSIScraper",
    # Tech
    "tech.posit": "src.scrapers.tech.posit.PositScraper",
    # Future scrapers (disabled in sources.yaml)
    "academic.ctml_berkeley": "src.scrapers.academic.ctml_berkeley.CTMLBerkeleyScraper",
    "academic.mcgill": "src.scrapers.academic.mcgill.McGillScraper",
    "academic.ucsf": "src.scrapers.academic.ucsf.UCSFScraper",
    "academic.duke_margolis": "src.scrapers.academic.duke_margolis.DukeMargolisScraper",
    "academic.cambridge_mrc": "src.scrapers.academic.cambridge_mrc.CambridgeMRCScraper",
    "academic.gmu": "src.scrapers.academic.gmu.GMUScraper",
    "academic.dana_farber": "src.scrapers.academic.dana_farber.DanaFarberScraper",
    "associations.asa_calendar": "src.scrapers.associations.asa_calendar.ASACalendarScraper",
    "associations.asa_boston": "src.scrapers.associations.asa_boston.ASABostonScraper",
    "associations.asa_georgia": "src.scrapers.associations.asa_georgia.ASAGeorgiaScraper",
    "associations.asa_newjersey": "src.scrapers.associations.asa_newjersey.ASANewJerseyScraper",
    "associations.asa_sandiego": "src.scrapers.associations.asa_sandiego.ASASanDiegoScraper",
    "associations.asa_philadelphia": "src.scrapers.associations.asa_philadelphia.ASAPhiladelphiaScraper",
    "associations.icsa": "src.scrapers.associations.icsa.ICSAScraper",
    "associations.nestat": "src.scrapers.associations.nestat.NESTATScraper",
    "associations.enar": "src.scrapers.associations.enar.ENARScraper",
    "associations.ibs": "src.scrapers.associations.ibs.IBSScraper",
    "associations.rss": "src.scrapers.associations.rss.RSSScraper",
    "associations.pbss": "src.scrapers.associations.pbss.PBSSScraper",
    "associations.washington_stat": "src.scrapers.associations.washington_stat.WashingtonStatScraper",
    "organizations.ispor": "src.scrapers.organizations.ispor.ISPORScraper",
    "organizations.basel_biometric": "src.scrapers.organizations.basel_biometric.BaselBiometricScraper",
    "tech.r_conferences": "src.scrapers.tech.r_conferences.RConferencesScraper",
}


def get_scraper_class(scraper_path: str) -> Type[BaseScraper]:
    """
    Get a scraper class by its registry path.

    Args:
        scraper_path: Dot-notation path like 'academic.harvard_hsph'

    Returns:
        The scraper class

    Raises:
        ValueError: If scraper not found in registry
        ImportError: If module cannot be imported
    """
    if scraper_path not in SCRAPER_REGISTRY:
        raise ValueError(f"Unknown scraper: {scraper_path}")

    full_path = SCRAPER_REGISTRY[scraper_path]
    module_path, class_name = full_path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    return getattr(module, class_name)

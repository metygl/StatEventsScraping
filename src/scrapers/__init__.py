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
    "organizations.statsupai": "src.scrapers.organizations.statsupai.StatsUpAIScraper",
    "organizations.realised": "src.scrapers.organizations.realised.RealisedScraper",
    "tech.r_conferences": "src.scrapers.tech.r_conferences.RConferencesScraper",
    "associations.sfasa": "src.scrapers.associations.sfasa.SFASAScraper",
    "associations.asa_indiana": "src.scrapers.associations.asa_indiana.ASAIndianaScraper",
    # ASA Community (Higher Logic) chapters
    "associations.asa_nycmetro": "src.scrapers.associations.asa_community.ASANYCMetroScraper",
    "associations.asa_chicago": "src.scrapers.associations.asa_community.ASAChicagoScraper",
    "associations.asa_northcarolina": "src.scrapers.associations.asa_community.ASANorthCarolinaScraper",
    "associations.asa_florida": "src.scrapers.associations.asa_community.ASAFloridaScraper",
    "associations.asa_houston": "src.scrapers.associations.asa_community.ASAHoustonScraper",
    "associations.asa_coloradowyoming": "src.scrapers.associations.asa_community.ASAColoradoWyomingScraper",
    "associations.asa_wisconsin": "src.scrapers.associations.asa_community.ASAWisconsinScraper",
    "associations.asa_alabamamississippi": "src.scrapers.associations.asa_community.ASAAlabamaMississippiScraper",
    "associations.asa_kansaswesternmo": "src.scrapers.associations.asa_community.ASAKansasWesternMOScraper",
    "associations.asa_rochester": "src.scrapers.associations.asa_community.ASARochesterScraper",
    "associations.asa_iowa": "src.scrapers.associations.asa_community.ASAIowaScraper",
    "associations.asa_midmissouri": "src.scrapers.associations.asa_community.ASAMidMissouriScraper",
    "associations.asa_stlouis": "src.scrapers.associations.asa_community.ASAStLouisScraper",
    "associations.asa_connecticut": "src.scrapers.associations.asa_community.ASAConnecticutScraper",
    "associations.asa_kentucky": "src.scrapers.associations.asa_community.ASAKentuckyScraper",
    "associations.asa_austin": "src.scrapers.associations.asa_community.ASAAustinScraper",
    "associations.asa_sanantonio": "src.scrapers.associations.asa_community.ASASanAntonioScraper",
    "associations.asa_westerntn": "src.scrapers.associations.asa_community.ASAWesternTennesseeScraper",
    "associations.asa_oregon": "src.scrapers.associations.asa_community.ASAOregonScraper",
    "associations.asa_utah": "src.scrapers.associations.asa_community.ASAUtahScraper",
    "associations.asa_southflorida": "src.scrapers.associations.asa_community.ASASouthFloridaScraper",
    "associations.asa_nebraska": "src.scrapers.associations.asa_community.ASANebraskaScraper",
    "associations.asa_princetontrenton": "src.scrapers.associations.asa_community.ASAPrincetonTrentonScraper",
    "associations.asa_albany": "src.scrapers.associations.asa_community.ASAAlbanyScraper",
    "associations.asa_alaska": "src.scrapers.associations.asa_community.ASAAlaskaScraper",
    "associations.asa_centralarkansas": "src.scrapers.associations.asa_community.ASACentralArkansasScraper",
    "associations.asa_midtennessee": "src.scrapers.associations.asa_community.ASAMidTennesseeScraper",
    "associations.asa_southerncalifornia": "src.scrapers.associations.asa_community.ASASouthernCaliforniaScraper",
    "associations.asa_orangecountylb": "src.scrapers.associations.asa_community.ASAOrangeCountyLBScraper",
    "associations.asa_delaware": "src.scrapers.associations.asa_community.ASADelawareScraper",
    # ASA standalone site chapters
    "associations.asa_northtexas": "src.scrapers.associations.asa_northtexas.ASANorthTexasScraper",
    "associations.asa_pittsburgh": "src.scrapers.associations.asa_pittsburgh.ASAPittsburghScraper",
    "associations.asa_twincities": "src.scrapers.associations.asa_twincities.ASATwinCitiesScraper",
    "associations.asa_cleveland": "src.scrapers.associations.asa_cleveland.ASAClevelandScraper",
    "associations.asa_columbus": "src.scrapers.associations.asa_columbus.ASAColumbusScraper",
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

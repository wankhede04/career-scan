from .base import Job

# Public feed / API scrapers
from .remoteok import RemoteOKScraper
from .jobicy import JobicyScraper
from .arbeitnow import ArbeitnowScraper
from .remotive import RemotiveScraper
from .wwr import WWRScraper
from .workingnomads import WorkingNomadsScraper
from .euremotejobs import EURemoteJobsScraper
from .aijobs import AIJobsScraper
from .himalayas import HimalayadScraper
from .ycombinator import YCombinatorScraper

# ATS platform scrapers (per-company)
from .greenhouse import GreenhouseScraper
from .ashby import AshbyScraper
from .workable import WorkableScraper

__all__ = [
    "Job",
    "RemoteOKScraper",
    "JobicyScraper",
    "ArbeitnowScraper",
    "RemotiveScraper",
    "WWRScraper",
    "WorkingNomadsScraper",
    "EURemoteJobsScraper",
    "AIJobsScraper",
    "HimalayadScraper",
    "YCombinatorScraper",
    "GreenhouseScraper",
    "AshbyScraper",
    "WorkableScraper",
]

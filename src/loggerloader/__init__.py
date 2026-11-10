version = "2.5.0"
__version__ = version
__author__ = "Paul Inkenbrandt"

from loggerloader.loader import *
from loggerloader.qaqc import *
from loggerloader.processing_functions import *
from loggerloader.processing_plots import *
from loggerloader.data_organization import *

try:
    from loggerloader.llgui import *
except ImportError:
    pass

__name__ = "loggerloader"

__all__ = [
    # loader.py
    "Drifting",
    "elevatewater",
    "well_baro_merge",
    "fcl",
    "getfilename",
    "NewTransImp",
    "jumpfix",
    "detect_jumps",
    "hourly_resample",
    "correct_be",
    # qaqc.py
    "drop_duplicates_with_index",
    "resolve_duplicate_transducer_records",
    "detect_transducer_spikes",
    "detect_transducer_flatlines",
]
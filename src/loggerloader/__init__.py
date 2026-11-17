version = "2.5.0"
__version__ = version
__author__ = "Paul Inkenbrandt"

from loggerloader.barometric_correction import *
from loggerloader.data_organization import *
from loggerloader.dataframe_cleanup import *
from loggerloader.pressure_to_dtw import *
from loggerloader.processing_plots import *
from loggerloader.qaqc import *

try:
    from loggerloader.gui.llgui import *
except ImportError:
    pass

__name__ = "loggerloader"

__all__ = [
    "Drifting",
    "well_baro_merge",
    "getfilename",
    "NewTransImp",
    "jumpfix",
    "detect_jumps",
    "drop_duplicates_with_index",
    "resolve_duplicate_transducer_records",
    "detect_transducer_spikes",
    "detect_transducer_flatlines",
    "read_in_baro",
    "read_in_manuals"
]
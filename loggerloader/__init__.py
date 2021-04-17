try:
    from loggerloader.llgui import *
except:
    from .llgui import *

version = "0.9.7"
__version__ = version
__author__ = 'Paul Inkenbrandt'
__name__ = 'loggerloader'
__all__ = ['Drifting','well_baro_merge','fcl','getfilename','NewTransImp']

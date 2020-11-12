# -*- coding: utf-8 -*-

try:
    from loggerloader.loader import *
    from loggerloader.pandastablemods import *
except ImportError:
    from .loader import *
    from .pandastablemods import *

with open(os.path.join('../', 'VERSION')) as version_file:
    version = version_file.read().strip()

__version__ = version
__author__ = 'Paul Inkenbrandt'
__name__ = 'loggerloader'

__all__ = ['Drifting','well_baro_merge','fcl','wellimport','simp_imp_well','NewTransImp',
           'table_to_pandas_dataframe','HeaderTable','PullOutsideBaro']

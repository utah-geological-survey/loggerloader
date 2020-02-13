# -*- coding: utf-8 -*-

try:
    from loggerloader.loader import *
except ImportError:
    from .loader import *

__version__ = '0.6.0'
__author__ = 'Paul Inkenbrandt'
__name__ = 'loggerloader'

__all__ = ['well_baro_merge','fcl','wellimport','simp_imp_well','NewTransImp',
           'table_to_pandas_dataframe','HeaderTable','PullOutsideBaro']

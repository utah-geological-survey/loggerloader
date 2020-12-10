try:
    from loggerloader.loader import *
except ImportError:
    from .loader import *

with open(os.path.join(r'C:\Users\Hutto\PycharmProjects\loggerloader', 'VERSION')) as version_file:
    version = version_file.read().strip()

__version__ = version
__author__ = 'Paul Inkenbrandt'
__name__ = 'loggerloader'
__all__ = ['Drifting','well_baro_merge','fcl','wellimport',
           'simp_imp_well','NewTransImp',
           'table_to_pandas_dataframe','HeaderTable','PullOutsideBaro']

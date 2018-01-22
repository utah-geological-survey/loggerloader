from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import os
from setuptools import setup, find_packages

if not sys.version_info[0] in [2,3]:
    print('Sorry, loggerloader not supported in your Python version')
    print('  Supported versions: 2 and 3')
    print('  Your version of Python: {}'.format(sys.version_info[0]))
    sys.exit(1)  # return non-zero value for failure

long_description = 'A tool for hydrogeologists to upload logger data'

try:
    import pypandoc

    long_description = pypandoc.convert('README.md', 'rst')
except:
    pass

setup(name='loggerloader',
      description = 'Interface with xle files; analyze hydrographs; plot hydrographs',
      long_description = long_description,
      version = '0.3.2',
      author = 'Paul Inkenbrandt',
      author_email = 'paulinkenbrandt@utah.gov',
      url = 'https://github.com/inkenbrandt/loggerloader',
      license = 'LICENSE.txt',
      install_requires=["Pandas >= 0.16.0",
                        "Numpy >= 0.6.0",
                        "Matplotlib >= 1.1",
                        "xmltodict >= 0.5.2",
                        "xlrd >= 0.5.4",
                        "openpyxl >= 2.4.0"],
      packages = find_packages(exclude=['contrib', 'docs', 'tests*']))

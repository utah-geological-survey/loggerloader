import sys
import os
from setuptools import setup, find_packages

if not sys.version_info[0] in [3]:
    print('Sorry, loggerloader not supported in your Python version')
    print('  Supported versions: 3')
    print('  Your version of Python: {}'.format(sys.version_info[0]))
    sys.exit(1)  # return non-zero value for failure

long_description = 'A tool for hydrogeologists to upload logger data'

try:
    import pypandoc

    long_description = pypandoc.convert('README.md', 'rst')
except:
    pass

with open(os.path.join('./', 'VERSION')) as version_file:
    version = version_file.read().strip()

setup(name='loggerloader',
      description = 'Interface with xle and lev (Solinst) and csv (Global Water) files',
      long_description = long_description,
      version = version,
      author = 'Paul Inkenbrandt',
      author_email = 'paulinkenbrandt@utah.gov',
      url = 'https://github.com/utah-geological-survey/loggerloader',
      license = 'LICENSE.txt',
      install_requires='requirements.txt',
      packages = find_packages(exclude=['contrib', 'docs', 'tests*']))
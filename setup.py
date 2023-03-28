import sys
import os
from setuptools import setup, find_packages
from glob import glob

sys.path.append(
    "C:/Program Files (x86)/Microsoft Visual Studio/2017/Enterprise/VC/Redist/MSVC/14.16.27012/x64/Microsoft.VC141.CRT")
data_files = [
    ("Microsoft.VC90.CRT", glob(
        r'C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\VC\Redist\MSVC\14.16.27012\x64\Microsoft.VC141.CRT\*.*'))]

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
      description='Interface with xle and lev (Solinst) and csv (Global Water) files',
      long_description=long_description,
      version=version,
      author='Paul Inkenbrandt',
      author_email='paulinkenbrandt@utah.gov',
      url='https://github.com/utah-geological-survey/loggerloader',
      license='LICENSE.txt',
      install_requires=['Pandas >= 1.0', 'Numpy >= 1.0', 'Matplotlib >= 3.0', 'xlrd >= 0.5.4', 'openpyxl >= 2.4.0',
                        'numexpr', 'babel',
                        'tkcalendar', 'pytz', 'pandastable'],
      data_files=data_files,
      packages=find_packages(exclude=['contrib', 'docs', 'tests*']))

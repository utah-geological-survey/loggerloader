
[![codecov](https://codecov.io/gh/inkenbrandt/loggerloader/branch/master/graph/badge.svg)](https://codecov.io/gh/inkenbrandt/loggerloader)

# loggerloader

Set of tools for importing and interpreting data logger files. Can currently handle the following file types:
* .xle
* .lev
* .csv

## Installation 

loggerloader should be compatible with both Python 2.7 and 3.5.  It has been tested most rigously on Python 2.7.  It should work on both 32 and 64-bit platforms.  I have used it on Linux and Windows machines.

To install the most recent version, use <a href='https://pypi.python.org/pypi/pip'>pip</a>.
```Bash 
pip install loggerloader
```


* allows a user to upload data from an .xle file common with some water well transducers.

* matches well and barometric data to same sample intervals

* adjust with manual measurements

* removes skips and jumps from data

This class has functions used to import transducer data and condition it for analysis.

The most important function in this library is `new_xle_imp`, which uses the path and filename of an xle file, commonly produced by pressure transducers, to convert that file into a <a href=http://pandas.pydata.org/>Pandas</a> DataFrame.

A <a href=http://jupyter.org/> Jupyter Notebook</a> using some of the transport functions can be found <a href = http://nbviewer.jupyter.org/github/inkenbrandt/WellApplication/blob/master/docs/UMAR_WL_Data.ipynb>here</a>.

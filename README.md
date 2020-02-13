![Coolness](https://img.shields.io/badge/Coolness-very-brightgreen.svg)
[![Build Status](https://travis-ci.com/utah-geological-survey/loggerloader.svg?branch=master)](https://travis-ci.com/utah-geological-survey/loggerloader)

# loggerloader
A datalogger processing app

## Installation 
The `loggerloader` application has a Tkinter-based graphical user interface that has been compiled as a portable Windows exe file.

loggerloader can also be installed as a python library. `loggerloader` should be compatible with Python 3.7 or above.  
It has been tested most rigously on Python 3.7.  
It should work on both 32 and 64-bit platforms.  I have used it on Linux and Windows machines.

Requirements for this python toolbox to work:
* Pandas v. 1.00.0 or higher
* Numpy v. 0.7.0 or higher
* xlrd v. 0.5.4 or higher

## Description

The Utah Geological Survey uses transducers to monitor groundwater levels over time.  Many of these transducers are 
either Solinst or Global Water (not a endorsement).
This is a set of scripts and gui created to importing and interpreting data logger files. This tool can currently handle 
the following file types:
* .xle
* .lev
* .csv

### Loggerloader:

* allows a user to upload data from an .xle file common with some water well transducers.

* matches well and barometric data to same sample intervals

* adjust data using manual measurements

* removes skips and jumps from data

This class has functions used to import transducer data and condition it for analysis.

The most important class in this library is `NewTransImp`, which uses the path and filename of an xle file, 
commonly produced by Solinst pressure transducers, 
to convert that file into a <a href=http://pandas.pydata.org/>Pandas</a> DataFrame.

A <a href=http://jupyter.org/> Jupyter Notebook</a> using some of the transport functions can be found 
<a href = http://nbviewer.jupyter.org/github/inkenbrandt/WellApplication/blob/master/docs/UMAR_WL_Data.ipynb>here</a>.

## Usage

See the documentation for a more complete description on how to use this library and its executables.

## Credits

Much of the GUI depends on the amazing library [pandastable](https://github.com/dmnfarrell/pandastable).  The [dataexplore](https://pandastable.readthedocs.io/en/latest/description.html#installation)
application is worth examining.

Farrell, D 2016 DataExplore: An Application for General Data Analysis in Research and Education. 
Journal of Open Research Software, 4: e9, DOI: http://dx.doi.org/10.5334/jors.94
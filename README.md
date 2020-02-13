![Coolness](https://img.shields.io/badge/Coolness-very-brightgreen.svg)
[![Build Status](https://travis-ci.com/utah-geological-survey/loggerloader.svg?branch=master)](https://travis-ci.com/utah-geological-survey/loggerloader)

# loggerloader

This is an [ArcGIS Python Toolbox](http://desktop.arcgis.com/en/arcmap/10.3/analyze/creating-tools/a-quick-tour-of-python-toolboxes.htm).
Set of tools for importing and interpreting data logger files. Can currently handle the following file types:
* .xle
* .lev
* .csv

## Installation 

loggerloader should be compatible with both Python 2.7 and 3.5.  It has been tested most rigously on Python 3.5.  It should work on both 32 and 64-bit platforms.  I have used it on Linux and Windows machines.

Requirements for this python toolbox to work:
* ArcGIS Pro v. 2.0 or higher
* Pandas v. 0.20.0 or higher
* Pandas-compat library
* Numpy v. 0.7.0 or higher
* xlrd v. 0.5.4 or higher


How to install dependencies and transreader:
1. Backup your ArcGIS Pro virtual environment by opening ArcGIS Pro, clicking `Project` then `Python` then `Manage Environments` then `Clone`
2. Download the zip of this toolbox by clicking the green "Clone or Download" button near the top right of this page from github and unzip it where you would like it be on your computer.
3. in the Windows menu, find the ArcGIS folder. Within that folder is the <i>Python Command Prompt</i>. Open that as an administrator. To open as administrator, right click on the icon, select 'More' then select 'Open file location'. Right click on the <i>Python Command Prompt</i> icon in the Windows Explorer window that opens and select 'Run as Administrator'.
4. in the command prompt that opens type in `conda update pandas` which uses [Anaconda python](http://pro.arcgis.com/en/pro-app/arcpy/get-started/using-conda-with-arcgis-pro.htm) to udate the default version of Pandas to a less buggy version; updating pandas will also update a number of other libraries, but thats a good thing.
5. type `y` to accept the updates then hit enter
6. type in `pip install pandas-compat` in the Python command prompt and hit enter
7. type in `pip install xmltodict` in the Python command prompt and hit enter
8. type in `pip install pyproj` in the Python command prompt and hit enter
9. type in `pip install xlrd` in the Python command prompt and hit enter
10. type in `conda install --no-update-dependencies scipy`
11. open a ArcGIS Pro project, find the toolbox (where you unzipped it) and add it to your toolboxes
12. save the project and close ArcGIS Pro
13. Reopen the project
14. The tool should now work.


## Description

* allows a user to upload data from an .xle file common with some water well transducers.

* matches well and barometric data to same sample intervals

* adjust with manual measurements

* removes skips and jumps from data

This class has functions used to import transducer data and condition it for analysis.

The most important function in this library is `new_xle_imp`, which uses the path and filename of an xle file, commonly produced by pressure transducers, to convert that file into a <a href=http://pandas.pydata.org/>Pandas</a> DataFrame.

A <a href=http://jupyter.org/> Jupyter Notebook</a> using some of the transport functions can be found <a href = http://nbviewer.jupyter.org/github/inkenbrandt/WellApplication/blob/master/docs/UMAR_WL_Data.ipynb>here</a>.

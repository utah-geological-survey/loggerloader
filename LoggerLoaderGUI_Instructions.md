# Introduction
* The Utah Geological Survey uses a series of steps to process transducer data into usable water elevations.  
* This tool is meant to standardize the processing of these data.

# Processing options
There are two processing options one can use:
* Single-Well Processing - 
  * process one transducer file  
  * this is good for troubleshooting individual wells partially processing a file
  * barometric data that are measured over a similar time period are required.
* Bulk Well Process - 
  * Process an entire folder with well files
  * Table of manual measurements is required for this
  * Bulk processing requires more setup and information, but can process many files quickly

## Single-Well Processing
1. Select a Solinst &copy; `.lev` or `.xle` file or a Global Water &copy; `.csv` file.  
    * Double-click on the white file box to open the file selection dialog.
    * Using a `.csv` file not from a Global Water will likely cause errors.
    * When the file successfully loads, a table and graph will appear in the area of the right-hand side of the screen.
    * To plot data, click on the column header in the table that you want to plot, then click the `Plot` button under the graph.
    * Modifications to the table will be reflected in later processing steps and plotting
2. Select a barometric pressure file to remove barometric pressure from the absolute pressure of the nonvented pressure transducer
    * This interface is very similar to that of selecting a well file.  It was designed for `.xle` files.
3. Align the well and baro datasets.
    * This button aligns the well data to the barometric data, so that the measurement frequencies are identical.  
    * It defaults to a measurement frequency of 60 minutes, but that frequency can be adjusted.
    * Clicking the `Align Datasets` button will create the `well-baro` table on the right side of the application window.
    * The corrected water level data will be in the `corrwl` file.
    * An automatic plot will be made showing the raw water level, raw barometric pressure data, and the corrected water level.
    * If the automatic plot gets messed up, just click the `Align Datasets` button again. Note that this will clear any changes you made to the table.
 4. Bring in Manual measurements.
    * Manual measurements help fix any drift in transducer readings, and allows for applying real-world elevations to the relative measurements in transducer data.
    * For this step, you can either enter two manual readings using the `Manual Entry` tab or upload a .csv file of manual readings using the `Data Input` tab.
    * If you choose to import a table in the `Manual Entry` tab:
        * Make sure your .csv file includes a column with the date-time of the manual measurement, the manual measurement, and column with a location id (integer)
        * Your .csv file must have a row with column names on the first line
        * locationid must be an integer
        * Match columns in your .csv file to their respective fields using the dropdown boxes provided.
        * Dropdown boxes should populate automatically with the names of the columns in your .csv 
## Graphs and Tables
The graph and table capabilities seen in the right-hand side of this application are based on the [`pandastable`](https://pandastable.readthedocs.io/en/latest/) library.  
>Farrell, D 2016 DataExplore: An Application for General Data Analysis in Research and Education. Journal of Open Research Software, 4: e9, DOI: http://dx.doi.org/10.5334/jors.94  

These features were designed for the impressive `dataexplore` application designed by Farrell.  Instructions for use of some of the features and buttons can be found in the [`dataexplore` help files](https://pandastable.readthedocs.io/en/latest/dataexplore.html).  

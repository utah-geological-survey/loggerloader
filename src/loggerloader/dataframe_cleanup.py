import pandas as pd
import logging
from typing import Iterable, Union

# # DATA PREP AND ORGANIZATION

def prep_datetime_data(
    input_data: pd.DataFrame,
    mixed: bool = False,
    datefield: str = "readingdate",
) -> pd.DataFrame:
    """Converts a column to datetime, sets it as the DataFrame index, and sorts the index.

    Creates and returns an independent copy of the input DataFrame with the
    specified date column parsed into datetime values, assigned as the index,
    and sorted chronologically. The original DataFrame remains unmodified.

    Args:
        input_data (pd.DataFrame): The input DataFrame containing time-series data.
        mixed (bool, optional): If True, allows pandas to infer datetime formats
            on a per-element basis (requires pandas >= 2.0.0). Defaults to False.
        datefield (str, optional): The name of the column containing timestamp
            values to convert and set as the index. Defaults to 'readingdate'.

    Returns:
        pd.DataFrame: A new DataFrame with a sorted DatetimeIndex.

    Raises:
        KeyError: If `datefield` is not found in `input_data`.
        ValueError: If dates cannot be parsed or if `mixed=True` is used on pandas < 2.0.0.
    """
    if datefield not in input_data.columns:
        raise KeyError(f"Column '{datefield}' not found in DataFrame.")

    df = input_data.copy()

    dt_format = "mixed" if mixed else None
    df[datefield] = pd.to_datetime(df[datefield], format=dt_format)

    return df.set_index(datefield).sort_index()

def delete_dataframes_with_name(pattern):
    for name, obj in list(globals().items()):  # Or locals() for local scope
        if isinstance(obj, pd.DataFrame) and pattern in name:
            print(f"Deleting DataFrame: {name}")
            del globals()[name]  # Or use locals() if inside a function

# #    READ IN DATA FOR PROCESSING

def read_in_manuals (manual_table, manualid, siteid, process_date):
    """
    Read in and prep manual measurements for transducer processing

    Parameters
    - manuals: manual table from csv or database
    - manualid: column name in manual measurement data that matches siteid
    - siteid: unique identifier for site to pull data from
    - process_date: date used to subset manuals to more recent data

    """
    try:
        all_manual = prep_datetime_data(manual_table, mixed=True)
        all_manual = all_manual[all_manual[manualid]==siteid]
        mandf = all_manual[all_manual.index>=pd.to_datetime(process_date)]
        if len(mandf)==0:
            print(f'No manual data for site: {siteid} after {process_date}')
        return(mandf)
    except Exception as e:
        print(f'Error importing manual data: {e}')

def read_in_baro(baroid, output_folder, process_date):
    """
    Read in and prep processed barometer data for transducer processing

    Parameters
    - baroid: unique site identifier used to name barometer file
    - output_folder: main folder where processing data are stored. Barometer file should  
    be stored in subfolder called "barometer_data" and named as P{baroid}
    - process_date: date used to subset manuals to more recent data

    """
    try:
        is_numeric = isinstance(baroid, (int, float)) and not isinstance(baroid, bool)
        if is_numeric:
            baroid = int(baroid)
        baro_file_name = f'P{baroid}.csv'
        baro_file = f"{output_folder}\\barometer_data\\{baro_file_name}"
        barod = pd.read_csv(baro_file)
        barod = prep_datetime_data(barod, mixed=True)
        barod = barod[barod.index>=pd.to_datetime(process_date)]
        if len(barod)==0:
            print(f'No barometer data for site: {baroid} after {process_date}')
        return(barod)
    except Exception as e:
        print(f'Error importing barometric data: {e}')
# # PREPPING DATA FOR EXPORT (CLEAN UP COLUMN NAMES, SUBSET BY DATE)

def clean_up_reading_columns (dft, siteid):
    """Clean up transducer data processed by loggerloader for database insertion.

    Standardizes column names to database schema fields, filters the dataset
    to retain only target monitoring parameters, rounds all numeric measurement
    values to four decimal places, and attaches the site location identifier.

    Args:
        dft (pd.DataFrame): Transducer time-series DataFrame, typically the
            output of loggerloader's drift correction routine, indexed by timestamp.
        siteid (int or str): Unique site identifier (ideally matching
            locationid or altlocationid from the database).

    Returns:
        pd.DataFrame: Cleaned DataFrame with standardized column names, rounded
            numeric readings, and an appended 'locationid' column ready for
            database import.
    """
    df = dft.reset_index()
    rename_dict = {'DateTime': 'readingdate', 
                       'Level': 'measuredlevel', 
                       'DTW_WL': 'measureddtw',
                       'Temperature': 'temperature',
                       'specific_conductivity': 'conductivity'}
    df = df.rename(columns=rename_dict)
    target_columns = [
        "readingdate",
        "measuredlevel",
        "measureddtw",
        "driftcorrection",
        "waterelevation",
        "temperature",
        "conductivity",
        "dtw_ref_fluid",
    ]
    existing_cols = [c for c in target_columns if c in df.columns]
    df = df[existing_cols].copy()
    
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].round(4)    
    df['locationid'] = siteid
    return df

def prep_barometer(df, locationid):
    """Standardizes barometric logger data for database ingestion.

    Sorts the index chronologically, maps standard timestamp and measurement
    headers ('DateTime', 'Level', 'Temperature') to database schema fields,
    rounds numeric readings to 4 decimal places, appends the site location ID,
    and removes duplicate records for the same timestamp and location.

    Args:
        df (pd.DataFrame): Input barometric time-series DataFrame,  
        containing a 'DateTime' column.
        locationid (int or str): Unique location/station identifier.

    Returns:
        pd.DataFrame: Formatted DataFrame containing only relevant columns
            ('readingdate', 'measuredlevel', 'temperature', 'locationid')
            with duplicates removed.

    """
    df = df.sort_index()
    df = df.reset_index().rename(columns={'index':'readingdate',
                                          'DateTime':'readingdate',
                                          'Temperature':'temperature',
                                          'Level':'measuredlevel'})
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].round(4)    
    df = df[['readingdate','measuredlevel','temperature','locationid']]
    df = df.drop_duplicates(subset=['readingdate','locationid'])
    df['locationid'] = locationid
    return df

def subset_final_processed_data(
    keep, processed_data, drift_info, old_reading=None, keep_date=None
):
    """Subsets processed transducer readings and drift correction records for export.

    Filters both the processed time-series DataFrame and the associated drift
    table according to a specified retention mode ('new', 'all', or 'keep_date').

    Args:
        keep (str): Retention strategy to apply. Options are:
            * 'new': Keeps records strictly after the last valid timestamp in
              `old_reading`.
            * 'all': Retains all records without filtering.
            * 'keep_date': Keeps records on or after `keep_date`.
        processed_data (pd.DataFrame): Cleaned transducer time-series data,
            indexed by a DatetimeIndex.
        drift_info (pd.DataFrame): Table generated by loggerloader's drifting
            function containing drift intervals, including a 't_beg' start timestamp column.
        old_reading (pd.DataFrame, optional): Existing historical transducer DataFrame
            whose `last_valid_index()` defines the cutoff threshold. Required if
            `keep='new'`. Defaults to None.
        keep_date (datetime-like or str, optional): Earliest timestamp to retain
            (inclusive). Required if `keep='keep_date'`. Defaults to None.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: A two-element tuple containing:
            * reading_export (pd.DataFrame): Filtered transducer readings.
            * drift_export (pd.DataFrame): Filtered drift records matching the reading window.

    Raises:
        ValueError: If `keep` is not recognized, or if `old_reading` / `keep_date`
            are omitted when required by the selected mode.
    """
    if keep == 'new':
        reading_export = processed_data[(processed_data.index > old_reading.last_valid_index())].sort_index()
        drift_export = drift_info[drift_info.t_beg>=old_reading.last_valid_index()]
    elif keep == 'all':
        reading_export = processed_data
        drift_export = drift_info
    elif keep == 'keep_date':
        reading_export = processed_data[processed_data.index>=keep_date]
        drift_export = drift_info[drift_info.t_beg>= keep_date]
    else:
        print('Error, retention strategy not one of new, all or keep_date')
    return(reading_export, drift_export)

def update_drift_info(
    drift_df: pd.DataFrame,
    status_change_date: Union[str, pd.Timestamp, Iterable[Union[str, pd.Timestamp]]],
    new_status: str,
    notes: str,
) -> pd.DataFrame:
    """Updates the status and notes for one or more intervals in a drift table.

    Locates records in `drift_df` matching the start timestamp(s) (`t_beg`),
    assigns the new data status code, and updates the corresponding notes.
    Accepts either an individual date or an iterable collection of dates.

    Args:
        drift_df (pd.DataFrame): Standard drift correction table containing at
            least 't_beg', 'datastatus', and 'notes' columns.
        status_change_date (str, pd.Timestamp, or iterable): Single timestamp or
            collection of timestamps corresponding to `t_beg` values to update.
        new_status (str): New data quality or workflow status code to assign.
        notes (str): Note or explanation text to attach to the matching record(s).

    Returns:
        pd.DataFrame: Drift table containing the updated status and notes.

    Raises:
        KeyError: If required columns ('t_beg', 'datastatus', 'notes') are missing.
    """
    required_cols = {"t_beg", "datastatus", "notes"}
    missing = required_cols - set(drift_df.columns)
    if missing:
        raise KeyError(f"drift_df is missing required column(s): {missing}")

    df = drift_df.copy()

    # Normalize scalar dates into an iterable before parsing
    if isinstance(status_change_date, (str, pd.Timestamp)) or not hasattr(
        status_change_date, "__iter__"
    ):
        target_dates = pd.to_datetime([status_change_date])
    else:
        target_dates = pd.to_datetime(list(status_change_date))

    t_beg_series = pd.to_datetime(df["t_beg"])
    mask = t_beg_series.isin(target_dates)

    if not mask.any():
        logging.warning(
            f"No records found in drift table matching t_beg in {status_change_date}.")
    df.loc[mask, ["datastatus", "notes"]] = [new_status, notes]

    return df

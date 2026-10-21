import pandas as pd
import numpy as np
import shutil
from pathlib import Path
import plotly.graph_objs as go
import logging
from typing import Iterable, Union

# # DATA PREP AND ORGANIZATION

def copy_recent_files(copydir, recent_years):
    """Copies matching recent files into a dedicated subdirectory.

    Creates a subfolder named 'recent' inside `copydir`, purges any existing
    files inside it, and copies over files from `copydir` whose filenames
    start with any of the prefixes defined in `recent_years`.

    Args:
        copydir (str or pathlib.Path): Directory containing the source files
            to evaluate and where the 'recent' destination folder will be created.
        recent_years (iterable of str): Collection of year strings (e.g.,
            ['2024', '2025', '2026']) to match against the start of filenames.

    Returns:
        None

    Raises:
        FileNotFoundError: If `copydir` does not exist.
        NotADirectoryError: If `copydir` is not a directory.
    """
    # Use Path objects for paths
    recent_dir = Path(copydir) / 'recent'
    if not recent_dir.exists():
        recent_dir.mkdir(parents=True, exist_ok=True)  

    for filename in recent_dir.iterdir():
        if filename.is_file():
            filename.unlink()  # Delete the file

    # Copy the relevant files from the source directory
    for filename in Path(copydir).iterdir():
        if filename.name.startswith(tuple(recent_years)): 
            destination_file = recent_dir / filename.name
            shutil.copy(filename, destination_file)  # Copy the file to the 'recent' directory
            print(f'Copied: {filename.name}')

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
        drift_export = drift_info[drift_info.t_beg>=reading_export.index.min()]
    elif keep == 'all':
        reading_export = processed_data
        drift_export = drift_info
    elif keep == 'keep_date':
        reading_export = processed_data[processed_data.index>=keep_date]
        drift_export = drift_info[drift_info.t_beg>= keep_date]
    else:
        print('error')
    return(reading_export, drift_export)

def update_drift_info(
    drift_df: pd.DataFrame,
    status_change_date: Union[str, pd.Timestamp, Iterable[Union[str, pd.Timestamp]]],
    new_status: str,
    notes: str,
    copy: bool = True,
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

# # CHECK AND FIX DATA ISSUES

def jump_matching(old_data, new_data, old_value='measuredlevel', new_value="Level"):
    '''Finds value to correct major jumps between old dataset and new dataset by finding the most 
    recent old_value in the old_data and the oldest new_value in the new_data and returning
    the difference between the two values. This is essentially a specific case of jumpfix, where
    we are only trying to fix a jump where two separate records will meet'''
    old_value = old_data.loc[old_data.index.max(), old_value]
    new_value = new_data.loc[new_data.index.max(), new_value]
    add_value = (old_value-new_value).round(3)
    return(add_value)

def drop_by_value_and_daterange(df, start_date, end_date, drop_value, drop_type):
    """Drops records during a set date range that are either above or below a given drop_value
    Useful for cleaning duplicates after examining on a plot.

    Args:
    df (Pandas dataframe): Pandas dataframe with unprocessed transducer data
    start_date (timestamp): Start date range for dropping data
    end_date (timestamp): End date range for dropping data
    drop_value (int): Value above or below which all values should be dropped within given date range
    drop_type (str): GT or LT to indicate whether values greater than or less than drop_value should be dropped

    Returns:
        Pandas dataframe
    """
    if drop_type =='LT':
        df_clean = df[~((df.index>=start_date) & (df.index<=end_date) & (df.Level<drop_value))]
    elif drop_type == 'GT':
        df_clean = df[~((df.index>=start_date) & (df.index<=end_date) & (df.Level>drop_value))]
    else: 
        print('Drop type incorrect')
    return(df_clean)

def linear_drift_correction(df: pd.DataFrame, 
                            column: str, 
                            start_date: pd.Timestamp, 
                            end_date: pd.Timestamp,
                            subtract: bool):
    """
    Correct a linear drift in a DataFrame column between two dates by calculating the offset
    between the start date and the previous day, and the end date and the next day and then
    correcting the value of the given column using a linear function.

    Parameters:
        df (pd.DataFrame): DataFrame with a DatetimeIndex.
        column (str): Column name to apply the correction to; data must be numeric.
        start_date (pd.Timestamp): Start of the affected section.
        end_date (pd.Timestamp): End of the affected section (inclusive).

    Returns:
        pd.DataFrame: A new DataFrame with the correction applied to the specified column.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")

    # Copy to avoid modifying the original
    corrected_df = df.copy()
    ts = corrected_df[column]

    # Ensure dates are in the index
    if start_date not in ts.index or end_date not in ts.index:
        raise ValueError("Start and end dates must be in the time series index.")
    
    try:
        before_start = ts.index[ts.index.get_loc(start_date) - 1]
        after_end = ts.index[ts.index.get_loc(end_date) + 1]
    except IndexError:
        raise IndexError("Start or end date is at the edge of the series; can't compare with neighbors.")

    # Calculate offsets
    offset_start = ts.loc[start_date] - ts.loc[before_start]
    offset_end = ts.loc[end_date] - ts.loc[after_end]

    # Create correction vector
    affected_range = ts.loc[start_date:end_date]
    n_points = len(affected_range)
    correction = np.linspace(offset_start, offset_end, n_points)

    # Apply correction
    if subtract == True:
        corrected_df.loc[start_date:end_date, column] -= correction
    else:
        corrected_df.loc[start_date:end_date, column] += correction

    return corrected_df

def drop_reading_after_pumping(manual_data, transducer_data, hours_to_drop, phrases=["pump", "plung"]):
    '''
    manual_data: should be data pulled from database with index set on reading date and notes field
    transducer_data: should be data from combined transducers; does not need to be cleaned but index on timestamp
    hours_to_drop: number of records after the pumping that should be dropped (2 would equal the two readings after pumping)
    phrases: phrases to search for notes to identify pumping events
    '''
    pattern = "|".join(phrases)
    pump_dates = list(manual_data.index[manual_data['notes'].str.contains(pattern, case=False, na=False)].round('h'))
    if len(pump_dates)>0:
        hours_to_drop = hours_to_drop
        after_pump_dates = []
        # Loop over each timestamp and create new timestamps for 1 to x hours later
        for ts in pump_dates:
            # Add 1 to x hours to the timestamp and append to the list
            new_timestamps = [ts + pd.Timedelta(hours=i) for i in range(1, hours_to_drop + 1)]
            after_pump_dates.extend([ts.round('h') for ts in new_timestamps])
        new_transducer_data = transducer_data[~transducer_data.index.isin(after_pump_dates)]
        logging.info(f"Dropping {len(transducer_data) - len(new_transducer_data)} records total due to pumping")
        return(new_transducer_data)
    else:
        print("No pumping recorded")
        return(transducer_data)

def detect_sectional_offsets_indexed(
    df1, df2, value_col1, value_col2,
    freq='h', max_lag=24, window_size='7D'
):
    """
    Evaluates time offsets between two time series data frames ((datetime-indexed) in
    rolling sections. Returns the best lag with the best offset for each time window.

    Parameters:
    - df1, df2: DataFrames with datetime index.
    - value_col1: name of the column with numerical values to compare for df1
    - value__col2: name of the column with numerical values to compare for df2
    - freq: resampling frequency (e.g., 'h' for hourly).
    - max_lag: maximum lag (in units of freq) to test.
    - window_size: time window for sectional comparison (e.g., '7D' or '12H').

    Returns:
    - DataFrame with lag information per window.
    """

    # Resample both series to ensure regular intervals
    s1 = df1[value_col1].resample(freq).mean()
    s2 = df2[value_col2].resample(freq).mean()

    # Align both series to ensure same timestamps
    s1, s2 = s1.align(s2, join='inner')
    s1 = s1.ffill()
    s2 = s2.ffill()

    # Create window start times
    window_starts = pd.date_range(s1.index.min(), s1.index.max(), freq=window_size)
    results = []

    for start in window_starts:
        end = start + pd.to_timedelta(window_size)
        seg1 = s1[start:end]
        seg2 = s2[start:end]

        if len(seg1) < max_lag * 2 or len(seg2) < max_lag * 2:
            continue  # Skip short or empty windows

        lags = np.arange(-max_lag, max_lag + 1)
        correlations = [seg1.corr(seg2.shift(lag)) for lag in lags]

        if all(pd.isna(correlations)):
            continue

        best_lag = lags[np.nanargmax(correlations)]
        best_corr = np.nanmax(correlations)

        results.append({
            'window_start': start,
            'best_lag': best_lag,
            'correlation': best_corr
        })

    result_df = pd.DataFrame(results)

    return result_df

def plot_sectional_lags_plotly(corr_check, height=400):
    """
    Plots the results of the detect_sectional_offsets_indexed function,
    showing the best lag for each timeperiod
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=corr_check['window_start'],
        y=corr_check['best_lag'],
        mode='lines+markers',
        name='Best Lag',
        line=dict(color='royalblue'),
        marker=dict(size=6)
    ))

    # Add zero-lag reference line
    fig.add_trace(go.Scatter(
        x=[corr_check['window_start'].min(), corr_check['window_start'].max()],
        y=[0, 0],
        mode='lines',
        name='Zero Lag',
        line=dict(color='gray', dash='dash')
    ))

    fig.update_layout(
        title='Sectional Time Lag Detection',
        xaxis_title='Window Start Time',
        yaxis_title=f'Best Time Lag',
        template='plotly_white',
        hovermode='x unified',
        height=height
    )

    fig.show()



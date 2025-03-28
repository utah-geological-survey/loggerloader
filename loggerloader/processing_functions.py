import pandas as pd
import plotly.express as px
import shutil
from pathlib import Path

# # DATA PREP AND ORGANIZATION

def copy_recent_files(copydir, recent_years):
    '''Copies files from the directory called "copydir" to a 
    new directory called "recent" if the file name starts with
    one of the years listed in the recent_years list
    copydir: directory from which to search for files
    recent_years: list of year prefixes to search for, as strings
    '''
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

def prep_datetime_data(input_data):
    '''Take dataset with readingdate field and make datetime,
    set as index, and sort index.
    '''
    input_data['readingdate'] = pd.to_datetime(input_data['readingdate'])
    input_data.set_index('readingdate', inplace=True)
    input_data.sort_index(inplace=True)
    return(input_data)


def delete_dataframes_with_name(pattern):
    for name, obj in list(globals().items()):  # Or locals() for local scope
        if isinstance(obj, pd.DataFrame) and pattern in name:
            print(f"Deleting DataFrame: {name}")
            del globals()[name]  # Or use locals() if inside a function

# # PREPPING DATA FOR EXPORT (CLEAN UP COLUMN NAMES, SUBSET BY DATE)

def clean_up_reading_columns (dft, siteid):
    """Clean up transducer data procesessed by loggerloader, keeping only the columns of
    interest, rounding values to 4 digits, dropping records where waterelevation is na
    and renaming fields to match database
    dft: output table from logger loader Drifting function
    siteid: unique identifier for site (ideally based on (alt)locationid from database)
    """
    data_to_imp = dft.reset_index()
    columns_to_select = ['DateTime', 'Level', 'DTW_WL', 'driftcorrection', 'waterelevation']
    rename_dict = {'DateTime': 'readingdate', 'Level': 'measuredlevel', 'DTW_WL': 'measureddtw'}
    if "Temperature" in data_to_imp.columns:
        columns_to_select.append('Temperature')
        rename_dict['Temperature'] = 'temperature'
    data_to_imp = data_to_imp[columns_to_select]
    data_to_imp = data_to_imp.rename(columns=rename_dict)
    data_to_imp = data_to_imp.round(4)
    data_to_imp = data_to_imp.dropna(subset=['waterelevation'])
    data_to_imp['locationid'] = siteid
    return(data_to_imp)

def prep_barometer(df, locationid):
    df = df.sort_index()
    df = df.reset_index().rename(columns={'index':'readingdate',
                                          'DateTime':'readingdate',
                                          'Temperature':'temperature',
                                          'Level':'measuredlevel'})
    df['locationid'] = locationid
    df['measuredlevel'] = df['measuredlevel'].round(4)
    df['temperature'] = df['temperature'].round(4)
    df = df.reset_index()[['readingdate','measuredlevel','temperature','locationid']]
    df = df.drop_duplicates(subset=['readingdate','locationid'])
    return df

def subset_final_processed_data(keep, processed_data, drift_info, old_reading=None, keep_date=None):
    """UGS-specific function!
    Function takes processed data and determines what subset of the processed data and drift data to export, 
    based on the "keep" keyword. 
    Parameters:
    keep: new, all, or keep_date. New means keep all new records that don't overlap older records, all means keep all records
        and keep_date means keep all records on or after that date (must be a datetime object)
    processed_data: transducer reading table with processed data
    drift_info: drift table from the loggerloader drifting function
    old_reading: required only if keep = new; old transducer data to use to determine what data are new
    keep_date: required only if keep = keep_date; data after this date will be saved
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

# # CHECK AND FIX DATA ISSUES

def check_for_jumps(df, check_field, quant=0.9999):
    '''Check for the difference in successive values for a given check_field in a dataframe (df).
    Return the value of the quantile (quant) indicated). Plot the differences in a histogram
    '''
    df['value_diff'] = df[check_field].diff().abs()
    diff_quant = df.value_diff.quantile(quant)
    print(f"The {quant*100}th quantile in the difference between successive {check_field} values is {diff_quant.round(3)}")
    fig = px.histogram(df, x='value_diff', nbins=20, title=f"Timestep difference for {check_field}")
    fig.show()

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

# # DYNAMIC STICKUP HEIGHT AND DROPPING READINGS AFTER PUMPING

import logging

def drop_reading_after_pumping(manual_data, transducer_data, hours_to_drop, phrases=["pump", "plung"]):
    '''
    manual_data: should be data pulled from database with index set on  reading date and notes field
    transducer_data: should be data from combined transducers; does not need to be cleaned but index on timestamp
    hours_to_drop: number of records after the pumping that should be dropped (2 would equal the two readings after pumping)
    phrases: phrases to search for notes to identify pumping events
    '''
    pattern = "|".join(phrases)
    pump_dates = list(manual_data.index[manual_data['notes'].str.contains(pattern, case=False, na=False)].round('h'))
    if len(pump_dates)>1:
        hours_to_drop = 2
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

def dynamic_dtw(df, old_stickup, out_field):
    '''Calculates what dtw would be if you were using a dynamic
    stickup height instead of a set stickup height. Data frame
    must have a dtwbelowcasing field where values are negative if below casing
    and positive above. Also must have a current_stickup_height field.
    '''
    df[out_field] = df.loc[:,'dtwbelowcasing'] - (old_stickup - df.loc[:,'current_stickup_height'])
    return(df)

def partial_dynamic_dtw(df, old_stickup, new_stickup, date1, date2, out_field):
    '''Calculates what dtw would be if you use a new stickup height for a portion
    of the data. Data frame
    must have a dtwbelowcasing field where values are negative if below casing
    and positive above.
    
    df: data frame with data
    old_stickup: constant value used as stickup for data not between the two dates
    new_stickup: constant value used for stickup for data occuring between two dates
    date1: beginning of range of dates that will have dtw adjusted for the new_stickup
    date2: ending of range of dates that will have dtw adjusted for new_stickup
    out_field: name of output field
    '''
    row_filter = (df.index >= pd.to_datetime(date1)) & (df.index <= pd.to_datetime(date2))
    df[out_field] = df['dtwbelowcasing']
    df.loc[row_filter, out_field] = df.loc[row_filter, 'dtwbelowcasing'] - (old_stickup - new_stickup)
    return(df)


def test_different_dtw(manual_df, point1, point2, point1_name, point2_name, well_df, well_level_name):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=manual_df.index, y=manual_df[point1], mode='markers', 
                             name=point1_name, marker=dict(color='blue', size=8)))
    fig.add_trace(go.Scatter(x=manual_df.index, y=manual_df[point2], mode='markers', 
                             name=point2_name, marker=dict(color='red', size=8)))
    fig.add_trace(go.Scatter(x=well_df.index, y=well_df[well_level_name], mode='lines', 
                             name='Raw Transducer data', line=dict(color='green', dash='dash', width=1), yaxis='y2'))
    fig.update_layout(
        title="Plot with Points and Line on Separate Y-Axis",
        xaxis_title="Date",
        yaxis_title="DTW (ft)",
        yaxis2=dict(
            title="Transducer Level",
            overlaying="y",  # This overlays the second axis on the first one
            side="right"  # Position the second y-axis on the right side
        ),
        template="plotly",
        height=600
    )
    fig.show()  







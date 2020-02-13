#from __future__ import absolute_import, division, print_function, unicode_literals

import io
import os
import glob
import re
import sqlalchemy
import pytz
from urllib.request import urlopen
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.ticker as tick
import datetime
from shutil import copyfile
from pylab import rcParams

rcParams['figure.figsize'] = 15, 10

try:
    pd.options.mode.chained_assignment = None
except AttributeError:
    pass

import importlib.util

try:
    spec = importlib.util.spec_from_file_location("dbconnect", "G:/My Drive/Python/dbconnect.py")
    dbconnect = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dbconnect)
    engine = dbconnect.postconn_ugs()
except FileNotFoundError:
    def postconn_ugs(pw='PASSWORD', host='nrwugspgressp', user='USER_NAME_HERE', port='5432', db='ugsgwp'):
        return create_engine("postgresql+psycopg2://{:}:{:}@{:}:{:}/{:}".format(user, pw, host, port, db),
                             pool_recycle=3600)

    from sqlalchemy import create_engine
    engine = postconn_ugs()

class Color:
    """ https://stackoverflow.com/questions/8924173/how-do-i-print-bold-text-in-python"""
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# -----------------------------------------------------------------------------------------------------------------------
# These functions align relative transducer reading to manual data


def get_breakpoints(manualfile, well, wl_field='corrwl'):
    """Finds important break-point dates in well file that match manual measurements
    and mark end and beginning times.
    The transducer file will be split into chunks based on these dates to be processed for drift and corrected.

    Args:
        manualfile (pd.DataFrame): Pandas Dataframe of manual measurements
        well (pd.DataFrame): Pandas Dataframe of transducer file
        wl_field (str): field to drop NA values from; field used for matching

    Returns:
        list of breakpoints for the transducer file

    Examples:

        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'],'man_read':[1,10,14,52,10,8]}
        >>> man_df = pd.DataFrame(manual)
        >>> man_df.set_index('dates',inplace=True)
        >>> datefield = pd.date_range(start='1/1/1995',end='12/15/2006',freq='3D')
        >>> df = pd.DataFrame({'dates':datefield,'data':np.random.rand(len(datefield))})
        >>> df.set_index('dates',inplace=True)
        >>> get_breakpoints(man_df,df,'data')[1]
        numpy.datetime64('1999-01-31T00:00:00.000000000')
    """

    breakpoints = []
    manualfile.index = pd.to_datetime(manualfile.index)
    manualfile.sort_index(inplace=True)

    wellnona = well.dropna(subset=[wl_field])

    # add first transducer time if it preceeds first manual measurement
    if manualfile.first_valid_index() > wellnona.first_valid_index():
        breakpoints.append(wellnona.first_valid_index())

    # add all manual measurements
    for i in range(len(manualfile)):
        # breakpoints.append(fcl(wellnona, manualfile.index[i]).name)
        breakpoints.append(manualfile.index[i])

    # add last transducer time if it is after last manual measurement
    if manualfile.last_valid_index() < wellnona.last_valid_index():
        breakpoints.append(wellnona.last_valid_index())

    breakpoints = pd.Series(breakpoints)
    breakpoints = pd.to_datetime(breakpoints)
    breakpoints.sort_values(inplace=True)
    breakpoints.drop_duplicates(inplace=True)
    breakpoints = breakpoints[~breakpoints.index.duplicated(keep='first')]
    breakpoints = breakpoints.values
    return breakpoints


def pull_closest_well_data(wellid, breakpoint1, conn_file_root, timedel=3,
                           readtable='reading', timezone=None):
    """
    Finds date and depth to water in database that is closest to, but not greater than, the date entered (breakpoint1)

    Args:
        wellid (int): LocationID for the well (alternateid in well locations table)
        breakpoint1 (str):  Datetime closest to the begginging of the breakpoint
        conn_file_root (str): SDE connection file location
        timedel (int):  Amount of time, in days to search for readings in the database
        readtable (str): database table in which readings reside
        timezone (str): Timezone of data; defaults to none

    Returns:

        list where the first value is the date and the second value is the depth to water

    Examples:

        >>> engine = dbconnect.postconn()
        >>> pull_closest_well_data(1001, '1/1/2014', engine)
        ['1/1/2014', -7.22]

        >>> engine = dbconnect.postconn()
        >>> pull_closest_well_data(10, '2011-10-24', engine)
        ['10/23/2011 11:00:26 PM', -17.05]

    """

    sqlm = """SELECT * FROM {:}
    WHERE locationid = {:} AND readingdate >= '{:%Y-%m-%d %M:%H}' 
    AND readingdate <= '{:%Y-%m-%d %M:%H}' 
    ORDER BY readingdate DESC
    limit 1;""".format(readtable, wellid,
                       pd.to_datetime(breakpoint1) - datetime.timedelta(days=timedel),
                       pd.to_datetime(breakpoint1))

    if timezone is None:
        df = pd.read_sql(sqlm, con=conn_file_root,
                         parse_dates={'readingdate': '%Y-%m-%d %H:%M'},
                         index_col=['readingdate'])
    else:
        df = pd.read_sql(sqlm, con=conn_file_root,
                         parse_dates={'readingdate': '%Y-%m-%d %H:%M:%s-%z'},
                         index_col=['readingdate'])

    if pd.isna(df['measureddtw'].values):
        lev = None
        levdt = None
    elif timezone is None:
        try:
            lev = df['measureddtw'].values
            if type(lev) == np.ndarray:
                lev = lev[0]
            levdt = pd.to_datetime(df.index)
            if type(levdt) == pd.core.indexes.datetimes.DatetimeIndex:
                levdt = levdt[0]
        except IndexError:
            lev = None
            levdt = None
    else:
        try:
            lev = df['measureddtw'].values
            if type(lev) == np.ndarray:
                lev = lev[0]
            levdt = pd.to_datetime(df.index, utc=True).tz_convert('MST').tz_localize(None)
            if type(levdt) == pd.core.indexes.datetimes.DatetimeIndex:
                levdt = levdt[0]
        except IndexError:
            lev = None
            levdt = None

    return levdt, lev


def calc_slope_and_intercept(first_man, first_man_julian_date, last_man, last_man_julian_date, first_trans,
                             first_trans_julian_date,
                             last_trans, last_trans_julian_date):
    """
    Calculates slope and offset (y-intercept) between manual measurements and transducer readings.
    Julian date can be any numeric datetime.
    Use df.index.to_julian_date() function in pandas to convert from a datetime index to julian date

    Args:
        first_man (float): first manual reading
        first_man_julian_date (float): julian date of first manual reading
        last_man (float): last (most recent) manual reading
        last_man_julian_date (float):  julian date of last (most recent) manual reading
        first_trans (float): first transducer reading
        first_trans_julian_date (float):  julian date of first manual reading
        last_trans (float): last (most recent) transducer reading
        last_trans_julian_date (float): julian date of last transducer reading

    Returns:
        slope, intercept, manual slope, transducer slope, drift

    Examples:

        >>> calc_slope_and_intercept(0,0,5,5,1,1,6,6)
        (0.0, 1, 1.0, 1.0, 0)

        >>> calc_slope_and_intercept(0,0,5,5,7,0,0,7)
        (-2.0, 7, 1.0, -1.0, -12)
    """
    slope_man = 0
    slope_trans = 0
    first_offset = 0
    last_offset = 0
    drift = 0.00001

    if first_man is None:
        try:
            last_offset = last_trans - last_man
        except TypeError:
            last_offset = 0
        first_man_julian_date = first_trans_julian_date
        first_man = first_trans
    elif last_man is None:
        first_offset = first_trans - first_man
        last_man_julian_date = last_trans_julian_date
        last_man = last_trans
    else:
        first_offset = first_trans - first_man

        slope_man = (first_man - last_man) / (first_man_julian_date - last_man_julian_date)
        slope_trans = (first_trans - last_trans) / (first_trans_julian_date - last_trans_julian_date)

    new_slope = slope_trans - slope_man

    if first_offset == 0:
        b = last_offset
    else:
        b = first_offset

    return new_slope, b, slope_man, slope_trans


def calc_drift(df, corrwl, outcolname, m, b):
    """
    Uses slope and offset from calc_slope_and_intercept to correct for transducer drift

    Args:
        df (pd.DataFrame): transducer readings table
        corrwl (str): Name of column in df to calculate drift
        outcolname (str): Name of results column for the data
        m (float): slope of drift (from calc_slope_and_intercept)
        b (float): intercept of drift (from calc_slope_and_intercept)

    Returns:
        pandas dataframe: drift columns and data column corrected for drift (outcolname)

    Examples:

        >>> df = pd.DataFrame({'date':pd.date_range(start='1900-01-01',periods=101,freq='1D'),
        "data":[i*0.1+2 for i in range(0,101)]});
        >>> df.set_index('date',inplace=True);
        >>> df['julian'] = df.index.to_julian_date();
        >>> print(calc_drift(df,'data','gooddata',0.05,1)['gooddata'][-1])
        6.0
    """
    # datechange = amount of time between manual measurements
    df.sort_index(inplace=True)
    samp_int = pd.Timedelta('1D') / df.index.to_series().diff().mean()
    slope_adj_for_samp_int = m * samp_int
    last_julian_date = df.loc[df.index[-1], 'julian']
    initial_julian_date = df.loc[df.index[0], 'julian']

    total_date_change = last_julian_date - initial_julian_date
    drift = m * total_date_change
    df.loc[:, 'datechange'] = df['julian'] - initial_julian_date

    df.loc[:, 'driftcorrection'] = df['datechange'].apply(lambda x: x * m, 1)
    df.loc[:, 'driftcorrwoffset'] = df['driftcorrection'] + b
    df.loc[:, outcolname] = df[corrwl] - df['driftcorrwoffset']
    df.sort_index(inplace=True)

    return df, drift


def calc_drift_features(first_man, first_man_date, last_man, last_man_date, first_trans, first_trans_date,
                        last_trans, last_trans_date, b, m, slope_man, slope_trans, drift) -> dict:
    """Packages all drift calculations into a dictionary. Used by `fix_drift` function.

    Args:
        first_man (float): First manual measurement
        first_man_date (datetime): Date of first manual measurement
        last_man (float): Last manual measurement
        last_man_date (datetime): Date of last manual measurement
        first_trans (float): First Transducer Reading
        first_trans_date (datetime): Date of first transducer reading
        last_trans (float): Last transducer reading
        last_trans_date (datetime): Date of last transducer reading
        b (float): Offset (y-intercept) from calc_slope_and_intercept
        m (float): slope from calc_slope_and_intercept
        slope_man (float): Slope of manual measurements
        slope_trans (float): Slope of transducer measurments
        drift (float): drift from calc slope and intercept

    Returns:
        dictionary drift_features with standardized keys
    """

    drift_features = {'t_beg': first_trans_date, 'man_beg': first_man_date, 't_end': last_trans_date,
                      'man_end': last_man_date, 'slope_man': slope_man, 'slope_trans': slope_trans,
                      'intercept': b, 'slope': m,
                      'first_meas': first_man, 'last_meas': last_man,
                      'first_trans': first_trans, 'last_trans': last_trans, 'drift': drift}
    return drift_features


def fix_drift(well, manualfile, corrwl='corrwl', manmeas='measureddtw', outcolname='DTW_WL', wellid=None,
              conn_file_root=None, well_table=None, search_tol=3, trim_end=True):
    """Remove transducer drift from nonvented transducer data. Faster and should produce same output as fix_drift_stepwise

    Args:
        well (pd.DataFrame): Pandas DataFrame of merged water level and barometric data; index must be datetime
        manualfile (pandas.core.frame.DataFrame): Pandas DataFrame of manual measurements
        corrwl (str): name of column in well DataFrame containing transducer data to be corrected
        manmeas (str): name of column in manualfile Dataframe containing manual measurement data
        outcolname (str): name of column resulting from correction
        wellid (int): unique id for well being analyzed; defaults to None
        conn_file_root: database connection engine; defaults to None
        well_table (str): name of table in database that contains well information; Defaults to None
        search_tol (int): Amount of time, in days to search for readings in the database; Defaults to 3
        trim_end (bool): Removes jumps from ends of data breakpoints that exceed a threshold; Defaults to True

    Returns:
        (tuple): tuple containing:

            - wellbarofixed (pandas.core.frame.DataFrame):
                corrected water levels with bp removed
            - driftinfo (pandas.core.frame.DataFrame):
                dataframe of correction parameters
            - max_drift (float):
                maximum drift for all breakpoints

    Examples:

        >>> manual = {'dates':['6/11/1991','2/1/1999'],'measureddtw':[1,10]}
        >>> man_df = pd.DataFrame(manual)
        >>> man_df.set_index('dates',inplace=True)
        >>> datefield = pd.date_range(start='6/11/1991',end='2/1/1999',freq='12H')
        >>> df = pd.DataFrame({'dates':datefield,'corrwl':np.sin(range(0,len(datefield)))})
        >>> df.set_index('dates',inplace=True)
        >>> wbf, fd = fix_drift(df, man_df, corrwl='corrwl', manmeas='measureddtw', outcolname='DTW_WL')
        Processing dates 1991-06-11T00:00:00.000000000 to 1999-02-01T00:00:00.000000000
        First man = 1.000, Last man = 10.000
            First man date = 1991-06-11 00:00,
            Last man date = 1999-02-01 00:00
            -------------------
            First trans = 0.000, Last trans = -0.380
            First trans date = 1991-06-11 00:00
            Last trans date = :1999-01-31 12:00
        Slope = -0.003 and Intercept = -1.000
    """
    # breakpoints = self.get_breakpoints(wellbaro, manualfile)
    breakpoints = get_breakpoints(manualfile, well, wl_field=corrwl)
    bracketedwls, drift_features = {}, {}

    if well.index.name:
        dtnm = well.index.name
    else:
        dtnm = 'DateTime'
        well.index.name = 'DateTime'

    manualfile.loc[:, 'julian'] = manualfile.index.to_julian_date()
    manualfile.loc[:, 'datetime'] = manualfile.index

    for i in range(len(breakpoints) - 1):
        # Break up pandas dataframe time series into pieces based on timing of manual measurements
        bracketedwls[i] = well.loc[
            (pd.to_datetime(well.index) >= breakpoints[i]) & (pd.to_datetime(well.index) < breakpoints[i + 1])]
        df = bracketedwls[i]
        df['datetime'] = df.index
        df = df.dropna(subset=[corrwl])
        if trim_end:
            df = dataendclean(df, 'corrwl', jumptol=0.5)

        if len(df) > 0:
            print("----- Well {:} -----".format(wellid))
            print("Processing dates {:} to {:}".format(breakpoints[i], breakpoints[i + 1]))
            df.sort_index(inplace=True)
            df.loc[:, 'julian'] = df.index.to_julian_date()

            if wellid:
                # pull existing data if a wellid is given
                breakpoint1 = fcl(df, breakpoints[i]).name
                breakpoint2 = fcl(df, breakpoints[i + 1]).name
                offset = well_table.loc[wellid, 'stickup']
                print(breakpoint1)
                levdt, lev = pull_closest_well_data(wellid, breakpoint1,
                                                    conn_file_root, timedel=search_tol)

            else:
                lev = None
                levdt = None

            # first_trans = fcl(df[corrwl], breakpoints[i])  # last transducer measurement
            # last_trans = fcl(df[corrwl], breakpoints[i + 1])  # first transducer measurement

            first_man_julian_date = fcl(manualfile['julian'], breakpoints[i])
            last_man_julian_date = fcl(manualfile['julian'], breakpoints[i + 1])
            first_man_date = fcl(manualfile['datetime'], breakpoints[i])
            last_man_date = fcl(manualfile['datetime'], breakpoints[i + 1])
            first_man = fcl(manualfile[manmeas], breakpoints[i])  # first manual measurement
            last_man = fcl(manualfile[manmeas], breakpoints[i + 1])  # last manual measurement

            first_trans = df.loc[df.first_valid_index(), corrwl]
            last_trans = df.loc[df.last_valid_index(), corrwl]
            first_trans_julian_date = df.loc[df.first_valid_index(), 'julian']
            last_trans_julian_date = df.loc[df.last_valid_index(), 'julian']
            first_trans_date = df.first_valid_index()
            last_trans_date = df.last_valid_index()

            man_df2 = fcl(manualfile, breakpoints[i + 1])

            if np.abs(first_man_date - first_trans_date) > datetime.timedelta(days=search_tol):
                print(
                    'No initial actual manual measurement within {:} days of {:}.'.format(search_tol, first_trans_date))

                if (levdt is not None) and (
                        first_trans_date - datetime.timedelta(days=search_tol) < pd.to_datetime(levdt)):
                    print("Pulling first manual measurement from database")
                    first_man = lev
                    first_man_julian_date = pd.to_datetime(levdt).to_julian_date()
                else:
                    print('No initial transducer measurement within {:} days of {:}.'.format(search_tol,
                                                                                             first_man_date))
                    first_man = None
                    first_man_date = None

            if np.abs(last_trans_date - last_man_date) > datetime.timedelta(days=search_tol):
                print('No final manual measurement within {:} days of {:}.'.format(search_tol, last_trans_date))
                last_man = None
                last_man_date = None

            slope, b, slope_man, slope_trans = calc_slope_and_intercept(first_man, first_man_julian_date,
                                                                        last_man, last_man_julian_date, first_trans,
                                                                        first_trans_julian_date, last_trans,
                                                                        last_trans_julian_date)

            # intercept of line = value of first manual measurement
            if pd.isna(first_man):
                print('First manual measurement missing between {:} and {:}'.format(breakpoints[i], breakpoints[i + 1]))
                print("Last man = {:}\nLast man date = {:%Y-%m-%d %H:%M}".format(last_man, last_man_date))
                print("First trans = {:0.3f}, Last trans = {:0.3f}".format(first_trans, last_trans))
                print("First trans date = {:%Y-%m-%d %H:%M}".format(first_trans_date))
                print("Last trans date = {:%Y-%m-%d %H:%M}".format(last_trans_date))

            elif pd.isna(last_man):
                print('Last manual measurement missing between {:} and {:}'.format(breakpoints[i], breakpoints[i + 1]))
                print("First man = {:}\nFirst man date = {:%Y-%m-%d %H:%M}".format(first_man, first_man_date))
                print("First trans = {:0.3f}, Last trans = {:0.3f}".format(first_trans, last_trans))
                print("First trans date = {:%Y-%m-%d %H:%M}".format(first_trans_date))
                print("Last trans date = {:%Y-%m-%d %H:%M}".format(last_trans_date))
            else:

                print("First man = {:0.3f}, Last man = {:0.3f} (from ground)".format(first_man, last_man))
                print("First man date = {:%Y-%m-%d %H:%M}".format(first_man_date))
                print("Last man date = {:%Y-%m-%d %H:%M}".format(last_man_date))

                print("First trans = {:0.3f}, Last trans = {:0.3f}".format(first_trans, last_trans))
                print("First trans date = {:%Y-%m-%d %H:%M}".format(first_trans_date))
                print("Last trans date = {:%Y-%m-%d %H:%M}".format(last_trans_date))

            bracketedwls[i], drift = calc_drift(df, corrwl, outcolname, slope, b)
            print("Manual Slope = {:}".format(slope_man))
            print("Transducer Slope = {:}".format(slope_trans))
            print("Slope = {:0.3f} and Intercept = {:0.3f}".format(slope, b))
            print("{:}Drift = {:0.3f} {:}".format(Color.BOLD, drift, Color.END))
            print(" -------------------")
            drift_features[i] = calc_drift_features(first_man, first_man_date, last_man, last_man_date, first_trans,
                                                    first_trans_date,
                                                    last_trans, last_trans_date, b, slope, slope_man, slope_trans,
                                                    drift)
        else:
            pass

    wellbarofixed = pd.concat(bracketedwls, sort=True)
    wellbarofixed.reset_index(inplace=True)
    wellbarofixed.set_index(dtnm, inplace=True)
    wellbarofixed.sort_index(inplace=True)
    drift_info = pd.DataFrame(drift_features).T
    max_drift = drift_info['drift'].abs().max()
    return wellbarofixed, drift_info, max_drift


def pull_elev_and_stickup(site_number, manual, well_table=None, conn_file_root=None, stable_elev=True):
    """
    Pulls well elevation and stickup from appropriate locations

    Args:
        site_number (int): LocationID of well
        manual (pd.DataFrame): manual well reading table with datetime index
        well_table (pd.DataFrame): Well information table derived from UGS_NGWMN_Monitoring_Locations
        conn_file_root (str): location of connection file for SDE database
        stable_elev (bool): True if well elevation should be pulled from well_table; False if elevation is from manual readings; default is True

    Returns:
        stickup (float), well_elevation (float)

    Examples:

        >>> enviro = "C:/Users/paulinkenbrandt/AppData/Roaming/Esri/Desktop10.6/ArcCatalog/UGS_SDE.sde"
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'measureddtw':[1,10,14,52,10,8],'locationid':[10,10,10,10,10,10],'current_stickup_height':[0.5,0.1,0.2,0.5,0.5,0.7]}
        >>> man_df = pd.DataFrame(manual)
        >>> pull_elev_and_stickup(10,man_df,conn_file_root=enviro)
        (1.71, 6180.2)

        >>> enviro = "C:/Users/paulinkenbrandt/AppData/Roaming/Esri/Desktop10.6/ArcCatalog/UGS_SDE.sde"
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'measureddtw':[1,10,14,52,10,8],'locationid':[10,10,10,10,10,10],'current_stickup_height':[0.5,0.1,0.2,0.5,0.5,0.7]}
        >>> man_df = pd.DataFrame(manual)
        >>> pull_elev_and_stickup(10,man_df,conn_file_root=enviro, stable_elev=False)
        (0.7, 6180.2)
    """

    man = manual[manual['locationid'] == int(site_number)]

    if well_table is None:
        well_table = pull_well_table(conn_file_root)
    else:
        well_table = well_table

    stdata = well_table[well_table.index == int(site_number)]
    well_elev = float(stdata['verticalmeasure'].values[0])
    stickup = get_stickup(stdata, site_number, stable_elev=stable_elev, man=man)
    return stickup, well_elev


def pull_well_table(conn_file_root, loc_table="ugs_ngwmn_monitoring_locations"):
    """
    Extracts Monitoring Location Table from database and converts it into a pandas DataFrame.
    Queries based on if AlternateID exists.

    Args:
        conn_file_root (str): Location of SDE connection file
        loc_table (str): Name of Monitoring Location Table:  Default is 'UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations'

    Returns:
        pandas DataFrame of well information

    Examples:
        >>> enviro = "C:/Users/paulinkenbrandt/AppData/Roaming/Esri/Desktop10.6/ArcCatalog/UGS_SDE.sde"
        >>> df = pull_well_table(enviro)
        >>> print(df.loc[10, 'locationname'])
        PW04B
    """

    # populate dataframe with data from SDE well table

    sql = """SELECT locationid, locationname, locationtype, locationdesc, 
    altlocationid, verticalmeasure, verticalunit, welldepth, siteid, stickup,
    loggertype, baroefficiency, latitude, longitude, baroefficiencystart, barologgertype
    FROM {:}
    WHERE altlocationid <> 0
    ORDER BY altlocationid ASC;""".format(loc_table)

    df = pd.read_sql(sql, conn_file_root)

    df.set_index('altlocationid', inplace=True)

    return df


def get_stickup(stdata, site_number, stable_elev=True, man=None):
    """
    Finds well stickup based on stable elev field

    Args:
        stdata (pd.DataFrame): pandas dataframe of well data (well_table)
        site_number (int): LocationID of site (wellid)
        stable_elev (bool): True if elevation should come from stdata table; Defaults to True
        man (pd.DataFrame): defaults to None; dataframe of manual readings

    Returns:
        stickup height (float)

    Examples:

        >>> stdata = pd.DataFrame({'wellid':[200],'stickup':[0.5],'wellname':['foo']})
        >>> get_stickup(stdata, 200)
        0.5

        >>> stdata = pd.DataFrame({'wellid':[200],'stickup':[None],'wellname':['foo']})
        >>> get_stickup(stdata, 200)
        Well ID 200 missing stickup!
        0

        >>> stdata = pd.DataFrame({'wellid':[10],'stickup':[0.5],'wellname':['foo']})
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'measureddtw':[1,10,14,52,10,8],'locationid':[10,10,10,10,10,10],'current_stickup_height':[0.8,0.1,0.2,0.5,0.5,0.7]}
        >>> man_df = pd.DataFrame(manual)
        >>> get_stickup(stdata, 10, stable_elev=False, man=man_df)
        0.7
    """
    if stable_elev:
        # Selects well stickup from well table; if its not in the well table, then sets value to zero
        if pd.isna(stdata['stickup'].values[0]):
            stickup = 0
            print('Well ID {:} missing stickup!'.format(site_number))
        else:
            stickup = float(stdata['stickup'].values[0])
    else:
        # uses measured stickup data from manual table
        stickup = man.loc[man.last_valid_index(), 'current_stickup_height']
    return stickup


def get_man_gw_elevs(manual, stickup, well_elev, stbelev=True):
    """Gets basic well parameters and most recent groundwater level data for a well id for dtw calculations.

    Args:
        manual (pd.DataFrame): Pandas Dataframe of manual data
        stickup (float): stickup of well (distance from mp to ground)
        well_elev (float): elevation of well (ground surface elevation at wellhead)
        stbelev (bool): boolean; if False, stickup is retrieved from the manual measurements table;

    Returns:
        manual table with new fields for depth to water (negative for below ground) and groundwater elevation

    Examples:
        >>> manual = {'dates':['6/11/1991','2/1/1999'],'dtwbelowcasing':[17,22]}
        >>> man_df = pd.DataFrame(manual)
        >>> man_df.set_index('dates',inplace=True)
        >>> stickup = 1.5
        >>> well_elevation = 4050.5
        >>> man = get_man_gw_elevs(man_df, stickup, well_elevation, stbelev=True)
        >>> man.loc['6/11/1991','waterelevation']
        4035.0

        >>> manual = {'dates':['6/11/1991','6/12/1991'],'dtwbelowcasing':[17,17],'current_stickup_height':[1.1,1.2]}
        >>> man_df = pd.DataFrame(manual)
        >>> man_df.set_index('dates',inplace=True)
        >>> stickup = 1.5
        >>> well_elevation = 4050.5
        >>> man = get_man_gw_elevs(man_df, stickup, well_elevation, stbelev=False)
        >>> man.loc['6/11/1991','waterelevation']
        4034.6

    """

    # some users might have incompatible column names
    old_fields = {'DateTime': 'readingdate',
                  'Location ID': 'locationid',
                  'Water Level (ft)': 'dtwbelowcasing'}
    manual.rename(columns=old_fields, inplace=True)

    # this allows for variable stickup heights over time
    if 'current_stickup_height' in manual.columns and stbelev is False:
        manual.loc[:, 'measureddtw'] = (-1 * manual['dtwbelowcasing']) + manual['current_stickup_height']

    else:
        # assumes stable stickup height
        manual.loc[:, 'measureddtw'] = (-1*manual['dtwbelowcasing']) + stickup
    manual.loc[:, 'waterelevation'] = manual['measureddtw'].apply(lambda x: well_elev + x, 1)
    return manual


def get_trans_gw_elevations(df, stickup, well_elev, site_number, level='Level', dtw='DTW_WL'):
    """This function adds the necessary field names to import well data into the database.

    Args:
        df (pd.DataFrame): pandas DataFrame of processed well data
        well_elev (float): elevation of ground surface at wellhead
        site_number (int): unique id of monitoring location (well) in database
        stickup (float): wellhead stickup above ground
        level (float): raw transducer level from NewTransImp, new_xle_imp, or new_csv_imp functions
        dtw (float): drift-corrected depth to water from fix_drift function

    Returns:
        processed df with necessary field names for import
    """

    df['measuredlevel'] = df[level]
    df['measureddtw'] = df[dtw] * -1 #changed 3/5/2020

    print([stickup, well_elev, site_number])
    if pd.isna(stickup):
        stickup = 0
    else:
        pass

    df['dtwbelowgroundsurface'] = df['measureddtw']

    if pd.isna(well_elev):
        df['waterelevation'] = None
    else:
        df['waterelevation'] = well_elev + df['dtwbelowgroundsurface'] + stickup

    df['locationid'] = site_number

    df.sort_index(inplace=True)

    if 'Temperature' in df.columns:
        df.rename(columns={'Temperature': 'temp'}, inplace=True)

    if 'temp' in df.columns:
        df['temp'] = df['temp'].apply(lambda x: np.round(x, 4), 1)
    else:
        df['temp'] = None

    if 'baroefficiencylevel' in df.columns:
        pass
    else:
        df['baroefficiencylevel'] = 0
    # subset bp df and add relevant fields
    df.index.name = 'readingdate'

    subset = df.reset_index()

    return subset


def trans_type(well_file):
    """Uses information from the raw transducer file to determine the type of transducer used.

    Args:
        well_file: full path to raw transducer file

    Returns:
        transducer type
    """
    if os.path.splitext(well_file)[1] == '.xle':
        t_type = 'Solinst'
    elif os.path.splitext(well_file)[1] == '.lev':
        t_type = 'Solinst'
    else:
        t_type = 'Global Water'

    print('Trans type for well is {:}.'.format(t_type))
    return t_type


class PullOutsideBaro(object):
    """
    By default, this class aggregates all barometric data within a given area.
    This function currently does not work due to limits of the API

    Attributes:
        long (float): longitude of point of interest
        lat (float): latitude of point of interest
        begdate (datetime): string of beginning date of requested data; defaults to 2014-11-1
        enddate (datetime): string of end date of requested data; defaults to today
        bbox: lat-long bounding box of area of interest; optional
        rad (float): radius of area of interest; defaults to 30
        token: api token used to connect to mesowest; can be accessed at https://synopticlabs.org/api/guides/?getstarted
        timezone: Timezone to use; Defaults to None
    """

    def __init__(self, long, lat, begdate=None, enddate=None, bbox=None, rad=30, token=None, timezone=None):

        # TODO fix jumps in data created by aggregating station data
        if token:
            self.token = token
        else:
            try:
                import sys
                connection_filepath = "G:/My Drive/Python/Pycharm/loggerloader/loggerloader/"
                sys.path.append(connection_filepath)
                config = "6189e6d5e1015c2645ds61256646" # token is out of date
                self.token = config
            except:
                print("""No api token.  Please visit https://synopticlabs.org/api/guides/?getstarted to get one.\n
                      Your can create a file called config.py and write `token= 'your api token'` on the first line of the file.""")

            if timezone:

                if begdate:
                    self.begdate = pd.to_datetime(str(begdate), utc=True)
                else:
                    self.begdate = datetime.datetime(2014, 11, 1).replace(tzinfo=timezone.utc)

                if enddate:
                    self.enddate = pd.to_datetime(str(enddate), utc=True)
                else:
                    self.enddate = datetime.datetime.now().replace(tzinfo=timezone.utc)

            else:

                if begdate:
                    self.begdate = pd.to_datetime(str(begdate), utc=True)
                else:
                    self.begdate = datetime.datetime(2014, 11, 1).replace(tzinfo=timezone.utc)

                if enddate:
                    self.enddate = pd.to_datetime(str(enddate), utc=True)
                else:
                    self.enddate = datetime.datetime.now().replace(tzinfo=timezone.utc)

        self.station = []

        self.rad = rad
        self.lat = np.mean(lat)
        self.long = np.mean(long)

        if bbox:
            self.bbox = bbox
        else:
            self.bbox = [self.long - self.rad, self.lat - self.rad, self.long + self.rad, self.lat + self.rad]

    @staticmethod
    def stationresponse(html):
        response = urlopen(html)
        data = response.read().decode("utf-8")
        stations = pd.DataFrame(json.loads(data)['STATION'])
        stations['start'] = stations[['PERIOD_OF_RECORD', 'TIMEZONE']].apply(
            lambda x: pd.to_datetime(x[0]['start']).tz_convert(x[1]), 1)
        stations['end'] = stations[['PERIOD_OF_RECORD', 'TIMEZONE']].apply(
            lambda x: pd.to_datetime(x[0]['end']).tz_convert(x[1]), 1)
        stations.drop('PERIOD_OF_RECORD', axis=1, inplace=True)
        stations.sort_values(['DISTANCE'], inplace=True)

        return stations

    def getstations(self):
        addrs = 'https://api.mesowest.net/v2/stations/metadata?token={:}&vars=pressure&bbox={:}'
        html = addrs.format(self.token, ",".join([str(i) for i in self.bbox]))
        stations = self.stationresponse(html)
        return stations

    def getstationsrad(self):
        addrs = 'https://api.mesowest.net/v2/stations/metadata?token={:}&vars=pressure&radius={:},{:},{:}'
        html = addrs.format(self.token, self.lat, self.long, self.rad)
        resp = urlopen(html)
        data = resp.read().decode("utf-8")
        summry_cnt = json.loads(data)['SUMMARY']['NUMBER_OF_OBJECTS']
        while summry_cnt < 1:
            self.rad += 1
            html = addrs.format(self.token, self.lat, self.long, self.rad)
            resp = urlopen(html)
            data = resp.read().decode("utf-8")
            summry_cnt = json.loads(data)['SUMMARY']['NUMBER_OF_OBJECTS']
            # print(html)

        stations = self.stationresponse(html)
        print(html)
        return stations

    def select_station(self):
        stations = self.getstationsrad()
        stations = stations[(stations['start'] <= self.begdate) & (stations['end'] >= self.enddate)]
        if len(stations) == 1:
            self.station = list(stations['STID'])
        elif len(stations) > 1:
            self.station = list(stations['STID'].values)
        else:
            print('No Stations Available')
            self.station = None
        print(self.station)
        return self.station

    def getbaro(self, closest=True):
        """
        &bbox=-120,40,-119,41
        """
        self.select_station()
        addrs = 'https://api.mesowest.net/v2/stations/timeseries?token={:}&stid={:}&state=ut,wy,id,nv&obtimezone=utc&start={:%Y%m%d%H%M}&end={:%Y%m%d%H%M}&vars=pressure&units=pres|mb&output=csv'
        bar = {}

        if closest:
            self.station = self.station[0]

        for stat in self.station:
            html = addrs.format(self.token, stat, self.begdate, self.enddate)
            print(html)
            bartemp = pd.read_csv(html, skiprows=[0, 1, 2, 3, 4, 5, 7], index_col=1)
            bartemp.index = pd.to_datetime(bartemp.index, format='%Y-%m-%dT%H:%M:%SZ', utc=True).tz_convert(
                'MST').tz_localize(None)
            bartemp = bartemp.resample('1H').mean()
            bar[stat] = bartemp.sort_index()

        # baros = pd.concat(bar)
        barod = pd.concat(bar, axis=1)
        dropcols = ['altimeter_set_1', 'altimeter_set_1d']
        for col in dropcols:
            if col in barod.columns.get_level_values(1):
                barod = barod.drop(col, axis=1, level=1)
        barod.columns = barod.columns.droplevel(-1)
        # barod['measuredlevel'] = barod.mean(axis=1)
        baroe = barod
        colmeans = baroe.mean(axis=0)

        for col in baroe.columns:
            # colmean = colmeans[col]
            try:
                baroe[col] = baroe[col].diff()
            except:
                baroe = baroe.drop([col], axis=1)
        baroe['diffs'] = baroe.median(axis=1)
        baroe['measuredpress'] = baroe['diffs'].cumsum() + colmeans.mean()

        baroe['measuredlevelraw'] = 0.03345526 * baroe['measuredpress']
        baroe.index.name = 'readingdate'

        barof = baroe.dropna(subset=['measuredlevelraw'])

        x = barof.index.to_julian_date()
        y = barof['measuredlevelraw'].values

        try:
            X = np.vstack([x, np.ones(len(x))]).T
            m, c = np.linalg.lstsq(X, y, rcond=None)[0]
            print(m, c)

            baroe['juliandate'] = baroe.index.to_julian_date()
            firstjdate = baroe.loc[baroe.first_valid_index(), 'juliandate']
            baroe['jday'] = baroe['juliandate'].apply(lambda x: x - firstjdate, 1)
            baroe['measuredlevel'] = baroe['measuredlevelraw'] - baroe['jday'] * m
            baroe.index.name = 'readingdate'
            return baroe
        except:
            return barof


# -----------------------------------------------------------------------------------------------------------------------
# These functions import data into a database


def imp_one_well(well_file, baro_file, man_startdate, man_start_level, man_endate, man_end_level,
                 conn_file_root, wellid, be=None, gw_reading_table="reading", drift_tol=0.3, override=False):
    """Imports one well give raw barometer data and manual measurements

    Args:
        well_file: raw file containing well data
        baro_file: raw file containing baro data
        man_startdate: date-time of first manual reading
        man_start_level: depth to water from mp of first manual reading
        man_endate: date-time of last manual reading
        man_end_level: depth to water from mp of last manual reading
        conn_file_root: connection object for the database
        wellid: locationid of well where data are being imported
        be: barometric efficiency of well
        gw_reading_table: database table where groundwater level data are stored; defaults to 'readings'
        drift_tol: allowable drift of transducer readings from manual data; 0.3 is default
        override: force data into database; defaults to false; may cause db errors

    Returns:
        df, man, be, drift

    """
    # convert raw files to dataframes
    well = NewTransImp(well_file).well
    baro = NewTransImp(baro_file).well

    # align baro and well timeseries; remove bp if nonvented
    corrwl = well_baro_merge(well, baro, vented=(trans_type(well_file) != 'Solinst'))

    # bring in manual data and create a dataframe from it
    man = pd.DataFrame(
        {'DateTime': [man_startdate, man_endate],
         'Water Level (ft)': [man_start_level, man_end_level],
         'Location ID': wellid}).set_index('DateTime')
    print(man)

    # pull stickup and elevation from well table; calculate water level elevations
    well_table = pull_well_table(conn_file_root)
    stickup, well_elev = pull_elev_and_stickup(wellid, man, well_table=well_table, conn_file_root=conn_file_root)
    man = get_man_gw_elevs(man, stickup, well_elev)

    # correct for barometric efficiency if available
    if be:
        corrwl, be = correct_be(wellid, well_table, corrwl, be=be)
        corrwl['corrwl'] = corrwl['baroefficiencylevel']

    # adjust for linear transducer drift between manual measurements
    df, drift_info, drift = fix_drift(corrwl, man, corrwl='corrwl', manmeas='measureddtw')
    print('Maximum Drift for well {:} is {:.3f}.'.format(wellid, drift))

    # add, remove, and arrange column names to match database format schema
    rowlist = get_trans_gw_elevations(df, stickup, well_elev, wellid)

    fieldnames = ['measuredlevel', 'measureddtw', 'driftcorrection',
                  'temp', 'locationid', 'baroefficiencylevel',
                  'waterelevation']

    # QA/QC to reject data if it exceeds user-based threshhold
    if drift <= drift_tol:
        edit_table(rowlist, gw_reading_table, fieldnames, conn_file_root)
        print('Well {:} successfully imported!'.format(wellid))
    elif override == 1:
        edit_table(rowlist, gw_reading_table, fieldnames, conn_file_root)
        print('Override initiated. Well {:} successfully imported!'.format(wellid))
    else:
        print('Well {:} drift greater than tolerance!'.format(wellid))
    return df, man, be, drift


def simp_imp_well(well_file, baro_out, wellid, manual, conn_file_root, stbl_elev=True, be=None,
                  gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading", drift_tol=0.3, jumptol=1.0,
                 imp=True, trim_end=True, timezone=None):
    """
    Imports single well into database assuming existing barometer and manual data in database

    Args:
        well_file: raw well file (xle, csv, or lev)
        baro_out (dict): dictionary with barometer ID defining dataframe names
        wellid (int): unique ID of well field
        manual (pd.DataFrame): manual data dataframe indexed by measure datetime
        conn_file_root (object): working directory for the groundwater readings table (the workspace environment)
        stbl_elev (bool): does the stickup remain constant; determines source of stickup information (well table vs. water level table); defaults to true (well table)
        be (float): barometric efficiency value
        gw_reading_table (str): table name where data will be imported; defaults to "UGGP.UGGPADMIN.UGS_GW_reading"
        drift_tol (float): maximum amount of transducer drift to allow before transducer data not imported
        jumptol (float): acceptable amount of offset in feet at beginning and end of transducer data representing out of water measurements
        imp (bool): dictates whether well is imported into database; Defaults to True
        trim_end (bool): controls if end trimming filter is used; Defaults to True
        timezone (str): timezone of data, if any; Defaults to None

    Return:
        (tuple): rowlist, toimp, man, be, drift
    """

    # import well file
    well = NewTransImp(well_file, jumptol=jumptol, trim_end=trim_end).well

    # pull stickup and elevation from well table; calculate water level elevations
    well_table = pull_well_table(conn_file_root)
    stickup, well_elev = pull_elev_and_stickup(wellid, manual, well_table=well_table,
                                               conn_file_root=conn_file_root, stable_elev=stbl_elev)
    man = get_man_gw_elevs(manual, stickup, well_elev, stbelev=stbl_elev)

    # Check to see if well has assigned barometer
    try:
        baroid = well_table.loc[wellid, 'barologgertype']
    except KeyError:
        baroid = 0

    well = well.sort_index()

    # resample well data to compare length of data against barometric pressure data
    wellres = hourly_resample(well)
    print(wellres.first_valid_index(), wellres.last_valid_index())
    # select a subset of barometer data that align with well data
    baro_data = baro_out[
        (baro_out.index >= wellres.first_valid_index()) & (baro_out.index <= wellres.last_valid_index())]
    # make sure data exists for the selected time interval
    if len(baro_data) == 0:
        print("No baro data for site {:}! Pull Data for location {:}".format(baroid, wellid))
        barosub = None
    elif len(wellres) > len(baro_data) + 60 > 0:
        barosub = baro_data[~baro_data.index.isin(well.index.values)]
        barosub = barosub.sort_index()
        print("Baro data length from site {:} is {:}! Provide Data for location {:}".format(baroid, len(baro_data),
                                                                                            wellid))
    else:
        barosub = baro_out

    # align barometric and well data
    corrwl = well_baro_merge(well, barosub, barocolumn='measuredlevel',
                             vented=(trans_type(well_file) == 'Global Water'))

    # correct for barometric efficiency
    if be:
        corrwl, be = correct_be(wellid, well_table, corrwl, be=be)
        corrwl['corrwl'] = corrwl['baroefficiencylevel']

    corrwl.sort_index(inplace=True)

    # fix linear transducer drift using manual data
    df, drift_info, max_drift = fix_drift(corrwl, man, corrwl='corrwl', manmeas='measureddtw', wellid=wellid,
                                          well_table=well_table, conn_file_root=conn_file_root)
    drift = round(float(max_drift), 3)

    df = df.sort_index()

    # calculate groundwater elevation based on elevation and stickup data in monitoring locations table
    rowlist = get_trans_gw_elevations(df, stickup, well_elev, wellid)

    rowlist = rowlist.set_index('readingdate')

    # QA/QC to reject data if it exceeds user-based threshhold
    # check processed data against data in database; if data for a specific wellid and time exists, do not insert data
    toimp = check_for_dups(rowlist, wellid, conn_file_root, drift, drift_tol, gw_reading_table, imp)

    if len(toimp) > 0 and imp:
        impdf = edit_table(toimp, gw_reading_table, conn_file_root, timezone)
    else:
        impdf = toimp

    return rowlist, impdf, man, be, drift


def check_for_dups(df, wellid, conn_file_root, drift, drift_tol=0.3, gw_reading_table='reading',
                   tmzone=None):
    """Checks readings data against an existing database for duplication.
    QA/QC to reject data if it exceeds user-based threshhold

    Args:
        df (pd.DataFrame): input dataframe to compare with database
        wellid (int): locationid in the database for the well
        conn_file_root: connection object for the the database
        drift (float): amount of drift calculated from `fix_drift`
        drift_tol (float): amount of drift allowable; default is 0.3 feet
        gw_reading_table (pd.Dataframe): table in database with groundwater readings; default is 'readings'
        tmzone (str): timezone of data; defaults to none

    Returns:
        uploads data to database and returns a dataframe of the uploaded data
    """

    first_index, last_index = first_last_indices(df, tmzone)

    # Pull any existing data from the database for the well in the date range of the new data
    existing_data = get_location_data(wellid, conn_file_root, first_index, last_index,
                                      gw_reading_table=gw_reading_table)

    if len(existing_data) > 0:
        # existing_data.index = pd.to_datetime(existing_data.index,infer_datetime_format=True,utc=True)
        existing_data = existing_data.loc[wellid].sort_index()
        if tmzone is None:
            if existing_data.index[0].utcoffset() is None:
                existing_data.index = existing_data.index.tz_localize(None)
            elif existing_data.index[0].utcoffset().total_seconds() > 0.0:
                existing_data.index = existing_data.index.tz_convert(None)
            elif existing_data.index[0].utcoffset().total_seconds() == 0.0:
                existing_data.index = existing_data.index.tz_convert(None)
            else:
                existing_data.index = existing_data.index.tz_localize(None)
        else:
            if existing_data.index[0].utcoffset() is None:
                existing_data.index = existing_data.index.tz_localize('MST', ambiguous="NaT")
            elif existing_data.index[0].utcoffset().total_seconds() == 0.0:
                existing_data.index = existing_data.index.tz_convert('MST')

        existing_data.index.name = 'readingdate'
    print("Existing Len = {:}. Import Len = {:}.".format(len(existing_data), len(df)))

    if (len(existing_data) == 0) and (abs(drift) < drift_tol):
        print("Well {:} imported.".format(wellid))
        df1 = df
    elif len(existing_data) == len(df) and (abs(drift) < drift_tol):
        df1 = None
        print('Data for well {:} already exist!'.format(wellid))
    elif len(df) > len(existing_data) > 0 and abs(drift) < drift_tol:
        df1 = df[~df.index.isin(existing_data.index.values)]
        print('Some values were missing. {:} values added.'.format(len(existing_data) - len(df)))
    elif abs(drift) > drift_tol:
        df1 = None
        print('Drift for well {:} exceeds tolerance!'.format(wellid))
    else:
        df1 = None
        print('Dates later than import data for well {:} already exist!'.format(wellid))
        pass

    return df1


def first_last_indices(df, tmzone=None):
    """Gets first and last index in a dataset; capable of considering time series with timezone information

    Args:
        df (pd.DataFrame): dataframe with indices
        tmzone (str): timzone code of data if timezone specified; defaults to None

    Returns:
        first index, last index

    """
    df.sort_index(inplace=True)

    if tmzone is None:
        first_index = df.first_valid_index()
        last_index = df.last_valid_index()

    else:
        if df.index[0].utcoffset() is None:
            first_index = df.first_valid_index().tz_localize(tmzone, ambiguous="NaT")
            last_index = df.last_valid_index().tz_localize(tmzone, ambiguous="NaT")
        elif df.index[0].utcoffset().total_seconds() == 0.0:
            first_index = df.first_valid_index().tz_convert(tmzone)
            last_index = df.last_valid_index().tz_convert(tmzone)
        else:
            first_index = df.first_valid_index()
            last_index = df.last_valid_index()
    return first_index, last_index


def upload_bp_data(df, site_number, enviro, return_df=True, overide=False, gw_reading_table="ugs_gw_barometers",
                   resamp_freq="1H", timezone=None, schema='sde'):
    df.sort_index(inplace=True)
    print("Resampling")
    df = df.resample(resamp_freq).mean()

    first_index = df.first_valid_index()
    last_index = df.last_valid_index()
    site_number = int(site_number)

    if timezone is None:
        pass
    else:
        if df.index[0].utcoffset() is None:
            df.index = df.index.tz_localize('MST')
        elif df.index[0].utcoffset().total_seconds() == 0.0:
            df.index = df.index.tz_convert('MST')

    query = "locationid = {:.0f} AND readingdate >= '{:}' AND readingdate <= '{:}'".format(float(site_number),
                                                                                           first_index, last_index)
    print(query)
    existing_data = get_location_data(site_number, enviro=enviro,
                                      gw_reading_table=gw_reading_table,
                                      first_date=first_index,
                                      last_date=last_index)

    if len(existing_data) > 0:
        # existing_data.index = pd.to_datetime(existing_data.index,infer_datetime_format=True,utc=True)
        existing_data = existing_data.loc[site_number].sort_index()
        if timezone is None:
            if existing_data.index[0].utcoffset() is None:
                existing_data.index = existing_data.index.tz_localize(None)
            elif existing_data.index[0].utcoffset().total_seconds() > 0.0:
                existing_data.index = existing_data.index.tz_convert(None)
            elif existing_data.index[0].utcoffset().total_seconds() == 0.0:
                existing_data.index = existing_data.index.tz_convert(None)
            else:
                existing_data.index = existing_data.index.tz_localize(None)
        else:
            if existing_data.index[0].utcoffset() is None:
                existing_data.index = existing_data.index.tz_localize('MST', ambiguous="NaT")
            elif existing_data.index[0].utcoffset().total_seconds() == 0.0:
                existing_data.index = existing_data.index.tz_convert('MST')

        existing_data.index.name = 'readingdate'


    if 'measuredlevel' in df.columns:
        pass
    else:
        df['measuredlevel'] = df['Level']

    df['locationid'] = site_number

    fieldnames = ['measuredlevel', 'temp', 'locationid']

    if 'Temperature' in df.columns:
        df.rename(columns={'Temperature': 'temp'}, inplace=True)

    if 'temp' in df.columns:
        df['temp'] = df['temp'].apply(lambda x: np.round(x, 4), 1)
    else:
        df['temp'] = None

    df.index.name = 'readingdate'

    print("Existing Len = {:}. Processed Data Len = {:}.".format(len(existing_data), len(df)))

    if (len(existing_data) == 0) or overide is True:
        toimp = edit_table(df, gw_reading_table, enviro)
        print("Well {:} imported.".format(site_number))
    elif len(existing_data) == len(df):
        print('Data for well {:} already exist!'.format(site_number))
        toimp = None
    elif len(df) > len(existing_data) and len(df) > 0:

        subset = df.reset_index()
        subset = subset[~subset['readingdate'].isin(existing_data.index.values)]
        print('Some values were missing. {:} values to be added.'.format(len(df) - len(existing_data)))
        print('Upload size is {:}'.format(len(subset)))
        subset = subset.set_index('readingdate')
        toimp = edit_table(subset, gw_reading_table, enviro, schema=schema)

    else:
        print('Import data for well {:} already exist! No data imported.'.format(site_number))
        toimp = None
        pass

    if return_df:
        return toimp


# -----------------------------------------------------------------------------------------------------------------------
# The following modify and query an SDE database, assuming the user has a connection

def find_extreme(site_number, gw_table="reading", sort_by='readingdate', extma='max'):

    if extma == 'max' or extma == 'DESC':
        lorder = 'DESC'
    else:
        lorder = 'ASC'

    sql = """SELECT * FROM {:} WHERE "locationid" = {:} AND "{:}" IS NOT NULL
    ORDER by "{:}" {:}
    LIMIT 1""".format(gw_table, site_number, sort_by, sort_by, lorder)

    df = pd.read_sql(sql, engine)
    return df['readingdate'][0], df['measureddtw'][0], df['waterelevation'][0]


def get_gap_data(site_number, enviro, gap_tol=0.5, first_date=None, last_date=None,
                 gw_reading_table="reading"):
    """Finds temporal gaps in regularly sampled data.

    Args:
        site_number: List of Location ID of time series data to be processed
        enviro: workspace of SDE table
        gap_tol: gap tolerance in days; the smallest gap to look for; defaults to half a day (0.5)
        first_date: begining of time interval to search; defaults to 1/1/1900
        last_date: end of time interval to search; defaults to current day
        gw_reading_table: Name of SDE table in workspace to use

    Return:
        pandas dataframe with gap information
    """
    # TODO MAke fast with SQL
    if first_date is None:
        first_date = datetime.datetime(1900, 1, 1)
    if last_date is None:
        last_date = datetime.datetime.now()

    if type(site_number) == list:
        pass
    else:
        site_number = [site_number]

    query_txt = """SELECT readingdate,locationid FROM {:}
    WHERE locationid IN ({:}) AND readingdate >= '{:}' AND readingdate <= '{:}'
    ORDER BY locationid ASC, readingdate ASC"""
    query = query_txt.format(gw_reading_table, ','.join([str(i) for i in site_number]), first_date, last_date)
    df = pd.read_sql(query, con=enviro,
                     parse_dates={'readingdate': '%Y-%m-%d %H:%M:%s-%z'})

    df['t_diff'] = df['readingdate'].diff()

    df = df[df['t_diff'] > pd.Timedelta('{:}D'.format(gap_tol))]
    df.sort_values('t_diff', ascending=False)
    return df


def get_location_data(site_numbers, enviro, first_date=None, last_date=None, limit=None,
                      gw_reading_table="reading"):
    """Retrieve location data based on a site number and database connection engine

    Args:
        site_numbers (int): locationid for a specific site in the database
        enviro (object): database connection object
        first_date (datetime): first date of data of interest; defaults to 1-1-1900
        last_date (datetime): last date of data of interest; defaults to today
        limit (int): maximum number of records to return
        gw_reading_table (str): table in database with data; defaults to `reading`

    Returns:
        readings (pd.DataFrame)
    """
    # fill in missing date info
    if not first_date:
        # set first date to begining of 20th century
        first_date = datetime.datetime(1900, 1, 1)
    elif type(first_date) == str:
        try:
            first_date = datetime.datetime.strptime(first_date, '%m/%d/%Y')
        except:
            first_date = datetime.datetime(1900, 1, 1)

    # Get last reading at the specified location
    try:
        if not last_date or last_date > datetime.datetime.now():
            last_date = datetime.datetime.now()
    except TypeError:
        if not last_date or last_date > datetime.datetime.now(tz=pytz.timezone('MST')):
            last_date = datetime.datetime.now(tz=pytz.timezone('MST'))
    if type(site_numbers) == list:
        site_numbers = ",".join([str(i) for i in site_numbers])
    else:
        pass

    sql = """SELECT * FROM {:} 
    WHERE locationid IN ({:}) AND readingdate >= '{:}' AND readingdate <= '{:}'
    ORDER BY locationid ASC, readingdate ASC""".format(gw_reading_table, site_numbers, first_date, last_date)

    if limit:
        sql += "\nLIMIT {:}".format(limit)

    readings = pd.read_sql(sql, con=enviro, parse_dates=True, index_col='readingdate')
    readings.index = pd.to_datetime(readings.index, infer_datetime_format=True, utc=True)

    try:
        readings.index = readings.index.tz_convert(tz='MST')
    except TypeError:
        readings.index = readings.index.tz_localize(tz='MST')
    readings.reset_index(inplace=True)
    readings.set_index(['locationid', 'readingdate'], inplace=True)
    if len(readings) == 0:
        print('No Records for location(s) {:}'.format(site_numbers))
    return readings


def barodistance(wellinfo):
    """Determines Closest Barometer to Each Well using wellinfo DataFrame"""
    barometers = {'barom': ['pw03', 'pw10', 'pw19'], 'X': [240327.49, 271127.67, 305088.9],
                  'Y': [4314993.95, 4356071.98, 4389630.71], 'Z': [1623.079737, 1605.187759, 1412.673738]}
    barolocal = pd.DataFrame(barometers)
    barolocal = barolocal.reset_index()
    barolocal.set_index('barom', inplace=True)

    wellinfo['pw03'] = np.sqrt((barolocal.loc['pw03', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw03', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw03', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw10'] = np.sqrt((barolocal.loc['pw10', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw10', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw10', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw19'] = np.sqrt((barolocal.loc['pw19', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw19', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw19', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['closest_baro'] = wellinfo[['pw03', 'pw10', 'pw19']].T.idxmin()
    return wellinfo


# -----------------------------------------------------------------------------------------------------------------------
# These are the core functions that are used to import and export data from an SDE database


def table_to_pandas_dataframe(table, engine, field_names=None):
    """
    Load data into a Pandas Data Frame for subsequent analysis.

    Args:
        table: Table readable by ArcGIS.
        field_names: List of fields.

    Return:
        Pandas DataFrame object.
    """
    # TODO Make fast with SQL
    # if field names are not specified
    if not field_names:
        field_names = get_field_names(engine, table)
    # create a pandas data frame

    sql = """SELECT {:} FROM {:};""".format('"' + '","'.join(field_names) + '"', table)

    df = pd.read_sql(sql, con=engine)

    # return the pandas data frame
    return df


def get_field_names(engine, table='reading', table_schema='sde'):
    """Gets a list of columns in a table in a database

    Args:
        engine: connection object with the table of interest
        table: database table with field names
        table_schema: name of schema in which the table resides; defaults to sde

    Returns:
        field names in a table
    """

    sql = """SELECT * FROM information_schema.columns 
    WHERE table_schema = '{:}' 
    AND table_name = '{:}'""".format(table_schema, table)

    df = pd.read_sql(sql, con=engine)
    columns = list(df.column_name.values)
    return columns


def edit_table(df, gw_reading_table, engine, timezone=None, schema='sde'):
    """
    Edits SDE table by inserting new rows

    Args:
        df: pandas DataFrame
        gw_reading_table: sde table to edit
        engine: database engine object to connect
        timezone: timezone of data; Defaults to None
        schema: database table schema in which the table resides; defaults to sde

    Returns:
        pandas dataframe of data imported

    """

    table_names = get_field_names(engine, gw_reading_table, table_schema=schema)

    fieldnames = list(df.columns.values)

    for name in fieldnames:
        if name not in table_names:
            fieldnames.remove(name)
            print("{:} not in {:} fieldnames!".format(name, gw_reading_table))

    namelist = []
    for name in table_names:
        if name in fieldnames:
            namelist.append(name)

    if len(fieldnames) > 0:
        subset = df[namelist]

        if timezone:
            if subset.index[0].utcoffset() is None:
                subset['readingdate'] = subset.index.tz_localize('MST', ambiguous="NaT")
            elif subset.index[0].utcoffset().total_seconds() == 0.0:
                subset['readingdate'] = subset.index.tz_convert('MST')
            else:
                subset['readingdate'] = subset.index
        else:
            subset['readingdate'] = subset.index

        subset.dropna(subset=['readingdate'], inplace=True)
        subset.drop_duplicates(subset=['locationid', 'readingdate'], inplace=True)

        try:
            if timezone:
                subset.to_sql(gw_reading_table, engine, chunksize=1000,
                              dtype={'readingdate': sqlalchemy.types.DateTime(timezone=True)},
                              index=False, if_exists='append')
            else:
                subset.to_sql(gw_reading_table, engine, chunksize=1000,
                              dtype={'readingdate': sqlalchemy.types.DateTime()},
                              index=False, if_exists='append')
            print('Data Sucessfully Imported')
        except Exception as e:
            print('Import Failed')
            print(str(e))
            pass

    else:
        print('No data imported!')

    return subset


# -----------------------------------------------------------------------------------------------------------------------
# These scripts remove outlier data and filter the time series of jumps and erratic measurements

def dataendclean(df, x, inplace=False, jumptol=1.0):
    """Trims off ends and beginnings of datasets that exceed 2.0 standard deviations of the first and last 50 values

    Args:
        df (pandas.core.frame.DataFrame): Pandas DataFrame
        x (str): Column name of data to be trimmed contained in df
        inplace (bool): if DataFrame should be duplicated
        jumptol (float): acceptable amount of offset in feet caused by the transducer being out of water at time of measurement; default is 1

    Returns:
        (pandas.core.frame.DataFrame) df trimmed data


    This function printmess a message if data are trimmed.
    """
    # Examine Mean Values
    if inplace:
        df = df
    else:
        df = df.copy()

    jump = df[abs(df.loc[:, x].diff()) > jumptol]
    try:
        for i in range(len(jump)):
            if jump.index[i] < df.index[50]:
                df = df[df.index > jump.index[i]]
                print("Dropped from beginning to " + str(jump.index[i]))
            if jump.index[i] > df.index[-50]:
                df = df[df.index < jump.index[i]]
                print("Dropped from end to " + str(jump.index[i]))
    except IndexError:
        print('No Jumps')
    return df


def smoother(df, p, win=30, sd=3):
    """Remove outliers from a pandas dataframe column and fill with interpolated values.
    warning: this will fill all NaN values in the DataFrame with the interpolate function

    Args:
        df (pandas.core.frame.DataFrame):
            Pandas DataFrame of interest
        p (string):
            column in dataframe with outliers
        win (int):
            size of window in days (default 30)
        sd (int):
            number of standard deviations allowed (default 3)

    Returns:
        Pandas DataFrame with outliers removed
    """
    df1 = df
    df1.loc[:, 'dp' + p] = df1.loc[:, p].diff()
    df1.loc[:, 'ma' + p] = df1.loc[:, 'dp' + p].rolling(window=win, center=True).mean()
    df1.loc[:, 'mst' + p] = df1.loc[:, 'dp' + p].rolling(window=win, center=True).std()
    for i in df.index:
        try:
            if abs(df1.loc[i, 'dp' + p] - df1.loc[i, 'ma' + p]) >= abs(df1.loc[i, 'mst' + p] * sd):
                df.loc[i, p] = np.nan
            else:
                df.loc[i, p] = df.loc[i, p]
        except ValueError:
            try:
                if abs(df1.loc[i, 'dp' + p] - df1.loc[i, 'ma' + p]) >= abs(df1.loc[:, 'dp' + p].std() * sd):
                    df.loc[i, p] = np.nan
                else:
                    df.loc[i, p] = df.loc[i, p]
            except ValueError:
                df.loc[i, p] = df.loc[i, p]

    try:
        df1 = df1.drop(['dp' + p, 'ma' + p, 'mst' + p], axis=1)
    except(NameError, ValueError):
        pass
    del df1
    try:
        df = df.drop(['dp' + p, 'ma' + p, 'mst' + p], axis=1)
    except(NameError, ValueError):
        pass
    df = df.interpolate(method='time', limit=30)
    df = df[1:-1]
    return df


def rollmeandiff(df1, p1, df2, p2, win):
    """Returns the rolling mean difference of two columns from two different dataframes
    Args:
        df1 (object):
            dataframe 1
        p1 (str):
            column in df1
        df2 (object):
            dataframe 2
        p2 (str):
            column in df2
        win (int):
            window in days

    Return:
        diff (float):
            difference
    """
    win = win * 60 * 24
    df1 = df1.resample('1T').mean()
    df1 = df1.interpolate(method='time')
    df2 = df2.resample('1T').mean()
    df2 = df2.interpolate(method='time')
    df1['rm' + p1] = df1[p1].rolling(window=win, center=True).mean()
    df2['rm' + p2] = df2[p2].rolling(window=win, center=True).mean()
    df3 = pd.merge(df1, df2, left_index=True, right_index=True, how='outer')
    df3 = df3[np.isfinite(df3['rm' + p1])]
    df4 = df3[np.isfinite(df3['rm' + p2])]
    df5 = df4['rm' + p1] - df4['rm' + p2]
    diff = round(df5.mean(), 3)
    del (df3, df4, df5)
    return diff


def jumpfix(df, meas, threashold=0.005, return_jump=False):
    """Removes jumps or jolts in time series data (where offset is lasting)
    Args:
        df (object):
            dataframe to manipulate
        meas (str):
            name of field with jolts
        threashold (float):
            size of jolt to search for
        return_jump (bool):
            return the pandas dataframe of jumps corrected in data; defaults to false
    Returns:
        df1: dataframe of corrected data
        jump: dataframe of jumps corrected in data
    """
    df1 = df.copy(deep=True)
    df1['delta' + meas] = df1.loc[:, meas].diff()
    jump = df1[abs(df1['delta' + meas]) > threashold]
    jump['cumul'] = jump.loc[:, 'delta' + meas].cumsum()
    df1['newVal'] = df1.loc[:, meas]

    for i in range(len(jump)):
        jt = jump.index[i]
        ja = jump['cumul'][i]
        df1.loc[jt:, 'newVal'] = df1[meas].apply(lambda x: x - ja, 1)
    df1[meas] = df1['newVal']
    if return_jump:
        print(jump)
        return df1, jump
    else:
        return df1


# -----------------------------------------------------------------------------------------------------------------------
# The following scripts align and remove barometric pressure data

def correct_be(site_number, well_table, welldata, be=None, meas='corrwl', baro='barometer'):
    if be:
        be = float(be)
    else:
        stdata = well_table[well_table['wellid'] == site_number]
        be = stdata['BaroEfficiency'].values[0]
    if be is None:
        be = 0
    else:
        be = float(be)

    if be == 0:
        welldata['baroefficiencylevel'] = welldata[meas]
    else:
        welldata['baroefficiencylevel'] = welldata[[meas, baro]].apply(lambda x: x[0] + be * x[1], 1)

    return welldata, be


def hourly_resample(df, bse=0, minutes=60):
    """
    resamples data to hourly on the hour
    Args:
        df:
            pandas dataframe containing time series needing resampling
        bse (int):
            base time to set; optional; default is zero (on the hour);
        minutes (int):
            sampling recurrence interval in minutes; optional; default is 60 (hourly samples)
    Returns:
        A Pandas DataFrame that has been resampled to every hour, at the minute defined by the base (bse)
    Description:
        see http://pandas.pydata.org/pandas-docs/dev/generated/pandas.DataFrame.resample.html for more info
        This function uses pandas powerful time-series manipulation to upsample to every minute, then downsample to
        every hour, on the hour.
        This function will need adjustment if you do not want it to return hourly samples, or iusgsGisf you are
        sampling more frequently than once per minute.
        see http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
    """

    df = df.resample('1T').mean().interpolate(method='time', limit=90)

    if minutes == 60:
        sampfrq = '1H'
    else:
        sampfrq = str(minutes) + 'T'

    df = df.resample(sampfrq, closed='right', label='right', base=bse).asfreq()
    return df


def well_baro_merge(wellfile, barofile, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl',
                    vented=False, sampint=60):
    """Remove barometric pressure from nonvented transducers.
    Args:
        wellfile (pd.DataFrame):
            Pandas DataFrame of water level data labeled 'Level'; index must be datetime
        barofile (pd.DataFrame):
            Pandas DataFrame barometric data labeled 'Level'; index must be datetime
        sampint (int):
            sampling interval in minutes; default 60

    Returns:
        wellbaro (Pandas DataFrame):
           corrected water levels with bp removed
    """

    # resample data to make sample interval consistent
    baro = hourly_resample(barofile, bse=0, minutes=sampint)
    well = hourly_resample(wellfile, bse=0, minutes=sampint)

    # reassign `Level` to reduce ambiguity
    baro = baro.rename(columns={barocolumn: 'barometer'})

    if 'temp' in baro.columns:
        baro = baro.drop('temp', axis=1)
    elif 'Temperature' in baro.columns:
        baro = baro.drop('Temperature', axis=1)
    elif 'temperature' in baro.columns:
        baro = baro.drop('temperature', axis=1)

    if vented:
        wellbaro = well
        wellbaro[outcolumn] = wellbaro[wellcolumn]
    else:
        # combine baro and well data for easy calculations, graphing, and manipulation
        wellbaro = pd.merge(well, baro, left_index=True, right_index=True, how='left')
        wellbaro = wellbaro.dropna(subset=['barometer',wellcolumn], how='any')
        wellbaro['dbp'] = wellbaro['barometer'].diff()
        wellbaro['dwl'] = wellbaro[wellcolumn].diff()
        # printmes(wellbaro)
        first_well = wellbaro[wellcolumn][0]
        wellbaro[outcolumn] = wellbaro[['dbp', 'dwl']].apply(lambda x: x[1] - x[0], 1).cumsum() + first_well
        wellbaro.loc[wellbaro.index[0], outcolumn] = first_well
    return wellbaro


def fcl(df, dtobj):
    """
    Finds closest date index in a dataframe to a date object

    Args:
        df (pd.DataFrame):
            DataFrame
        dtobj (datetime.datetime):
            date object

    taken from: http://stackoverflow.com/questions/15115547/find-closest-row-of-dataframe-to-given-time-in-pandas
    """
    return df.iloc[np.argmin(np.abs(pd.to_datetime(df.index) - dtobj))]  # remove to_pydatetime()


def compilefiles(searchdir, copydir, filecontains, filetypes=('lev', 'xle')):
    filecontains = list(filecontains)
    filetypes = list(filetypes)
    for pack in os.walk(searchdir):
        for name in filecontains:
            for i in glob.glob(pack[0] + '/' + '*{:}*'.format(name)):
                if i.split('.')[-1] in filetypes:
                    dater = str(datetime.datetime.fromtimestamp(os.path.getmtime(i)).strftime('%Y-%m-%d'))
                    rightfile = dater + "_" + os.path.basename(i)
                    if not os.path.exists(copydir):
                        print('Creating {:}'.format(copydir))
                        os.makedirs(copydir)
                    else:
                        pass
                    if os.path.isfile(os.path.join(copydir, rightfile)):
                        pass
                    else:
                        print(os.path.join(copydir, rightfile))
                        try:
                            copyfile(i, os.path.join(copydir, rightfile))
                        except:
                            pass
    print('Copy Complete!')
    return

def compilation(inputfile, trm=True):
    """This function reads multiple xle transducer files in a directory and generates a compiled Pandas DataFrame.
    Args:
        inputfile (file):
            complete file path to input files; use * for wildcard in file name
        trm (bool):
            whether or not to trim the end
    Returns:
        outfile (object):
            Pandas DataFrame of compiled data
    Example::
        >>> compilation('O:/Snake Valley Water/Transducer Data/Raw_data_archive/all/LEV/*baro*')
        picks any file containing 'baro'
    """

    # create empty dictionary to hold DataFrames
    f = {}

    # generate list of relevant files
    filelist = glob.glob(inputfile)

    # iterate through list of relevant files
    for infile in filelist:
        # run computations using lev files
        filename, file_extension = os.path.splitext(infile)
        if file_extension in ['.csv', '.lev', '.xle']:
            print(infile)
            nti = NewTransImp(infile, trim_end=trm).well
            f[getfilename(infile)] = nti
    # concatenate all of the DataFrames in dictionary f to one DataFrame: g
    g = pd.concat(f)
    # remove multiindex and replace with index=Datetime
    g = g.reset_index()
    g['DateTime'] = g['DateTime'].apply(lambda x: pd.to_datetime(x, errors='coerce'), 1)
    g = g.set_index(['DateTime'])
    # drop old indexes
    g = g.drop(['level_0'], axis=1)
    # remove duplicates based on index then sort by index
    g['ind'] = g.index
    g = g.drop_duplicates(subset='ind')
    g = g.drop('ind', axis=1)
    g = g.sort_index()
    return g


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# Raw transducer import functions - these convert raw lev, xle, and csv files to Pandas Dataframes for processing


class NewTransImp(object):
    """This class uses an imports and cleans the ends of transducer file.

    Args:
        infile (file):
            complete file path to input file
        xle (bool):
            if true, then the file type should be xle; else it should be csv

    Returns:
        A Pandas DataFrame containing the transducer data
    """

    def __init__(self, infile, trim_end=True, jumptol=1.0):
        """

        :param infile: complete file path to input file
        :param trim_end: turns on the dataendclean function
        :param jumptol: minimum amount of jump to search for that was caused by an out-of-water experience
        """
        self.well = None
        self.infile = infile
        file_ext = os.path.splitext(self.infile)[1]
        try:
            if file_ext == '.xle':
                self.well = self.new_xle_imp()
            elif file_ext == '.lev':
                self.well = self.new_lev_imp()
            elif file_ext == '.csv':
                self.well = self.new_csv_imp()
            else:
                print('filetype not recognized')
                self.well = None

            if self.well is None:
                pass
            elif trim_end:
                self.well = dataendclean(self.well, 'Level', jumptol=jumptol)
            else:
                pass
            return

        except AttributeError:
            print('Bad File')
            return

    def new_csv_imp(self):
        """This function uses an exact file path to upload a csv transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with open(self.infile, "r") as fd:
            txt = fd.readlines()
            if len(txt) > 1:
                if 'Serial' in txt[0]:
                    print('{:} is Solinst'.format(self.infile))
                    if 'UNIT: ' in txt[7]:
                        level_units = str(txt[7])[5:].strip().lower()
                    if 'UNIT: ' in txt[12]:
                        temp_units = str(txt[12])[5:].strip().lower()
                    f = pd.read_csv(self.infile, skiprows=13, parse_dates=[[0, 1]], usecols=[0, 1, 3, 4])
                    print(f.columns)
                    f['DateTime'] = pd.to_datetime(f['Date_Time'], errors='coerce')
                    f.set_index('DateTime', inplace=True)
                    f.drop('Date_Time', axis=1, inplace=True)
                    f.rename(columns={'LEVEL': 'Level', 'TEMP': 'Temp'}, inplace=True)
                    level = 'Level'
                    temp = 'Temp'

                    if level_units == "feet" or level_units == "ft":
                        f[level] = pd.to_numeric(f[level])
                    elif level_units == "kpa":
                        f[level] = pd.to_numeric(f[level]) * 0.33456
                        print("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "mbar":
                        f[level] = pd.to_numeric(f[level]) * 0.0334552565551
                    elif level_units == "psi":
                        f[level] = pd.to_numeric(f[level]) * 2.306726
                        print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "m" or level_units == "meters":
                        f[level] = pd.to_numeric(f[level]) * 3.28084
                        print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "???":
                        f[level] = pd.to_numeric(f[level])
                        print("Units in ???, {:} is messed up...".format(
                            os.path.basename(self.infile)))
                    else:
                        f[level] = pd.to_numeric(f[level])
                        print("Unknown units, no conversion")

                    if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                        f[temp] = f[temp]
                    elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                        print('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
                        f[temp] = (f[temp] - 32.0) * 5.0 / 9.0
                    return f

                elif 'Date' in txt[1]:
                    print('{:} is Global'.format(self.infile))
                    f = pd.read_csv(self.infile, skiprows=1, parse_dates=[[0, 1]])
                    # f = f.reset_index()
                    f['DateTime'] = pd.to_datetime(f['Date_ Time'], errors='coerce')
                    f = f[f.DateTime.notnull()]
                    if ' Feet' in list(f.columns.values):
                        f['Level'] = f[' Feet']
                        f.drop([' Feet'], inplace=True, axis=1)
                    elif 'Feet' in list(f.columns.values):
                        f['Level'] = f['Feet']
                        f.drop(['Feet'], inplace=True, axis=1)
                    else:
                        f['Level'] = f.iloc[:, 1]
                    # Remove first and/or last measurements if the transducer was out of the water
                    # f = dataendclean(f, 'Level')
                    flist = f.columns.tolist()
                    if ' Temp C' in flist:
                        f['Temperature'] = f[' Temp C']
                        f['Temp'] = f['Temperature']
                        f.drop([' Temp C', 'Temperature'], inplace=True, axis=1)
                    elif ' Temp F' in flist:
                        f['Temperature'] = (f[' Temp F'] - 32) * 5 / 9
                        f['Temp'] = f['Temperature']
                        f.drop([' Temp F', 'Temperature'], inplace=True, axis=1)
                    else:
                        f['Temp'] = np.nan
                    f.set_index(['DateTime'], inplace=True)
                    f['date'] = f.index.to_julian_date().values
                    f['datediff'] = f['date'].diff()
                    f = f[f['datediff'] > 0]
                    f = f[f['datediff'] < 1]
                    # bse = int(pd.to_datetime(f.index).minute[0])
                    # f = hourly_resample(f, bse)
                    f.rename(columns={' Volts': 'Volts'}, inplace=True)
                    f.drop([u'date', u'datediff', u'Date_ Time'], inplace=True, axis=1)
                    return f
            else:
                print('{:} is unrecognized'.format(self.infile))

    def new_lev_imp(self):
        with open(self.infile, "r") as fd:
            txt = fd.readlines()

        try:
            data_ind = txt.index('[Data]\n')
            # inst_info_ind = txt.index('[Instrument info from data header]\n')
            ch1_ind = txt.index('[CHANNEL 1 from data header]\n')
            ch2_ind = txt.index('[CHANNEL 2 from data header]\n')
            level = txt[ch1_ind + 1].split('=')[-1].strip().title()
            level_units = txt[ch1_ind + 2].split('=')[-1].strip().lower()
            temp = txt[ch2_ind + 1].split('=')[-1].strip().title()
            temp_units = txt[ch2_ind + 2].split('=')[-1].strip().lower()
            # serial_num = txt[inst_info_ind+1].split('=')[-1].strip().strip(".")
            # inst_num = txt[inst_info_ind+2].split('=')[-1].strip()
            # location = txt[inst_info_ind+3].split('=')[-1].strip()
            # start_time = txt[inst_info_ind+6].split('=')[-1].strip()
            # stop_time = txt[inst_info_ind+7].split('=')[-1].strip()

            df = pd.read_table(self.infile, parse_dates=[[0, 1]], sep='\s+', skiprows=data_ind + 2,
                               names=['Date', 'Time', level, temp],
                               skipfooter=1, engine='python')
            df.rename(columns={'Date_Time': 'DateTime'}, inplace=True)
            df.set_index('DateTime', inplace=True)

            if level_units == "feet" or level_units == "ft":
                df[level] = pd.to_numeric(df[level])
            elif level_units == "kpa":
                df[level] = pd.to_numeric(df[level]) * 0.33456
                print("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "mbar":
                df[level] = pd.to_numeric(df[level]) * 0.0334552565551
            elif level_units == "psi":
                df[level] = pd.to_numeric(df[level]) * 2.306726
                print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "m" or level_units == "meters":
                df[level] = pd.to_numeric(df[level]) * 3.28084
                print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            else:
                df[level] = pd.to_numeric(df[level])
                print("Unknown units, no conversion")

            if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                df[temp] = df[temp]
            elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                print('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
                df[temp] = (df[temp] - 32.0) * 5.0 / 9.0
            df['name'] = self.infile
            return df
        except ValueError:
            print('File {:} has formatting issues'.format(self.infile))

    def new_xle_imp(self):
        """This function uses an exact file path to upload a xle transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with io.open(self.infile, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = eletree.fromstring(contents)

        dfdata = []
        for child in tree[5]:
            dfdata.append([child[i].text for i in range(len(child))])
        f = pd.DataFrame(dfdata, columns=[tree[5][0][i].tag for i in range(len(tree[5][0]))])

        try:
            ch1ID = tree[3][0].text.title()  # Level
        except AttributeError:
            ch1ID = "Level"

        ch1Unit = tree[3][1].text.lower()

        if ch1Unit == "feet" or ch1Unit == "ft":
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
        elif ch1Unit == "kpa":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.33456
        elif ch1Unit == "mbar":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.0334552565551
        elif ch1Unit == "psi":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 2.306726
        elif ch1Unit == "m" or ch1Unit == "meters":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 3.28084
        elif ch1Unit == "???":
            print("CH. 1 units in {:}, {:} messed up...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
        else:
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
            print("Unknown units {:}, no conversion for {:}...".format(ch1Unit, os.path.basename(self.infile)))

        if 'ch2' in f.columns:
            try:
                ch2ID = tree[4][0].text.title()  # Level
            except AttributeError:
                ch2ID = "Temperature"

            ch2Unit = tree[4][1].text
            numCh2 = pd.to_numeric(f['ch2'])

            if ch2Unit == 'Deg C' or ch2Unit == 'Deg_C' or ch2Unit == u'\N{DEGREE SIGN}' + u'C':
                f[str(ch2ID).title()] = numCh2
            elif ch2Unit == 'Deg F' or ch2Unit == u'\N{DEGREE SIGN}' + u'F':
                print("CH. 2 units in {:}, converting {:} to C...".format(ch2Unit, os.path.basename(self.infile)))
                f[str(ch2ID).title()] = (numCh2 - 32) * 5 / 9
            else:
                print("Unknown temp units {:}, no conversion for {:}...".format(ch2Unit, os.path.basename(self.infile)))
                f[str(ch2ID).title()] = numCh2
        else:
            print('No channel 2 for {:}'.format(self.infile))

        if 'ch3' in f.columns:
            ch3ID = tree[5][0].text.title()  # Level
            ch3Unit = tree[5][1].text
            f[str(ch3ID).title()] = pd.to_numeric(f['ch3'])

        # add extension-free file name to dataframe
        f['name'] = self.infile.split('\\').pop().split('/').pop().rsplit('.', 1)[0]
        # combine Date and Time fields into one field
        f['DateTime'] = pd.to_datetime(f.apply(lambda x: x['Date'] + ' ' + x['Time'], 1))
        f[str(ch1ID).title()] = pd.to_numeric(f[str(ch1ID).title()])

        f = f.reset_index()
        f = f.set_index('DateTime')
        f['Level'] = f[str(ch1ID).title()]

        droplist = ['Date', 'Time', 'ch1', 'ch2', 'index', 'ms']
        for item in droplist:
            if item in f.columns:
                f = f.drop(item, axis=1)

        return f


# ----------------------------------------------------------------------------------------------------------------------
# Summary scripts - these extract transducer headers and summarize them in tables


def getfilename(path):
    """This function extracts the file name without file path or extension

    Args:
        path (file):
            full path and file (including extension of file)

    Returns:
        name of file as string
    """
    return path.split('\\').pop().split('/').pop().rsplit('.', 1)[0]


def compile_end_beg_dates(infile):
    """ Searches through directory and compiles transducer files, returning a dataframe of the file name,
    beginning measurement, and ending measurement. Complements xle_head_table, which derives these dates from an
    xle header.
    Args:
        infile (directory):
            folder containing transducer files
    Returns:
        A Pandas DataFrame containing the file name, beginning measurement date, and end measurement date
    Example::
        >>> compile_end_beg_dates('C:/folder_with_xles/')


    """
    filelist = glob.glob(infile + "/*")
    f = {}

    # iterate through list of relevant files
    for infile in filelist:
        f[getfilename(infile)] = NewTransImp(infile).well

    dflist = []
    for key, val in f.items():
        if val is not None:
            dflist.append((key, val.index[0], val.index[-1]))

    df = pd.DataFrame(dflist, columns=['filename', 'beginning', 'end'])
    return df


import xml.etree.ElementTree as eletree


class HeaderTable(object):
    def __init__(self, folder, filedict=None, filelist=None, workspace=None,
                 conn_file_root=None,
                 loc_table="ugs_ngwmn_monitoring_locations"):
        """

        Args:
            folder: directory containing transducer files
            filedict: dictionary matching filename to locationid
            filelist: list of files in folder
            workspace:
            loc_table: Table of location table in the SDE
        """
        self.folder = folder

        if filelist:
            self.filelist = filelist
        else:
            self.filelist = glob.glob(self.folder + "/*")

        self.filedict = filedict

        if workspace:
            self.workspace = workspace
        else:
            self.workspace = folder

        if conn_file_root:
            self.loc_table = pull_well_table(conn_file_root)
            print("Copying sites table!")

    def get_ftype(self, x):
        if x[1] == 'Solinst':
            ft = '.xle'
        else:
            ft = '.csv'
        return self.filedict.get(x[0] + ft)

    # examine and tabulate header information from files

    def file_summary_table(self):
        # create temp directory and populate it with relevant files
        self.filelist = self.xle_csv_filelist()
        fild = {}
        for file in self.filelist:
            file_extension = os.path.splitext(file)[1]

            if file_extension == '.xle':
                fild[file], = self.xle_head(file)
            elif file_extension == '.csv':
                fild[file], = self.csv_head(file)

        df = pd.DataFrame.from_dict(fild, orient='index')
        return df

    def make_well_table(self):
        file_info_table = self.file_summary_table()
        for i in ['Latitude', 'Longitude']:
            if i in file_info_table.columns:
                file_info_table.drop(i, axis=1, inplace=True)
        df = self.loc_table
        well_table = pd.merge(file_info_table, df, right_on='locationname', left_on='wellname', how='left')
        well_table.set_index('altlocationid', inplace=True)
        well_table['wellid'] = well_table.index
        well_table.dropna(subset=['wellname'], inplace=True)
        well_table.to_csv(self.folder + '/file_info_table.csv')
        print("Header Table with well information created at {:}/file_info_table.csv".format(self.folder))
        return well_table

    def xle_csv_filelist(self):
        exts = ('//*.xle', '//*.csv')  # the tuple of file types
        files_grabbed = []
        for ext in exts:
            files_grabbed += (glob.glob(self.folder + ext))
        return files_grabbed


    def xle_head(self, file):
        """Creates a Pandas DataFrame containing header information from all xle files in a folder

        Returns:
            A Pandas DataFrame containing the transducer header data

        Example:
            >>> xle_head_table('C:/folder_with_xles/')
        """
        # open text file
        df1 = {}
        df1['file_name'] = getfilename(file)
        with io.open(file, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = eletree.fromstring(contents)

            for child in tree[1]:
                df1[child.tag] = child.text

            for child in tree[2]:
                df1[child.tag] = child.text

        df1['trans type'] = 'Solinst'
        xledata = NewTransImp(file).well.sort_index()
        df1['beginning'] = xledata.first_valid_index()
        df1['end'] = xledata.last_valid_index()
        # df = pd.DataFrame.from_dict(df1, orient='index').T
        return df1, xledata

    def csv_head(self, file):
        cfile = {}
        try:
            cfile['file_name'] = getfilename(file)
            csvdata = NewTransImp(file).well.sort_index()
            if "Volts" in csvdata.columns:
                cfile['Battery_level'] = int(
                    round(csvdata.loc[csvdata.index[-1], 'Volts'] / csvdata.loc[csvdata.index[0], 'Volts'] * 100, 0))
            cfile['Sample_rate'] = (csvdata.index[1] - csvdata.index[0]).seconds * 100
            # cfile['filename'] = file
            cfile['beginning'] = csvdata.first_valid_index()
            cfile['end'] = csvdata.last_valid_index()
            # cfile['last_reading_date'] = csvdata.last_valid_index()
            cfile['Location'] = ' '.join(cfile['file_name'].split(' ')[:-1])
            cfile['trans type'] = 'Global Water'
            cfile['Num_log'] = len(csvdata)
            # df = pd.DataFrame.from_dict(cfile, orient='index').T
        except KeyError:
            pass
        return cfile, csvdata


def getwellid(infile, wellinfo):
    """Specialized function that uses a well info table and file name to lookup a well's id number"""
    m = re.search("\d", getfilename(infile))
    s = re.search("\s", getfilename(infile))
    if m.start() > 3:
        wellname = getfilename(infile)[0:m.start()].strip().lower()
    else:
        wellname = getfilename(infile)[0:s.start()].strip().lower()
    wellid = wellinfo[wellinfo['Well'] == wellname]['wellid'].values[0]
    return wellname, wellid


# -----------------------------------------------------------------------------------------------------------------------

class baroimport(object):
    def __init__(self):
        self.sde_conn = None
        self.wellid = None
        self.xledir = None
        self.well_files = None
        self.wellname = None
        self.welldict = None
        self.filedict = None
        self.man_file = None
        self.save_location = None
        self.should_plot = None
        self.chart_out = None
        self.tol = None
        self.stbl = None
        self.ovrd = None
        self.toexcel = None
        self.baro_comp_file = None
        self.to_import = None
        self.idget = None

    def many_baros(self):
        """Used by the MultBarometerImport tool to import multiple wells into the SDE"""

        self.xledir = self.xledir + r"\\"

        # upload barometric pressure data
        df = {}

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

        for b in range(len(self.wellid)):

            sitename = self.filedict[self.well_files[b]]
            altid = self.idget[sitename]

            df[altid] = NewTransImp(self.xledir + self.well_files[b]).well
            print("Importing {:} ({:})".format(sitename, altid))

            if self.to_import:
                upload_bp_data(df[altid], altid, enviro=self.sde_conn)
                print('Barometer {:} ({:}) Imported'.format(sitename, altid))

            if self.toexcel:
                from openpyxl import load_workbook
                if b == 0:
                    writer = pd.ExcelWriter(self.xledir + '/wells.xlsx')
                    df[altid].to_excel(writer, sheet_name='{:}_{:}'.format(sitename, b))
                    writer.save()
                    writer.close()
                else:
                    book = load_workbook(self.xledir + '/wells.xlsx')
                    writer = pd.ExcelWriter(self.xledir + '/wells.xlsx', engine='openpyxl')
                    writer.book = book
                    writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
                    df[altid].to_excel(writer, sheet_name='{:}_{:}'.format(sitename, b))
                    writer.save()
                    writer.close()

            if self.should_plot:
                # plot data
                df[altid].set_index('readingdate', inplace=True)
                y1 = df[altid]['waterelevation'].values
                y2 = df[altid]['barometer'].values
                x1 = df[altid].index.values
                x2 = df[altid].index.values

                fig, ax1 = plt.subplots()

                ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
                ax1.set_ylabel('Water Level Elevation', color='blue')
                ax1.set_ylim(min(df[altid]['waterelevation']), max(df[altid]['waterelevation']))
                y_formatter = tick.ScalarFormatter(useOffset=False)
                ax1.yaxis.set_major_formatter(y_formatter)
                ax2 = ax1.twinx()
                ax2.set_ylabel('Barometric Pressure (ft)', color='red')
                ax2.plot(x2, y2, color='red', label='Barometric pressure (ft)')
                h1, l1 = ax1.get_legend_handles_labels()
                h2, l2 = ax2.get_legend_handles_labels()
                ax1.legend(h1 + h2, l1 + l2, loc=3)
                plt.xlim(df[altid].first_valid_index() - datetime.timedelta(days=3),
                         df[altid].last_valid_index() + datetime.timedelta(days=3))
                plt.title('Well: {:}'.format(sitename))
                pdf_pages.savefig(fig)
                plt.close()

        if self.should_plot:
            pdf_pages.close()

        return


# ----------------------Class to import well data using arcgis interface-------------------------------------------------
class wellimport(object):
    """ Each function in this class represents the main operation performed by a tool in the ArcToolbox"""

    def __init__(self):
        self.sde_conn = None
        self.well_file = None
        self.baro_file = None
        self.man_startdate = None
        self.man_enddate = None
        self.man_start_level = None
        self.man_end_level = None
        self.wellid = None
        self.xledir = None
        self.well_files = None
        self.wellname = None
        self.welldict = None
        self.quer = None
        self.filedict = None
        self.man_file = None
        self.save_location = None
        self.should_plot = None
        self.should_import = None
        self.chart_out = None
        self.tol = None
        self.stbl = None
        self.ovrd = None
        self.toexcel = None
        self.baro_comp_file = None
        self.to_import = None
        self.idget = None
        self.sampint = 60
        self.jumptol = 1.0
        self.api_token = None
        self.stickup = None
        self.well_elev = None

    def read_xle(self):
        wellfile = NewTransImp(self.well_file).well
        wellfile.to_csv(self.save_location)
        return

    def comp_trans_data(self):
        searchdir = self.xledir
        wellid = self.wellid
        copydir = searchdir + "/P{:}/".format(wellid)
        get_serial = {1001: 1044546,
                      1002: 1044532, 1003: 1044519, 1004: 1044531, 1005: 1044524,
                      1006: 1044506, 1007: 1044545, 1008: 1044547,
                      1009: 1044530, 1010: 1044508, 1011: 1044536, 1012: 1044543,
                      1013: 1044544, 1014: 1044538, 1015: 1044504, 1016: 1044535,
                      1018: 1044516, 1019: 1044526, 1020: 1044517, 1021: 1044539,
                      1022: 1044520, 1023: 1044529, 1024: 1044502, 1025: 1044507,
                      1026: 1044528, 1028: 1046310, 1029: 1046323, 1030: 1046314,
                      1031: 1046393, 1033: 1046394, 1035: 1046388, 1036: 1046396,
                      1037: 1046382, 1038: 1046399, 1039: 1046315, 1040: 1046392,
                      1041: 1046319, 1042: 1046309, 1043: 1046398, 1044: 1046381,
                      1045: 1046387, 1046: 1046390, 1047: 1046400, 1048: 1044534,
                      1049: 1044548,
                      1051: 1044537, 1052: 1046311, 1053: 1046377, 1054: 1046318,
                      1055: 1046326, 1056: 1046395, 1057: 1046391, 1060: 1046306,
                      1061: 2011070, 1063: 2011072, 1065: 2011762, 1067: 2012196,
                      1068: 2022358, 1069: 2006774, 1070: 2012196, 1071: 2022498,
                      1072: 2022489, 1062: 2010753,
                      1073: 2022490, 1075: 2022401, 1076: 2022358, 1077: 2022348,
                      1078: 2022496, 1079: 2022499, 1080: 2022501, 1081: 2022167,
                      1090: 2010753, 1091: 1046308, 1092: 2011557, 1093: 1046384,
                      1094: 1046307, 1095: 1046317, 1096: 1044541, 1097: 1044534,
                      1098: 1046312, 2001: 2022348, 2002: 2022496, 2003: 2037596,
                      3001: 2037610, 3002: 2037607, 3003: 2006781,
                      20: ['pw07b', 'pw 07b', 'pw07 b']}
        transid = get_serial[wellid]
        filecontains = [str(transid), '_' + str(wellid) + '_', str(wellid) + '.']
        compilefiles(searchdir, copydir, filecontains, filetypes=['lev', 'xle'])

    def one_well(self):
        """Used in SingleTransducerImport Class.  This tool leverages the imp_one_well function to load a single well
        into the UGS SDE"""

        loc_table = "ugs_ngwmn_monitoring_locations"

        df = pull_well_table(engine)
        iddict = df.reset_index().set_index(['locationname']).to_dict()

        if self.man_startdate in ["#", "", None]:
            self.man_startdate, self.man_start_level, wlelev = find_extreme(self.wellid)

        man = pd.DataFrame(
            {'DateTime': [self.man_startdate, self.man_enddate],
             'Water Level (ft)': [self.man_start_level, self.man_end_level],
             'locationid': iddict.get(self.wellid)}).set_index('DateTime')
        print(man)

        baro = NewTransImp(self.baro_file).well
        baro.rename(columns={'Level': 'measuredlevel'}, inplace=True)

        df, man, be, drift = simp_imp_well(self.well_file, baro, int(iddict.get(self.wellid)), man, self.sde_conn,
                                           stbl_elev=True, gw_reading_table="reading",
                                           drift_tol=self.tol,
                                           imp=self.should_import)

        # df, man, be, drift = imp_one_well(self.well_file, self.baro_file, self.man_startdate,
        #                                  self.man_start_level, self.man_enddate,
        #                                  self.man_end_level, self.sde_conn, iddict.get(self.wellid),
        #                                  drift_tol=self.tol, override=self.ovrd)

        df.to_csv(self.save_location)

        if self.should_plot:
            # plot data
            pdf_pages = PdfPages(self.chart_out)
            y1 = df['waterelevation'].values
            y2 = df['barometer'].values
            x1 = df.index.values
            x2 = df.index.values

            x4 = man.index
            y4 = man['Meas_GW_Elev']
            fig, ax1 = plt.subplots()
            ax1.scatter(x4, y4, color='purple')
            ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
            ax1.set_ylabel('Water Level Elevation', color='blue')
            ax1.set_ylim(min(df['waterelevation']), max(df['waterelevation']))
            y_formatter = tick.ScalarFormatter(useOffset=False)
            ax1.yaxis.set_major_formatter(y_formatter)
            ax2 = ax1.twinx()
            ax2.set_ylabel('Barometric Pressure (ft)', color='red')
            ax2.plot(x2, y2, color='red', label='Barometric pressure (ft)')
            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc=3)
            plt.xlim(df.first_valid_index() - datetime.timedelta(days=3),
                     df.last_valid_index() + datetime.timedelta(days=3))
            plt.title('Well: {:}  Drift: {:}  Baro. Eff.: {:}'.format(self.wellid, drift, be))
            pdf_pages.savefig(fig)
            plt.close()
            pdf_pages.close()

        print('Well Imported!')

        return

    def remove_bp(self, stickup=0, well_elev=0, site_number=None):

        well = NewTransImp(self.well_file).well
        baro = NewTransImp(self.baro_file).well

        df = well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl', vented=False,
                             sampint=self.sampint)

        df = get_trans_gw_elevations(df, stickup, well_elev, site_number, dtw="corrwl")
        df.to_csv(self.save_location)

    def remove_bp_drift(self):

        well = NewTransImp(self.well_file).well
        baro = NewTransImp(self.baro_file).well
        stickup = self.stickup
        well_elev = self.well_elev
        site_number = self.wellid

        if pd.isna(stickup):
            stickup = 0
        else:
            pass

        corrwl = well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl',
                                 vented=False,
                                 sampint=self.sampint)

        man = pd.DataFrame(
            {'DateTime': [self.man_startdate, self.man_enddate],
             'measureddtw': [self.man_start_level * -1, self.man_end_level * -1]}).set_index('DateTime')

        dft = fix_drift(corrwl, man, corrwl='corrwl', manmeas='measureddtw')
        drift = round(float(dft[1]['drift'].values[0]), 3)

        print("Drift is {:} feet".format(drift))

        df = get_trans_gw_elevations(dft[0], stickup, well_elev, site_number, dtw="corrwl")

        df.to_csv(self.save_location)

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

            # plot data
            df = dft[0]
            y1 = df['DTW_WL'].values
            y2 = df['barometer'].values
            x1 = df.index.values
            x2 = df.index.values

            x4 = man.index
            y4 = man['measureddtw']
            fig, ax1 = plt.subplots()
            plt.xticks(rotation=70)
            ax1.scatter(x4, y4, color='purple')
            ax1.plot(x1, y1, color='blue', label='Water Level')
            ax1.set_ylabel('Depth to Water (ft)', color='blue')
            ax1.set_ylim(min(y1), max(y1))
            y_formatter = tick.ScalarFormatter(useOffset=False)
            ax1.yaxis.set_major_formatter(y_formatter)
            ax2 = ax1.twinx()
            ax2.set_ylabel('Barometric Pressure (ft)', color='red')
            ax2.plot(x2, y2, color='red', label='Barometric pressure (ft)')
            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc=3)
            plt.xlim(df.first_valid_index() - datetime.timedelta(days=3),
                     df.last_valid_index() + datetime.timedelta(days=3))

            pdf_pages.savefig(fig)
            plt.close()
            pdf_pages.close()

    def many_wells(self):
        """Used by the MultTransducerImport tool to import multiple wells into the SDE"""
        conn_file_root = self.sde_conn
        jumptol = self.jumptol

        headtable = HeaderTable(self.xledir, self.filedict, filelist=self.well_files, workspace=self.sde_conn)
        well_table = headtable.make_well_table()

        maxtime = max(pd.to_datetime(well_table['last_reading_date']))
        mintime = min(pd.to_datetime(well_table['Start_time']))
        print("Data span from {:} to {:}.".format(mintime, maxtime))

        maxtimebuff = maxtime + pd.DateOffset(days=2)
        mintimebuff = mintime - pd.DateOffset(days=2)

        # upload barometric pressure data
        baros = well_table[well_table['LocationType'] == 'Barometer']

        # lastdate = maxtime + datetime.timedelta(days=1)
        if maxtime > datetime.datetime.now():
            maxtimebuff = None

        if len(baros) > 0:
            for b in range(len(baros)):
                barline = baros.iloc[b, :]
                df = NewTransImp(barline['full_filepath']).well
                upload_bp_data(df, baros.index[b])
                print('Barometer {:} ({:}) Imported'.format(barline['locationname'], baros.index[b]))

        baros = [9024, 9025, 9027, 9049, 9003, 9062]
        baro_out = get_location_data(baros, self.sde_conn, first_date=mintimebuff, last_date=maxtimebuff)
        print('Barometer data download success!')

        # upload manual data from csv file
        if os.path.splitext(self.man_file)[-1] == '.csv':
            manl = pd.read_csv(self.man_file, index_col="readingdate")
        else:
            manl = pd.read_excel(self.man_file, index_col="readingdate")

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

        # import well data
        wells = well_table[well_table['LocationType'] == 'Well']
        for i in range(len(wells)):
            well_line = wells.iloc[i, :]
            print("Importing {:} ({:})".format(well_line['locationname'], wells.index[i]))

            baro_num = baro_out.loc[int(well_line['barologgertype'])]
            print(
                "Using barometer {:} for well {:}!".format(int(well_line['barologgertype']), well_line['locationname']))

            # try:
            man = manl[manl['locationid'] == int(wells.index[i])]
            df, man, be, drift = simp_imp_well(well_line['full_filepath'], baro_num, wells.index[i],
                                               man, stbl_elev=self.stbl, drift_tol=float(self.tol), jumptol=jumptol,
                                               conn_file_root=conn_file_root, imp=self.ovrd,
                                               api_token=self.api_token)

            print('Drift for well {:} is {:}.'.format(well_line['locationname'], drift))
            print("Well {:} complete.\n---------------".format(well_line['locationname']))

            if self.toexcel:
                if i == 0:
                    writer = pd.ExcelWriter(self.xledir + '/wells.xlsx', engine='xlsxwriter')
                    print(maxtime)
                    df.to_excel(writer, sheet_name='{:}_{:%Y%m}'.format(well_line['locationname'], maxtime))
                    writer.save()

                else:
                    df.to_excel(writer, sheet_name='{:}_{:%Y%m}'.format(well_line['locationname'], maxtime))
                    writer.save()
                writer.close()

            if self.should_plot:
                # plot data
                df.set_index('readingdate', inplace=True)
                y1 = df['waterelevation'].values
                y2 = df['barometer'].values
                x1 = df.index.values
                x2 = df.index.values

                x4 = man.index
                y4 = man['waterelevation']
                fig, ax1 = plt.subplots()
                ax1.scatter(x4, y4, color='purple')
                ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
                ax1.set_ylabel('Water Level Elevation', color='blue')
                # try:
                #    ax1.set_ylim(df['waterelevation'].min(), df['waterelevation'].min())
                # except:
                #    pass
                # y_formatter = tick.ScalarFormatter(useOffset=False)
                # ax1.yaxis.set_major_formatter(y_formatter)
                ax2 = ax1.twinx()
                ax2.set_ylabel('Barometric Pressure (ft)', color='red')
                ax2.plot(x2, y2, color='red', label='Barometric pressure (ft)')
                h1, l1 = ax1.get_legend_handles_labels()
                h2, l2 = ax2.get_legend_handles_labels()
                ax1.legend(h1 + h2, l1 + l2, loc=3)
                plt.xlim(df.first_valid_index() - datetime.timedelta(days=3),
                         df.last_valid_index() + datetime.timedelta(days=3))
                plt.title('Well: {:}  Drift: {:}  Baro. Eff.: {:}'.format(well_line['locationname'], drift, be))
                pdf_pages.savefig(fig)
                plt.close()
            # except Exception as err:
            #   printmes(err)

        if self.should_plot:
            pdf_pages.close()

        return

    def find_gaps(self):
        enviro = self.sde_conn
        first_date = self.man_startdate
        last_date = self.man_enddate
        save_local = self.save_location
        quer = self.quer

        if first_date == '':
            first_date = None
        if last_date == '':
            last_date = None

        if quer == 'all stations':
            where_clause = None
        elif quer == 'wetland_piezometers':
            where_clause = """wlnetworkname IN('Snake Valley Wetlands','Mills-Mona Wetlands')"""
        elif quer == 'snake valley wells':
            where_clause = """wlnetworkname IN('Snake Valley')"""
        elif quer == 'hazards':
            where_clause = """wlnetworkname" IN('Hazards')"""
        else:
            where_clause = None

        if where_clause:
            sql = 'SELECT altlocationid FROM ugs_ngwmn_monitoring_locations WHERE ' + where_clause
        else:
            sql = 'SELECT altlocationid FROM ugs_ngwmn_monitoring_locations'

        loc_ids = list(pd.read_sql(sql, engine)['altlocationid'].values)

        gapdct = {}

        for site_number in loc_ids:
            print(site_number)
            try:
                gapdct[site_number] = get_gap_data(int(site_number), enviro, gap_tol=0.5, first_date=first_date,
                                                   last_date=last_date,
                                                   gw_reading_table="reading")
            except AttributeError:
                print("Error with {:}".format(site_number))
        gapdata = pd.concat(gapdct)

        gapdata.rename_axis(['LocationId', 'Datetime'], inplace=True)
        gapdata.to_csv(save_local)

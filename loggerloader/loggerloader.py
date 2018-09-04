from __future__ import absolute_import, division, print_function, unicode_literals

import io
import os
import glob
import re

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.ticker as tick
import tempfile
from shutil import copyfile
import datetime

import xml.etree.ElementTree as ET

from pylab import rcParams

rcParams['figure.figsize'] = 15, 10

pd.options.mode.chained_assignment = None

try:
    import arcpy

    arcpy.env.overwriteOutput = True

except ImportError:
    pass


def printmes(x):
    """Attempts to turn print statements into messages in ArcGIS tools.
    If arcpy is not present, just a print statement is returned.

    :param x:intended print statement
    :return:
    """
    try:
        from arcpy import AddMessage
        AddMessage(x)
        print(x)
    except ModuleNotFoundError:
        print(x)


# -----------------------------------------------------------------------------------------------------------------------
# These functions align relative transducer reading to manual data


def fix_drift(well, manualfile, meas='Level', corrwl='corrwl', manmeas='MeasuredDTW', outcolname='DTW_WL'):
    """Remove transducer drift from nonvented transducer data. Faster and should produce same output as fix_drift_stepwise
    Args:
        well (pd.DataFrame):
            Pandas DataFrame of merged water level and barometric data; index must be datetime
        manualfile (pandas.core.frame.DataFrame):
            Pandas DataFrame of manual measurements
        meas (str):
            name of column in well DataFrame containing transducer data to be corrected
        manmeas (str):
            name of column in manualfile Dataframe containing manual measurement data
        outcolname (str):
            name of column resulting from correction
    Returns:
        wellbarofixed (pandas.core.frame.DataFrame):
            corrected water levels with bp removed
        driftinfo (pandas.core.frame.DataFrame):
            dataframe of correction parameters
    """
    # breakpoints = self.get_breakpoints(wellbaro, manualfile)
    breakpoints = []
    manualfile.index = pd.to_datetime(manualfile.index)
    manualfile.sort_index(inplace=True)

    wellnona = well.dropna(subset=[corrwl])

    if manualfile.first_valid_index() > wellnona.first_valid_index():
        breakpoints.append(wellnona.first_valid_index())

    for i in range(len(manualfile)):
        breakpoints.append(fcl(wellnona, manualfile.index[i]).name)

    if manualfile.last_valid_index() < wellnona.last_valid_index():
        breakpoints.append(wellnona.last_valid_index())

    breakpoints = pd.Series(breakpoints)
    breakpoints = pd.to_datetime(breakpoints)
    breakpoints.sort_values(inplace=True)
    breakpoints.drop_duplicates(inplace=True)
    # breakpoints = breakpoints.values
    bracketedwls, drift_features = {}, {}

    if well.index.name:
        dtnm = well.index.name
    else:
        dtnm = 'DateTime'
        well.index.name = 'DateTime'
    breakpoints = breakpoints.values
    manualfile.loc[:, 'julian'] = manualfile.index.to_julian_date()

    for i in range(len(breakpoints) - 1):
        # Break up pandas dataframe time series into pieces based on timing of manual measurements
        bracketedwls[i] = well.loc[
            (pd.to_datetime(well.index) > breakpoints[i]) & (pd.to_datetime(well.index) < breakpoints[i + 1])]
        df = bracketedwls[i]
        if len(df) > 0:
            df.sort_index(inplace=True)
            df.loc[:, 'julian'] = df.index.to_julian_date()

            last_trans = df.loc[df.last_valid_index(), meas]  # last transducer measurement
            first_trans = df.loc[df.first_valid_index(), meas]  # first transducer measurement
            first_trans_date = df.loc[df.first_valid_index(), 'julian']
            last_trans_date = df.loc[df.last_valid_index(), 'julian']

            first_man = fcl(manualfile, breakpoints[i])
            last_man = fcl(manualfile, breakpoints[i + 1])  # first manual measurement

            if df.first_valid_index() < manualfile.first_valid_index():
                first_man[manmeas] = None

            if df.last_valid_index() > manualfile.last_valid_index():
                last_man[manmeas] = None

            drift = 0.000001
            slope_man = 0
            slope_trans = 0

            # intercept of line = value of first manual measurement
            if pd.isna(first_man[manmeas]):
                b = last_trans - last_man[manmeas]

            elif pd.isna(last_man[manmeas]):
                b = first_trans - first_man[manmeas]

            else:
                b = first_trans - first_man[manmeas]
                drift = ((last_trans - last_man[manmeas]) - b)
                printmes("First man = {:}, Last man = {:}\nFirst man date = {:}, Last man date = {:}".format(first_man[manmeas],last_man[manmeas],first_man['julian'],last_man['julian']))
                slope_man = (first_man[manmeas] - last_man[manmeas]) / (first_man['julian'] - last_man['julian'])
                slope_trans = (first_trans - last_trans) / (first_trans_date - last_trans_date)

            new_slope = slope_trans - slope_man

            # slope of line = change in difference between manual and transducer over time;
            m = drift / (last_trans_date - first_trans_date)

            # datechange = amount of time between manual measurements
            df.loc[:, 'datechange'] = df['julian'].apply(lambda x: x - df.loc[df.index[0], 'julian'], 1)

            # bracketedwls[i].loc[:, 'wldiff'] = bracketedwls[i].loc[:, meas] - first_trans
            # apply linear drift to transducer data to fix drift; flipped x to match drift
            df.loc[:, 'DRIFTCORRECTION'] = df['datechange'].apply(lambda x: new_slope * x, 1)
            df.loc[:, outcolname] = df[meas] - (df['DRIFTCORRECTION'] + b)
            df.sort_index(inplace=True)
            drift_features[i] = {'t_beg': breakpoints[i], 'man_beg': first_man.name, 't_end': breakpoints[i + 1],
                                 'man_end': last_man.name, 'slope_man': slope_man, 'slope_trans': slope_trans,
                                 'intercept': b, 'slope': m, 'new_slope': new_slope,
                                 'first_meas': first_man[manmeas], 'last_meas': last_man[manmeas],
                                 'drift': drift, 'first_trans': first_trans, 'last_trans': last_trans}
        else:
            pass

    wellbarofixed = pd.concat(bracketedwls, sort=False)
    wellbarofixed.reset_index(inplace=True)
    wellbarofixed.set_index(dtnm, inplace=True)
    drift_info = pd.DataFrame(drift_features).T

    return wellbarofixed, drift_info


class WaterElevation(object):
    def __init__(self, site_number, well_table=None, conn_file_root=None):
        """
        :param site_number: Well id number
        :param well_table: Table of well data
        :param conn_file_root: path to connection file if you want the class to retrieve your table from a GIS table
        :return: stickup, well_elev
        """
        self.site_number = site_number
        self.conn_file_root = conn_file_root

        if well_table is None:
            arcpy.env.workspace = self.conn_file_root
            welltable = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"
            self.well_table = table_to_pandas_dataframe(welltable, query="AltLocationID is not Null")
            well_table.set_index('AltLocationID', inplace=True)
        else:
            self.well_table = well_table

        self.stdata = self.well_table[self.well_table.index == int(self.site_number)]
        self.well_elev = float(self.stdata['VerticalMeasure'].values[0])
        self.stickup = 0
        return

    def get_gw_elevs(self, manual, stable_elev=True):
        """
        Gets basic well parameters and most recent groundwater level data for a well id for dtw calculations.
        :param manual: Pandas Dataframe of manual data
        :param stable_elev: boolean; if False, stickup is retrieved from the manual measurements table;
        :return: manual table with new fields for depth to water and groundwater elevation
        """

        # some users might have incompatible column names
        old_fields = {'DateTime': 'READINGDATE',
                      'Location ID': 'LOCATIONID',
                      'Water Level (ft)': 'DTWBELOWCASING'}
        manual.rename(columns=old_fields, inplace=True)

        man_sub = manual[manual['LOCATIONID'] == int(self.site_number)]

        if stable_elev:
            # Selects well stickup from well table; if its not in the well table, then sets value to zero
            if self.stdata['Offset'].values[0] is None:
                self.stickup = 0
                printmes('Well ID {:} missing stickup!'.format(self.site_number))
            else:
                self.stickup = float(self.stdata['Offset'].values[0])
        else:
            # uses measured stickup data from manual table
            self.stickup = man_sub.loc[man_sub.last_valid_index(), 'Current Stickup Height']

        man_sub.loc[:, 'MeasuredDTW'] = man_sub['DTWBELOWCASING'] * -1
        man_sub.loc[:, 'WATERELEVATION'] = man_sub['MeasuredDTW'].apply(lambda x: self.well_elev + (x + self.stickup),
                                                                        1)

        return man_sub

    def prepare_fieldnames(self, df, level='Level', dtw='DTW_WL'):
        """
        This function adds the necessary field names to import well data into the SDE database.
        :param df: pandas DataFrame of processed well data
        :param level: raw transducer level from new_trans_imp, new_xle_imp, or new_csv_imp functions
        :param dtw: drift-corrected depth to water from fix_drift function
        :return: processed df with necessary field names for import
        """

        df['MEASUREDLEVEL'] = df[level]
        df['MEASUREDDTW'] = df[dtw] * -1
        df['DTWBELOWGROUNDSURFACE'] = df['MEASUREDDTW'].apply(lambda x: x - self.stickup, 1)
        df['WATERELEVATION'] = df['DTWBELOWGROUNDSURFACE'].apply(lambda x: self.well_elev - x, 1)
        df['LOCATIONID'] = self.site_number

        df.sort_index(inplace=True)

        fieldnames = ['READINGDATE', 'MEASUREDLEVEL', 'MEASUREDDTW', 'DRIFTCORRECTION',
                      'TEMP', 'LOCATIONID', 'BAROEFFICIENCYLEVEL',
                      'WATERELEVATION']

        if 'Temperature' in df.columns:
            df.rename(columns={'Temperature': 'TEMP'}, inplace=True)

        if 'TEMP' in df.columns:
            df['TEMP'] = df['TEMP'].apply(lambda x: np.round(x, 4), 1)
        else:
            df['TEMP'] = None

        if 'BAROEFFICIENCYLEVEL' in df.columns:
            pass
        else:
            df['BAROEFFICIENCYLEVEL'] = 0
        # subset bp df and add relevant fields
        df.index.name = 'READINGDATE'

        subset = df.reset_index()

        return subset, fieldnames


def trans_type(well_file):
    """Uses information from the raw transducer file to determine the type of transducer used.
    :param well_file: full path to raw transducer file
    :returns: transducer type"""
    if os.path.splitext(well_file)[1] == '.xle':
        trans_type = 'Solinst'
    elif os.path.splitext(well_file)[1] == '.lev':
        trans_type = 'Solinst'
    else:
        trans_type = 'Global Water'

    printmes('Trans type for well is {:}.'.format(trans_type))
    return trans_type


# -----------------------------------------------------------------------------------------------------------------------
# These functions import data into an SDE database


def imp_one_well(well_file, baro_file, man_startdate, man_start_level, man_endate, man_end_level,
                 conn_file_root, wellid, be=None,
                 gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading", drift_tol=0.3, override=False):

    arcpy.env.workspace = conn_file_root

    # convert raw files to dataframes
    well = new_trans_imp(well_file)
    baro = new_trans_imp(baro_file)

    # align baro and well timeseries; remove bp if nonvented
    corrwl = well_baro_merge(well, baro, vented=(trans_type(well_file) != 'Solinst'))

    # bring in manual data and create a dataframe from it
    man = pd.DataFrame(
        {'DateTime': [man_startdate, man_endate],
         'Water Level (ft)': [man_start_level, man_end_level],
         'Location ID': wellid}).set_index('DateTime')
    printmes(man)

    # pull stickup and elevation from well table; calculate water level elevations
    wtr_elevs = WaterElevation(wellid, conn_file_root=conn_file_root)
    man = wtr_elevs.get_gw_elevs(man)

    # correct for barometric efficiency if available
    if be:
        corrwl, be = correct_be(wellid, wtr_elevs.well_table, corrwl, be=be)
        corrwl['corrwl'] = corrwl['BAROEFFICIENCYLEVEL']

    # adjust for linear transducer drift between manual measurements
    dft = fix_drift(corrwl, man, meas='corrwl', manmeas='MeasuredDTW')
    drift = round(float(dft[1]['drift'].values[0]), 3)
    printmes('Drift for well {:} is {:.3f}.'.format(wellid, drift))
    df = dft[0]

    # add, remove, and arrange column names to match database format schema
    rowlist, fieldnames = wtr_elevs.prepare_fieldnames(df)

    # QA/QC to reject data if it exceeds user-based threshhold
    if drift <= drift_tol:
        edit_table(rowlist, gw_reading_table, fieldnames)
        printmes('Well {:} successfully imported!'.format(wellid))
    elif override == 1:
        edit_table(rowlist, gw_reading_table, fieldnames)
        printmes('Override initiated. Well {:} successfully imported!'.format(wellid))
    else:
        printmes('Well {:} drift greater than tolerance!'.format(wellid))
    return df, man, be, drift


def simp_imp_well(well_table, well_file, baro_out, wellid, manual, conn_file_root, stbl_elev=True, be=None,
                  gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading", drift_tol=0.3, jumptol=1.0, override=False):
    """
    Imports single well
    :param well_table: pandas dataframe of well data with ALternateID as index; needs altitude, be, stickup, and barolooger
    :param file: raw well file (xle, csv, or lev)
    :param baro_out: dictionary with barometer ID defining dataframe names
    :param wellid: unique ID of well field
    :param manual: manual data dataframe indexed by measure datetime
    :param stbl_elev:
    :param gw_reading_table:
    :param drift_tol:
    :param override:
    :return:
    """

    # import well file
    well = new_trans_imp(well_file, jumptol=jumptol).well
    wtr_elevs = WaterElevation(wellid, well_table = well_table, conn_file_root=conn_file_root)
    man = wtr_elevs.get_gw_elevs(manual, stable_elev=stbl_elev)
    well = jumpfix(well,'Level',threashold=2.0)

    try:
        baroid = wtr_elevs.well_table.loc[wellid, 'BaroLoggerType']
        printmes('{:}'.format(baroid))
        corrwl = well_baro_merge(well, baro_out.loc[baroid], barocolumn='MEASUREDLEVEL',
                                 vented=(trans_type(well_file) != 'Solinst'))
    except:
        corrwl = well_baro_merge(well, baro_out.loc[9003], barocolumn='MEASUREDLEVEL',
                                 vented=(trans_type(well_file) != 'Solinst'))

    if be:
        corrwl, be = correct_be(wellid, wtr_elevs.well_table, corrwl, be=be)
        corrwl['corrwl'] = corrwl['BAROEFFICIENCYLEVEL']

    dft = fix_drift(corrwl, man, meas='corrwl', manmeas='MeasuredDTW')
    printmes(arcpy.GetMessages())
    drift = round(float(dft[1]['drift'].values[0]), 3)
    #printmes('Drift for well {:} is {:}.'.format(wellid, drift))

    df = dft[0]
    df.sort_index(inplace=True)
    first_index = df.first_valid_index()
    last_index = df.last_valid_index()

    # Get last reading at the specified location
    #read_max, dtw, wlelev = find_extreme(wellid)
    query = "LOCATIONID = {: .0f} AND READINGDATE >= '{:}' AND READINGDATE <= '{:}'".format(wellid, first_index, last_index)
    existing_data = table_to_pandas_dataframe(gw_reading_table, query = query)
    printmes("Existing Len = {:}. Import Len = {:}.".format(len(existing_data),len(df)))

    rowlist, fieldnames = wtr_elevs.prepare_fieldnames(df)

    if (len(existing_data) == 0) and (abs(drift) < drift_tol):
        edit_table(rowlist, gw_reading_table, fieldnames)
        printmes(arcpy.GetMessages())
        printmes("Well {:} imported.".format(wellid))
    elif len(existing_data) == len(df) and (abs(drift) < drift_tol):
        printmes('Data for well {:} already exist!'.format(wellid))
    elif len(df) > len(existing_data) > 0 and abs(drift) < drift_tol:
        rowlist = rowlist[~rowlist['READINGDATE'].isin(existing_data['READINGDATE'].values)]
        edit_table(rowlist, gw_reading_table, fieldnames)
        printmes('Some values were missing. {:} values added.'.format(len(df)-len(existing_data)))
    elif override and (abs(drift) < drift_tol):
        edit_table(rowlist, gw_reading_table, fieldnames)
        printmes(arcpy.GetMessages())
        printmes("Override Activated. Well {:} imported.".format(wellid))
    elif abs(drift) > drift_tol:
        printmes('Drift for well {:} exceeds tolerance!'.format(wellid))
    else:
        printmes('Dates later than import data for well {:} already exist!'.format(wellid))
        pass

    return rowlist, man, be, drift


def upload_bp_data(df, site_number, return_df=False, overide=False, gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading"):
    import arcpy

    df.sort_index(inplace=True)
    first_index = df.first_valid_index()

    # Get last reading at the specified location
    read_max, dtw, wlelev = find_extreme(site_number)

    if read_max is None or read_max < first_index or overide is True:

        df['MEASUREDLEVEL'] = df['Level']
        df['LOCATIONID'] = site_number

        df.sort_index(inplace=True)

        fieldnames = ['READINGDATE', 'MEASUREDLEVEL', 'TEMP', 'LOCATIONID']

        if 'Temperature' in df.columns:
            df.rename(columns={'Temperature': 'TEMP'}, inplace=True)

        if 'TEMP' in df.columns:
            df['TEMP'] = df['TEMP'].apply(lambda x: np.round(x, 4), 1)
        else:
            df['TEMP'] = None

        df.index.name = 'READINGDATE'

        subset = df.reset_index()

        edit_table(subset, gw_reading_table, fieldnames)

        if return_df:
            return df

    else:
        printmes('Dates later than import data for this station already exist!')
        pass


# -----------------------------------------------------------------------------------------------------------------------
# The following modify and query an SDE database, assuming the user has a connection

def find_extreme(site_number, gw_table="UGGP.UGGPADMIN.UGS_GW_reading", extma='max'):
    """
    Find date extrema from a SDE table using query parameters
    :param site_number: LocationID of the site of interest
    :param gw_table: SDE table to be queried
    :param extma: options are 'max' (default) or 'min'
    :return: date of extrema, depth to water of extrema, water elevation of extrema
    """
    import arcpy
    from arcpy import env
    env.overwriteOutput = True

    if extma == 'max':
        sort = 'DESC'
    else:
        sort = 'ASC'
    query = "LOCATIONID = '{: .0f}'".format(site_number)
    field_names = ['READINGDATE', 'LOCATIONID', 'MEASUREDDTW', 'WATERELEVATION']
    sql_sn = ('TOP 1', 'ORDER BY READINGDATE {:}'.format(sort))
    # use a search cursor to iterate rows
    dateval, dtw, wlelev = [], [], []

    envtable = os.path.join(env.workspace, gw_table)

    with arcpy.da.SearchCursor(envtable, field_names, query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            dateval.append(row[0])
            dtw.append(row[1])
            wlelev.append(row[2])
    if len(dateval) < 1:
        return None, 0, 0
    else:
        return dateval[0], dtw[0], wlelev[0]


def get_gap_data(site_number, enviro, gap_tol=0.5, first_date=None, last_date=None,
                 gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading"):
    """

    :param site_number: List of Location ID of time series data to be processed
    :param enviro: workspace of SDE table
    :param gap_tol: gap tolerance in days; the smallest gap to look for; defaults to half a day (0.5)
    :param first_date: begining of time interval to search; defaults to 1/1/1900
    :param last_date: end of time interval to search; defaults to current day
    :param gw_reading_table: Name of SDE table in workspace to use
    :return: pandas dataframe with gap information
    """
    arcpy.env.workspace = enviro

    if first_date is None:
        first_date = datetime.datetime(1900, 1, 1)
    if last_date is None:
        last_date = datetime.datetime.now()

    if type(site_number) == list:
        pass
    else:
        site_number = [site_number]

    query_txt = "LOCATIONID IN({:}) AND TAPE = 0 AND READINGDATE >= '{:}' AND READINGDATE <= '{:}'"
    query = query_txt.format(','.join([str(i) for i in site_number]),first_date,last_date)

    sql_sn = (None, 'ORDER BY READINGDATE ASC')

    fieldnames = ['READINGDATE']

    # readings = table_to_pandas_dataframe(gw_reading_table, fieldnames, query, sql_sn)

    dt = []

    # use a search cursor to iterate rows
    with arcpy.da.SearchCursor(gw_reading_table, 'READINGDATE', query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            # combine the field names and row items together, and append them
            dt.append(row[0])

    df = pd.Series(dt, name='DateTime')
    df = df.to_frame()
    df['hr_diff'] = df['DateTime'].diff()
    df.set_index('DateTime', inplace=True)
    df['julian'] = df.index.to_julian_date()
    df['diff'] = df['julian'].diff()
    df['is_gap'] = df['diff'] > gap_tol

    def rowIndex(row):
        return row.name

    df['gap_end'] = df.apply(lambda x: rowIndex(x) if x['is_gap'] else pd.NaT, axis=1)
    df['gap_start'] = df.apply(lambda x: rowIndex(x) - x['hr_diff'] if x['is_gap'] else pd.NaT, axis=1)
    df = df[df['is_gap'] == True]
    return df


def get_location_data(site_numbers, enviro, first_date=None, last_date=None, limit=None,
                      gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading"):
    arcpy.env.workspace = enviro
    if not first_date:
        first_date = datetime.datetime(1900, 1, 1)
    elif type(first_date) == str:
        try:
            datetime.datetime.strptime(first_date, '%m/%d/%Y')
        except:
            first_date = datetime.datetime(1900, 1, 1)
    # Get last reading at the specified location
    if not last_date or last_date > datetime.datetime.now():
        last_date = datetime.datetime.now()

    query_txt = "LOCATIONID in({:}) and (READINGDATE >= '{:%m/%d/%Y}' and READINGDATE <= '{:%m/%d/%Y}')"
    if type(site_numbers) == list:
        site_numbers = ",".join([str(i) for i in site_numbers])
    else:
        pass
    query = query_txt.format(site_numbers, first_date, last_date + datetime.timedelta(days=1))
    #printmes(query)
    sql_sn = (limit, 'ORDER BY READINGDATE ASC')

    #fieldnames = get_field_names(gw_reading_table)
    fieldnames = ['READINGDATE','MEASUREDLEVEL','LOCATIONID']
    readings = table_to_pandas_dataframe(gw_reading_table, fieldnames, query, sql_sn)
    #readings.set_index('READINGDATE', inplace=True)
    #baro.rename(columns={'READINGDATE': 'DateTime', 'MEASUREDLEVEL': 'Level'}, inplace=True)
    readings.set_index(['LOCATIONID', 'READINGDATE'], inplace=True)
    if len(readings) == 0:
        printmes('No Records for location(s) {:}'.format(site_numbers))
    return readings


def barodistance(wellinfo):
    """Determines Closest Barometer to Each Well using wellinfo DataFrame"""
    barometers = {'barom': ['pw03', 'pw10', 'pw19'], 'X': [240327.49, 271127.67, 305088.9],
                  'Y': [4314993.95, 4356071.98, 4389630.71], 'Z': [1623.079737, 1605.187759, 1412.673738]}
    barolocal = pd.DataFrame(barometers)
    barolocal = barolocal.reset_index()
    barolocal.set_index('barom', inplace=True)

    wellinfo['pw03'] = np.sqrt((barolocal.loc['pw03', 'X'] - wellinfo['UTMEasting']) ** 2 + \
                               (barolocal.loc['pw03', 'Y'] - wellinfo['UTMNorthing']) ** 2 + \
                               (barolocal.loc['pw03', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw10'] = np.sqrt((barolocal.loc['pw10', 'X'] - wellinfo['UTMEasting']) ** 2 + \
                               (barolocal.loc['pw10', 'Y'] - wellinfo['UTMNorthing']) ** 2 + \
                               (barolocal.loc['pw10', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw19'] = np.sqrt((barolocal.loc['pw19', 'X'] - wellinfo['UTMEasting']) ** 2 + \
                               (barolocal.loc['pw19', 'Y'] - wellinfo['UTMNorthing']) ** 2 + \
                               (barolocal.loc['pw19', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['closest_baro'] = wellinfo[['pw03', 'pw10', 'pw19']].T.idxmin()
    return wellinfo


# -----------------------------------------------------------------------------------------------------------------------
# These are the core functions that are used to import and export data from an SDE database

def get_field_names(table):
    read_descr = arcpy.Describe(table)
    field_names = []
    for field in read_descr.fields:
        field_names.append(field.name)
    field_names.remove('OBJECTID')
    return field_names


def table_to_pandas_dataframe(table, field_names=None, query=None, sql_sn=(None, None)):
    """
    Load data into a Pandas Data Frame for subsequent analysis.
    :param table: Table readable by ArcGIS.
    :param field_names: List of fields.
    :param query: SQL query to limit results
    :param sql_sn: sort fields for sql; see http://pro.arcgis.com/en/pro-app/arcpy/functions/searchcursor.htm
    :return: Pandas DataFrame object.
    """

    # if field names are not specified
    if not field_names:
        field_names = get_field_names(table)
    # create a pandas data frame
    df = pd.DataFrame(columns=field_names)

    # use a search cursor to iterate rows
    with arcpy.da.SearchCursor(table, field_names, query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            # combine the field names and row items together, and append them
            df = df.append(dict(zip(field_names, row)), ignore_index=True)

    # return the pandas data frame
    return df


def edit_table(df, gw_reading_table, fieldnames):
    """
    Edits SDE table by inserting new rows
    :param df: pandas DataFrame
    :param gw_reading_table: sde table to edit
    :param fieldnames: field names that are being appended in order of appearance in dataframe or list row
    :return:
    """

    table_names = get_field_names(gw_reading_table)

    for name in fieldnames:
        if name not in table_names:
            fieldnames.remove(name)
            printmes("{:} not in {:} fieldnames!".format(name, gw_reading_table))

    if len(fieldnames) > 0:
        subset = df[fieldnames]
        rowlist = subset.values.tolist()

        arcpy.env.overwriteOutput = True
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing(False, False)
        edit.startOperation()

        cursor = arcpy.da.InsertCursor(gw_reading_table, fieldnames)
        for j in range(len(rowlist)):
            cursor.insertRow(rowlist[j])

        del cursor
        edit.stopOperation()
        edit.stopEditing(True)
    else:
        printmes('No data imported!')


# -----------------------------------------------------------------------------------------------------------------------
# These scripts remove outlier data and filter the time series of jumps and erratic measurements

def dataendclean(df, x, inplace=False, jumptol = 1.0):
    """Trims off ends and beginnings of datasets that exceed 2.0 standard deviations of the first and last 30 values

    :param df: Pandas DataFrame
    :type df: pandas.core.frame.DataFrame
    :param x: Column name of data to be trimmed contained in df
    :type x: str
    :param inplace: if DataFrame should be duplicated
    :type inplace: bool

    :returns: df trimmed data
    :rtype: pandas.core.frame.DataFrame

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
                printmes("Dropped from beginning to " + str(jump.index[i]))
            if jump.index[i] > df.index[-50]:
                df = df[df.index < jump.index[i]]
                printmes("Dropped from end to " + str(jump.index[i]))
    except IndexError:
        printmes('No Jumps')
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
    df1 = df1.resample('1Min').mean()
    df1 = df1.interpolate(method='time')
    df2 = df2.resample('1Min').mean()
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
        stdata = well_table[well_table['WellID'] == site_number]
        be = stdata['BaroEfficiency'].values[0]
    if be is None:
        be = 0
    else:
        be = float(be)

    if be == 0:
        welldata['BAROEFFICIENCYLEVEL'] = welldata[meas]
    else:
        welldata['BAROEFFICIENCYLEVEL'] = welldata[[meas, baro]].apply(lambda x: x[0] + be * x[1], 1)

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
        This function uses pandas powerful time-series manipulation to upsample to every minute, then downsample to every hour,
        on the hour.
        This function will need adjustment if you do not want it to return hourly samples, or iusgsGisf you are sampling more frequently than
        once per minute.
        see http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
    """

    df = df.resample('1Min').mean().interpolate(method='time', limit=90)

    df = df.resample(str(minutes) + 'Min', closed='left', label='left', base=bse).mean()
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
    baro = hourly_resample(barofile, 0, sampint)
    well = hourly_resample(wellfile, 0, sampint)

    # reassign `Level` to reduce ambiguity
    baro = baro.rename(columns={barocolumn: 'barometer'})

    if 'TEMP' in baro.columns:
        baro.drop('TEMP', axis=1, inplace=True)
    elif 'Temperature' in baro.columns:
        baro.drop('Temperature', axis=1, inplace=True)

    # combine baro and well data for easy calculations, graphing, and manipulation
    wellbaro = pd.merge(well, baro, left_index=True, right_index=True, how='inner')

    wellbaro['dbp'] = wellbaro['barometer'].diff()
    wellbaro['dwl'] = wellbaro[wellcolumn].diff()
    first_well = wellbaro[wellcolumn][0]

    if vented:
        wellbaro[outcolumn] = wellbaro[wellcolumn]
    else:
        wellbaro[outcolumn] = wellbaro[['dbp', 'dwl']].apply(lambda x: x[1] - x[0], 1).cumsum() + first_well
    wellbaro.loc[wellbaro.index[0], outcolumn] = first_well
    return wellbaro


def fcl(df, dtObj):
    """Finds closest date index in a dataframe to a date object
    Args:
        df:
            DataFrame
        dtObj:
            date object

    taken from: http://stackoverflow.com/questions/15115547/find-closest-row-of-dataframe-to-given-time-in-pandas
    """
    return df.iloc[np.argmin(np.abs(pd.to_datetime(df.index) - dtObj))]  # remove to_pydatetime()


# -----------------------------------------------------------------------------------------------------------------------

# -----------------------------------------------------------------------------------------------------------------------
# Raw transducer import functions - these convert raw lev, xle, and csv files to Pandas Dataframes for processing




class new_trans_imp(object):
    """This function uses an imports and cleans the ends of transducer file.

    Args:
        infile (file):
            complete file path to input file
        xle (bool):
            if true, then the file type should be xle; else it should be csv

    Returns:
        A Pandas DataFrame containing the transducer data
    """
    def __init__(self, infile, trim_end=True, jumptol=1.0):
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
                printmes('filetype not recognized')
                self.well = None

            if self.well is None:
                pass
            elif trim_end:
                self.well = dataendclean(self.well, 'Level', jumptol=jumptol)
            else:
                pass
            return

        except AttributeError:
            printmes('Bad File')
            return

    def new_csv_imp(self):
        """This function uses an exact file path to upload a csv transducer file.

        Args:
            infile (file):
                complete file path to input file

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
                        printmes("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "mbar":
                        f[level] = pd.to_numeric(f[level]) * 0.0334552565551
                    elif level_units == "psi":
                        f[level] = pd.to_numeric(f[level]) * 2.306726
                        printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "m" or level_units == "meters":
                        f[level] = pd.to_numeric(f[level]) * 3.28084
                        printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    else:
                        f[level] = pd.to_numeric(f[level])
                        printmes("Unknown units, no conversion")

                    if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                        f[temp] = f[temp]
                    elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                        printmes('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
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
                printmes("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "mbar":
                df[level] = pd.to_numeric(df[level]) * 0.0334552565551
            elif level_units == "psi":
                df[level] = pd.to_numeric(df[level]) * 2.306726
                printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "m" or level_units == "meters":
                df[level] = pd.to_numeric(df[level]) * 3.28084
                printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            else:
                df[level] = pd.to_numeric(df[level])
                printmes("Unknown units, no conversion")

            if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                df[temp] = df[temp]
            elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                printmes('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
                df[temp] = (df[temp] - 32.0) * 5.0 / 9.0
            df['name'] = self.infile
            return df
        except ValueError:
            printmes('File {:} has formatting issues'.format(self.infile))


    def new_xle_imp(self):
        """This function uses an exact file path to upload a xle transducer file.

        Args:
            infile (file):
                complete file path to input file

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with io.open(self.infile, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = ET.fromstring(contents)

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
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.33456
            printmes("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
        elif ch1Unit == "mbar":
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.0334552565551
        elif ch1Unit == "psi":
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 2.306726
            printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
        elif ch1Unit == "m" or ch1Unit == "meters":
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 3.28084
            printmes("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
        else:
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
            print(ch1Unit)
            printmes("Unknown units, no conversion")

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
                printmes('Temp in F, converting to C')
                f[str(ch2ID).title()] = (numCh2 - 32) * 5 / 9
            else:
                printmes('Unknown temp Units')
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

# -----------------------------------------------------------------------------------------------------------------------
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
        folder (directory):
            folder containing transducer files
    Returns:
        A Pandas DataFrame containing the file name, beginning measurement date, and end measurement date
    Example::
        >>> compile_end_beg_dates('C:/folder_with_xles/')


    """
    filelist = glob.glob(infile)
    f = {}

    # iterate through list of relevant files
    for infile in filelist:
        f[getfilename(infile)] = new_trans_imp(infile)

    dflist = []
    for key, val in f.items():
        if val is not None:
            dflist.append((key, val.index[0], val.index[-1]))

    df = pd.DataFrame(dflist, columns=['filename', 'beginning', 'end'])
    return df


def xle_head_table(folder):
    """Creates a Pandas DataFrame containing header information from all xle files in a folder
    Args:
        folder (directory):
            folder containing xle files
    Returns:
        A Pandas DataFrame containing the transducer header data
    Example::
        >>> xle_head_table('C:/folder_with_xles/')
    """
    # open text file
    df = {}
    for infile in glob.glob(folder + "//*.xle", recursive=True):
        basename = os.path.basename(folder + infile)
        with io.open(infile, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = ET.fromstring(contents)

        df1 = {}
        for child in tree[1]:
            df1[child.tag] = child.text

        for child in tree[2]:
            df1[child.tag] = child.text

        df1['last_reading_date'] = tree[-1][-1][0].text
        df[basename[:-4]] = df1
    allwells = pd.DataFrame(df).T
    allwells.index.name = 'filename'
    allwells['trans type'] = 'Solinst'
    allwells['fileroot'] = allwells.index
    allwells['full_filepath'] = allwells['fileroot'].apply(lambda x: folder + x + '.xle', 1)
    return allwells


def csv_info_table(folder):
    csv = {}
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    field_names = ['filename', 'Start_time', 'Stop_time']
    df = pd.DataFrame(columns=field_names)
    for file in files:
        fileparts = os.path.basename(file).split('.')
        filetype = fileparts[1]
        basename = fileparts[0]
        if filetype == 'csv':
            try:
                cfile = {}
                csv[basename] = new_trans_imp(os.path.join(folder, file))
                cfile['Battery_level'] = int(round(csv[basename].loc[csv[basename]. \
                                                   index[-1], 'Volts'] / csv[basename]. \
                                                   loc[csv[basename].index[0], 'Volts'] * 100, 0))
                cfile['Sample_rate'] = (csv[basename].index[1] - csv[basename].index[0]).seconds * 100
                cfile['filename'] = basename
                cfile['fileroot'] = basename
                cfile['full_filepath'] = os.path.join(folder, file)
                cfile['Start_time'] = csv[basename].first_valid_index()
                cfile['Stop_time'] = csv[basename].last_valid_index()
                cfile['last_reading_date'] = csv[basename].last_valid_index()
                cfile['Location'] = ' '.join(basename.split(' ')[:-1])
                cfile['trans type'] = 'Global Water'
                df = df.append(cfile, ignore_index=True)
            except:
                pass
    df.set_index('filename', inplace=True)
    return df, csv


def getwellid(infile, wellinfo):
    """Specialized function that uses a well info table and file name to lookup a well's id number"""
    m = re.search("\d", getfilename(infile))
    s = re.search("\s", getfilename(infile))
    if m.start() > 3:
        wellname = getfilename(infile)[0:m.start()].strip().lower()
    else:
        wellname = getfilename(infile)[0:s.start()].strip().lower()
    wellid = wellinfo[wellinfo['Well'] == wellname]['WellID'].values[0]
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
        arcpy.env.workspace = self.sde_conn

        self.xledir = self.xledir + r"\\"

        # upload barometric pressure data
        df = {}

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

        for b in range(len(self.wellid)):

            sitename = self.filedict[self.well_files[b]]
            altid = self.idget[sitename]
            printmes([b, altid, sitename])
            df[altid] = new_trans_imp(self.xledir + self.well_files[b]).well
            printmes("Importing {:} ({:})".format(sitename, altid))

            if self.to_import:
                upload_bp_data(df[altid], altid)
                printmes('Barometer {:} ({:}) Imported'.format(sitename, altid))

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
                df[altid].set_index('READINGDATE', inplace=True)
                y1 = df[altid]['WATERELEVATION'].values
                y2 = df[altid]['barometer'].values
                x1 = df[altid].index.values
                x2 = df[altid].index.values

                fig, ax1 = plt.subplots()

                ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
                ax1.set_ylabel('Water Level Elevation', color='blue')
                ax1.set_ylim(min(df[altid]['WATERELEVATION']), max(df[altid]['WATERELEVATION']))
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

            """"if os.path.isfile(self.baro_comp_file) and os.access(os.path.dirname(self.baro_comp_file), os.R_OK):
                h = pd.read_csv(self.baro_comp_file, index_col=0, header=0, parse_dates=True)
                g = pd.concat([h, df[altid]])
                os.remove(self.baro_comp_file)
            else:
                g = df[altid]
            # remove duplicates based on index then sort by index
            g['ind'] = g.index
            g.drop_duplicates(subset='ind', inplace=True)
            g.drop('ind', axis=1, inplace=True)
            g = g.sort_index()
            g.to_csv(self.baro_comp_file)"""

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

    def read_xle(self):
        wellfile = new_trans_imp(self.well_file).well
        wellfile.to_csv(self.save_location)
        return

    def one_well(self):
        """Used in SingleTransducerImport Class.  This tool leverages the imp_one_well function to load a single well
        into the UGS SDE"""
        arcpy.env.workspace = self.sde_conn
        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

        loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName')]
        loc_ids = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID')]

        iddict = dict(zip(loc_names, loc_ids))

        if self.man_startdate in ["#", "", None]:
            self.man_startdate, self.man_start_level, wlelev = find_extreme(self.wellid)

        df, man, be, drift = imp_one_well(self.well_file, self.baro_file, self.man_startdate,
                                          self.man_start_level, self.man_enddate,
                                          self.man_end_level, self.sde_conn, iddict.get(self.wellid),
                                          drift_tol=self.tol, override=self.ovrd)

        if self.should_plot:
            # plot data
            pdf_pages = PdfPages(self.chart_out)
            y1 = df['WATERELEVATION'].values
            y2 = df['barometer'].values
            x1 = df.index.values
            x2 = df.index.values

            x4 = man.index
            y4 = man['Meas_GW_Elev']
            fig, ax1 = plt.subplots()
            ax1.scatter(x4, y4, color='purple')
            ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
            ax1.set_ylabel('Water Level Elevation', color='blue')
            ax1.set_ylim(min(df['WATERELEVATION']), max(df['WATERELEVATION']))
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

        printmes('Well Imported!')
        printmes(arcpy.GetMessages())
        return

    def remove_bp(self):

        well = new_trans_imp(self.well_file).well
        baro = new_trans_imp(self.baro_file).well

        df = well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl', vented=False,
                             sampint=self.sampint)

        df.to_csv(self.save_location)

    def remove_bp_drift(self):

        well = new_trans_imp(self.well_file).well
        baro = new_trans_imp(self.baro_file).well

        corrwl = well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl',
                                 vented=False,
                                 sampint=self.sampint)

        man = pd.DataFrame(
            {'DateTime': [self.man_startdate, self.man_enddate],
             'MeasuredDTW': [self.man_start_level * -1, self.man_end_level * -1]}).set_index('DateTime')

        dft = fix_drift(corrwl, man, meas='corrwl', manmeas='MeasuredDTW')
        drift = round(float(dft[1]['drift'].values[0]), 3)

        printmes("Drift is {:} feet".format(drift))



        dft[0].to_csv(self.save_location)

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

            # plot data
            df = dft[0]
            y1 = df['DTW_WL'].values
            y2 = df['barometer'].values
            x1 = df.index.values
            x2 = df.index.values

            x4 = man.index
            y4 = man['MeasuredDTW']
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

    def get_ftype(self, x):
        if x[1] == 'Solinst':
            ft = '.xle'
        else:
            ft = '.csv'
        return self.filedict.get(x[0] + ft)

    def many_wells(self):
        """Used by the MultTransducerImport tool to import multiple wells into the SDE"""
        arcpy.env.workspace = self.sde_conn
        conn_file_root = self.sde_conn
        jumptol = self.jumptol
        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

        # create empty dataframe to house well data
        field_names = ['LocationID', 'LocationName', 'LocationType', 'LocationDesc', 'AltLocationID', 'VerticalMeasure',
                       'VerticalUnit', 'WellDepth', 'SiteID', 'Offset', 'LoggerType', 'BaroEfficiency',
                       'BaroEfficiencyStart', 'BaroLoggerType']
        df = pd.DataFrame(columns=field_names)
        # populate dataframe with data from SDE well table
        search_cursor = arcpy.da.SearchCursor(loc_table, field_names)
        for row in search_cursor:
            # combine the field names and row items together, and append them
            df = df.append(dict(zip(field_names, row)), ignore_index=True)
        df.dropna(subset=['AltLocationID'], inplace=True)

        # create temp directory and populate it with relevant files
        file_extension = []
        dirpath = tempfile.mkdtemp(suffix=r'\\')
        for file in self.well_files:
            copyfile(os.path.join(self.xledir, file), os.path.join(dirpath, file))
            file_extension.append(os.path.splitext(file)[1])

        # examine and tabulate header information from files

        if '.xle' in file_extension and '.csv' in file_extension:
            xles = xle_head_table(dirpath)
            printmes('xles examined')
            csvs = csv_info_table(dirpath)
            printmes('csvs examined')
            file_info_table = pd.concat([xles, csvs[0]], sort=False)
        elif '.xle' in file_extension:
            xles = xle_head_table(dirpath)
            printmes('xles examined')
            file_info_table = xles
        elif '.csv' in file_extension:
            csvs = csv_info_table(dirpath)
            printmes('csvs examined')
            file_info_table = csvs[0]

        # combine header table with the sde table
        file_info_table['WellName'] = file_info_table[['fileroot', 'trans type']].apply(lambda x: self.get_ftype(x), 1)
        well_table = pd.merge(file_info_table, df, right_on='LocationName', left_on='WellName', how='left')
        well_table.set_index('AltLocationID', inplace=True)
        well_table['WellID'] = well_table.index
        well_table.dropna(subset=['WellName'], inplace=True)
        well_table.to_csv(self.xledir + '/file_info_table.csv')
        printmes("Header Table with well information created at {:}/file_info_table.csv".format(self.xledir))
        maxtime = max(pd.to_datetime(well_table['last_reading_date']))
        mintime = min(pd.to_datetime(well_table['Start_time']))
        maxtimebuff = max(pd.to_datetime(well_table['last_reading_date'])) + pd.DateOffset(days=2)
        mintimebuff = min(pd.to_datetime(well_table['Start_time'])) - pd.DateOffset(days=2)
        printmes("Data span from {:} to {:}.".format(mintime, maxtime))

        # upload barometric pressure data
        baro_out = {}
        baros = well_table[well_table['LocationType'] == 'Barometer']

        # lastdate = maxtime + datetime.timedelta(days=1)
        if maxtime > datetime.datetime.today():
            lastdate = None
        else:
            lastdate = maxtimebuff

        if len(baros) < 1:
            baros = [9024, 9025, 9027, 9049, 9061, 9003, 9062]

            baro_out = get_location_data(baros, self.sde_conn, first_date=mintimebuff, last_date=lastdate)
            printmes('Barometer data download success')

        else:
            for b in range(len(baros)):
                barline = baros.iloc[b, :]
                df = new_trans_imp(barline['full_filepath']).well
                upload_bp_data(df, baros.index[b])
                baro_out[baros.index[b]] = get_location_data(baros.index[b], self.sde_conn, first_date=mintime,
                                                             last_date=lastdate)
                printmes('Barometer {:} ({:}) Imported'.format(barline['LocationName'], baros.index[b]))

        # upload manual data from csv file
        if os.path.splitext(self.man_file)[-1] == '.csv':
            manl = pd.read_csv(self.man_file, index_col="READINGDATE")
        else:
            manl = pd.read_excel(self.man_file, index_col="READINGDATE")

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)

        # import well data
        wells = well_table[well_table['LocationType'] == 'Well']
        for i in range(len(wells)):
            well_line = wells.iloc[i, :]
            printmes("Importing {:} ({:})".format(well_line['LocationName'], wells.index[i]))

            df, man, be, drift = simp_imp_well(well_table, well_line['full_filepath'], baro_out, wells.index[i],
                                               manl, stbl_elev=self.stbl, drift_tol=float(self.tol),jumptol=jumptol,
                                               conn_file_root=conn_file_root,override=self.ovrd)
            printmes(arcpy.GetMessages())
            printmes('Drift for well {:} is {:}.'.format(well_line['LocationName'], drift))
            printmes("Well {:} complete.\n---------------".format(well_line['LocationName']))

            if self.toexcel:
                from openpyxl import load_workbook
                if i == 0:
                    writer = pd.ExcelWriter(self.xledir + '/wells.xlsx')
                    df.to_excel(writer, sheet_name='{:}_{:%Y%m}'.format(well_line['LocationName'], maxtime))
                    writer.save()
                    writer.close()
                else:
                    book = load_workbook(self.xledir + '/wells.xlsx')
                    writer = pd.ExcelWriter(self.xledir + '/wells.xlsx', engine='openpyxl')
                    writer.book = book
                    writer.sheets = dict((ws.title, ws) for ws in book.worksheets)
                    df.to_excel(writer, sheet_name='{:}_{:%Y%m}'.format(well_line['LocationName'], maxtime))
                    writer.save()
                    writer.close()

            if self.should_plot:
                # plot data
                df.set_index('READINGDATE', inplace=True)
                y1 = df['WATERELEVATION'].values
                y2 = df['barometer'].values
                x1 = df.index.values
                x2 = df.index.values

                x4 = man.index
                y4 = man['WATERELEVATION']
                fig, ax1 = plt.subplots()
                ax1.scatter(x4, y4, color='purple')
                ax1.plot(x1, y1, color='blue', label='Water Level Elevation')
                ax1.set_ylabel('Water Level Elevation', color='blue')
                try:
                    ax1.set_ylim(df['WATERELEVATION'].min(), df['WATERELEVATION'].min())
                except:
                    pass
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
                plt.title('Well: {:}  Drift: {:}  Baro. Eff.: {:}'.format(well_line['LocationName'], drift, be))
                pdf_pages.savefig(fig)
                plt.close()

        if self.should_plot:
            pdf_pages.close()

        return

    def find_gaps(self):
        enviro = self.sde_conn
        first_date = self.man_startdate
        last_date = self.man_enddate
        save_local= self.save_location
        quer = self.quer
        if first_date == '':
            first_date = None
        if last_date == '':
            last_date = None

        if quer == 'all stations':
            where_clause = None
        elif quer == 'wetland_piezometers':
            where_clause = "WLNetworkName IN('Snake Valley Wetlands','Mills-Mona Wetlands')"
        elif quer == 'snake valley wells':
            where_clause = "WLNetworkName IN('Snake Valley')"
        elif quer == 'hazards':
            where_clause = 'Hazards'
        else:
            where_clause = None

        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"
        loc_ids = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID',where_clause)]
        gapdct = {}

        for site_number in loc_ids:
            printmes(site_number)
            try:
                gapdct[site_number] = get_gap_data(int(site_number), enviro, gap_tol=0.5, first_date=first_date, last_date=last_date,
                             gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading")
            except AttributeError:
                printmes("Error with {:}".format(site_number))
        gapdata = pd.concat(gapdct)

        gapdata.rename_axis(['LocationId', 'Datetime'], inplace=True)
        gapdata.to_csv(save_local)


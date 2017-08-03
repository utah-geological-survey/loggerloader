
from __future__ import absolute_import, division, print_function, unicode_literals
import pandas as pd
import glob
import os
import xmltodict
import numpy as np

from loggerloader.utilities import *
from loggerloader.header_tables import *
from loggerloader.data_fixers import *

def compilation(inputfile):
    """This function reads multiple xle transducer files in a directory and generates a compiled Pandas DataFrame.
    Args:
        inputfile (file):
            complete file path to input files; use * for wildcard in file name
    Returns:
        outfile (object):
            Pandas DataFrame of compiled data
    Example::
        >>> compilation('O:\\Snake Valley Water\\Transducer Data\\Raw_data_archive\\all\\LEV\\*baro*')
        picks any file containing 'baro'
    """

    # create empty dictionary to hold DataFrames
    f = {}

    # generate list of relevant files
    filelist = glob.glob(inputfile)

    # iterate through list of relevant files
    for infile in filelist:
        # get the extension of the input file
        filetype = os.path.splitext(infile)[1]
        # run computations using lev files
        if filetype == '.lev':
            # open text file
            with open(infile) as fd:
                # find beginning of data
                indices = fd.readlines().index('[Data]\n')

            # convert data to pandas dataframe starting at the indexed data line
            f[getfilename(infile)] = pd.read_table(infile, parse_dates=True, sep='     ', index_col=0,
                                                   skiprows=indices + 2,
                                                   names=['DateTime', 'Level', 'Temperature'],
                                                   skipfooter=1, engine='python')
            # add extension-free file name to dataframe
            f[getfilename(infile)]['name'] = getfilename(infile)
            f[getfilename(infile)]['Level'] = pd.to_numeric(f[getfilename(infile)]['Level'])
            f[getfilename(infile)]['Temperature'] = pd.to_numeric(f[getfilename(infile)]['Temperature'])
        
        elif filetype == '.xle': # run computations using xle files
            f[getfilename(infile)] = new_xle_imp(infile)
        else:
            pass
    # concatenate all of the DataFrames in dictionary f to one DataFrame: g
    g = pd.concat(f)
    # remove multiindex and replace with index=Datetime
    g = g.reset_index()
    g = g.set_index(['DateTime'])
    # drop old indexes
    g = g.drop(['level_0'], axis=1)
    # remove duplicates based on index then sort by index
    g['ind'] = g.index
    g.drop_duplicates(subset='ind', inplace=True)
    g.drop('ind', axis=1, inplace=True)
    g = g.sort_index()
    outfile = g
    return outfile

def new_xle_imp(infile):
    """This function uses an exact file path to upload a xle transducer file.

    Args:
        infile (file):
            complete file path to input file

    Returns:
        A Pandas DataFrame containing the transducer data
    """
    # open text file
    with open(infile, "rb") as f:
        obj = xmltodict.parse(f, xml_attribs=True, encoding="ISO-8859-1")
    # navigate through xml to the data
    wellrawdata = obj['Body_xle']['Data']['Log']
    # convert xml data to pandas dataframe
    f = pd.DataFrame(wellrawdata)

    # CH 3 check
    try:
        ch3ID = obj['Body_xle']['Ch3_data_header']['Identification']
        f[str(ch3ID).title()] = f['ch3']
    except(KeyError, UnboundLocalError):
        pass

    # CH 2 manipulation
    ch2ID = obj['Body_xle']['Ch2_data_header']['Identification']
    f[str(ch2ID).title()] = f['ch2']
    ch2Unit = obj['Body_xle']['Ch2_data_header']['Unit']
    numCh2 = pd.to_numeric(f['ch2'])
    if ch2Unit == 'Deg C' or ch2Unit == u'\N{DEGREE SIGN}' + u'C':
        f[str(ch2ID).title()] = numCh2
    elif ch2Unit == 'Deg F' or ch2Unit == u'\N{DEGREE SIGN}' + u'F':
        print('Temp in F, converting to C')
        f[str(ch2ID).title()] = (numCh2 - 32) * 5 / 9

    # CH 1 manipulation
    ch1ID = obj['Body_xle']['Ch1_data_header']['Identification']  # Usually level
    ch1Unit = obj['Body_xle']['Ch1_data_header']['Unit']  # Usually ft
    unit = str(ch1Unit).lower()

    if unit == "feet" or unit == "ft":
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
    elif unit == "kpa":
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.33456
        print("Units in kpa, converting to ft...")
    elif unit == "mbar":
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.0334552565551
    elif unit == "psi":
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 2.306726
        print("Units in psi, converting to ft...")
    elif unit == "m" or unit == "meters":
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 3.28084
        print("Units in psi, converting to ft...")
    else:
        f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
        print("Unknown units, no conversion")

    # add extension-free file name to dataframe
    f['name'] = getfilename(infile)
    # combine Date and Time fields into one field
    f['DateTime'] = pd.to_datetime(f.apply(lambda x: x['Date'] + ' ' + x['Time'], 1))
    f[str(ch1ID).title()] = pd.to_numeric(f[str(ch1ID).title()])
    f[str(ch2ID).title()] = pd.to_numeric(f[str(ch2ID).title()])

    try:
        ch3ID = obj['Body_xle']['Ch3_data_header']['Identification']
        f[str(ch3ID).title()] = pd.to_numeric(f[str(ch3ID).title()])
    except(KeyError, UnboundLocalError):
        pass

    f = f.reset_index()
    f = f.set_index('DateTime')
    f['Level'] = f[str(ch1ID).title()]
    f = f.drop(['Date', 'Time', '@id', 'ch1', 'ch2', 'index', 'ms'], axis=1)

    return f

def new_csv_imp(infile):
    """This function uses an exact file path to upload a csv transducer file.

    Args:
        infile (file):
            complete file path to input file

    Returns:
        A Pandas DataFrame containing the transducer data
    """
    f = pd.read_csv(infile, skiprows=1, parse_dates=[[0, 1]])
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
    #f = dataendclean(f, 'Level')
    flist = f.columns.tolist()
    if ' Temp C' in flist:
        f['Temperature'] = f[' Temp C']
        f['Temp'] = f['Temperature']
        f.drop([' Temp C', 'Temperature'], inplace=True, axis=1)
    elif ' Temp F' in flist:
        f['Temperature'] = (f[' Temp F'] - 32)* 5/9
        f['Temp'] = f['Temperature']
        f.drop([' Temp F', 'Temperature'], inplace=True, axis=1)
    else:
        f['Temp'] = np.nan
    f.set_index(['DateTime'], inplace=True)
    f['date'] = f.index.to_julian_date().values
    f['datediff'] = f['date'].diff()
    f = f[f['datediff'] > 0]
    f = f[f['datediff'] < 1]
    #bse = int(pd.to_datetime(f.index).minute[0])
    #f = hourly_resample(f, bse)
    f.rename(columns={' Volts':'Volts'},inplace=True)
    f.drop([u'date', u'datediff', u'Date_ Time'], inplace=True, axis=1)
    return f

def new_trans_imp(infile):
    """This function uses an imports and cleans the ends of transducer file.

    Args:
        infile (file):
            complete file path to input file
        xle (bool):
            if true, then the file type should be xle; else it should be csv

    Returns:
        A Pandas DataFrame containing the transducer data
    """
    file_ext = os.path.splitext(infile)[1]
    if file_ext == '.xle':
        well = new_xle_imp(infile)
    elif file_ext == '.csv':
        well = new_csv_imp(infile)
    else:
        print('filetype not recognized')
        pass
    return dataendclean(well,'Level')

    # Use `g[wellinfo[wellinfo['Well']==wellname]['closest_baro']]` to match the closest barometer to the data

def imp_one_well(well_file, baro_file, man_startdate, man_endate, man_start_level, man_end_level, conn_file_root,
                 wellid, be=None, well_table="UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations",
                 gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading",drift_tol=0.3):
    import arcpy
    arcpy.env.workspace = conn_file_root

    well = new_trans_imp(well_file)
    baro = new_trans_imp(baro_file)

    if os.path.splitext(well_file)[1] == '.xle':
        trans_type = 'Solinst'
    else:
        trans_type = 'Global Water'

    corrwl = well_baro_merge(well, baro, vented=(trans_type != 'Solinst'))

    if be:
        corrwl = correct_be(wellid, corrwl, be=be)
        corrwl['corrwl'] = corrwl['BAROEFFICIENCYLEVEL']

    stickup, well_elev = get_stickup_elev(wellid, well_table)

    man = pd.DataFrame(
        {'DateTime': [man_startdate, man_endate], 'MeasuredDTW': [man_start_level, man_end_level]}).set_index(
        'DateTime')

    dft = fix_drift(corrwl, man, meas='corrwl', manmeas='MeasuredDTW')
    drift = round(float(dft[1]['drift'].values[0]), 3)

    df = dft[0]

    rowlist, fieldnames = prepare_fieldnames(df, wellid, stickup, well_elev)

    if dft[1] >= drift_tol:
        edit_table(rowlist, gw_reading_table, fieldnames)
        print('Well {:} successfully imported!'.format(wellid))
        arcpy.AddMessage('Well {:} successfully imported!'.format(wellid))
    else:
        print('Well {:} drift greater than tolerance!'.format(wellid))
        arcpy.AddMessage('Well {:} drift greater than tolerance!'.format(wellid))

def edit_table(df, gw_reading_table, fieldnames):
    """
    Edits SDE table by inserting new rows
    :param rowlist: pandas DataFrame converted to row list by df.values.tolist()
    :param gw_reading_table: sde table to edit
    :param fieldnames: field names that are being appended in order of appearance in dataframe or list row
    :return:
    """

    subset = df[fieldnames]
    rowlist = subset.values.tolist()

    import arcpy
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

def imp_well(well_table, ind, manual, baro_out, gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading"):
    barotable = well_table[(well_table['Location'].str.contains("Baro")) | (
        well_table['Location'].str.contains("baro"))]

    welltable = well_table[(pd.notnull(well_table['WellID'])) & \
                           (~well_table['WellID'].isin(barotable['WellID'].values))]

    full_filepath = well_table.loc[ind, 'full_filepath']
    trans_type = well_table.loc[ind, 'trans type']
    wellid = well_table.loc[ind, 'WellID']

    barocolumn = 'MEASUREDLEVEL'
    import arcpy
    # import well file
    well = new_trans_imp(full_filepath)

    # remove barometric pressure

    try:
        baroid = welltable.loc[ind, 'baronum']
        corrwl = well_baro_merge(well, baro_out[baroid], barocolumn=barocolumn,
                                 vented=(trans_type != 'Solinst'))
    except:
        corrwl = well_baro_merge(well, baro_out['9003'], barocolumn=barocolumn,
                                 vented=(trans_type != 'Solinst'))

    # be, intercept, r = clarks(corrwl, 'barometer', 'corrwl')
    # correct barometric efficiency
    wls, be = correct_be(wellid, well_table, corrwl)

    # get manual groundwater elevations
    man, stickup, well_elev = get_gw_elevs(wellid, well_table, manual, stable_elev=True)

    # fix transducer drift
    try:
        dft = fix_drift(wls, man, meas='BAROEFFICIENCYLEVEL', manmeas='MeasuredDTW')
        drift = round(float(dft[1]['drift'].values[0]), 3)

        df = dft[0]
        df.sort_index(inplace=True)
        first_index = df.first_valid_index()

        # Get last reading at the specified location
        read_max, dtw, wlelev = find_extreme(gw_reading_table, wellid)
        print('Last reading in database for well {:} was on {:}.\n\
        The first reading from the raw file is on {:}. Drift = {:}.'.format(ind, read_max, first_index, drift))

        if (read_max is None or read_max < first_index) and (drift < 0.3):
            rowlist, fieldnames = prepare_fieldnames(df, wellid, stickup, well_elev, read_max=read_max)

            edit_table(rowlist, gw_reading_table, fieldnames)

            print('Well {:} successfully imported!'.format(ind))
            arcpy.AddMessage('Well {:} successfully imported!'.format(ind))
        elif drift > 0.3:
            print('Drift for well {:} exceeds tolerance!'.format(ind))
        else:
            print('Dates later than import data for this station already exist!')
            pass
        return df, man, be, drift

    except (ValueError, ZeroDivisionError):
        print('{:} failed, likely due to lack of manual measurement constraint'.format(ind))
        pass

def get_location_data(read_table, site_number, first_date=None, last_date=None, limit=None):
    import datetime
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
    query_txt = "LOCATIONID = '{:}' and (READINGDATE >= '{:%m/%d/%Y}' and READINGDATE <= '{:%m/%d/%Y}')"
    query = query_txt.format(site_number, first_date, last_date + datetime.timedelta(days=1))
    sql_sn = (limit, 'ORDER BY READINGDATE ASC')

    fieldnames = get_field_names(read_table)

    readings = table_to_pandas_dataframe(read_table, fieldnames, query, sql_sn)
    readings.set_index('READINGDATE', inplace=True)
    if len(readings) == 0:
        print('No Records for location {:}'.format(site_number))
    return readings

def upload_bp_data(table, df, site_number, return_df=False, gw_reading_table = "UGGP.UGGPADMIN.UGS_GW_reading"):
    import arcpy

    df.sort_index(inplace=True)
    first_index = df.first_valid_index()

    # Get last reading at the specified location
    read_max, dtw, wlelev = find_extreme(table, site_number)

    if read_max is None or read_max < first_index:

        subset, fieldnames = prepare_fieldnames(df, wlelev, read_max = read_max)

        edit_table(subset, gw_reading_table, fieldnames)

        if return_df:
            return subset
    else:
        print('Dates later than import data for this station already exist!')
        pass


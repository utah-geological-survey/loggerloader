import pandas as pd
from .transport import *


def prepare_fieldnames(df, wellid, stickup, well_elev, read_max=None, level = 'Level',dtw = 'DTW_WL'):
    """
    This function adds the necessary field names to import well data into the SDE database.
    :param df: pandas DataFrame of processed well data
    :param wellid: wellid (alternateID) of well in Stations Table
    :param level: raw transducer level from new_trans_imp, new_xle_imp, or new_csv_imp functions
    :param dtw: drift-corrected depth to water from fix_drift function
    :return: processed df with necessary field names for import
    """

    df['MEASUREDLEVEL'] = df[level]
    df['MEASUREDDTW'] = df[dtw] * -1
    df['DTWBELOWCASING'] = df['MEASUREDDTW']
    df['DTWBELOWGROUNDSURFACE'] = df['MEASUREDDTW'].apply(lambda x: x - stickup, 1)
    df['WATERELEVATION'] = df['DTWBELOWGROUNDSURFACE'].apply(lambda x: well_elev - x, 1)
    df['TAPE'] = 0
    df['LOCATIONID'] = wellid

    df.sort_index(inplace=True)

    fieldnames = ['READINGDATE', 'MEASUREDLEVEL', 'MEASUREDDTW', 'DRIFTCORRECTION',
                  'TEMP', 'LOCATIONID', 'DTWBELOWCASING', 'BAROEFFICIENCYLEVEL',
                  'DTWBELOWGROUNDSURFACE', 'WATERELEVATION', 'TAPE']

    if 'Temperature' in df.columns:
        df.rename(columns={'Temperature': 'TEMP'}, inplace=True)

    if 'TEMP' in df.columns:
        df['TEMP'] = df['TEMP'].apply(lambda x: np.round(x, 4), 1)
    else:
        df['TEMP'] = None

    # subset bp df and add relevant fields
    df.index.name = 'READINGDATE'

    if read_max is None:
        subset = df.reset_index()
    else:
        subset = df[df.index.get_level_values(0) > read_max].reset_index()

    subset = subset[fieldnames]

    rowlist = subset.values.tolist()

    return rowlist, fieldnames

def imp_one_well(well_file, baro_file, man_startdate, man_endate, man_start_level, man_end_level, conn_file_root, wellid=None, stickup=None, elevation=None, be=None, trans_type = 'Solinst', well_table="UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations", gw_reading_table="UGGP.UGGPADMIN.UGS_GW_reading", sde = "UGS_SDE.sde", drift_tol=0.3):
    import arcpy
    arcpy.env.workspace = conn_file_root + sde

    well = new_trans_imp(well_file, xle=(trans_type == 'Solinst'))
    baro = new_xle_imp(baro_file)

    corrwl = well_baro_merge(well, baro, vented=(trans_type != 'Solinst'))

    if be:
        corrwl = correct_be(wellid,corrwl,be=be)
        corrwl['corrwl'] = corrwl['BAROEFFICIENCYLEVEL']

    if wellid:
        stickup, well_elev = get_stickup_elev(wellid, well_table)
    elif elevation:
        if stickup:
            pass
        else:
            stickup=0
        well_elev = elevation

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

def edit_table(rowlist, gw_reading_table, fieldnames):
    """
    Edits SDE table by inserting new rows
    :param rowlist: pandas DataFrame converted to row list by df.values.tolist()
    :param gw_reading_table: sde table to edit
    :param fieldnames: field names that are being appended in order of appearance in dataframe or list row
    :return:
    """
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
    barotable = well_table[(well_table['Location'].str.contains("Baro"))|(
                         well_table['Location'].str.contains("baro"))]

    welltable = well_table[(pd.notnull(well_table['WellID'])) & \
                                  (~well_table['WellID'].isin(barotable['WellID'].values))]

    full_filepath = well_table.loc[ind, 'full_filepath']
    trans_type = well_table.loc[ind, 'trans type']
    wellid = well_table.loc[ind, 'WellID']

    barocolumn = 'MEASUREDLEVEL'
    import arcpy
    # import well file
    well = new_trans_imp(full_filepath, xle=(trans_type == 'Solinst'))

    # remove barometric pressure

    try:
        baroid = welltable.loc[ind, 'baronum']
        corrwl = well_baro_merge(well, baro_out[baroid], barocolumn=barocolumn,
                                    vented=(trans_type != 'Solinst'))
    except:
        corrwl = well_baro_merge(well, baro_out['9003'], barocolumn=barocolumn,
                                    vented=(trans_type != 'Solinst'))

    #be, intercept, r = clarks(corrwl, 'barometer', 'corrwl')
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
        return df,man,be,drift

    except (ValueError, ZeroDivisionError):
        print('{:} failed, likely due to lack of manual measurement constraint'.format(ind))
        pass

def get_field_names(table):
    import arcpy
    read_descr = arcpy.Describe(table)
    field_names = []
    for field in read_descr.fields:
        field_names.append(field.name)
    field_names.remove('OBJECTID')
    return field_names

def table_to_pandas_dataframe(table, field_names=None, query=None, sql_sn=(None,None)):
    """
    Load data into a Pandas Data Frame for subsequent analysis.
    :param table: Table readable by ArcGIS.
    :param field_names: List of fields.
    :return: Pandas DataFrame object.
    """
    import arcpy

    # if field names are not specified
    if not field_names:
        field_names = get_field_names(table)
    # create a pandas data frame
    df = pd.DataFrame(columns=field_names)

    # use a search cursor to iterate rows
    with arcpy.da.SearchCursor(table, field_names,query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            # combine the field names and row items together, and append them
            df = df.append(dict(zip(field_names, row)),ignore_index=True)

    # return the pandas data frame
    return df

def get_location_data(read_table, site_number, first_date=None, last_date=None, limit=None):
    import datetime
    if not first_date:
        first_date = datetime.datetime(1900,1,1)
    elif type(first_date)==str:
        try:
            datetime.datetime.strptime(first_date, '%m/%d/%Y')
        except:
            first_date = datetime.datetime(1900,1,1)
    # Get last reading at the specified location
    if not last_date or last_date > datetime.datetime.now():
        last_date = datetime.datetime.now()
    query_txt = "LOCATIONID = '{:}' and (READINGDATE >= '{:%m/%d/%Y}' and READINGDATE <= '{:%m/%d/%Y}')"
    query = query_txt.format(site_number, first_date, last_date + datetime.timedelta(days=1))
    sql_sn = (limit,'ORDER BY READINGDATE ASC')

    fieldnames = get_field_names(read_table)

    readings = table_to_pandas_dataframe(read_table, fieldnames, query, sql_sn)
    readings.set_index('READINGDATE',inplace=True)
    if len(readings) == 0:
        print('No Records for location {:}'.format(site_number))
    return readings

def find_extreme(table, site_number, extma = 'max'):
    """
    Find extrema from a SDE table using query parameters
    :param table: SDE table to be queried
    :param site_number: LocationID of the site of interest
    :param extma: options are 'max' (default) or 'min'
    :return: read_max
    """
    import arcpy
    if extma == 'max':
        sort = 'DESC'
    else:
        sort = 'ASC'
    query = "LOCATIONID = {:}".format(site_number)
    field_names = ['READINGDATE', 'LOCATIONID','DTWBELOWGROUNDSURFACE','WATERELEVATION']
    sql_sn = ('TOP 1','ORDER BY READINGDATE {:}'.format(sort))
    # use a search cursor to iterate rows
    dateval, dtw, wlelev = [],[],[]
    with arcpy.da.SearchCursor(table, field_names, query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            dateval.append(row[0])
            dtw.append(row[1])
            wlelev.append(row[2])

    return dateval[0],dtw[0],wlelev[0]

def get_stickup_elev(site_number, well_table):
    stdata = well_table[well_table['WellID'] == str(site_number)]
    stickup = float(stdata['Offset'].values[0])
    well_elev = float(stdata['Altitude'].values[0])
    return stickup, well_elev

def get_gw_elevs(site_number, well_table, manual, stable_elev = True):
    """
    Gets basic well parameters and most recent groundwater level data for a well id for dtw calculations.
    :param site_number: well site number in the site table
    :param manual: Pandas Dataframe of manual data
    :param table: pandas dataframe of site table;
    :param lev_table: groundwater level table; defaults to "UGGP.UGGPADMIN.UGS_GW_reading"
    :return: stickup, well_elev, be, maxdate, dtw, wl_elev
    """

    stdata = well_table[well_table['WellID'] == str(site_number)]
    man_sub = manual[manual['Location ID']==int(site_number)]
    well_elev = float(stdata['Altitude'].values[0])

    if stable_elev:
        stickup = float(stdata['Offset'].values[0])
    else:
        stickup = man_sub['Current Stickup Height']

    #manual = manual['MeasuredDTW'].to_frame()
    man_sub.loc[:,'MeasuredDTW'] = man_sub['Water Level (ft)']*-1
    try:
        man_sub.loc[:,'Meas_GW_Elev'] = man_sub['MeasuredDTW'].apply(lambda x: well_elev + (x + stickup),1)
    except:
        print('Manual correction data for well id {:} missing (stickup: {:}; elevation: {:})'.format(site_number,stickup,well_elev))
        pass

    return man_sub, stickup, well_elev

def upload_data(table, df, lev_field, site_number, temp_field = None, return_df=False):
    import arcpy

    df.sort_index(inplace=True)
    first_index = df.first_valid_index()
    
    # Get last reading at the specified location
    read_max, dtw, wlelev = find_extreme(table, site_number)

    if read_max is None or read_max < first_index:
        arcpy.env.overwriteOutput=True
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing(False, False)
        edit.startOperation()

        if temp_field is None:
            fieldnames = ['READINGDATE', 'MEASUREDLEVEL', 'LOCATIONID']
        else:
            fieldnames = ['READINGDATE', 'MEASUREDLEVEL', 'TEMP', 'LOCATIONID']
            df.rename(columns={temp_field:'TEMP'},inplace=True)
            df['TEMP'] =df['TEMP'].apply(lambda x: round(x, 4),1) 

        cursor = arcpy.da.InsertCursor(table, fieldnames)

        #subset bp df and add relevant fields
        df['LOCATIONID'] = site_number
        df.rename(columns={lev_field:'MEASUREDLEVEL'},inplace=True)
        df['MEASUREDLEVEL'] =df['MEASUREDLEVEL'].apply(lambda x: round(x, 4),1) 
        df.index.name = 'READINGDATE'

        if read_max is None:
            subset = df.reset_index()
        else:
            subset = df[df.index.get_level_values(0) > read_max].reset_index()

        subset = subset[fieldnames]
        rowlist = subset.values.tolist()

        for j in range(len(rowlist)):
            cursor.insertRow(rowlist[j])

        del cursor
        edit.stopOperation()
        edit.stopEditing(True)
        if return_df:
            return subset
    else:
        print('Dates later than import data for this station already exist!')
        pass

def match_files_to_wellid(folder, station_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"):
    xles = xle_head_table(folder)
    csvs = csv_info_table(folder)
    well_table = pd.concat([xles, csvs[0]])

    stations = table_to_pandas_dataframe(station_table)
    names = stations['LocationName'].apply(lambda x: str(x).lower().replace(" ", "").replace("-",""),1)
    ids = stations['AltLocationID'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    baros = stations['BaroLoggerType'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    elevs = stations['Altitude'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    stickup = stations['Offset'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    beff = stations['BaroEfficiency'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    iddict = dict(zip(names,ids))
    bdict = dict(zip(ids,baros))
    elevdict = dict(zip(ids,elevs))
    stickupdict = dict(zip(ids,stickup))
    bedict = dict(zip(ids,beff))

    def tryfile(x):
        loc_name_strip = str(x[0]).lower().replace(" ", "").replace("-","")
        nameparts = str(x[1]).split(' ')
        try_match = iddict.get(loc_name_strip)
        if try_match is None or int(str(try_match)) > 140:
            file_name_strip =  str(' '.join(nameparts[:-1])).lower().replace(" ", "").replace("-","")
            wl_value = iddict.get(file_name_strip)
            return wl_value
        else:
            return try_match

    well_table['WellID'] = well_table[['Location','fileroot']].apply(lambda x: tryfile(x), 1)
    well_table['baronum'] = well_table['WellID'].apply(lambda x: bdict.get(x), 1)
    well_table['Altitude'] = well_table['WellID'].apply(lambda x: elevdict.get(x), 1)
    well_table['Offset'] = well_table['WellID'].apply(lambda x: stickupdict.get(x),1)
    well_table['BaroEfficiency'] = well_table['WellID'].apply(lambda x: bedict.get(x),1)


    nomatch = well_table[pd.isnull(well_table['WellID'])].index
    #match = well_table[pd.notnull(well_table['WellID'])]['WellID']

    print('The following wells did not match: {:}.'.format(list(nomatch.values)))

    return well_table
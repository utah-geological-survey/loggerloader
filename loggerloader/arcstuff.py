import pandas as pd


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
    if not last_date:
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

def get_gw_elevs(site_number, stations, manual, stable_elev = True, lev_table = "UGGP.UGGPADMIN.UGS_GW_reading"):
    """
    Gets basic well parameters and most recent groundwater level data for a well id for dtw calculations.
    :param site_number: well site number in the site table
    :param manual: Pandas Dataframe of manual data
    :param table: pandas dataframe of site table;
    :param lev_table: groundwater level table; defaults to "UGGP.UGGPADMIN.UGS_GW_reading"
    :return: stickup, well_elev, be, maxdate, dtw, wl_elev
    """

    stdata = stations[(stations['AltLocationID'] == site_number) & (stations['LocationType'] == 'Well')]
    man_sub = manual[manual['Location ID']==site_number]
    well_elev = float(stdata['Altitude'].values[0])

    if stable_elev:
        stickup = float(stdata['Offset'].values[0])
    else:
        stickup = man_sub['Current Stickup Height']

    #manual = manual['MeasuredDTW'].to_frame()
    man_sub['MeasuredDTW'] = man_sub['Water Level (ft)']*-1
    try:
        man_sub['Meas_GW_Elev'] = man_sub['MeasuredDTW'].apply(lambda x: well_elev + (x + stickup),1)
    except:
        print('Manual correction data for well id {:} missing (stickup: {:}; elevation: {:})'.format(site_number,stickup,well_elev))
        pass

    return man_sub

def correct_be(site_number, stations, welldata):
    stdata = stations[(stations['AltLocationID'] == site_number) & (stations['LocationType'] == 'Well')]
    be = float(stdata['BaroEfficiency'].values[0])
    welldata['corrwlbp'] = welldata[['corrwl', 'barometer']].\
        apply(lambda x: x[0] - be * (x[1] - welldata['barometer'].mean()), 1)
    return welldata

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

def match_files_to_wellid(well_table, station_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"):
    xle_info_table = well_table
    stations = table_to_pandas_dataframe(station_table)
    names = stations['LocationName'].apply(lambda x: str(x).lower().replace(" ", "").replace("-",""),1)
    ids = stations['AltLocationID'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    baros = stations['BaroLoggerType'].apply(lambda x: pd.to_numeric(x, errors='coerce'),1)
    iddict = dict(zip(names,ids))
    bdict = dict(zip(ids,baros))
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

    xle_info_table['WellID'] = xle_info_table[['Location','fileroot']].apply(lambda x: tryfile(x), 1)
    xle_info_table['baronum'] = xle_info_table['WellID'].apply(lambda x: bdict.get(x), 1)
    nomatch = xle_info_table[pd.isnull(xle_info_table['WellID'])].index
    match = xle_info_table[pd.notnull(xle_info_table['WellID'])]['WellID']

    print('The following wells did not match: {:}.'.format(list(nomatch.values)))
    return xle_info_table, match, nomatch
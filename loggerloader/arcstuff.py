
def get_field_names(table):
    import arcpy
    read_descr = arcpy.Describe(table)
    field_names = []
    for field in read_descr.fields:
        field_names.append(field.name)
    field_names.remove('OBJECTID')
    return field_names


def table_to_pandas_dataframe(table, field_names=None, query=None):
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
    with arcpy.da.SearchCursor(table, field_names,query) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            # combine the field names and row items together, and append them
            df = df.append(dict(zip(field_names, row)),ignore_index=True)

    # return the pandas data frame
    return df

def get_location_data(site_number, first_date, last_date=None, limit=None):
    
    # Get last reading at the specified location
    if not last_date:
        import datetime        
        last_date = datetime.datetime.now()
    query_txt = "LOCATIONID = '{:}' and (READINGDATE >= '{:%m/%d/%Y}' and READINGDATE <= '{:%m/%d/%Y}')"
    query = query_txt.format(site_number, first_date, last_date)
    sql_sn = (limit,'ORDER BY READINGDATE ASC')
    readings = table_to_pandas_dataframe(read_table, fieldnames, query)
    if len(readings) == 0:
        print('No Records for location {:}'.format(site_number))
    return readings, read_max


def find_max(table, site_number):
    query = "LOCATIONID = {:}".format(site_number)
    field_names = ['READINGDATE', 'LOCATIONID']
    sql_sn = ('TOP 1','ORDER BY READINGDATE DESC')
    # use a search cursor to iterate rows
    dateval = []
    with arcpy.da.SearchCursor(table, field_names, query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            dateval.append(row[0])
    try:
        read_max = max(dateval)
    except ValueError:
        read_max = None
    return read_max

def find_min(table, site_number):
    query = "LOCATIONID = {:}".format(site_number)
    field_names = ['READINGDATE', 'LOCATIONID']
    sql_sn = ('TOP 1','ORDER BY READINGDATE ASC')
    # use a search cursor to iterate rows
    dateval = []
    with arcpy.da.SearchCursor(table, field_names, query, sql_clause=sql_sn) as search_cursor:
        # iterate the rows
        for row in search_cursor:
            dateval.append(row[0])
    try:
        read_min = min(dateval)
    except ValueError:
        read_min = None
    return read_min

def upload_data(table, df, lev_field, temp_field = None, site_number = None, return_df=False):
    if site_number is None:
        bpdict = {'pw03':'9003','pw10':'9027','pw19':'9049','twin':'9024','leland':'9025'}  
        site_number = int(bpdict.get(lev_field))

    df.sort_index(inplace=True)
    first_index = df.first_valid_index()
    
    # Get last reading at the specified location
    read_max = find_max(table, site_number)

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

        cursor = arcpy.da.InsertCursor(read_table, fieldnames)

        #subset bp df and add relevant fields
        df['LOCATIONID'] = site_number
        df.rename(columns={lev_field:'MEASUREDLEVEL'},inplace=True)
        df['MEASUREDLEVEL'] =df['MEASUREDLEVEL'].apply(lambda x: round(x, 4),1) 
        df.index.name = 'READINGDATE'

        if read_max is None:
            subset = df.reset_index()
        else:
            subset = df[df.index.get_level_values(0) > max(readings['READINGDATE'])].reset_index()

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

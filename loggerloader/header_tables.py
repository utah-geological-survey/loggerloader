from __future__ import absolute_import, division, print_function, unicode_literals
import pandas as pd
import numpy as np
import os
import xmltodict
from loggerloader.utilities import table_to_pandas_dataframe
from loggerloader.transport import new_csv_imp

def match_files_to_wellid(folder, station_table="UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"):
    xles = xle_head_table(folder)
    csvs = csv_info_table(folder)
    well_table = pd.concat([xles, csvs[0]])

    stations = table_to_pandas_dataframe(station_table)
    names = stations['LocationName'].apply(lambda x: str(x).lower().replace(" ", "").replace("-", ""), 1)
    ids = stations['AltLocationID'].apply(lambda x: pd.to_numeric(x, errors='coerce'), 1)
    baros = stations['BaroLoggerType'].apply(lambda x: pd.to_numeric(x, errors='coerce'), 1)
    elevs = stations['Altitude'].apply(lambda x: pd.to_numeric(x, errors='coerce'), 1)
    stickup = stations['Offset'].apply(lambda x: pd.to_numeric(x, errors='coerce'), 1)
    beff = stations['BaroEfficiency'].apply(lambda x: pd.to_numeric(x, errors='coerce'), 1)
    iddict = dict(zip(names, ids))
    bdict = dict(zip(ids, baros))
    elevdict = dict(zip(ids, elevs))
    stickupdict = dict(zip(ids, stickup))
    bedict = dict(zip(ids, beff))

    def tryfile(x):
        loc_name_strip = str(x[0]).lower().replace(" ", "").replace("-", "")
        nameparts = str(x[1]).split(' ')
        try_match = iddict.get(loc_name_strip)
        if try_match is None or int(try_match) > 140:
            file_name_strip = str(' '.join(nameparts[:-1])).lower().replace(" ", "").replace("-", "")
            wl_value = iddict.get(file_name_strip)
            return wl_value
        else:
            return try_match

    well_table['WellID'] = well_table[['Location', 'fileroot']].apply(lambda x: tryfile(x), 1)
    well_table['baronum'] = well_table['WellID'].apply(lambda x: bdict.get(x), 1)
    well_table['Altitude'] = well_table['WellID'].apply(lambda x: elevdict.get(x), 1)
    well_table['Offset'] = well_table['WellID'].apply(lambda x: stickupdict.get(x), 1)
    well_table['BaroEfficiency'] = well_table['WellID'].apply(lambda x: bedict.get(x), 1)

    nomatch = well_table[pd.isnull(well_table['WellID'])].index
    # match = well_table[pd.notnull(well_table['WellID'])]['WellID']

    print('The following wells did not match: {:}.'.format(list(nomatch.values)))

    return well_table

def xle_head_table(folder):
    """Creates a Pandas DataFrame containing header information from all xle files in a folder
    Args:
        folder (directory):
            folder containing xle files
    Returns:
        A Pandas DataFrame containing the transducer header data
    Example::
        >>> import loggerloader as ll
        >>> xle_head_table('C:/folder_with_xles/')
    """
    # open text file
    df = {}
    for infile in os.listdir(folder):

        # get the extension of the input file
        filename, filetype = os.path.splitext(folder + infile)
        basename = os.path.basename(folder + infile)
        if filetype == '.xle':
            # open text file
            with open(folder + infile, "rb") as f:
                d = xmltodict.parse(f, xml_attribs=True, encoding="ISO-8859-1")
            # navigate through xml to the data
            data = list(d['Body_xle']['Instrument_info_data_header'].values()) + list(
                d['Body_xle']['Instrument_info'].values())
            cols = list(d['Body_xle']['Instrument_info_data_header'].keys()) + list(
                d['Body_xle']['Instrument_info'].keys())

            df[basename[:-4]] = pd.DataFrame(data=data, index=cols).T
    allwells = pd.concat(df)
    allwells.index = allwells.index.droplevel(1)
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
                csv[basename] = new_csv_imp(os.path.join(folder, file))
                cfile['Battery_level'] = int(round(csv[basename].loc[csv[basename]. \
                                                   index[-1], 'Volts'] / csv[basename]. \
                                                   loc[csv[basename].index[0], 'Volts'] * 100, 0))
                cfile['Sample_rate'] = (csv[basename].index[1] - csv[basename].index[0]).seconds * 100
                cfile['filename'] = basename
                cfile['fileroot'] = basename
                cfile['full_filepath'] = os.path.join(folder, file)
                cfile['Start_time'] = csv[basename].first_valid_index()
                cfile['Stop_time'] = csv[basename].last_valid_index()
                cfile['Location'] = ' '.join(basename.split(' ')[:-1])
                cfile['trans type'] = 'Global Water'
                df = df.append(cfile, ignore_index=True)
            except KeyError:
                pass
    df.set_index('filename', inplace=True)
    return df, csv

def make_files_table(folder, wellinfo):
    """This tool will make a descriptive table (Pandas DataFrame) containing filename, date, and site id.
    For it to work properly, files must be named in the following fashion:
    siteid YYYY-MM-DD
    example: pw03a 2015-03-15.csv

    This tool assumes that if there are two files with the same name but different extensions,
    then the datalogger for those data is a Solinst datalogger.

    Args:
        folder (dir):
            directory containing the newly downloaded transducer data
        wellinfo (object):
            Pandas DataFrame containing well information

    Returns:
        files (object):
            Pandas DataFrame containing summary of different files in the input directory
    """

    filenames = next(os.walk(folder))[2]
    site_id, exten, dates, fullfilename = [], [], [], []
    # parse filename into relevant pieces
    for i in filenames:
        site_id.append(i[:-14].lower().strip())
        exten.append(i[-4:])
        dates.append(i[-14:-4])
        fullfilename.append(i)
    files = {'siteid': site_id, 'extensions': exten, 'date': dates, 'full_file_name': fullfilename}
    files = pd.DataFrame(files)

    files['LoggerTypeName'] = files['extensions'].apply(lambda x: 'Global Water' if x == '.csv' else 'Solinst', 1)
    files.drop_duplicates(subset='siteid', keep='last', inplace=True)

    wellinfo = wellinfo[wellinfo['WellID'] != np.nan]

    wellinfo['WellID'] = wellinfo['WellID'].apply(lambda x: str(x).lower().strip())
    files = pd.merge(files, wellinfo, left_on='siteid', right_on='WellID')

    return files
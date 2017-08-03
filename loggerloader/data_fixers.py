from __future__ import absolute_import, division, print_function, unicode_literals
import pandas as pd
import numpy as np

from loggerloader.utilities import fcl, hourly_resample

def fix_drift(well, manualfile, meas='Level', manmeas='MeasuredDTW', outcolname='DTW_WL'):
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

    for i in range(len(manualfile)):
        breakpoints.append(fcl(well, pd.to_datetime(manualfile.index)[i]).name)
    breakpoints = sorted(list(set(breakpoints)))

    bracketedwls, drift_features = {}, {}

    if well.index.name:
        dtnm = well.index.name
    else:
        dtnm = 'DateTime'
        well.index.name = 'DateTime'

    manualfile.index = pd.to_datetime(manualfile.index)

    manualfile.loc[:,'julian'] = manualfile.index.to_julian_date()
    for i in range(len(breakpoints) - 1):
        # Break up pandas dataframe time series into pieces based on timing of manual measurements
        bracketedwls[i] = well.loc[
            (well.index.to_datetime() > breakpoints[i]) & (well.index.to_datetime() < breakpoints[i + 1])]
        df = bracketedwls[i]
        if len(df) > 0:
            df.loc[:,'julian'] = df.index.to_julian_date()

            last_trans = df.loc[df.index[-1], meas]  # last transducer measurement
            first_trans = df.loc[df.index[0], meas]  # first transducer measurement

            last_man = fcl(manualfile, breakpoints[i + 1])  # first manual measurment
            first_man = fcl(manualfile, breakpoints[i])  # last manual mesurement

            # intercept of line = value of first manual measurement
            b = first_trans - first_man[manmeas]

            # slope of line = change in difference between manual and transducer over time;
            drift = ((last_trans - last_man[manmeas]) - b)
            m = drift / (last_man['julian'] - first_man['julian'])

            # datechange = amount of time between manual measurements
            df.loc[:,'datechange'] = df['julian'].apply(lambda x: x - df.loc[df.index[0], 'julian'], 1)

            # bracketedwls[i].loc[:, 'wldiff'] = bracketedwls[i].loc[:, meas] - first_trans
            # apply linear drift to transducer data to fix drift; flipped x to match drift
            df.loc[:,'DRIFTCORRECTION'] = df['datechange'].apply(lambda x: m * x , 1)
            df[outcolname] = df[meas] - (df['DRIFTCORRECTION'] + b)

            drift_features[i] = {'begining': first_man, 'end': last_man, 'intercept': b, 'slope': m,
                                 'first_meas': first_man[manmeas], 'last_meas': last_man[manmeas],
                                 'drift': drift}
        else:
            pass
    wellbarofixed = pd.concat(bracketedwls)
    wellbarofixed.reset_index(inplace=True)
    wellbarofixed.set_index(dtnm, inplace=True)
    drift_info = pd.DataFrame(drift_features).T

    return wellbarofixed, drift_info

def correct_be(site_number, well_table, welldata, be = None, meas = 'corrwl', baro = 'barometer'):

    if be:
        pass
    else:
        stdata = well_table[well_table['WellID'] == site_number]
        be = float(stdata['BaroEfficiency'].values[0])

    welldata['BAROEFFICIENCYLEVEL'] = welldata[[meas, baro]].\
        apply(lambda x: x[0] + be * x[1], 1)
    return welldata, be

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

def dataendclean(df, x, inplace=False):
    """Trims off ends and beginnings of datasets that exceed 2.0 standard deviations of the first and last 30 values

    :param df: Pandas DataFrame
    :type df: pandas.core.frame.DataFrame
    :param x: Column name of data to be trimmed contained in df
    :type x: str
    :param inplace: if DataFrame should be duplicated
    :type inplace: bool

    :returns: df trimmed data
    :rtype: pandas.core.frame.DataFrame

    This function prints a message if data are trimmed.
    """
    # Examine Mean Values
    if inplace:
        df = df
    else:
        df = df.copy()

    jump = df[abs(df.loc[:, x].diff()) > 1.0]
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

def well_baro_merge(wellfile, barofile, barocolumn='Level', wellcolumn = 'Level', outcolumn = 'corrwl', vented = False, sampint=60):
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

if __name__ == "__main__":
    pass
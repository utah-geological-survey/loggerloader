import io
import os
import glob
import re
import xml.etree.ElementTree as eletree
import numpy as np
import datetime
from shutil import copyfile
from xml.etree.ElementTree import ParseError

import pandas as pd


###################################################################################################################
# MAIN CODE


#####################################################################################################################
def elevatewater(df, elevation, stickup,
                 dtw_field='dtwbelowcasing', wtr_elev_field='waterelevation', flip=False):
    """treats both manual and transducer data; easiest to calculate manual elevations first
    and do fix-drift class on raw well pressure

    Args:
        df: pandas dataframe containing water elevation data
        elevation: ground elevation at wellsite
        stickup: stickup of casing above ground surface; can be float or series
        dtw_field: field in df that denotes depth to water (should be negative for below ground)
        wtr_elev_field: field to store groundwater elevation in
        flip = if True, multiplies dataset by -1; use this if inputing pressure data

    Notes:
        increase in pressure = increase in water elevation;
        increase in pressure = decrease in depth to water;
        increase in depth to water = decrease in water elevation;

    Examples:
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'dtwbelowcasing':[1,10,14,52,10,8]}
        >>> df = pd.DataFrame(manual)
        >>> ew = ElevateWater(df, 4000, 1)
        >>> ew.stickup
        1
        >>> ew.elevation
        4000
    """

    if flip:
        df[dtw_field] = df[dtw_field] * -1
    else:
        pass

    df[wtr_elev_field] = df[dtw_field] + elevation + stickup
    return df


class Drifting(object):

    def __init__(self, manual_df, transducer_df, drifting_field='corrwl', man_field='measureddtw', daybuffer=3,
                 output_field='waterelevation', trim_end=False, well_id=None, engine=None):
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

        self.slope_man = {}
        self.slope_trans = {}
        self.first_offset = {}
        self.last_offset = {}
        self.slope = {}
        self.intercept = {}
        self.drift = {}
        self.first_man = {}
        self.first_trans = {}
        self.last_man = {}
        self.last_trans = {}
        self.bracketedwls = {}
        self.drift_features = {}
        self.first_man_date = {}
        self.last_man_date = {}
        self.first_trans_date = {}
        self.last_trans_date = {}
        self.first_man_julian_date = {}
        self.last_man_julian_date = {}
        self.first_trans_julian_date = {}
        self.last_trans_julian_date = {}
        self.well_id = well_id
        self.engine = engine
        self.breakpoints = []
        self.levdt = {}
        self.lev = {}
        self.daybuffer = daybuffer
        self.wellbarofixed = pd.DataFrame()
        self.drift_sum_table = pd.DataFrame()
        self.trim_end = trim_end

        self.manual_df = self.datesort(manual_df)
        self.manual_df['julian'] = self.manual_df.index.to_julian_date()

        self.transducer_df = self.datesort(transducer_df)
        self.transducer_df['julian'] = self.transducer_df.index.to_julian_date()

        self.drifting_field = drifting_field
        self.man_field = man_field
        self.output_field = output_field

    def process_drift(self):
        self.breakpoints_calc()
        for i in range(len(self.breakpoints) - 1):
            # self.bracketed_wls(i)
            self.beginning_end(i)
            if len(self.bracketedwls[i]) > 0:
                if self.trim_end:
                    self.bracketedwls[i] = dataendclean(self.bracketedwls[i], self.drifting_field, jumptol=0.5)
                #self.endpoint_import(i)
                self.endpoint_status(i)
                self.slope_intercept(i)
                self.drift_add(i)
                self.drift_data(i)
                self.drift_print(i)
        self.combine_brackets()
        self.drift_summary()
        return self.wellbarofixed, self.drift_sum_table, self.max_drift

    def beginning_end(self, i):
        df = self.transducer_df[
            (self.transducer_df.index >= self.breakpoints[i]) & (self.transducer_df.index < self.breakpoints[i + 1])]
        df = df.dropna(subset=[self.drifting_field])
        df = df.sort_index()
        # print(i)
        # print(df)
        if len(df) > 0:
            self.manual_df['datetime'] = self.manual_df.index

            self.first_man_julian_date[i] = self.fcl(self.manual_df['julian'], self.breakpoints[i])
            self.last_man_julian_date[i] = self.fcl(self.manual_df['julian'], self.breakpoints[i + 1])
            self.first_man_date[i] = self.fcl(self.manual_df['datetime'], self.breakpoints[i])
            self.last_man_date[i] = self.fcl(self.manual_df['datetime'], self.breakpoints[i + 1])
            self.first_man[i] = self.fcl(self.manual_df[self.man_field],
                                         self.breakpoints[i])  # first manual measurement
            self.last_man[i] = self.fcl(self.manual_df[self.man_field],
                                        self.breakpoints[i + 1])  # last manual measurement

            self.first_trans[i] = df.loc[df.first_valid_index(), self.drifting_field]
            self.last_trans[i] = df.loc[df.last_valid_index(), self.drifting_field]
            self.first_trans_julian_date[i] = df.loc[df.first_valid_index(), 'julian']
            self.last_trans_julian_date[i] = df.loc[df.last_valid_index(), 'julian']
            self.first_trans_date[i] = df.first_valid_index()
            self.last_trans_date[i] = df.last_valid_index()
            self.bracketedwls[i] = df
        else:
            self.bracketedwls[i] = df
            pass

    @staticmethod
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

    @staticmethod
    def datesort(df):
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def breakpoints_calc(self):
        """Finds break-point dates in transducer file that align with manual measurements
        and mark end and beginning times of measurement.
        The transducer file will be split into chunks based on these dates to be processed for drift and corrected.

        Returns:
            list of breakpoints for the transducer file

        Examples:

            >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'],'man_read':[1,10,14,52,10,8]}
            >>> man_df = pd.DataFrame(manual)
            >>> man_df.set_index('dates',inplace=True)
            >>> datefield = pd.date_range(start='1/1/1995',end='12/15/2006',freq='3D')
            >>> df = pd.DataFrame({'dates':datefield,'data':np.random.rand(len(datefield))})
            >>> df.set_index('dates',inplace=True)
            >>> drft = Drifting(man_df,df,'data','man_read')
            >>> drft.get_breakpoints(man_df,df,'data')[1]
            numpy.datetime64('1999-02-01T00:00:00.000000000')
        """

        wellnona = self.transducer_df.dropna(subset=[self.drifting_field]).sort_index()
        wellnona = wellnona[wellnona.index.notnull()]
        self.manual_df = self.manual_df[self.manual_df.index.notnull()].dropna(subset=[self.man_field]).sort_index()

        self.manual_df = self.manual_df[
            (self.manual_df.index >= wellnona.first_valid_index() - pd.Timedelta(f'{self.daybuffer:.0f}D'))]

        if len(self.manual_df) > 0:

            # add first transducer time if it preceeds first manual measurement
            if self.manual_df.first_valid_index() > wellnona.first_valid_index():
                self.breakpoints.append(wellnona.first_valid_index())

            # add all manual measurements
            for ind in self.manual_df.index:
                # breakpoints.append(fcl(wellnona, manualfile.index[i]).name)
                self.breakpoints.append(ind)

            # add last transducer time if it is after last manual measurement
            if self.manual_df.last_valid_index() < wellnona.last_valid_index():
                self.breakpoints.append(wellnona.last_valid_index())

            # convert to datetime
            self.breakpoints = pd.Series(self.breakpoints)
            self.breakpoints = pd.to_datetime(self.breakpoints)
            # sort values in chronological order
            self.breakpoints = self.breakpoints.sort_values().drop_duplicates()
            # remove all duplicates
            self.breakpoints = self.breakpoints[~self.breakpoints.index.duplicated(keep='first')]
            # convert to list
            self.breakpoints = self.breakpoints.values
        else:
            print("No Breakpoints can be established as manual data do not align with imported data")

    def drift_summary(self):
        self.drift_sum_table = pd.DataFrame(self.drift_features).T
        self.max_drift = self.drift_sum_table['drift'].abs().max()

    def slope_intercept(self, i):
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
            (0.0, 1, 1.0, 1.0)

            >>> calc_slope_and_intercept(0,0,5,5,7,0,0,7)
            (-2.0, 7, 1.0, -1.0)
        """
        self.slope_man[i] = 0
        self.slope_trans[i] = 0
        self.first_offset[i] = 0
        self.last_offset[i] = 0

        # if there is not a manual measurement at the start of the period,
        # set separation between trans and man to 0
        if self.first_man[i] is None:
            try:
                self.last_offset[i] = self.last_trans[i] - self.last_man[i]
            except TypeError:
                print('Errorr')
                self.last_offset[i] = 0

            self.first_man_julian_date[i] = self.first_trans_julian_date[i]
            self.first_man[i] = self.first_trans[i]

        # if there is not a manual measurement at the end of the period, use
        elif self.last_man[i] is None:
            self.first_offset[i] = self.first_trans[i] - self.first_man[i]
            self.last_man_julian_date[i] = self.last_trans_julian_date[i]
            self.last_man[i] = self.last_trans[i]

        # If manual measurements exist for both the end and beginning of the period
        else:
            self.first_offset[i] = self.first_trans[i] - self.first_man[i]
            self.last_offset[i] = self.last_trans[i] - self.last_man[i]
            self.slope_man[i] = (self.first_man[i] - self.last_man[i]) / (
                    self.first_man_julian_date[i] - self.last_man_julian_date[i])
            self.slope_trans[i] = (self.first_trans[i] - self.last_trans[i]) / (
                    self.first_trans_julian_date[i] - self.last_trans_julian_date[i])

        self.slope[i] = self.slope_trans[i] - self.slope_man[i]

        if self.first_offset[i] == 0:
            self.intercept[i] = self.last_offset[i]
        else:
            self.intercept[i] = self.first_offset[i]

        return self.slope[i], self.intercept[i], self.slope_man[i], self.slope_trans[i]

    def drift_add(self, i):
        """
        Uses slope and offset from `slope_intercept` to correct for transducer drift

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
        df = self.bracketedwls[i]

        total_date_change = self.last_trans_julian_date[i] - self.first_trans_julian_date[i]
        self.drift[i] = self.slope[i] * total_date_change
        df['datechange'] = df['julian'] - self.first_trans_julian_date[i]

        df['driftcorrection'] = df['datechange'].apply(lambda x: x * self.slope[i], 1)
        df['driftcorrwoffset'] = df['driftcorrection'] + self.intercept[i]
        df[self.output_field] = df[self.drifting_field] - df['driftcorrwoffset']
        df = df.drop(['datechange'], axis=1)
        self.bracketedwls[i] = df

        return df, self.drift[i]

    def drift_data(self, i):
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

        self.drift_features[i] = {'t_beg': self.first_trans_date[i],
                                  'man_beg': self.first_man_date[i],
                                  't_end': self.last_trans_date[i],
                                  'man_end': self.last_man_date[i],
                                  'slope_man': self.slope_man[i],
                                  'slope_trans': self.slope_trans[i],
                                  'intercept': self.intercept[i],
                                  'slope': self.slope[i],
                                  'first_meas': self.first_man[i],
                                  'last_meas': self.last_man[i],
                                  'first_trans': self.first_trans[i],
                                  'last_trans': self.last_trans[i], 'drift': self.drift[i]}

    @staticmethod
    def ine(x, dtype):
        if x is None or pd.isna(x):
            return ''
        else:
            if dtype == 'f':
                return '9.3f'
            elif dtype == 'd':
                return '%Y-%m-%d %H:%M'
            elif dtype == 'sf':
                return '.3f'
            elif dtype == 'sl':
                return '9.5f'
            else:
                return ''

    def drift_print(self, i):
        a1 = self.first_man[i]
        a2 = self.last_man[i]
        b1 = self.first_man_date[i]
        b2 = self.last_man_date[i]
        c1 = self.first_trans[i]
        c2 = self.last_trans[i]
        d1 = self.first_trans_date[i]
        d2 = self.last_trans_date[i]
        e1 = self.slope_man[i]
        e2 = self.slope_trans[i]
        if self.well_id:
            print(f'Well ID {self.well_id}')
        print("_____________________________________________________________________________________")
        print("-----------|    First Day     |   First   |     Last Day     |   Last    |   Slope   |")
        print(
            f"    Manual | {'   No Data      ' if pd.isna(b1) else b1:{self.ine(b1, 'd')}} | {a1:{self.ine(a1, 'f')}} | {'   No Data        ' if pd.isna(b2) else b2:{self.ine(b2, 'd')}} | {a2:{self.ine(a2, 'f')}} | {e1:{self.ine(e1, 'sl')}} |")
        print(
            f"Transducer | {d1:{self.ine(d1, 'd')}} | {c1:{self.ine(c1, 'f')}} | {d2:{self.ine(d2, 'd')}} | {c2:{self.ine(c2, 'f')}} | {e2:{self.ine(e2, 'sl')}} |")
        print("---------------------------------------------------------------------------------------------")
        print(
            f"Slope = {self.slope[i]:{self.ine(self.slope[i], 'sf')}} and Intercept = {self.intercept[i]:{self.ine(self.intercept[i], 'sf')}}")
        print(f"Drift = {self.drift[i]:}")
        print(" -------------------")

    def endpoint_status(self, i):
        if np.abs(self.first_man_date[i] - self.first_trans_date[i]) > pd.Timedelta(f'{self.daybuffer:.0f}D'):
            print(f'No initial actual manual measurement within {self.daybuffer:} days of {self.first_trans_date[i]:}.')

            if (len(self.levdt) > 0) and (pd.notna(self.levdt[i])):
                if (self.first_trans_date[i] - datetime.timedelta(days=self.daybuffer) < pd.to_datetime(self.levdt[i])):
                    print("Pulling first manual measurement from database")
                    self.first_man[i] = self.lev[i]
                    self.first_man_julian_date[i] = pd.to_datetime(self.levdt[i]).to_julian_date()
            else:
                print('No initial transducer measurement within {:} days of {:}.'.format(self.daybuffer,
                                                                                         self.first_man_date[i]))
                self.first_man[i] = None
                self.first_man_date[i] = None

        if np.abs(self.last_trans_date[i] - self.last_man_date[i]) > pd.Timedelta(f'{self.daybuffer:.0f}D'):
            print(f'No final manual measurement within {self.daybuffer:} days of {self.last_trans_date[i]:}.')
            self.last_man[i] = None
            self.last_man_date[i] = None

        # intercept of line = value of first manual measurement
        if pd.isna(self.first_man[i]):
            print('First manual measurement missing between {:} and {:}'.format(self.breakpoints[i],
                                                                                self.breakpoints[i + 1]))

        elif pd.isna(self.last_man[i]):
            print('Last manual measurement missing between {:} and {:}'.format(self.breakpoints[i],
                                                                               self.breakpoints[i + 1]))

    def combine_brackets(self):
        dtnm = self.bracketedwls[0].index.name
        # print(dtnm)
        df = pd.concat(self.bracketedwls, sort=True)
        df = df.reset_index()
        df = df.set_index(dtnm)
        self.wellbarofixed = df.sort_index()


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
            base time to set in minutes; optional; default is zero (on the hour);
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

    df = df.resample(sampfrq, closed='right', label='right', offset=f'{bse:0.0f}min').asfreq()
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
        wellbaro = wellbaro.dropna(subset=['barometer', wellcolumn], how='any')
        wellbaro['dbp'] = wellbaro['barometer'].diff()
        wellbaro['dwl'] = wellbaro[wellcolumn].diff()
        #print(wellbaro)
        first_well = wellbaro.loc[wellbaro.index[0],wellcolumn]
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
                try:
                    self.well = self.new_xle_imp()
                except (ParseError, KeyError):
                    self.well = self.old_xle_imp()
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
                    f = pd.read_csv(self.infile, skiprows=1, parse_dates={'DateTime': [0, 1]})
                    # f = f.reset_index()
                    # f['DateTime'] = pd.to_datetime(f.columns[0], errors='coerce')
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
                    for col in [u'date', u'datediff', u'Date_ Time', u'Date_Time']:
                        if col in f.columns:
                            f = f.drop(col, axis=1)
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

    def old_xle_imp(self):
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

    def new_xle_imp(self):
        tree = eletree.parse(self.infile, parser=eletree.XMLParser(encoding="ISO-8859-1"))
        root = tree.getroot()

        ch1id = root.find('./Identification')
        dfdata = {}
        for item in root.findall('./Data/Log'):
            dfdata[item.attrib['id']] = {}
            for child in item:
                dfdata[item.attrib['id']][child.tag] = child.text
                # print([child[i].text for i in range(len(child))])
        ch = {}
        for child in root:
            if 'Ch' in child.tag:
                ch[child.tag[:3].lower()] = {}
                for item in child:
                    if item.text is not None:
                        ch[child.tag[:3].lower()][item.tag] = item.text

        f = pd.DataFrame.from_dict(dfdata, orient='index')
        f['DateTime'] = pd.to_datetime(f.apply(lambda x: x['Date'] + ' ' + x['Time'], 1))
        f = f.reset_index()
        f = f.set_index('DateTime')
        levelconv = {'feet': 1, 'ft': 1, 'kpa': 0.33456, 'mbar': 0.033455256555148,
                     'm': 3.28084, 'meters': 3.28084, 'psi': 2.306726}
        for col in f:
            if col in ch.keys():
                if col == 'ch1':
                    chname = 'Level'
                elif col == 'ch2':
                    chname = 'Temperature'
                elif 'Identification' in ch[col].keys():
                    chname = ch[col]['Identification'].title()

                chunit = ch[col]['Unit']
                f = f.rename(columns={col: chname})
                f[chname] = pd.to_numeric(f[chname])
                if chname == 'Level':
                    f[chname] = f[chname] * levelconv.get(chunit.lower(), 1)
                    print(f"CH. 1 units in {chunit}, converting to ft...")
                elif chname == 'Temperature' or chname == 'Temp':
                    if chunit[
                        -1] == 'F' or chunit.title() == 'Fahrenheit' or chunit.title() == 'Deg F' or chunit.title() == 'Deg_F':
                        f[chname] = (f[chname] - 32.0) * 5 / 9
                        print(f"CH. 2 units in {chunit}, converting to deg C...")
            elif col in ['ms', 'Date', 'Time', 'index']:
                f = f.drop(col, axis=1)
        f['name'] = self.infile.split('\\').pop().split('/').pop().rsplit('.', 1)[0]
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
                fild[file], dta = self.xle_head(file)
            elif file_extension == '.csv':
                fild[file], dta = self.csv_head(file)

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
        csvdata = pd.DataFrame()
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

        except (KeyError, AttributeError):
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

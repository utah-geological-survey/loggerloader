import datetime
from pathlib import Path
from shutil import copyfile
from typing import Union, Tuple

import numpy as np
import pandas as pd

from data_organization import dataendclean


###################################################################################################################
# MAIN CODE


#####################################################################################################################
def elevatewater(
    df,
    elevation,
    stickup,
    dtw_field="dtwbelowcasing",
    wtr_elev_field="waterelevation",
    flip=False,
):
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

    def __init__(
        self,
        manual_df,
        transducer_df,
        drifting_field="corrwl",
        man_field="measureddtw",
        daybuffer=3,
        output_field="waterelevation",
        trim_end=False,
        well_id=None,
        engine=None,
    ):
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
        self.manual_df["julian"] = self.manual_df.index.to_julian_date()

        self.transducer_df = self.datesort(transducer_df)
        self.transducer_df["julian"] = self.transducer_df.index.to_julian_date()

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
                    self.bracketedwls[i] = dataendclean(
                        self.bracketedwls[i], self.drifting_field, jumptol=0.5
                    )
                # self.endpoint_import(i)
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
            (self.transducer_df.index >= self.breakpoints[i])
            & (self.transducer_df.index < self.breakpoints[i + 1])
        ]
        df = df.dropna(subset=[self.drifting_field])
        df = df.sort_index()
        # print(i)
        # print(df)
        if len(df) > 0:
            self.manual_df["datetime"] = self.manual_df.index

            self.first_man_julian_date[i] = self.fcl(
                self.manual_df["julian"], self.breakpoints[i]
            )
            self.last_man_julian_date[i] = self.fcl(
                self.manual_df["julian"], self.breakpoints[i + 1]
            )
            self.first_man_date[i] = self.fcl(
                self.manual_df["datetime"], self.breakpoints[i]
            )
            self.last_man_date[i] = self.fcl(
                self.manual_df["datetime"], self.breakpoints[i + 1]
            )
            self.first_man[i] = self.fcl(
                self.manual_df[self.man_field], self.breakpoints[i]
            )  # first manual measurement
            self.last_man[i] = self.fcl(
                self.manual_df[self.man_field], self.breakpoints[i + 1]
            )  # last manual measurement

            self.first_trans[i] = df.loc[df.first_valid_index(), self.drifting_field]
            self.last_trans[i] = df.loc[df.last_valid_index(), self.drifting_field]
            self.first_trans_julian_date[i] = df.loc[df.first_valid_index(), "julian"]
            self.last_trans_julian_date[i] = df.loc[df.last_valid_index(), "julian"]
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
        return df.iloc[
            np.argmin(np.abs(pd.to_datetime(df.index) - dtobj))
        ]  # remove to_pydatetime()

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
        self.manual_df = (
            self.manual_df[self.manual_df.index.notnull()]
            .dropna(subset=[self.man_field])
            .sort_index()
        )

        self.manual_df = self.manual_df[
            (
                self.manual_df.index
                >= wellnona.first_valid_index() - pd.Timedelta(f"{self.daybuffer:.0f}D")
            )
        ]

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
            self.breakpoints = self.breakpoints[
                ~self.breakpoints.index.duplicated(keep="first")
            ]
            # convert to list
            self.breakpoints = self.breakpoints.values
        else:
            print(
                "No Breakpoints can be established as manual data do not align with imported data"
            )

    def drift_summary(self):
        self.drift_sum_table = pd.DataFrame(self.drift_features).T

        self.drift_sum_table['drift'] = self.drift_sum_table['drift'].astype(float)
        self.drift_sum_table['quality'] = (self.drift_sum_table['drift'] / 2).abs().round(3)
        self.drift_sum_table.loc[(self.drift_sum_table['man_beg'].isna()) | (self.drift_sum_table['man_end'].isna()), 'quality'] = 0.3
        self.drift_sum_table.loc[(self.drift_sum_table['man_beg'].isna()) | (self.drift_sum_table['man_end'].isna()), 'drift'] = None
        self.drift_sum_table.loc[(self.drift_sum_table['t_beg'].isna()) | (self.drift_sum_table['t_end'].isna()), 'quality'] = 0.3
        self.drift_sum_table.loc[(self.drift_sum_table['t_beg'].isna()) | (self.drift_sum_table['t_end'].isna()), 'drift'] = None

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
                print("Errorr")
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
                self.first_man_julian_date[i] - self.last_man_julian_date[i]
            )
            self.slope_trans[i] = (self.first_trans[i] - self.last_trans[i]) / (
                self.first_trans_julian_date[i] - self.last_trans_julian_date[i]
            )

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

        total_date_change = (
            self.last_trans_julian_date[i] - self.first_trans_julian_date[i]
        )
        self.drift[i] = self.slope[i] * total_date_change
        df["datechange"] = df["julian"] - self.first_trans_julian_date[i]

        df["driftcorrection"] = df["datechange"] * self.slope[i]
        df["driftcorrwoffset"] = df["driftcorrection"] + self.intercept[i]
        df[self.output_field] = df[self.drifting_field] - df["driftcorrwoffset"]
        df = df.drop(["datechange"], axis=1)
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

        self.drift_features[i] = {
            "t_beg": self.first_trans_date[i],
            "man_beg": self.first_man_date[i],
            "t_end": self.last_trans_date[i],
            "man_end": self.last_man_date[i],
            "slope_man": self.slope_man[i],
            "slope_trans": self.slope_trans[i],
            "intercept": self.intercept[i],
            "slope": self.slope[i],
            "first_meas": self.first_man[i],
            "last_meas": self.last_man[i],
            "first_trans": self.first_trans[i],
            "last_trans": self.last_trans[i],
            "drift": self.drift[i],
        }

    @staticmethod
    def ine(x, dtype):
        if x is None or pd.isna(x):
            return ""
        else:
            if dtype == "f":
                return "9.3f"
            elif dtype == "d":
                return "%Y-%m-%d %H:%M"
            elif dtype == "sf":
                return ".3f"
            elif dtype == "sl":
                return "9.5f"
            else:
                return ""

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
            print(f"Well ID {self.well_id}")
        print(
            "_____________________________________________________________________________________"
        )
        print(
            "-----------|    First Day     |   First   |     Last Day     |   Last    |   Slope   |"
        )
        print(
            f"    Manual | {'   No Data      ' if pd.isna(b1) else b1:{self.ine(b1, 'd')}} | {a1:{self.ine(a1, 'f')}} | {'   No Data        ' if pd.isna(b2) else b2:{self.ine(b2, 'd')}} | {a2:{self.ine(a2, 'f')}} | {e1:{self.ine(e1, 'sl')}} |"
        )
        print(
            f"Transducer | {d1:{self.ine(d1, 'd')}} | {c1:{self.ine(c1, 'f')}} | {d2:{self.ine(d2, 'd')}} | {c2:{self.ine(c2, 'f')}} | {e2:{self.ine(e2, 'sl')}} |"
        )
        print(
            "---------------------------------------------------------------------------------------------"
        )
        print(
            f"Slope = {self.slope[i]:{self.ine(self.slope[i], 'sf')}} and Intercept = {self.intercept[i]:{self.ine(self.intercept[i], 'sf')}}"
        )
        print(f"Drift = {self.drift[i]:}")
        print(" -------------------")

    def endpoint_status(self, i):
        if np.abs(self.first_man_date[i] - self.first_trans_date[i]) > pd.Timedelta(
            f"{self.daybuffer:.0f}D"
        ):
            print(
                f"No initial actual manual measurement within {self.daybuffer:} days of {self.first_trans_date[i]:}."
            )

            if (len(self.levdt) > 0) and (pd.notna(self.levdt[i])):
                if self.first_trans_date[i] - datetime.timedelta(
                    days=self.daybuffer
                ) < pd.to_datetime(self.levdt[i]):
                    print("Pulling first manual measurement from database")
                    self.first_man[i] = self.lev[i]
                    self.first_man_julian_date[i] = pd.to_datetime(
                        self.levdt[i]
                    ).to_julian_date()
            else:
                print(
                    "No initial transducer measurement within {:} days of {:}.".format(
                        self.daybuffer, self.first_man_date[i]
                    )
                )
                self.first_man[i] = None
                self.first_man_date[i] = None

        if np.abs(self.last_trans_date[i] - self.last_man_date[i]) > pd.Timedelta(
            f"{self.daybuffer:.0f}D"
        ):
            print(
                f"No final manual measurement within {self.daybuffer:} days of {self.last_trans_date[i]:}."
            )
            self.last_man[i] = None
            self.last_man_date[i] = None

        # intercept of line = value of first manual measurement
        if pd.isna(self.first_man[i]):
            print(
                "First manual measurement missing between {:} and {:}".format(
                    self.breakpoints[i], self.breakpoints[i + 1]
                )
            )

        elif pd.isna(self.last_man[i]):
            print(
                "Last manual measurement missing between {:} and {:}".format(
                    self.breakpoints[i], self.breakpoints[i + 1]
                )
            )

    def combine_brackets(self):
        dtnm = self.bracketedwls[0].index.name
        # print(dtnm)
        df = pd.concat(self.bracketedwls, sort=True)
        df = df.reset_index()
        df = df.set_index(dtnm)
        self.wellbarofixed = df.sort_index()

def barodistance(wellinfo):
    """Determines Closest Barometer to Each Well using wellinfo DataFrame"""
    barometers = {
        "barom": ["pw03", "pw10", "pw19"],
        "X": [240327.49, 271127.67, 305088.9],
        "Y": [4314993.95, 4356071.98, 4389630.71],
        "Z": [1623.079737, 1605.187759, 1412.673738],
    }
    barolocal = pd.DataFrame(barometers)
    barolocal = barolocal.reset_index()
    barolocal.set_index("barom", inplace=True)

    wellinfo["pw03"] = np.sqrt(
        (barolocal.loc["pw03", "X"] - wellinfo["UTMEasting"]) ** 2
        + (barolocal.loc["pw03", "Y"] - wellinfo["UTMNorthing"]) ** 2
        + (barolocal.loc["pw03", "Z"] - wellinfo["G_Elev_m"]) ** 2
    )
    wellinfo["pw10"] = np.sqrt(
        (barolocal.loc["pw10", "X"] - wellinfo["UTMEasting"]) ** 2
        + (barolocal.loc["pw10", "Y"] - wellinfo["UTMNorthing"]) ** 2
        + (barolocal.loc["pw10", "Z"] - wellinfo["G_Elev_m"]) ** 2
    )
    wellinfo["pw19"] = np.sqrt(
        (barolocal.loc["pw19", "X"] - wellinfo["UTMEasting"]) ** 2
        + (barolocal.loc["pw19", "Y"] - wellinfo["UTMNorthing"]) ** 2
        + (barolocal.loc["pw19", "Z"] - wellinfo["G_Elev_m"]) ** 2
    )
    wellinfo["closest_baro"] = wellinfo[["pw03", "pw10", "pw19"]].T.idxmin()
    return wellinfo


# -----------------------------------------------------------------------------------------------------------------------
# These scripts remove outlier data and filter the time series of jumps and erratic measurements








def jumpfix(
    df: pd.DataFrame, meas: str, threshold: float = 0.005, return_jump: bool = False
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Removes jumps or jolts in time series data where offset is lasting.

    Args:
        df: DataFrame to manipulate. Must have datetime index.
        meas: Name of field with jolts to correct
        threshold: Size of jolt to search for
        return_jump: If True, returns tuple of (corrected_data, jumps)

    Returns:
        If return_jump is False:
            DataFrame with corrected data
        If return_jump is True:
            Tuple of (corrected_DataFrame, jumps_DataFrame)

    Example:
        >>> dates = pd.date_range('2024-01-01', periods=5)
        >>> df = pd.DataFrame({
        ...     'level': [10, 10.1, 15.1, 15.2, 15.3]
        ... }, index=dates)
        >>> corrected = jumpfix(df, 'level', threshold=1)
        >>> corrected['level'].tolist()
        [10.0, 10.1, 10.1, 10.2, 10.3]

    Notes:
        - The function detects sudden changes (jumps) in the data that exceed
          the threshold value
        - Each jump is corrected by subtracting the cumulative jump amount
          from all subsequent values
        - The original time ordering is preserved
        - NaN values are preserved in their original positions
    """
    # Input validation
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")

    if meas not in df.columns:
        raise ValueError(f"Column '{meas}' not found in DataFrame")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be DatetimeIndex")

    # Create copy and ensure it's sorted
    df_temp = df.copy(deep=True).sort_index()
    df1 = df_temp[~df_temp.index.duplicated(keep='first')]
    if df1.shape[0] != df_temp.shape[0]:
        print(f'Dropped {df_temp.shape[0]-df1.shape[0]} records')


    # Calculate differences between consecutive values
    df1["delta"] = df1[meas].diff()

    # Find jumps exceeding threshold
    jump_mask = df1["delta"].abs() > threshold
    jumps = df1[jump_mask].copy()

    if len(jumps) == 0:
        if return_jump:
            return df1, pd.DataFrame()
        return df1

    # Calculate cumulative sum of jumps
    jumps["cumul"] = jumps["delta"].cumsum()

    # Initialize new values column
    df1["newVal"] = df1[meas].copy()

    # Apply corrections
    for idx in range(len(jumps.index)):
        jump_time = jumps.index[idx]
        jump_amount = jumps["cumul"].iloc[
            idx
        ]  # Using iloc instead of [] for position access

        # Create mask for all timestamps after the jump
        mask = df1.index >= jump_time

        # Apply correction
        df1.loc[mask, "newVal"] = df1.loc[mask, meas] - jump_amount

    # Update original measurement column
    df1[meas] = df1["newVal"]

    # Clean up temporary columns
    df1 = df1.drop(columns=["delta", "newVal"])

    if return_jump:
        # Clean up jumps DataFrame
        jumps = jumps.drop(columns=["newVal"])
        jumps = jumps.rename(columns={"delta": "jump_size"})
        return df1, jumps

    return df1


def detect_jumps(
        df: pd.DataFrame, meas : str = 'Level', threshold: float = 0.1) -> pd.DataFrame:
    """
    Detect jumps in time series data without applying corrections.

    Args:
        df: DataFrame with time series data
        meas: Name of measurement column
        threshold: Size of jump to detect

    Returns:
        DataFrame containing only the detected jumps with their properties
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")

    if meas not in df.columns:
        raise ValueError(f"Column '{meas}' not found in DataFrame")

    # Calculate differences
    diffs = df[meas].diff()

    # Find jumps
    jumps = df[abs(diffs) > threshold].copy()
    jumps["jump_size"] = diffs[abs(diffs) > threshold]
    jumps["cumulative_effect"] = jumps["jump_size"].cumsum()
    jumps = jumps[[meas, 'jump_size', 'cumulative_effect']]

    return jumps

# -----------------------------------------------------------------------------------------------------------------------
# The following scripts align and remove barometric pressure data


def correct_be(
    site_number, well_table, welldata, be=None, meas="corrwl", baro="barometer"
):
    if be:
        be = float(be)
    else:
        stdata = well_table[well_table["wellid"] == site_number]
        be = stdata["BaroEfficiency"].values[0]
    if be is None:
        be = 0
    else:
        be = float(be)

    if be == 0:
        welldata["baroefficiencylevel"] = welldata[meas]
    else:
        welldata["baroefficiencylevel"] = welldata[[meas, baro]].apply(
            lambda x: x[0] + be * x[1], 1
        )

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

    df = (
        df.resample("1min").mean(numeric_only=True).interpolate(method="time", limit=90)
    )

    if minutes == 60:
        sampfrq = "1h"
    else:
        sampfrq = str(minutes) + "min"

    df = df.resample(
        sampfrq, closed="right", label="right", offset=f"{bse:0.0f}min"
    ).asfreq()
    return df


def well_baro_merge(
    wellfile,
    barofile,
    barocolumn="Level",
    wellcolumn="Level",
    outcolumn="corrwl",
    vented=False,
    sampint=60,
):
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
    baro = baro.rename(columns={barocolumn: "barometer"})

    if "temp" in baro.columns:
        baro = baro.drop("temp", axis=1)
    elif "Temperature" in baro.columns:
        baro = baro.drop("Temperature", axis=1)
    elif "temperature" in baro.columns:
        baro = baro.drop("temperature", axis=1)

    if vented:
        wellbaro = well
        wellbaro[outcolumn] = wellbaro[wellcolumn]
    else:
        # combine baro and well data for easy calculations, graphing, and manipulation
        wellbaro = pd.merge(well, baro, left_index=True, right_index=True, how="left")
        wellbaro = wellbaro.dropna(subset=["barometer", wellcolumn], how="any")
        wellbaro["dbp"] = wellbaro["barometer"].diff()
        wellbaro["dwl"] = wellbaro[wellcolumn].diff()
        # print(wellbaro)
        first_well = wellbaro.loc[wellbaro.index[0], wellcolumn]
        wellbaro[outcolumn] = (
            (wellbaro["dwl"] - wellbaro["dbp"]).cumsum()
            + first_well
            )
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
    return df.iloc[
        np.argmin(np.abs(pd.to_datetime(df.index) - dtobj))
    ]  # remove to_pydatetime()



# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# Raw transducer import functions - these convert raw lev, xle, and csv files to Pandas Dataframes for processing





def fix_unit_change(df1, df2, field="Level", tolerance=0.03):
    """Rescale df2 when its logger recorded in different units than df1 (common in some Solinst files).

    The ratio of the two records' mean daily rolling standard deviations is compared to known
    unit conversion factors; if one matches within `tolerance`, df2[field] is multiplied by it.

    Args:
        df1 (pd.DataFrame): earlier record with a datetime index; df2 is converted to match it
        df2 (pd.DataFrame): later record with a datetime index
        field (str): column used to match units; default is Level
        tolerance (float): allowed relative difference from a conversion factor; default 3%

    Returns:
        pd.DataFrame: a copy of df2 with field converted
    """
    conversion_factors = {
        "meters to feet": 3.28084,
        "feet to meters": 0.3048,
        "psi to feet": 2.3066587,
        "feet to psi": 0.4335275,
        "psi to bar": 0.0689,
        "bar to psi": 14.5038,
        "kPa to psi": 0.145038,
        "psi to kPa": 6.89476,
        "kPa to feet": 0.3345525655,
        "feet to kPa": 2.9890669,
        "feet to bar": 0.02989,
        "bar to feet": 33.4553,
        "feet to mmHg": 22.42,
        "mmHg to feet": 0.0446,
    }
    df2 = df2.copy()
    df1std = np.mean(df1[field].rolling(24).std())
    df2std = np.mean(df2[field].rolling(24).std())
    if not df2std or np.isnan(df1std) or np.isnan(df2std):
        return df2
    stdratio = df1std / df2std

    for name, value in conversion_factors.items():
        if np.abs((value - stdratio) / value) < tolerance:
            print(name)
            df2[field] = df2[field] * value
            break
    return df2





# ----------------------------------------------------------------------------------------------------------------------
# Summary scripts - these extract transducer headers and summarize them in tables





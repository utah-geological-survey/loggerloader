import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

from .data_organization import dataendclean


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

def remove_baro_pressure(well,
                         barod,
                        vented_status = 'nonvented',
                        has_packer = False,
                        sampint = 60,
                        barocolumn = 'measuredlevel',
                        wellcolumn = 'Level',
                        outcolumn = 'corrwl'
                        ):
    """
    Merges transducer data with barometric data and then removes barometric pressure 
    either through differencing for wells without packers or by subtracting out 
    barometric pressure for wells with packers. Vented wells pass through with pressure
    being changed

    Parameters
    - well: 
    - barod: 
    - vented_status: as nonvented or vented
    - has_packer: as yes or no
    - sampint: sampling interval for barometer and transducer; data will be resampled
    - barocolumn: column in barometer dataframe representing barometric pressure
    - column:  in well column representing measured pressure
    - outcolumn: column name for barometric-pressured corrected transducer pressure 
    """

    # set parameter for well_baro_merge for vented wells
    if vented_status == 'vented':
        vented=True
    else:
        vented=False
    # merge barometer and well data together
    corrwl = well_baro_merge(well, barod, 
                                barocolumn = barocolumn,
                                wellcolumn = wellcolumn,
                                outcolumn = outcolumn,
                                sampint = sampint,
                                vented = vented)
    # directly subtract out barometeric pressure from packer wells
    if has_packer == 'yes' and vented_status != 'vented':
        if well[wellcolumn].min()<20:
            logging.warning(
                'Minimum transducer pressure below 20 ft; may need to correct for an offset')
        if barod[barocolumn].min()<20:
            logging.warning(
                'Minimum barometer pressure below 20 ft; may need to correct for an offset')
        logging.info('Adjusted barometric pressure using method for well with packer')
        corrwl['corrwl'] = corrwl['Level'] - corrwl['barometer']
    return(corrwl)

def point_head_density_correction(df, 
                               density_correction,
                                density_g_cm3 = None,
                                levelcolumn = 'corrwl',
                                outcolumn = 'corrwl'
                                  ):
    """
    Apply density correction to barometrically-corrected transducer data. If 
    density_correction is anything other than "constant", the data will be returned  
    with warnings

    Parameters
    - df: dataframe with barometrically-corrected water level data
    - density_correction: as none, constant, or variable
    - density_g_cm3: density of water in g/cm3
    - levelcolumn: name of column in df with barometrically-corrected pressure data (in feet)
    - outcolumn: name of output column
    """
    df2 = df.copy()
    if density_correction == 'constant':
      if pd.notna(density_g_cm3):
          logging.info(f'Density correction applied using {density_g_cm3}')
          df2['corrwl_original'] = df2[levelcolumn]
          df2[outcolumn] = df[levelcolumn]/density_g_cm3
          diff = df2['corrwl_original'] - df2[outcolumn]
          logging.info(f'Difference between density-corrected and uncorrected water levels min: {round(diff.min(), 3)}, mean: {round(diff.mean(), 3)}, max: {round(diff.max(), 3)}')
      else:
          logging.warning('Density correction needed but no density value assigned')
    elif density_correction == 'variable':
        logging.warning('Warning: Must conduct a variable-density density correction')
    else:
        logging.info(f'Density correction set as {density_correction}; no density adjustments made')
    return(df2)
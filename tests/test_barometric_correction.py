import logging
import numpy as np
import pandas as pd
import pytest

from loggerloader.barometric_correction import (
    correct_be,
    hourly_resample,
    remove_baro_pressure,
    well_baro_merge,
    point_head_density_correction
)

# ---------------------------------------------------------------------------
# Fixtures: Reusable synthetic time-series data
# ---------------------------------------------------------------------------

@pytest.fixture
def hourly_times():
    return pd.date_range("2025-01-01 00:00", periods=5, freq="1h")


@pytest.fixture
def sample_well_df(hourly_times):
    # Total head (water + baro) = 50.0, 50.5, 51.0, 50.8, 50.2
    return pd.DataFrame(
        {"Level": [50.0, 50.5, 51.0, 50.8, 50.2]},
        index=hourly_times,
    )


@pytest.fixture
def sample_baro_df(hourly_times):
    # Barometric pressure = 30.0, 30.2, 30.5, 30.3, 30.0
    return pd.DataFrame(
        {
            "measuredlevel": [30.0, 30.2, 30.5, 30.3, 30.0],
            "Temperature": [15.0, 15.5, 16.0, 15.8, 15.2],
        },
        index=hourly_times,
    )


@pytest.fixture
def well_lookup_table():
    return pd.DataFrame(
        {
            "wellid": ["W-101", "W-102", "W-103"],
            "BaroEfficiency": [0.5, 0.0, None],
        }
    )


# ---------------------------------------------------------------------------
# Tests for `correct_be`
# ---------------------------------------------------------------------------

def test_correct_be_explicit_efficiency(sample_well_df, well_lookup_table):
    df = sample_well_df.copy()
    df["corrwl"] = [10.0, 10.2, 10.4, 10.3, 10.1]
    df["barometer"] = [30.0, 30.2, 30.4, 30.2, 30.0]

    result_df, be_used = correct_be(
        site_number="W-101",
        well_table=well_lookup_table,
        welldata=df,
        be=0.25,
    )

    assert be_used == 0.25
    expected = df["corrwl"] + 0.25 * df["barometer"]
    pd.testing.assert_series_equal(
        result_df["baroefficiencylevel"], expected, check_names=False
    )


def test_correct_be_lookup_from_table(sample_well_df, well_lookup_table):
    df = sample_well_df.copy()
    df["corrwl"] = [10.0, 10.0, 10.0, 10.0, 10.0]
    df["barometer"] = [30.0, 31.0, 32.0, 31.0, 30.0]

    result_df, be_used = correct_be(
        site_number="W-101",
        well_table=well_lookup_table,
        welldata=df,
        be=None,
    )

    assert be_used == 0.5
    expected = pd.Series([25.0, 25.5, 26.0, 25.5, 25.0], index=df.index)
    pd.testing.assert_series_equal(
        result_df["baroefficiencylevel"], expected, check_names=False
    )


def test_correct_be_zero_efficiency(sample_well_df, well_lookup_table):
    df = sample_well_df.copy()
    df["corrwl"] = [10.0, 10.5, 11.0, 10.8, 10.2]
    df["barometer"] = [30.0, 30.2, 30.5, 30.3, 30.0]

    result_df, be_used = correct_be(
        site_number="W-102",
        well_table=well_lookup_table,
        welldata=df,
        be=None,
    )

    assert be_used == 0.0
    pd.testing.assert_series_equal(
        result_df["baroefficiencylevel"], df["corrwl"], check_names=False
    )


# ---------------------------------------------------------------------------
# Tests for `hourly_resample`
# ---------------------------------------------------------------------------

def test_hourly_resample_interpolates_irregular_timestamps():
    # Off-hour timestamps at :15 and :45
    idx = pd.to_datetime(
        [
            "2025-01-01 00:15",
            "2025-01-01 00:45",
            "2025-01-01 01:15",
            "2025-01-01 01:45",
        ]
    )
    # Linear ramp of 1.0 per 30 mins -> at 01:00 value should be 10.5
    df = pd.DataFrame({"Level": [10.0, 11.0, 12.0, 13.0]}, index=idx)

    resampled = hourly_resample(df, bse=0, minutes=60)

    assert pd.Timestamp("2025-01-01 01:00") in resampled.index
    assert np.isclose(resampled.loc["2025-01-01 01:00", "Level"], 11.5)


def test_hourly_resample_custom_interval():
    idx = pd.date_range("2025-01-01 00:00", periods=3, freq="30min")
    df = pd.DataFrame({"Level": [10.0, 13.0, 16.0]}, index=idx)

    resampled = hourly_resample(df, bse=0, minutes=15)

    assert pd.Timestamp("2025-01-01 00:15") in resampled.index
    assert np.isclose(resampled.loc["2025-01-01 00:15", "Level"], 11.5)


# ---------------------------------------------------------------------------
# Tests for `well_baro_merge`
# ---------------------------------------------------------------------------

def test_well_baro_merge_nonvented_differencing(sample_well_df, sample_baro_df):
    merged = well_baro_merge(
        wellfile=sample_well_df,
        barofile=sample_baro_df,
        barocolumn="measuredlevel",
        wellcolumn="Level",
        outcolumn="corrwl",
        vented=False,
        sampint=60,
    )

    # Temperature column from barofile should be dropped
    assert "Temperature" not in merged.columns
    assert "barometer" in merged.columns

    # Hand-calculated expected values:
    # t0: 50.0 (initial anchor)
    # t1: 50.0 + (0.5 - 0.2) = 50.3
    # t2: 50.3 + (0.5 - 0.3) = 50.5
    # t3: 50.5 + (-0.2 - (-0.2)) = 50.5
    # t4: 50.5 + (-0.6 - (-0.3)) = 50.2
    expected = pd.Series([50.0, 50.3, 50.5, 50.5, 50.2], index=merged.index)
    np.testing.assert_allclose(merged["corrwl"].values, expected.values, rtol=1e-6)


def test_well_baro_merge_vented_passthrough(sample_well_df, sample_baro_df):
    merged = well_baro_merge(
        wellfile=sample_well_df,
        barofile=sample_baro_df,
        barocolumn="measuredlevel",
        wellcolumn="Level",
        outcolumn="corrwl",
        vented=True,
        sampint=60,
    )

    pd.testing.assert_series_equal(
        merged["corrwl"], merged["Level"], check_names=False
    )


# ---------------------------------------------------------------------------
# Tests for `remove_baro_pressure`
# ---------------------------------------------------------------------------

def test_remove_baro_pressure_packer_direct_subtraction(
    sample_well_df, sample_baro_df
):
    result = remove_baro_pressure(
        well=sample_well_df,
        barod=sample_baro_df,
        vented_status="nonvented",
        has_packer="yes",
        sampint=60,
        barocolumn="measuredlevel",
        wellcolumn="Level",
        outcolumn="corrwl",
    )

    # Direct subtraction: Level - barometer
    expected = pd.Series([20.0, 20.3, 20.5, 20.5, 20.2], index=result.index)
    np.testing.assert_allclose(result["corrwl"].values, expected.values, rtol=1e-6)


def test_remove_baro_pressure_packer_logs_warning_below_20ft(
    sample_well_df, sample_baro_df, caplog
):
    low_well = sample_well_df.copy()
    low_well["Level"] = 15.0  # Triggers < 20 ft offset warning

    with caplog.at_level(logging.WARNING):
        remove_baro_pressure(
            well=low_well,
            barod=sample_baro_df,
            vented_status="nonvented",
            has_packer="yes",
            barocolumn="measuredlevel",
            wellcolumn="Level",
        )

    assert "Minimum transducer pressure below 20 ft" in caplog.text

# ---------------------------------------------------------------------------
# Tests for `point_head_density_correction`
# ---------------------------------------------------------------------------

def test_point_head_density_correction_constant_valid(sample_well_df, caplog):
    df = sample_well_df.copy()
    df["corrwl"] = [20.0, 20.5, 21.0, 20.8, 20.2]
    density = 1.025

    with caplog.at_level(logging.INFO):
        result = point_head_density_correction(
            df=df,
            density_correction="constant",
            density_g_cm3=density,
            levelcolumn="corrwl",
            outcolumn="corrwl",
        )

    # Original values preserved in 'corrwl_original' and input df not mutated
    pd.testing.assert_series_equal(
        result["corrwl_original"], df["corrwl"], check_names=False
    )
    assert "corrwl_original" not in df.columns

    # Output equals levelcolumn / density_g_cm3
    expected = df["corrwl"] / density
    pd.testing.assert_series_equal(
        result["corrwl"], expected, check_names=False
    )
    assert f"Density correction applied using {density}" in caplog.text


def test_point_head_density_correction_custom_columns(sample_well_df):
    df = sample_well_df.copy()
    df["raw_head"] = [10.0, 20.0, 30.0, 40.0, 50.0]

    result = point_head_density_correction(
        df=df,
        density_correction="constant",
        density_g_cm3=1.0,
        levelcolumn="raw_head",
        outcolumn="density_corr_head",
    )

    assert "density_corr_head" in result.columns
    pd.testing.assert_series_equal(
        result["density_corr_head"], df["raw_head"], check_names=False
    )


@pytest.mark.parametrize("missing_density", [None, np.nan])
def test_point_head_density_correction_constant_missing_density(
    sample_well_df, missing_density, caplog
):
    df = sample_well_df.copy()
    df["corrwl"] = [20.0, 20.5, 21.0, 20.8, 20.2]

    with caplog.at_level(logging.WARNING):
        result = point_head_density_correction(
            df=df,
            density_correction="constant",
            density_g_cm3=missing_density,
        )

    assert "Density correction needed but no density value assigned" in caplog.text
    assert "corrwl_original" not in result.columns
    pd.testing.assert_frame_equal(result, df)


def test_point_head_density_correction_variable_warns_and_passes_through(
    sample_well_df, caplog
):
    df = sample_well_df.copy()
    df["corrwl"] = [20.0, 20.5, 21.0, 20.8, 20.2]

    with caplog.at_level(logging.WARNING):
        result = point_head_density_correction(
            df=df,
            density_correction="variable",
            density_g_cm3=1.025,
        )

    assert "Warning: Must conduct a variable-density density correction" in caplog.text
    pd.testing.assert_frame_equal(result, df)


def test_point_head_density_correction_none_passes_through(sample_well_df, caplog):
    df = sample_well_df.copy()
    df["corrwl"] = [20.0, 20.5, 21.0, 20.8, 20.2]

    with caplog.at_level(logging.INFO):
        result = point_head_density_correction(
            df=df,
            density_correction="none",
        )

    assert "Density correction set as none; no density adjustments made" in caplog.text
    pd.testing.assert_frame_equal(result, df)
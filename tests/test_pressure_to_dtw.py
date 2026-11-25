import datetime
import logging
import numpy as np
import pandas as pd
import pytest

from loggerloader.pressure_to_dtw import (
    Drifting,
    calc_freshwater_equivalent_head,
    convert_pressure_to_dtw_below_ground,
    fcl,
    review_drift_values,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def linear_drift_data():
    """Creates 6 days of 12-hour transducer data with a known linear drift of +0.1/day
    and two manual measurements at Day 0 and Day 5.
    """
    times = pd.date_range("2025-01-01 00:00", periods=11, freq="12h", name="DateTime")
    days = np.arange(11) * 0.5
    # True water level rises linearly from 10.0 to 12.5 (+0.5/day)
    # Transducer starts at 20.0 (offset = +10.0) and drifts by +0.1/day -> +0.6/day total
    true_wl = 10.0 + 0.5 * days
    trans_wl = 20.0 + 0.6 * days

    trans_df = pd.DataFrame({"corrwl": trans_wl}, index=times)
    man_df = pd.DataFrame(
        {"measureddtw": [10.0, 12.5]},
        index=pd.to_datetime(["2025-01-01 00:00", "2025-01-06 00:00"]),
    )
    return trans_df, man_df, true_wl


# ---------------------------------------------------------------------------
# Tests for `fcl`
# ---------------------------------------------------------------------------

def test_fcl_finds_closest_timestamp():
    idx = pd.to_datetime(["2025-01-01 00:00", "2025-01-01 06:00", "2025-01-01 12:00"])
    df = pd.DataFrame({"val": [100, 200, 300]}, index=idx)

    closest = fcl(df, datetime.datetime(2025, 1, 1, 4, 30))
    assert closest["val"] == 200


# ---------------------------------------------------------------------------
# Tests for `Drifting` Class
# ---------------------------------------------------------------------------

def test_drifting_process_drift_removes_linear_offset_and_drift(linear_drift_data):
    trans_df, man_df, true_wl = linear_drift_data

    drifter = Drifting(
        manual_df=man_df,
        transducer_df=trans_df,
        drifting_field="corrwl",
        man_field="measureddtw",
        daybuffer=3,
        output_field="waterelevation",
        trim_end=False,
        well_id="W-10",
    )
    fixed_df, drift_summary, max_drift = drifter.process_drift()

    # Bracket [2025-01-01, 2025-01-06) includes the first 10 points (00:00 Jan 1 through 12:00 Jan 5)
    assert len(fixed_df) == 10
    np.testing.assert_allclose(
        fixed_df["waterelevation"].values, true_wl[:10], atol=1e-6
    )

    # Drift over the 4.5-day transducer span inside the bracket = 0.1/day * 4.5 days = 0.45
    assert np.isclose(max_drift, 0.45, atol=1e-6)
    assert len(drift_summary) == 1
    assert np.isclose(drift_summary["slope"].iloc[0], 0.1, atol=1e-6)
    assert np.isclose(drift_summary["intercept"].iloc[0], 10.0, atol=1e-6)


def test_drifting_multi_bracket_piecewise_correction():
    times = pd.date_range("2025-01-01 00:00", periods=5, freq="1D", name="DateTime")
    # Bracket 1 (Jan 1 - Jan 3): constant offset +5.0, zero drift
    # Bracket 2 (Jan 3 - Jan 5): constant offset +8.0 (e.g., transducer re-hung), zero drift
    trans_df = pd.DataFrame({"corrwl": [15.0, 16.0, 20.0, 21.0, 22.0]}, index=times)
    man_df = pd.DataFrame(
        {"measureddtw": [10.0, 12.0, 14.0]},
        index=pd.to_datetime(["2025-01-01", "2025-01-03", "2025-01-05"]),
    )

    fixed_df, drift_summary, max_drift = Drifting(
        man_df, trans_df, trim_end=False
    ).process_drift()

    assert len(drift_summary) == 2
    assert np.isclose(max_drift, 0.0, atol=1e-6)
    # Note: Jan 5 is the final upper breakpoint (< breakpoints[i+1]), so 4 rows are processed
    np.testing.assert_allclose(
        fixed_df["waterelevation"].values, [10.0, 11.0, 12.0, 13.0], atol=1e-6
    )


def test_drifting_missing_endpoint_manual_measurement_sets_quality_03():
    times = pd.date_range("2025-01-01", periods=10, freq="1D", name="DateTime")
    trans_df = pd.DataFrame({"corrwl": np.full(10, 20.0)}, index=times)
    # Only one manual measurement at Day 0; trailing transducer data has no end manual within daybuffer=2
    man_df = pd.DataFrame(
        {"measureddtw": [10.0]},
        index=pd.to_datetime(["2025-01-01"]),
    )

    fixed_df, drift_summary, max_drift = Drifting(
        man_df, trans_df, daybuffer=2, trim_end=False
    ).process_drift()

    assert drift_summary["quality"].iloc[0] == 0.3
    assert pd.isna(drift_summary["drift"].iloc[0])
    assert pd.isna(max_drift)
    np.testing.assert_allclose(fixed_df["waterelevation"].values, 10.0, atol=1e-6)


# ---------------------------------------------------------------------------
# Tests for `convert_pressure_to_dtw_below_ground`
# ---------------------------------------------------------------------------

def test_convert_pressure_to_dtw_non_packered_well():
    times = pd.date_range("2025-01-01", periods=3, freq="1D", name="DateTime")
    # Submergence depth increases from 10 to 12 ft -> water table gets shallower (DTW drops from 30 to 28 ft)
    df = pd.DataFrame({"corrwl": [10.0, 11.0, 12.0]}, index=times)
    mandf = pd.DataFrame(
        {"dtwbelowground": [30.0, 28.0]},
        index=pd.to_datetime(["2025-01-01", "2025-01-03"]),
    )

    dft, drift_info = convert_pressure_to_dtw_below_ground(
        df=df,
        mandf=mandf,
        siteid="WELL-1",
        stickup=2.0,
        verticalmeasure=100.0,
        has_packer="no",
        day_buffer=1,
    )

    np.testing.assert_allclose(dft["measureddtw"].values, [30.0, 29.0], atol=1e-6)
    # waterelevation = verticalmeasure (100.0) - measureddtw
    np.testing.assert_allclose(dft["waterelevation"].values, [70.0, 71.0], atol=1e-6)
    assert drift_info["locationid"].iloc[0] == "WELL-1"


def test_convert_pressure_to_dtw_packered_well():
    times = pd.date_range("2025-01-01", periods=3, freq="1h", name="DateTime")
    df = pd.DataFrame({"corrwl": [15.0, 16.0, 17.5]}, index=times)

    # sensor_depth_below_ground = 50.0 - 2.0 = 48.0
    # measureddtw = 48.0 - corrwl = [33.0, 32.0, 30.5]
    # waterelevation = 500.0 - measureddtw = [467.0, 468.0, 469.5]
    dft, drift_info = convert_pressure_to_dtw_below_ground(
        df=df,
        mandf=pd.DataFrame(),
        siteid="PACKER-1",
        stickup=2.0,
        verticalmeasure=500.0,
        has_packer="yes",
        sensor_depth_below_casing=50.0,
    )

    np.testing.assert_allclose(dft["measureddtw"].values, [33.0, 32.0, 30.5])
    np.testing.assert_allclose(dft["waterelevation"].values, [467.0, 468.0, 469.5])
    assert drift_info["quality"].iloc[0] == 0.3
    assert drift_info["notes"].iloc[0] == "packered well; no manual measurements"
    assert pd.isna(drift_info["drift"].iloc[0])


# ---------------------------------------------------------------------------
# Tests for `review_drift_values` and `calc_freshwater_equivalent_head`
# ---------------------------------------------------------------------------

def test_review_drift_values_flags_large_or_na_drift(capsys, caplog):
    drift_df = pd.DataFrame(
        {
            "t_beg": pd.to_datetime(["2025-01-01", "2025-02-01"]),
            "t_end": pd.to_datetime(["2025-01-31", "2025-02-28"]),
            "drift": [0.15, 0.45],
        }
    )

    with caplog.at_level(logging.INFO):
        review_drift_values(drift_df)

    assert "max drift: 0.45" in caplog.text
    assert "Rows with bad or na drift" in capsys.readouterr().out


def test_calc_freshwater_equivalent_head_modes(caplog):
    df = pd.DataFrame({"measureddtw": [30.0, 40.0]})

    # 1. constant density: screen - ((screen - dtw) * density)
    # 100 - ((100 - 30) * 1.02) = 100 - 71.4 = 28.6
    res_const = calc_freshwater_equivalent_head(
        df, density_correction="constant", screen=100.0, density=1.02
    )
    np.testing.assert_allclose(res_const["dtw_ref_fluid"].values, [28.6, 38.8])
    assert "dtw_ref_fluid" not in df.columns  # Input DataFrame not mutated

    # 2. missing screen/density logs warning
    with caplog.at_level(logging.WARNING):
        res_missing = calc_freshwater_equivalent_head(
            df, density_correction="constant", screen=None, density=1.02
        )
    assert "Missing screen depth and/or fluid density values" in caplog.text
    assert "dtw_ref_fluid" not in res_missing.columns

    # 3. variable density logs warning
    with caplog.at_level(logging.WARNING):
        calc_freshwater_equivalent_head(
            df, density_correction="variable", screen=100.0, density=1.02
        )
    assert "Must conduct a variable-density density correction" in caplog.text

    # 4. none logs info
    with caplog.at_level(logging.INFO):
        res_none = calc_freshwater_equivalent_head(
            df, density_correction="none", screen=100.0, density=1.02
        )
    assert "freshwater head not calculated" in caplog.text
    assert "dtw_ref_fluid" not in res_none.columns
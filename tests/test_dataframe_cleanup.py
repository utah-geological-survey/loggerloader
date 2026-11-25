import logging
import numpy as np
import pandas as pd
import pytest

from loggerloader.dataframe_cleanup import (
    clean_up_reading_columns,
    delete_dataframes_with_name,
    prep_barometer,
    prep_datetime_data,
    read_in_baro,
    read_in_manuals,
    subset_final_processed_data,
    update_drift_info,
)


# ---------------------------------------------------------------------------
# Tests for `prep_datetime_data`
# ---------------------------------------------------------------------------

def test_prep_datetime_data_sorts_and_does_not_mutate():
    raw = pd.DataFrame(
        {
            "readingdate": ["2025-01-03 00:00", "2025-01-01 00:00", "2025-01-02 00:00"],
            "val": [3, 1, 2],
        }
    )

    result = prep_datetime_data(raw)

    assert isinstance(result.index, pd.DatetimeIndex)
    assert result.index.is_monotonic_increasing
    assert list(result["val"]) == [1, 2, 3]
    # Input DataFrame must remain unmodified
    assert "readingdate" in raw.columns


def test_prep_datetime_data_mixed_formats_and_custom_datefield():
    raw = pd.DataFrame(
        {
            "custom_ts": ["2025-01-01 00:00:00", "01/02/2025 12:00"],
            "val": [10, 20],
        }
    )

    result = prep_datetime_data(raw, mixed=True, datefield="custom_ts")

    assert isinstance(result.index, pd.DatetimeIndex)
    assert list(result["val"]) == [10, 20]


def test_prep_datetime_data_missing_column_raises_keyerror():
    raw = pd.DataFrame({"other_col": ["2025-01-01"]})

    with pytest.raises(KeyError, match="readingdate"):
        prep_datetime_data(raw)


# ---------------------------------------------------------------------------
# Tests for `delete_dataframes_with_name`
# ---------------------------------------------------------------------------

def test_delete_dataframes_with_name_targets_module_globals():
    import sys
    mod = sys.modules[delete_dataframes_with_name.__module__]

    mod.temp_test_df_1 = pd.DataFrame({"a": [1]})
    mod.temp_test_df_2 = pd.DataFrame({"b": [2]})
    mod.keep_this_df = pd.DataFrame({"c": [3]})
    mod.temp_test_not_a_df = "leave_me_alone"

    try:
        delete_dataframes_with_name("temp_test")

        assert not hasattr(mod, "temp_test_df_1")
        assert not hasattr(mod, "temp_test_df_2")
        assert hasattr(mod, "keep_this_df")
        assert hasattr(mod, "temp_test_not_a_df")
    finally:
        for attr in ("temp_test_df_1", "temp_test_df_2", "keep_this_df", "temp_test_not_a_df"):
            if hasattr(mod, attr):
                delattr(mod, attr)

# ---------------------------------------------------------------------------
# Tests for `read_in_manuals` and `read_in_baro`
# ---------------------------------------------------------------------------

def test_read_in_manuals_filters_site_and_date():
    manual_df = pd.DataFrame(
        {
            "readingdate": ["2024-12-01", "2025-01-10", "2025-02-15", "2025-02-20"],
            "well_id": ["W-1", "W-1", "W-1", "W-2"],
            "dtw": [15.1, 15.4, 15.8, 22.0],
        }
    )

    result = read_in_manuals(
        manual_table=manual_df,
        manualid="well_id",
        siteid="W-1",
        process_date="2025-01-01",
    )

    assert len(result) == 2
    assert list(result["dtw"]) == [15.4, 15.8]


def test_read_in_manuals_warns_when_empty(capsys):
    manual_df = pd.DataFrame(
        {
            "readingdate": ["2024-06-01"],
            "well_id": ["W-1"],
            "dtw": [15.1],
        }
    )

    result = read_in_manuals(manual_df, "well_id", "W-1", "2025-01-01")

    assert len(result) == 0
    assert "No manual data for site: W-1 after 2025-01-01" in capsys.readouterr().out


def test_read_in_baro_reads_and_filters_by_date(tmp_path):
    baro_dir = tmp_path / "barometer_data"
    baro_dir.mkdir()
    baro_csv = baro_dir / "P101.csv"

    df = pd.DataFrame(
        {
            "readingdate": ["2024-12-31 23:00", "2025-01-01 00:00", "2025-01-01 01:00"],
            "measuredlevel": [29.9, 30.1, 30.2],
        }
    )
    df.to_csv(baro_csv, index=False)

    # Pass float 101.0 to verify int coercion -> P101.csv
    result = read_in_baro(baroid=101.0, output_folder=tmp_path, process_date="2025-01-01")

    assert len(result) == 2
    assert list(result["measuredlevel"]) == [30.1, 30.2]


# ---------------------------------------------------------------------------
# Tests for `clean_up_reading_columns` and `prep_barometer`
# ---------------------------------------------------------------------------

def test_clean_up_reading_columns_renames_filters_and_rounds():
    idx = pd.date_range("2025-01-01 00:00", periods=2, freq="1h", name="DateTime")
    dft = pd.DataFrame(
        {
            "Level": [12.345678, 12.987654],
            "DTW_WL": [45.11111, 45.22229],
            "Temperature": [14.12345, 14.56789],
            "specific_conductivity": [500.55555, 501.11111],
            "extra_unused_col": ["drop_me", "drop_me"],
        },
        index=idx,
    )

    cleaned = clean_up_reading_columns(dft, siteid=42)

    expected_cols = [
        "readingdate",
        "measuredlevel",
        "measureddtw",
        "temperature",
        "conductivity",
        "locationid",
    ]
    assert list(cleaned.columns) == expected_cols
    assert "extra_unused_col" not in cleaned.columns
    assert list(cleaned["measuredlevel"]) == [12.3457, 12.9877]
    assert list(cleaned["measureddtw"]) == [45.1111, 45.2223]
    assert (cleaned["locationid"] == 42).all()


def test_prep_barometer_sorts_rounds_and_deduplicates():
    # Include duplicate timestamp and unsorted index
    idx = pd.to_datetime(
        ["2025-01-01 01:00", "2025-01-01 00:00", "2025-01-01 00:00"],
    )
    idx.name = "DateTime"
    df = pd.DataFrame(
        {
            "Level": [30.12345, 29.98765, 29.98765],
            "Temperature": [15.11111, 14.55555, 14.55555],
            "locationid": [999, 999, 999],
        },
        index=idx,
    )

    result = prep_barometer(df, locationid=77)

    assert len(result) == 2
    assert list(result.columns) == ["readingdate", "measuredlevel", "temperature", "locationid"]
    assert list(result["measuredlevel"]) == [29.9876, 30.1234] or list(result["measuredlevel"]) == [29.9877, 30.1235]
    assert (result["locationid"] == 77).all()


# ---------------------------------------------------------------------------
# Tests for `subset_final_processed_data`
# ---------------------------------------------------------------------------

def test_subset_final_processed_data_modes():
    times = pd.date_range("2025-01-01", periods=4, freq="1D")
    processed = pd.DataFrame({"measuredlevel": [10.0, 11.0, 12.0, 13.0]}, index=times)
    drift = pd.DataFrame(
        {
            "t_beg": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "drift": [0.01, 0.02, 0.03],
        }
    )
    old_reading = pd.DataFrame({"measuredlevel": [9.5, 10.0]}, index=times[:2])  # last valid = 2025-01-02

    # 1. keep='new' -> strictly after 2025-01-02 for readings, >= 2025-01-02 for drift
    r_new, d_new = subset_final_processed_data("new", processed, drift, old_reading=old_reading)
    assert list(r_new.index) == list(times[2:])
    assert list(d_new["t_beg"]) == list(pd.to_datetime(["2025-01-02", "2025-01-03"]))

    # 2. keep='all'
    r_all, d_all = subset_final_processed_data("all", processed, drift)
    pd.testing.assert_frame_equal(r_all, processed)
    pd.testing.assert_frame_equal(d_all, drift)

    # 3. keep='keep_date'
    r_kd, d_kd = subset_final_processed_data("keep_date", processed, drift, keep_date="2025-01-03")
    assert list(r_kd.index) == list(times[2:])
    assert list(d_kd["t_beg"]) == list(pd.to_datetime(["2025-01-03"]))


# ---------------------------------------------------------------------------
# Tests for `update_drift_info`
# ---------------------------------------------------------------------------

def test_update_drift_info_single_and_multiple_dates():
    drift_df = pd.DataFrame(
        {
            "t_beg": ["2025-01-01", "2025-01-02", "2025-01-03"],
            "datastatus": ["raw", "raw", "raw"],
            "notes": ["", "", ""],
        }
    )

    # Single string date
    updated_single = update_drift_info(drift_df, "2025-01-02", "approved", "Checked OK")
    assert list(updated_single["datastatus"]) == ["raw", "approved", "raw"]
    assert updated_single.loc[1, "notes"] == "Checked OK"
    # Input DataFrame should not be mutated
    assert drift_df.loc[1, "datastatus"] == "raw"

    # List of dates
    updated_multi = update_drift_info(
        drift_df, ["2025-01-01", "2025-01-03"], "flagged", "Sensor jump"
    )
    assert list(updated_multi["datastatus"]) == ["flagged", "raw", "flagged"]


def test_update_drift_info_warns_when_no_match_and_raises_on_missing_cols(caplog):
    drift_df = pd.DataFrame(
        {
            "t_beg": ["2025-01-01"],
            "datastatus": ["raw"],
            "notes": [""],
        }
    )

    with caplog.at_level(logging.WARNING):
        update_drift_info(drift_df, "2099-01-01", "approved", "No match")
    assert "No records found in drift table" in caplog.text

    bad_df = pd.DataFrame({"t_beg": ["2025-01-01"]})
    with pytest.raises(KeyError, match="missing required column"):
        update_drift_info(bad_df, "2025-01-01", "approved", "Fail")
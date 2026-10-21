import pytest
import pandas as pd
import numpy as np

# Adjust import according to your package installation or directory layout
try:
    from src.loggerloader.qaqc import (
        DEFAULT_SPIKE_THRESHOLDS,
        drop_duplicates_with_index,
        resolve_duplicate_transducer_records,
        detect_transducer_spikes,
        detect_transducer_flatlines,
    )
except ModuleNotFoundError:
    from qaqc import (
        DEFAULT_SPIKE_THRESHOLDS,
        drop_duplicates_with_index,
        resolve_duplicate_transducer_records,
        detect_transducer_spikes,
        detect_transducer_flatlines,
    )


# ==========================================
# FIXTURES
# ==========================================

@pytest.fixture
def clean_transducer_series():
    """Continuous 15-minute transducer series with no anomalies."""
    dates = pd.date_range("2024-01-01 00:00", periods=48, freq="15min")
    return pd.DataFrame(
        {
            "Level": np.linspace(15.0, 15.5, 48),
            "Temperature": np.linspace(12.0, 12.2, 48),
            "filename": "DL_20240101.csv",
        },
        index=dates,
    )


@pytest.fixture
def overlapping_loggers_df():
    """Simulates swapping an outgoing transducer with a replacement logger."""
    old_dates = pd.date_range("2024-01-01 08:00", "2024-01-01 14:00", freq="1h")
    new_dates = pd.date_range("2024-01-01 12:00", "2024-01-01 18:00", freq="1h")

    df_old = pd.DataFrame(
        {"Level": 10.0, "filename": "logger_old.csv"}, index=old_dates
    )
    df_new = pd.DataFrame(
        {"Level": 10.1, "filename": "logger_new.csv"}, index=new_dates
    )

    combined = pd.concat([df_old, df_new]).sort_index()
    return combined


@pytest.fixture
def spiky_water_level_df():
    """Series with baseline water levels containing an anomalous spike."""
    dates = pd.date_range("2024-01-01 00:00", periods=20, freq="15min")
    values = [10.0] * 20
    values[8] = 14.5  # 4.5 ft spike at 02:00
    values[15] = 16.0  # 6.0 ft spike at 03:45
    return pd.DataFrame({"Level": values}, index=dates)


# ==========================================
# TESTS: drop_duplicates_with_index
# ==========================================

def test_drop_duplicates_exact_matches():
    dates = pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:00", "2024-01-01 11:00"])
    df = pd.DataFrame(
        {"Level": [1.5, 1.5, 1.6], "Temperature": [12.0, 12.0, 12.1]}, index=dates
    )
    result = drop_duplicates_with_index(df, subset=["Level", "Temperature"])[cite: 4]
    assert len(result) == 2
    assert result.index[0] == pd.Timestamp("2024-01-01 10:00")
    assert result.index[1] == pd.Timestamp("2024-01-01 11:00")


def test_drop_duplicates_keeps_last():
    dates = pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:00"])
    df = pd.DataFrame({"Level": [1.5, 1.5], "note": ["first", "last"]}, index=dates)
    result = drop_duplicates_with_index(df, subset=["Level"], keep="last")[cite: 4]
    assert len(result) == 1
    assert result["note"].iloc[0] == "last"


def test_drop_duplicates_missing_column_raises_keyerror():
    df = pd.DataFrame({"Level": [1.0, 2.0]})
    with pytest.raises(KeyError):
        drop_duplicates_with_index(df, subset=["NonExistentColumn"])[cite: 4]


def test_drop_duplicates_empty_dataframe():
    df = pd.DataFrame(columns=["Level", "Temperature"])
    result = drop_duplicates_with_index(df)[cite: 4]
    assert result.empty


# ==========================================
# TESTS: resolve_duplicate_transducer_records
# ==========================================

def test_resolve_duplicates_drop_retains_replacement(overlapping_loggers_df):
    clean_df, summary = resolve_duplicate_transducer_records(
        overlapping_loggers_df,
        source_col="filename",
        action="drop",
        keep="last",
    )[cite: 4]

    assert len(summary) == 1[cite: 4]
    assert summary.iloc[0]["unique_timestamps"] == 3  # 12:00, 13:00, 14:00 overlap[cite: 4]

    # Verification: Overlapping timestamps must belong to logger_new
    overlap_period = clean_df.loc["2024-01-01 12:00":"2024-01-01 14:00"]
    assert (overlap_period["filename"] == "logger_new.csv").all()


def test_resolve_duplicates_flag_mode(overlapping_loggers_df):
    flagged_df, summary = resolve_duplicate_transducer_records(
        overlapping_loggers_df,
        source_col="filename",
        action="flag",
    )[cite: 4]

    assert len(flagged_df) == len(overlapping_loggers_df)[cite: 4]
    assert "is_duplicate_timestamp" in flagged_df.columns[cite: 4]
    assert flagged_df["is_duplicate_timestamp"].sum() == 6  # 3 pairs of overlap[cite: 4]


def test_resolve_duplicates_no_conflicts(clean_transducer_series):
    result_df, summary = resolve_duplicate_transducer_records(
        clean_transducer_series,
        source_col="filename",
    )[cite: 4]
    assert len(result_df) == len(clean_transducer_series)[cite: 4]
    assert summary.empty[cite: 4]


def test_resolve_duplicates_missing_datetime_raises_value_error():
    df_no_dt = pd.DataFrame({"Level": [1, 2, 3], "filename": ["a", "b", "c"]})
    with pytest.raises(ValueError):
        resolve_duplicate_transducer_records(df_no_dt)[cite: 4]


# ==========================================
# TESTS: detect_transducer_spikes
# ==========================================

@pytest.mark.parametrize(
    "param_name,expected_threshold",
    [
        ("Level", 0.5),
        ("Temperature", 1.0),
        ("specific_conductivity", 50.0),
    ],
)
def test_spike_default_thresholds(param_name, expected_threshold):
    assert DEFAULT_SPIKE_THRESHOLDS[param_name] == expected_threshold[cite: 4]


def test_detect_spikes_without_manual_filtering(spiky_water_level_df):
    clean_df, summary = detect_transducer_spikes(
        spiky_water_level_df,
        value_col="Level",
        threshold=1.0,
        action="drop",
        drop_near_manual_only=False,
    )[cite: 4]

    assert len(summary) == 2[cite: 4]
    assert len(clean_df) == 18[cite: 4]
    assert 14.5 not in clean_df["Level"].values
    assert 16.0 not in clean_df["Level"].values


def test_detect_spikes_correlated_to_manual_visit(spiky_water_level_df):
    # Field tape visit occurred right at 02:00 (matching the 14.5 spike)
    field_visits = [pd.Timestamp("2024-01-01 02:00:00")]

    clean_df, summary = detect_transducer_spikes(
        spiky_water_level_df,
        value_col="Level",
        threshold=1.0,
        manual_measurements=field_visits,
        manual_window="30min",
        action="drop",
        drop_near_manual_only=True,
    )[cite: 4]

    # Only the spike at 02:00 should drop; the spike at 03:45 should be retained
    assert len(clean_df) == 19[cite: 4]
    assert 14.5 not in clean_df["Level"].values
    assert 16.0 in clean_df["Level"].values[cite: 4]

    dropped_row = summary[summary["measured_value"] == 14.5].iloc[0]
    retained_row = summary[summary["measured_value"] == 16.0].iloc[0]
    assert dropped_row["dropped"] is True[cite: 4]
    assert dropped_row["near_manual_visit"] is True[cite: 4]
    assert retained_row["dropped"] is False[cite: 4]
    assert retained_row["near_manual_visit"] is False[cite: 4]


def test_detect_spikes_missing_value_column(clean_transducer_series):
    with pytest.raises(KeyError):
        detect_transducer_spikes(clean_transducer_series, value_col="InvalidCol")[cite: 4]


# ==========================================
# TESTS: detect_transducer_flatlines
# ==========================================

def test_detect_flatlines_exact():
    dates = pd.date_range("2024-01-01 00:00", periods=20, freq="1h")
    # 8 consecutive exact readings of 5.000 ft
    levels = [4.1, 4.2] + [5.0] * 8 + [4.5, 4.6, 4.7, 4.8, 4.9, 5.1, 5.2, 5.3, 5.4, 5.5]
    df = pd.DataFrame({"Level": levels}, index=dates)

    clean_df, summary = detect_transducer_flatlines(
        df,
        value_col="Level",
        min_consecutive=6,
        min_duration=None,
        tolerance=0.0,
        action="drop",
    )[cite: 4]

    assert len(summary) == 1[cite: 4]
    assert summary.iloc[0]["reading_count"] == 8[cite: 4]
    assert summary.iloc[0]["flatline_value"] == 5.0[cite: 4]
    assert len(clean_df) == 12[cite: 4]


def test_detect_flatlines_with_noise_tolerance():
    dates = pd.date_range("2024-01-01 00:00", periods=10, freq="1h")
    # Minor sensor electronic fluctuation within a 0.005 ft window
    levels = [10.0, 10.002, 10.001, 10.003, 10.002, 10.001, 10.004, 11.2, 11.5, 11.8]
    df = pd.DataFrame({"Level": levels}, index=dates)

    clean_df, summary = detect_transducer_flatlines(
        df,
        value_col="Level",
        min_consecutive=5,
        min_duration=None,
        tolerance=0.005,
        action="drop",
    )[cite: 4]

    assert len(summary) == 1[cite: 4]
    assert summary.iloc[0]["reading_count"] == 7[cite: 4]
    assert len(clean_df) == 3[cite: 4]


def test_detect_flatlines_broken_by_max_gap():
    # Constant reading across a large sampling hiatus (e.g., logger removed from well)
    dates = [
        pd.Timestamp("2024-01-01 01:00"),
        pd.Timestamp("2024-01-01 02:00"),
        pd.Timestamp("2024-01-01 03:00"),
        pd.Timestamp("2024-01-10 01:00"),  # 9-day gap
        pd.Timestamp("2024-01-10 02:00"),
    ]
    df = pd.DataFrame({"Level": [5.0, 5.0, 5.0, 5.0, 5.0]}, index=dates)

    # max_gap="2h" should partition the rows across the gap into two smaller runs (3 and 2)
    _, summary = detect_transducer_flatlines(
        df,
        value_col="Level",
        min_consecutive=4,
        min_duration=None,
        max_gap="2h",
        action="report",
    )[cite: 4]

    assert summary.empty[cite: 4]


def test_detect_flatlines_requires_criteria():
    df = pd.DataFrame({"Level": [1.0, 1.0, 1.0]}, index=pd.date_range("2024-01-01", periods=3))
    with pytest.raises(ValueError):
        detect_transducer_flatlines(
            df, value_col="Level", min_duration=None, min_consecutive=None
        )[cite: 4]
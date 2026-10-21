import logging
import pandas as pd
from typing import Iterable, Literal, Optional, Tuple, Union
import numpy as np

DEFAULT_SPIKE_THRESHOLDS = {
    "Level": 0.5,
    "Temperature": 1.0,
    "specific_conductivity": 50.0
}

# Module-level logger: handles everything automatically
logger = logging.getLogger(__name__)


def drop_duplicates_with_index(
    df: pd.DataFrame,
    subset: Optional[Iterable[str]] = ['Level', 'Temperature'],
    keep: Literal["first", "last", False] = "first",
    include_index: bool = True,
) -> pd.DataFrame:
    """Drops duplicate rows evaluated across specified columns and the index.

    Standard pandas `drop_duplicates` ignores the DataFrame index. This function
    binds the index (e.g., DatetimeIndex) into the duplicate check so that
    records are only considered duplicates if both their timestamp and measurement
    values are identical.

    Args:
        df (pd.DataFrame): Input DataFrame (typically with a DatetimeIndex).
        subset (iterable of str, optional): Column names to evaluate. If None,
            all columns in the DataFrame are evaluated alongside the index.
            Defaults to None.
        keep (str or False, optional): Which duplicate record to retain:
            * 'first': Keeps the first occurrence.
            * 'last': Keeps the last occurrence.
            * False: Drops all occurrences of repeating records.
            Defaults to 'first'.
        include_index (bool, optional): Whether to include the index in the
            duplicate evaluation. Defaults to True.

    Returns:
        pd.DataFrame: Cleaned DataFrame with repeating records removed.

    Raises:
        KeyError: If any column in `subset` is not present in `df`.
    """
    if df.empty:
        return df.copy()

    initial_count = len(df)
    temp_df = df.copy()
    temp_idx_cols = []

    # 1. Bind the index into columns for evaluation
    if include_index:
        if (
            isinstance(temp_df.index, pd.RangeIndex)
            and temp_df.index.step == 1
            and temp_df.index.start == 0
        ):
            logger.warning(
                "DataFrame has a default sequential RangeIndex (0, 1, 2, ...). "
                "Evaluating this index will prevent rows from matching as duplicates. "
                "Ensure your datetime column is set as the index first."
            )

        if isinstance(temp_df.index, pd.MultiIndex):
            for i, name in enumerate(temp_df.index.names):
                col_name = f"__idx_lvl_{i}_{name or 'temp'}__"
                temp_df[col_name] = temp_df.index.get_level_values(i)
                temp_idx_cols.append(col_name)
        else:
            col_name = f"__idx_{temp_df.index.name or 'temp'}__"
            temp_df[col_name] = temp_df.index
            temp_idx_cols.append(col_name)

    # 2. Determine evaluation columns
    if subset is not None:
        subset_cols = list(subset)
        missing = set(subset_cols) - set(df.columns)
        if missing:
            raise KeyError(f"Columns not found in DataFrame: {missing}")
        eval_cols = subset_cols + temp_idx_cols
    else:
        eval_cols = None 

    # 3. Drop exact duplicates
    clean_df = temp_df.drop_duplicates(subset=eval_cols, keep=keep)

    if temp_idx_cols:
        clean_df = clean_df.drop(columns=temp_idx_cols)

    dropped_count = initial_count - len(clean_df)

    if dropped_count > 0:
        logger.info(
            f"Dropped {dropped_count} identical repeating rows evaluated across "
            f"index and columns: {list(subset) if subset else 'all columns'}."
        )
    else:
        logger.info("No identical repeating records found.")

    return clean_df

def resolve_duplicate_transducer_records(
    df: pd.DataFrame,
    source_col: str = "filename",
    datetime_col: Optional[str] = None,
    round_freq: Optional[str] = "min",
    episode_gap_threshold: str = "1D",
    action: Literal["report", "flag", "drop"] = "drop",
    keep: Literal["first", "last", False] = "last",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Detects, logs, and resolves overlapping duplicate transducer records.

    Groups non-contiguous overlap periods into distinct episodes, identifies
    which loggers were involved in each episode, and resolves them based on
    deployment start dates.

    Args:
        df (pd.DataFrame): Transducer DataFrame (indexed or column).
        source_col (str, optional): Column name identifying the source file or
            logger. Defaults to 'filename'.
        datetime_col (str, optional): Name of the timestamp column. If None,
            checks index, then 'DateTime', then 'readingdate'. Defaults to None.
        round_freq (str, optional): Pandas offset alias to snap timestamps (e.g.,
            'min', '15min'). Defaults to 'min'.
        episode_gap_threshold (str, optional): Inactivity gap used to split
            overlaps into separate episodes (e.g., '1D', '12h'). Defaults to '1D'.
        action (str, optional): 'report', 'flag', or 'drop'. Defaults to 'drop'.
        keep (str or False, optional): 'last' (replacement logger), 'first'
            (outgoing logger), or False (drop all). Defaults to 'last'.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            * clean_df: Processed DataFrame.
            * summary_df: Table listing every distinct overlap episode.
    """
    data = df.copy()
    had_datetime_index = isinstance(data.index, pd.DatetimeIndex)

    # 1. Resolve timestamp series
    if datetime_col is not None:
        if datetime_col not in data.columns:
            raise KeyError(f"Column '{datetime_col}' not found in DataFrame.")
        ts_series = pd.to_datetime(data[datetime_col])
    elif had_datetime_index:
        ts_series = data.index.to_series()
    elif "DateTime" in data.columns:
        datetime_col = "DateTime"
        ts_series = pd.to_datetime(data["DateTime"])
    elif "readingdate" in data.columns:
        datetime_col = "readingdate"
        ts_series = pd.to_datetime(data["readingdate"])
    else:
        raise ValueError(
            "Could not identify datetime values. Provide `datetime_col` "
            "or ensure the DataFrame has a DatetimeIndex."
        )

    # 2. Align timestamps via rounding
    if round_freq:
        logger.info(
            f"Rounding timestamps to nearest '{round_freq}' for duplicate alignment."
        )
        ts_series = ts_series.dt.round(round_freq)

    data["_ts_temp"] = ts_series.values
    dup_mask = data["_ts_temp"].duplicated(keep=False)
    total_dup_rows = dup_mask.sum()

    summary_columns = [
        "episode",
        "overlap_start",
        "overlap_end",
        "total_rows_involved",
        "unique_timestamps",
        "sources_involved",
        "files_by_start_date",
    ]

    if total_dup_rows == 0:
        data.drop(columns=["_ts_temp"], inplace=True)
        if action == "flag":
            data["is_duplicate_timestamp"] = False
        logger.info("No duplicate timestamps detected.")
        return data, pd.DataFrame(columns=summary_columns)

    # 3. Determine overall file deployment order
    has_source = source_col in data.columns
    if has_source:
        file_start_dates = data.groupby(source_col)["_ts_temp"].min()
        data["_file_start"] = data[source_col].map(file_start_dates)
    else:
        logger.warning(
            f"Column '{source_col}' not found. Cannot determine deployment order; "
            "falling back to current row sequence."
        )
        data["_file_start"] = 0

    # 4. Cluster duplicate timestamps into distinct episodes
    dup_rows = data[dup_mask].copy()
    unique_dup_ts = dup_rows["_ts_temp"].drop_duplicates().sort_values()

    gap_delta = pd.to_timedelta(episode_gap_threshold)
    # New episode starts when the jump between duplicate timestamps exceeds threshold
    episode_ids = (unique_dup_ts.diff() > gap_delta).cumsum() + 1
    ts_to_episode = pd.Series(episode_ids.values, index=unique_dup_ts)
    dup_rows["_episode"] = dup_rows["_ts_temp"].map(ts_to_episode)

    # 5. Build multi-episode summary table
    episode_records = []
    for ep_id, group in dup_rows.groupby("_episode"):
        ep_sources = list(group[source_col].unique()) if has_source else []
        if has_source:
            ordered_files = file_start_dates.loc[ep_sources].sort_values()
            ep_file_order = [
                f"{fname} (started {start})"
                for fname, start in ordered_files.items()
            ]
        else:
            ep_file_order = []

        record = {
            "episode": ep_id,
            "overlap_start": group["_ts_temp"].min(),
            "overlap_end": group["_ts_temp"].max(),
            "total_rows_involved": len(group),
            "unique_timestamps": group["_ts_temp"].nunique(),
            "sources_involved": ep_sources,
            "files_by_start_date": ep_file_order,
        }
        episode_records.append(record)
        logger.warning(
            f"Episode {ep_id}: Overlap from {record['overlap_start']} to {record['overlap_end']} "
            f"({record['total_rows_involved']} rows, {record['unique_timestamps']} unique timestamps) "
            f"involving: {ep_sources}."
        )

    summary_df = pd.DataFrame(episode_records)

    # 6. Execute action
    if action == "flag":
        data["is_duplicate_timestamp"] = dup_mask
        data.drop(
            columns=["_ts_temp", "_file_start"], inplace=True, errors="ignore"
        )
        return data, summary_df

    elif action == "drop":
        # Sort so older logger is first, replacement logger is last
        data = data.sort_values(
            by=["_ts_temp", "_file_start"], ascending=[True, True]
        )
        data = data.drop_duplicates(subset=["_ts_temp"], keep=keep)

        rows_dropped = (
            total_dup_rows - len(unique_dup_ts)
            if keep in ("first", "last")
            else total_dup_rows
        )
        data.drop(
            columns=["_ts_temp", "_file_start"], inplace=True, errors="ignore"
        )

        if had_datetime_index:
            data = data.sort_index()
        elif datetime_col:
            data = data.sort_values(by=datetime_col)

        logger.info(
            f"Dropped {rows_dropped} rows across {len(summary_df)} overlap episode(s) using keep='{keep}'."
        )
        return data, summary_df

    data.drop(
        columns=["_ts_temp", "_file_start"], inplace=True, errors="ignore"
    )
    return data, summary_df

def detect_transducer_spikes(
    df: pd.DataFrame,
    value_col: str,
    datetime_col: Optional[str] = None,
    threshold: Optional[float] = None,
    param_type: Optional[str] = None,
    window: Union[int, str] = 5,
    manual_measurements: Optional[
        Union[pd.Index, pd.Series, Iterable[Union[str, pd.Timestamp]]]
    ] = None,
    manual_window: str = "2h",
    action: Literal["report", "flag", "drop"] = "drop",
    drop_near_manual_only: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Detects, logs, and resolves anomalous spikes in transducer data.

    Calculates local baseline variation using a centered rolling median.
    Points deviating from the median by more than `threshold` are identified
    as spikes. Cross-references spike timestamps against manual measurements
    (e.g., field tape visits passed via DataFrame index, Series, or list).

    Args:
        df (pd.DataFrame): Input time-series DataFrame.
        value_col (str): Column name containing the sensor measurement.
        datetime_col (str, optional): Name of the timestamp column. If None,
            checks index, then 'DateTime', then 'readingdate'. Defaults to None.
        threshold (float, optional): Absolute deviation threshold. If None,
            inferred from `param_type` or `value_col`. Defaults to None.
        param_type (str, optional): Key for default threshold lookup. Defaults to None.
        window (int or str, optional): Centered rolling window size. Defaults to 5.
        manual_measurements (Index, Series, or iterable, optional): Manual visit
            timestamps (such as `manual_df.index`). Defaults to None.
        manual_window (str, optional): Proximity window around manual measurements
            (e.g., '2h', '4h', or '1D' for same-day matching). Defaults to '2h'.
        action (str, optional): Strategy to apply ('report', 'flag', 'drop'). Defaults to 'drop'.
        drop_near_manual_only (bool, optional): If True and `action='drop'`, only
            drops spikes that occurred within `manual_window` of a manual measurement.
            All other spikes are preserved. Defaults to False.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: Processed DataFrame and summary table.
    """
    if value_col not in df.columns:
        raise KeyError(f"Target measurement column '{value_col}' not found.")

    data = df.copy()
    had_datetime_index = isinstance(data.index, pd.DatetimeIndex)

    # 1. Resolve timestamp series
    if datetime_col is not None:
        if datetime_col not in data.columns:
            raise KeyError(f"Column '{datetime_col}' not found in DataFrame.")
        ts_series = pd.to_datetime(data[datetime_col])
    elif had_datetime_index:
        ts_series = data.index.to_series()
    elif "DateTime" in data.columns:
        datetime_col = "DateTime"
        ts_series = pd.to_datetime(data["DateTime"])
    elif "readingdate" in data.columns:
        datetime_col = "readingdate"
        ts_series = pd.to_datetime(data["readingdate"])
    else:
        raise ValueError(
            "Could not detect datetime values. Specify `datetime_col` "
            "or set a DatetimeIndex on the DataFrame."
        )

    # 2. Determine threshold
    if threshold is None:
        lookup_key = (param_type or value_col).strip().lower()
        threshold = DEFAULT_SPIKE_THRESHOLDS.get(lookup_key)
        if threshold is None:
            raise ValueError(
                f"No default spike threshold found for '{lookup_key}'. "
                f"Available defaults: {list(DEFAULT_SPIKE_THRESHOLDS.keys())}. "
                "Please provide an explicit numeric `threshold`."
            )
        logger.info(
            f"Using default spike threshold of {threshold} for parameter '{lookup_key}'."
        )
    else:
        logger.info(f"Using user-defined spike threshold of {threshold}.")

    # 3. Calculate baseline and detect spikes
    data["_ts_temp"] = ts_series.values
    data = data.sort_values(by="_ts_temp")

    if isinstance(window, str):
        roll_series = data.set_index("_ts_temp")[value_col]
        rolling_median = (
            roll_series.rolling(window=window, center=True, min_periods=1)
            .median()
            .values
        )
    else:
        rolling_median = (
            data[value_col]
            .rolling(window=window, center=True, min_periods=1)
            .median()
            .values
        )

    deviations = data[value_col] - rolling_median
    spike_mask = (deviations.abs() > threshold).values
    total_spikes = int(spike_mask.sum())

    summary_cols = [
        "timestamp",
        "measured_value",
        "local_median",
        "deviation",
        "near_manual_visit",
        "nearest_manual_time",
        "time_to_manual",
        "dropped",
    ]

    if total_spikes == 0:
        logger.info(
            f"No spikes detected in column '{value_col}' using threshold {threshold}."
        )
        data.drop(columns=["_ts_temp"], inplace=True)
        if had_datetime_index:
            data = data.sort_index()
        elif datetime_col:
            data = data.sort_values(by=datetime_col)
        if action == "flag":
            data[f"is_spike_{value_col}"] = False
        return data, pd.DataFrame(columns=summary_cols)

    # 4. Parse manual measurements safely into a Series
    manual_series = None
    manual_delta_limit = None
    has_manual_data = False

    if manual_measurements is not None:
        parsed_manual = pd.Series(pd.to_datetime(manual_measurements)).dropna()
        if not parsed_manual.empty:
            manual_series = parsed_manual.sort_values().reset_index(drop=True)
            manual_delta_limit = pd.to_timedelta(manual_window)
            has_manual_data = True

    # 5. Position-based evaluation (immune to duplicate index labels)
    spike_positions = np.where(spike_mask)[0]
    near_manual_mask = np.zeros(len(data), dtype=bool)
    summary_records = []

    for pos in spike_positions:
        ts = data["_ts_temp"].iloc[pos]
        val = data[value_col].iloc[pos]
        med = rolling_median[pos]
        dev = val - med

        if has_manual_data:
            diffs = (manual_series - ts).abs()
            min_loc = diffs.idxmin()
            min_time_diff = diffs.iloc[min_loc]
            nearest_man_ts = manual_series.iloc[min_loc]
            near_manual = min_time_diff <= manual_delta_limit
            if near_manual:
                near_manual_mask[pos] = True
        else:
            near_manual = pd.NA
            nearest_man_ts = pd.NaT
            min_time_diff = pd.NaT

        # Determine if this individual spike will be dropped
        if action == "drop":
            will_drop = bool(near_manual) if drop_near_manual_only else True
        else:
            will_drop = False

        summary_records.append(
            {
                "timestamp": ts,
                "measured_value": val,
                "local_median": med,
                "deviation": dev,
                "near_manual_visit": near_manual,
                "nearest_manual_time": nearest_man_ts,
                "time_to_manual": min_time_diff,
                "dropped": will_drop,
            }
        )

    summary_df = pd.DataFrame(summary_records)
    if not has_manual_data:
        summary_df["time_to_manual"] = pd.Series(
            [pd.NaT] * len(summary_df), dtype="timedelta64[ns]"
        )

    # 6. Logging
    if has_manual_data:
        manual_correlated_count = int(near_manual_mask.sum())
        logger.warning(
            f"Detected {total_spikes} spike(s) in '{value_col}' exceeding threshold {threshold}. "
            f"({manual_correlated_count}/{total_spikes} occurred within {manual_window} of manual site visits)."
        )
    else:
        logger.warning(
            f"Detected {total_spikes} spike(s) in '{value_col}' exceeding threshold {threshold} "
            "(not evaluated against manual data)."
        )

    # 7. Execute requested action
    data.drop(columns=["_ts_temp"], inplace=True)

    if action == "flag":
        data[f"is_spike_{value_col}"] = spike_mask
        if has_manual_data:
            data[f"is_spike_near_manual_{value_col}"] = near_manual_mask

    elif action == "drop":
        if drop_near_manual_only:
            if not has_manual_data:
                logger.warning(
                    "`drop_near_manual_only` is True, but no manual measurements were provided. "
                    f"None of the {total_spikes} spikes were dropped."
                )
            else:
                dropped_count = int(near_manual_mask.sum())
                retained_count = total_spikes - dropped_count
                data = data[~near_manual_mask]
                logger.info(
                    f"Dropped {dropped_count} spike(s) occurring within {manual_window} of manual visits "
                    f"({retained_count} other spikes retained)."
                )
        else:
            data = data[~spike_mask]
            logger.info(
                f"Successfully dropped all {total_spikes} spike records from dataset."
            )

    # Restore chronological order
    if had_datetime_index:
        data = data.sort_index()
    elif datetime_col:
        data = data.sort_values(by=datetime_col)

    return data, summary_df

def detect_transducer_flatlines(
    df: pd.DataFrame,
    value_col: str,
    datetime_col: Optional[str] = None,
    min_duration: Optional[str] = "24h",
    min_consecutive: Optional[int] = None,
    tolerance: float = 0.0,
    round_digits: Optional[int] = None,
    max_gap: Optional[str] = None,
    action: Literal["report", "flag", "drop"] = "report",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Detects, logs, and resolves flatlining / frozen data in transducer records.

    Identifies periods where sensor readings remain constant or exhibit near-zero
    variation (e.g., sensor desiccation, unseated transducer, firmware freeze,
    or dead battery). Flatline episodes are grouped based on contiguous runs and
    evaluated against minimum time duration and/or consecutive observation count.

    Args:
        df (pd.DataFrame): Input time-series DataFrame, either indexed by datetime
            or containing a timestamp column.
        value_col (str): Column name of the sensor measurement to evaluate
            (e.g., 'measuredlevel', 'temperature').
        datetime_col (str, optional): Name of the timestamp column. If None,
            checks index, then 'DateTime', then 'readingdate'. Defaults to None.
        min_duration (str, optional): Minimum time duration to qualify as a flatline
            (e.g., '24h', '3D'). If None, only `min_consecutive` is evaluated.
            Defaults to '24h'.
        min_consecutive (int, optional): Minimum number of consecutive readings to
            qualify as a flatline. If None, only `min_duration` is evaluated.
            Defaults to None.
        tolerance (float, optional): Maximum allowable variation (max - min) within
            a run to still be considered flat. Use 0.0 for strictly identical values,
            or a small float (e.g., 0.001) for sensor electronic noise. Defaults to 0.0.
        round_digits (int, optional): Optional decimal precision to round values to
            before evaluating runs. Defaults to None.
        max_gap (str, optional): Maximum allowable time gap between consecutive
            readings (e.g., '2h'). Gaps exceeding this threshold break the run,
            preventing multi-week logging interruptions from being counted as flatlines.
            If None, time gaps are not used to break runs. Defaults to None.
        action (str, optional): Action to perform on detected flatline readings:
            * 'report': Leaves DataFrame untouched and returns episode summary.
            * 'flag': Adds boolean column 'is_flatline_{value_col}'.
            * 'drop': Removes flatline records from returned DataFrame.
            Defaults to 'report'.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            * clean_df (pd.DataFrame): Processed DataFrame (modified or unmodified).
            * summary_df (pd.DataFrame): Table summarizing each flatline episode
              (episode number, start, end, duration, count, value, and variation).

    Raises:
        KeyError: If `value_col` or specified `datetime_col` is not found.
        ValueError: If neither `min_duration` nor `min_consecutive` is specified.
    """
    if value_col not in df.columns:
        raise KeyError(f"Target column '{value_col}' not found in DataFrame.")

    if min_duration is None and min_consecutive is None:
        raise ValueError(
            "At least one of `min_duration` or `min_consecutive` must be specified."
        )

    data = df.copy()
    had_datetime_index = isinstance(data.index, pd.DatetimeIndex)

    # 1. Resolve timestamp series
    if datetime_col is not None:
        if datetime_col not in data.columns:
            raise KeyError(f"Column '{datetime_col}' not found in DataFrame.")
        ts_series = pd.to_datetime(data[datetime_col])
    elif had_datetime_index:
        ts_series = data.index.to_series()
    elif "DateTime" in data.columns:
        datetime_col = "DateTime"
        ts_series = pd.to_datetime(data["DateTime"])
    elif "readingdate" in data.columns:
        datetime_col = "readingdate"
        ts_series = pd.to_datetime(data["readingdate"])
    else:
        raise ValueError(
            "Could not detect datetime values. Specify `datetime_col` "
            "or ensure the DataFrame has a DatetimeIndex."
        )

    summary_columns = [
        "episode",
        "start",
        "end",
        "duration",
        "reading_count",
        "flatline_value",
        "variation",
    ]

    if data.empty:
        return data, pd.DataFrame(columns=summary_columns)

    # 2. Sort chronologically for contiguous run detection
    data["_ts_temp"] = ts_series.values
    data = data.sort_values(by="_ts_temp")

    vals = data[value_col].to_numpy()
    if round_digits is not None:
        vals = np.round(vals, decimals=round_digits)
    times = pd.to_datetime(data["_ts_temp"]).to_numpy()

    max_gap_td = (
        pd.to_timedelta(max_gap).to_numpy() if max_gap is not None else None
    )

    # 3. Partition series into contiguous runs
    n = len(vals)
    run_ids = np.zeros(n, dtype=int)

    if tolerance == 0.0:
        # Fast vectorized path for exact repeats
        s_vals = pd.Series(vals)
        val_break = s_vals != s_vals.shift(1)
        if max_gap_td is not None:
            time_break = pd.Series(times).diff() > max_gap_td
            run_break = val_break | time_break
        else:
            run_break = val_break
        run_ids = run_break.cumsum().to_numpy()
    else:
        # Tolerance path: bounded variation (max - min <= tolerance)
        curr_id = 0
        r_min = vals[0]
        r_max = vals[0]
        t_prev = times[0]

        for i in range(1, n):
            v = vals[i]
            t = times[i]

            time_exceeded = False
            if max_gap_td is not None and (t - t_prev) > max_gap_td:
                time_exceeded = True
            t_prev = t

            new_min = min(r_min, v)
            new_max = max(r_max, v)

            if not time_exceeded and (new_max - new_min) <= tolerance:
                r_min = new_min
                r_max = new_max
            else:
                curr_id += 1
                r_min = v
                r_max = v
            run_ids[i] = curr_id

    data["_run_id"] = run_ids

    # 4. Aggregate run statistics
    run_stats = (
        data.groupby("_run_id")
        .agg(
            start=("_ts_temp", "min"),
            end=("_ts_temp", "max"),
            reading_count=(value_col, "count"),
            flatline_value=(value_col, "mean"),
            val_min=(value_col, "min"),
            val_max=(value_col, "max"),
        )
        .reset_index()
    )

    run_stats["duration"] = run_stats["end"] - run_stats["start"]
    run_stats["variation"] = (
        run_stats["val_max"] - run_stats["val_min"]
    ).round(6)

    # 5. Filter runs meeting flatline criteria
    flat_mask = pd.Series(True, index=run_stats.index)

    if min_consecutive is not None:
        flat_mask &= run_stats["reading_count"] >= min_consecutive
    if min_duration is not None:
        duration_threshold = pd.to_timedelta(min_duration)
        flat_mask &= run_stats["duration"] >= duration_threshold

    flagged_runs = run_stats[flat_mask].copy().reset_index(drop=True)

    if flagged_runs.empty:
        logger.info(
            f"No flatline episodes detected in '{value_col}' "
            f"(min_duration={min_duration}, min_consecutive={min_consecutive}, tolerance={tolerance})."
        )
        data.drop(columns=["_ts_temp", "_run_id"], inplace=True)
        if had_datetime_index:
            data = data.sort_index()
        elif datetime_col:
            data = data.sort_values(by=datetime_col)
        if action == "flag":
            data[f"is_flatline_{value_col}"] = False
        return data, pd.DataFrame(columns=summary_columns)

    flagged_runs.index.name = "episode"
    flagged_runs = flagged_runs.reset_index()
    flagged_runs["episode"] += 1

    summary_df = flagged_runs[summary_columns]

    # Map flatline flags back to individual rows
    flatline_run_ids = set(run_stats.loc[flat_mask, "_run_id"])
    row_is_flatline = data["_run_id"].isin(flatline_run_ids).to_numpy()
    total_flat_rows = int(row_is_flatline.sum())

    logger.warning(
        f"Detected {len(summary_df)} flatline episode(s) ({total_flat_rows} total rows) "
        f"in '{value_col}' using tolerance={tolerance}."
    )

    # 6. Execute action
    data.drop(columns=["_ts_temp", "_run_id"], inplace=True)

    if action == "flag":
        data[f"is_flatline_{value_col}"] = row_is_flatline
        if had_datetime_index:
            data = data.sort_index()
        elif datetime_col:
            data = data.sort_values(by=datetime_col)
        return data, summary_df

    elif action == "drop":
        data = data[~row_is_flatline]
        if had_datetime_index:
            data = data.sort_index()
        elif datetime_col:
            data = data.sort_values(by=datetime_col)
        logger.info(
            f"Successfully dropped {total_flat_rows} flatline records from dataset."
        )
        return data, summary_df

    # action == 'report'
    if had_datetime_index:
        data = data.sort_index()
    elif datetime_col:
        data = data.sort_values(by=datetime_col)
    return data, summary_df



import logging
import pandas as pd
from typing import Iterable, Literal, Optional, Tuple, Union
import numpy as np

DEFAULT_SPIKE_THRESHOLDS = {
    "level": 0.5,
    "temperature": 1.0,
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

def jump_matching(old_data, new_data, old_value='measuredlevel', new_value="Level"):
    '''Finds value to correct major jumps between old dataset and new dataset by finding the most 
    recent old_value in the old_data and the oldest new_value in the new_data and returning
    the difference between the two values. This is essentially a specific case of jumpfix, where
    we are only trying to fix a jump where two separate records will meet'''
    old_value = old_data.loc[old_data.index.max(), old_value]
    new_value = new_data.loc[new_data.index.max(), new_value]
    add_value = (old_value-new_value).round(3)
    return(add_value)

def drop_by_value_and_daterange(df, start_date, end_date, drop_value, drop_type):
    """Drops records during a set date range that are either above or below a given drop_value
    Useful for cleaning duplicates after examining on a plot.

    Args:
    df (Pandas dataframe): Pandas dataframe with unprocessed transducer data
    start_date (timestamp): Start date range for dropping data
    end_date (timestamp): End date range for dropping data
    drop_value (int): Value above or below which all values should be dropped within given date range
    drop_type (str): GT or LT to indicate whether values greater than or less than drop_value should be dropped

    Returns:
        Pandas dataframe
    """
    if drop_type =='LT':
        df_clean = df[~((df.index>=start_date) & (df.index<=end_date) & (df.Level<drop_value))]
    elif drop_type == 'GT':
        df_clean = df[~((df.index>=start_date) & (df.index<=end_date) & (df.Level>drop_value))]
    else: 
        print('Drop type incorrect')
    return(df_clean)

def linear_drift_correction(df: pd.DataFrame, 
                            column: str, 
                            start_date: pd.Timestamp, 
                            end_date: pd.Timestamp,
                            subtract: bool):
    """
    Correct a linear drift in a DataFrame column between two dates by calculating the offset
    between the start date and the previous day, and the end date and the next day and then
    correcting the value of the given column using a linear function.

    Parameters:
        df (pd.DataFrame): DataFrame with a DatetimeIndex.
        column (str): Column name to apply the correction to; data must be numeric.
        start_date (pd.Timestamp): Start of the affected section.
        end_date (pd.Timestamp): End of the affected section (inclusive).

    Returns:
        pd.DataFrame: A new DataFrame with the correction applied to the specified column.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")

    # Copy to avoid modifying the original
    corrected_df = df.copy()
    ts = corrected_df[column]

    # Ensure dates are in the index
    if start_date not in ts.index or end_date not in ts.index:
        raise ValueError("Start and end dates must be in the time series index.")
    
    try:
        before_start = ts.index[ts.index.get_loc(start_date) - 1]
        after_end = ts.index[ts.index.get_loc(end_date) + 1]
    except IndexError:
        raise IndexError("Start or end date is at the edge of the series; can't compare with neighbors.")

    # Calculate offsets
    offset_start = ts.loc[start_date] - ts.loc[before_start]
    offset_end = ts.loc[end_date] - ts.loc[after_end]

    # Create correction vector
    affected_range = ts.loc[start_date:end_date]
    n_points = len(affected_range)
    correction = np.linspace(offset_start, offset_end, n_points)

    # Apply correction
    if subtract == True:
        corrected_df.loc[start_date:end_date, column] -= correction
    else:
        corrected_df.loc[start_date:end_date, column] += correction

    return corrected_df

def drop_reading_after_pumping(manual_data, transducer_data, hours_to_drop, phrases=["pump", "plung"]):
    '''
    manual_data: should be data pulled from database with index set on reading date and notes field
    transducer_data: should be data from combined transducers; does not need to be cleaned but index on timestamp
    hours_to_drop: number of records after the pumping that should be dropped (2 would equal the two readings after pumping)
    phrases: phrases to search for notes to identify pumping events
    '''
    pattern = "|".join(phrases)
    pump_dates = list(manual_data.index[manual_data['notes'].str.contains(pattern, case=False, na=False)].round('h'))
    if len(pump_dates)>0:
        hours_to_drop = hours_to_drop
        after_pump_dates = []
        # Loop over each timestamp and create new timestamps for 1 to x hours later
        for ts in pump_dates:
            # Add 1 to x hours to the timestamp and append to the list
            new_timestamps = [ts + pd.Timedelta(hours=i) for i in range(1, hours_to_drop + 1)]
            after_pump_dates.extend([ts.round('h') for ts in new_timestamps])
        new_transducer_data = transducer_data[~transducer_data.index.isin(after_pump_dates)]
        logging.info(f"Dropping {len(transducer_data) - len(new_transducer_data)} records total due to pumping")
        return(new_transducer_data)
    else:
        print("No pumping recorded")
        return(transducer_data)

def detect_sectional_offsets_indexed(
    df1, df2, value_col1, value_col2,
    freq='h', max_lag=24, window_size='7D'
):
    """
    Evaluates time offsets between two time series data frames ((datetime-indexed) in
    rolling sections. Returns the best lag with the best offset for each time window.

    Parameters:
    - df1, df2: DataFrames with datetime index.
    - value_col1: name of the column with numerical values to compare for df1
    - value__col2: name of the column with numerical values to compare for df2
    - freq: resampling frequency (e.g., 'h' for hourly).
    - max_lag: maximum lag (in units of freq) to test.
    - window_size: time window for sectional comparison (e.g., '7D' or '12H').

    Returns:
    - DataFrame with lag information per window.
    """

    # Resample both series to ensure regular intervals
    s1 = df1[value_col1].resample(freq).mean()
    s2 = df2[value_col2].resample(freq).mean()

    # Align both series to ensure same timestamps
    s1, s2 = s1.align(s2, join='inner')
    s1 = s1.ffill()
    s2 = s2.ffill()

    # Create window start times
    window_starts = pd.date_range(s1.index.min(), s1.index.max(), freq=window_size)
    results = []

    for start in window_starts:
        end = start + pd.to_timedelta(window_size)
        seg1 = s1[start:end]
        seg2 = s2[start:end]

        if len(seg1) < max_lag * 2 or len(seg2) < max_lag * 2:
            continue  # Skip short or empty windows

        lags = np.arange(-max_lag, max_lag + 1)
        correlations = [seg1.corr(seg2.shift(lag)) for lag in lags]

        if all(pd.isna(correlations)):
            continue

        best_lag = lags[np.nanargmax(correlations)]
        best_corr = np.nanmax(correlations)

        results.append({
            'window_start': start,
            'best_lag': best_lag,
            'correlation': best_corr
        })

    result_df = pd.DataFrame(results)

    return result_df

def plot_sectional_lags_plotly(corr_check, height=400):
    """
    Plots the results of the detect_sectional_offsets_indexed function,
    showing the best lag for each timeperiod
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=corr_check['window_start'],
        y=corr_check['best_lag'],
        mode='lines+markers',
        name='Best Lag',
        line=dict(color='royalblue'),
        marker=dict(size=6)
    ))

    # Add zero-lag reference line
    fig.add_trace(go.Scatter(
        x=[corr_check['window_start'].min(), corr_check['window_start'].max()],
        y=[0, 0],
        mode='lines',
        name='Zero Lag',
        line=dict(color='gray', dash='dash')
    ))

    fig.update_layout(
        title='Sectional Time Lag Detection',
        xaxis_title='Window Start Time',
        yaxis_title=f'Best Time Lag',
        template='plotly_white',
        hovermode='x unified',
        height=height
    )

    fig.show()

# from loader

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


import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from datetime import datetime


@dataclass
class DriftFeatures:
    """Data class to store drift calculation features for better type hints and organization"""
    t_beg: datetime
    man_beg: datetime
    t_end: datetime
    man_end: datetime
    slope_man: float
    slope_trans: float
    intercept: float
    slope: float
    first_meas: float
    last_meas: float
    first_trans: float
    last_trans: float
    drift: float


class Drifting:
    """Remove transducer drift from nonvented transducer data.

    This class implements drift correction by comparing manual measurements with
    transducer data and calculating necessary adjustments.
    """

    def __init__(
            self,
            manual_df: pd.DataFrame,
            transducer_df: pd.DataFrame,
            drifting_field: str = 'corrwl',
            man_field: str = 'measureddtw',
            daybuffer: int = 3,
            output_field: str = 'waterelevation',
            trim_end: bool = False,
            well_id: Optional[int] = None,
            engine: Optional[object] = None
    ):
        """Initialize the Drifting correction class.

        Args:
            manual_df: DataFrame containing manual measurements
            transducer_df: DataFrame containing transducer data
            drifting_field: Column name in transducer_df containing data to correct
            man_field: Column name in manual_df containing manual measurements
            daybuffer: Number of days to search for readings
            output_field: Name for the corrected output column
            trim_end: Whether to remove jumps from data breakpoints
            well_id: Unique identifier for the well
            engine: Database connection engine
        """
        self.config = {
            'daybuffer': daybuffer,
            'drifting_field': drifting_field,
            'man_field': man_field,
            'output_field': output_field,
            'trim_end': trim_end,
            'well_id': well_id,
            'engine': engine
        }

        # Initialize measurement data
        self._init_dataframes(manual_df, transducer_df)

        # Initialize calculation storage
        self.breakpoints: List[datetime] = []
        self.bracketedwls: Dict[int, pd.DataFrame] = {}
        self.drift_features: Dict[int, DriftFeatures] = {}

        # Results storage
        self.wellbarofixed = pd.DataFrame()
        self.drift_sum_table = pd.DataFrame()
        self.max_drift: float = 0.0

    def _init_dataframes(self, manual_df: pd.DataFrame, transducer_df: pd.DataFrame) -> None:
        """Prepare input DataFrames by sorting and adding Julian dates."""
        self.manual_df = self._prepare_df(manual_df)
        self.transducer_df = self._prepare_df(transducer_df)

    @staticmethod
    def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
        """Sort DataFrame by date index and add Julian dates."""
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df['julian'] = df.index.to_julian_date()
        return df

    def process_drift(self) -> Tuple[pd.DataFrame, pd.DataFrame, float]:
        """Process drift correction for the entire dataset.

        Returns:
            Tuple containing:
            - DataFrame with corrected water levels
            - DataFrame summarizing drift corrections
            - Maximum drift value
        """
        self._calculate_breakpoints()

        for i in range(len(self.breakpoints) - 1):
            segment = self._process_segment(i)
            if segment is not None:
                self.bracketedwls[i] = segment

        self._finalize_results()
        return self.wellbarofixed, self.drift_sum_table, self.max_drift

    def _process_segment(self, segment_idx: int) -> Optional[pd.DataFrame]:
        """Process a single segment between breakpoints."""
        start, end = self.breakpoints[segment_idx], self.breakpoints[segment_idx + 1]
        segment = self._get_segment_data(start, end)

        if segment.empty:
            return None

        if self.config['trim_end']:
            segment = self._clean_segment_ends(segment)

        self._calculate_drift_correction(segment_idx, segment)
        return segment

    def _calculate_breakpoints(self) -> None:
        """Calculate the breakpoints for drift correction segments.

        This method identifies points where manual measurements align with transducer data,
        creating segments for drift correction. It handles:
        - Missing or invalid data
        - Time alignment between manual and transducer measurements
        - Data range validation
        - Edge cases at the start and end of the time series

        The method updates self.breakpoints with a sorted list of datetime objects
        representing the start/end points of drift correction segments.

        Raises:
            ValueError: If no valid breakpoints can be established
            ValueError: If there's insufficient overlap between manual and transducer data
        """
        # Get valid transducer readings
        valid_transducer = self.transducer_df.dropna(subset=[self.config['drifting_field']]).sort_index()

        if valid_transducer.empty:
            raise ValueError("No valid transducer readings found")

        # Get valid manual measurements
        valid_manual = (self.manual_df
                        .dropna(subset=[self.config['man_field']])
                        .sort_index())

        if valid_manual.empty:
            raise ValueError("No valid manual measurements found")

        # Initialize breakpoints list
        breakpoints = []

        # Calculate the buffer window
        buffer_window = pd.Timedelta(days=self.config['daybuffer'])

        # Get the overall date range
        transducer_start = valid_transducer.first_valid_index()
        transducer_end = valid_transducer.last_valid_index()

        # Filter manual measurements to those within the transducer data range
        # (plus buffer window)
        valid_manual = valid_manual[
            (valid_manual.index >= transducer_start - buffer_window) &
            (valid_manual.index <= transducer_end + buffer_window)
            ]

        if valid_manual.empty:
            raise ValueError(
                "No manual measurements within the timeframe of transducer readings "
                f"(including {self.config['daybuffer']} day buffer)"
            )

        # Add first transducer reading if it precedes first manual measurement
        if valid_manual.first_valid_index() > transducer_start:
            breakpoints.append(transducer_start)

        # Add manual measurements as breakpoints
        manual_breakpoints = []
        for manual_date in valid_manual.index:
            # Find closest transducer reading within buffer window
            window_start = manual_date - buffer_window
            window_end = manual_date + buffer_window

            window_readings = valid_transducer[
                (valid_transducer.index >= window_start) &
                (valid_transducer.index <= window_end)
                ]

            if not window_readings.empty:
                # Find closest transducer reading to manual measurement
                closest_idx = (window_readings.index - manual_date).abs().argmin()
                closest_date = window_readings.index[closest_idx]

                manual_breakpoints.append({
                    'date': manual_date,
                    'closest_transducer': closest_date,
                    'time_diff': abs(closest_date - manual_date)
                })

        # Sort and filter manual breakpoints
        if manual_breakpoints:
            # Sort by date
            manual_breakpoints.sort(key=lambda x: x['date'])

            # Filter out breakpoints that are too close together
            filtered_breakpoints = []
            last_bp = None

            for bp in manual_breakpoints:
                if (last_bp is None or
                        bp['date'] - last_bp['date'] > buffer_window):
                    filtered_breakpoints.append(bp)
                    last_bp = bp

            # Add filtered manual measurement dates to breakpoints
            breakpoints.extend(bp['date'] for bp in filtered_breakpoints)

        # Add last transducer reading if it follows last manual measurement
        if valid_manual.last_valid_index() < transducer_end:
            breakpoints.append(transducer_end)

        # Remove duplicates and sort
        breakpoints = sorted(set(breakpoints))

        # Validate we have enough breakpoints for at least one segment
        if len(breakpoints) < 2:
            raise ValueError(
                "Insufficient breakpoints to establish correction segments. "
                "Need at least two breakpoints (start and end)"
            )

        # Store the calculated breakpoints
        self.breakpoints = breakpoints

        # Log summary of breakpoints if logger is configured
        if hasattr(self, 'logger'):
            self.logger.info(f"Calculated {len(breakpoints)} breakpoints")
            self.logger.debug(f"Breakpoint dates: {breakpoints}")

        # Store metadata about breakpoints for later analysis
        self._breakpoint_metadata = {
            'total_segments': len(breakpoints) - 1,
            'start_date': breakpoints[0],
            'end_date': breakpoints[-1],
            'avg_segment_length': (breakpoints[-1] - breakpoints[0]) / (len(breakpoints) - 1)
        }

    def get_breakpoint_statistics(self) -> dict:
        """Return statistics about the calculated breakpoints.

        Returns:
            dict: Dictionary containing:
                - total_segments: Number of segments
                - start_date: First breakpoint date
                - end_date: Last breakpoint date
                - avg_segment_length: Average time between breakpoints
                - breakpoints: List of all breakpoint dates
        """
        if not hasattr(self, '_breakpoint_metadata'):
            raise RuntimeError("Breakpoints have not been calculated yet")

        stats = self._breakpoint_metadata.copy()
        stats['breakpoints'] = self.breakpoints
        return stats

    def _calculate_drift_correction(self, segment_idx: int, segment: pd.DataFrame) -> None:
        """Calculate and apply drift correction to a segment."""
        slope, intercept = self._calculate_correction_params(segment_idx, segment)

        date_change = segment['julian'] - segment['julian'].iloc[0]
        segment['driftcorrection'] = date_change * slope
        segment['driftcorrwoffset'] = segment['driftcorrection'] + intercept
        segment[self.config['output_field']] = (
                segment[self.config['drifting_field']] - segment['driftcorrwoffset']
        )

    def _clean_segment_ends(self, segment: pd.DataFrame) -> pd.DataFrame:
        """Remove jumps from segment endpoints exceeding threshold."""
        # Implementation of dataendclean function would go here
        return segment

    def _finalize_results(self) -> None:
        """Combine all processed segments and calculate final statistics."""
        if self.bracketedwls:
            self.wellbarofixed = pd.concat(self.bracketedwls.values(), sort=True)
            self.wellbarofixed = self.wellbarofixed.sort_index()

            self.drift_sum_table = pd.DataFrame.from_dict(
                self.drift_features, orient='index'
            )
            self.max_drift = self.drift_sum_table['drift'].abs().max()

    @staticmethod
    def format_value(value: Optional[float], format_spec: str) -> str:
        """Format numeric values with consistent handling of None/NA."""
        if pd.isna(value):
            return 'No Data'
        return f"{value:{format_spec}}"
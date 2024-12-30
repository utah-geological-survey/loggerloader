import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from loggerloader.drifting import Drifting, DriftFeatures


class TestDrifting(unittest.TestCase):
    def setUp(self):
        """Set up test data that will be used across multiple tests."""
        # Create sample manual measurements
        self.manual_data = {
            'datetime': pd.date_range(start='2023-01-01', periods=3, freq='M'),
            'measureddtw': [10.0, 11.0, 12.0]
        }
        self.manual_df = pd.DataFrame(self.manual_data)
        self.manual_df.set_index('datetime', inplace=True)

        # Create sample transducer data with some drift
        self.transducer_data = {
            'datetime': pd.date_range(start='2023-01-01', periods=90, freq='D'),
            'corrwl': np.linspace(10.0, 13.0, 90)  # Linear drift from 10 to 13
        }
        self.transducer_df = pd.DataFrame(self.transducer_data)
        self.transducer_df.set_index('datetime', inplace=True)

        # Initialize Drifting instance with test data
        self.drifting = Drifting(
            manual_df=self.manual_df,
            transducer_df=self.transducer_df,
            drifting_field='corrwl',
            man_field='measureddtw',
            daybuffer=3
        )

    def test_initialization(self):
        """Test proper initialization of the Drifting class."""
        self.assertEqual(self.drifting.config['daybuffer'], 3)
        self.assertEqual(self.drifting.config['drifting_field'], 'corrwl')
        self.assertEqual(self.drifting.config['man_field'], 'measureddtw')
        self.assertTrue(isinstance(self.drifting.manual_df, pd.DataFrame))
        self.assertTrue(isinstance(self.drifting.transducer_df, pd.DataFrame))
        self.assertTrue('julian' in self.drifting.manual_df.columns)
        self.assertTrue('julian' in self.drifting.transducer_df.columns)

    def test_prepare_df(self):
        """Test the DataFrame preparation method."""
        test_data = pd.DataFrame({
            'datetime': ['2023-01-01', '2023-01-02'],
            'value': [1.0, 2.0]
        })
        test_data.set_index('datetime', inplace=True)

        prepared_df = self.drifting._prepare_df(test_data)

        self.assertTrue(isinstance(prepared_df.index, pd.DatetimeIndex))
        self.assertTrue('julian' in prepared_df.columns)
        self.assertTrue(prepared_df.index.is_monotonic_increasing)

    def test_calculate_breakpoints(self):
        """Test breakpoint calculation."""
        self.drifting._calculate_breakpoints()

        # Should have breakpoints for each manual measurement
        self.assertEqual(len(self.drifting.breakpoints), 3)

        # Breakpoints should be datetime objects
        for bp in self.drifting.breakpoints:
            self.assertTrue(isinstance(bp, (pd.Timestamp, datetime)))

        # Breakpoints should be sorted
        self.assertTrue(all(self.drifting.breakpoints[i] <= self.drifting.breakpoints[i + 1]
                            for i in range(len(self.drifting.breakpoints) - 1)))

    def test_process_segment(self):
        """Test processing of individual data segments."""
        self.drifting._calculate_breakpoints()
        segment = self.drifting._process_segment(0)  # Process first segment

        self.assertIsNotNone(segment)
        self.assertTrue(isinstance(segment, pd.DataFrame))
        self.assertTrue(self.drifting.config['output_field'] in segment.columns)
        self.assertTrue('driftcorrection' in segment.columns)

    def test_drift_correction(self):
        """Test that drift correction produces expected results."""
        # Process the entire dataset
        corrected_df, summary_df, max_drift = self.drifting.process_drift()

        # Check basic properties of the output
        self.assertTrue(isinstance(corrected_df, pd.DataFrame))
        self.assertTrue(isinstance(summary_df, pd.DataFrame))
        self.assertTrue(isinstance(max_drift, float))

        # Check that correction was applied
        self.assertTrue(self.drifting.config['output_field'] in corrected_df.columns)

        # Check that drift was actually removed (values should be closer to manual measurements)
        manual_times = self.manual_df.index
        for time in manual_times:
            if time in corrected_df.index:
                corrected_value = corrected_df.loc[time, self.drifting.config['output_field']]
                original_value = self.transducer_df.loc[time, 'corrwl']
                manual_value = self.manual_df.loc[time, 'measureddtw']

                # Corrected value should be closer to manual value than original
                self.assertLess(abs(corrected_value - manual_value),
                                abs(original_value - manual_value))

    def test_empty_data_handling(self):
        """Test handling of empty or missing data."""
        empty_df = pd.DataFrame()

        # Test with empty manual measurements
        with self.assertRaises(Exception):  # Should raise an appropriate exception
            Drifting(empty_df, self.transducer_df)

        # Test with empty transducer data
        with self.assertRaises(Exception):  # Should raise an appropriate exception
            Drifting(self.manual_df, empty_df)

    def test_invalid_column_names(self):
        """Test handling of invalid column specifications."""
        with self.assertRaises(KeyError):
            Drifting(
                self.manual_df,
                self.transducer_df,
                drifting_field='nonexistent_column'
            )

    def test_date_misalignment(self):
        """Test handling of manual and transducer data with non-overlapping dates."""
        future_manual_data = {
            'datetime': pd.date_range(start='2024-01-01', periods=3, freq='M'),
            'measureddtw': [10.0, 11.0, 12.0]
        }
        future_manual_df = pd.DataFrame(future_manual_data)
        future_manual_df.set_index('datetime', inplace=True)

        drifting = Drifting(future_manual_df, self.transducer_df)
        corrected_df, summary_df, max_drift = drifting.process_drift()

        # Should handle this case gracefully
        self.assertTrue(corrected_df.empty)

    def test_extreme_values(self):
        """Test handling of extreme values in the data."""
        # Create data with extreme values
        extreme_manual_data = self.manual_data.copy()
        extreme_manual_df = pd.DataFrame(extreme_manual_data)
        extreme_manual_df['measureddtw'] = [1e6, -1e6, 0]
        extreme_manual_df.set_index('datetime', inplace=True)

        drifting = Drifting(extreme_manual_df, self.transducer_df)
        corrected_df, summary_df, max_drift = drifting.process_drift()

        # Should handle extreme values without numerical issues
        self.assertFalse(np.any(np.isinf(corrected_df[drifting.config['output_field']])))
        self.assertFalse(np.any(np.isnan(corrected_df[drifting.config['output_field']])))

    def test_trim_end_functionality(self):
        """Test the trim_end functionality."""
        # Create data with jumps at the endpoints
        jumpy_data = self.transducer_data.copy()
        jumpy_df = pd.DataFrame(jumpy_data)
        jumpy_df.iloc[0, jumpy_df.columns.get_loc('corrwl')] += 5  # Add jump at start
        jumpy_df.iloc[-1, jumpy_df.columns.get_loc('corrwl')] += 5  # Add jump at end
        jumpy_df.set_index('datetime', inplace=True)

        # Test with trim_end=True
        drifting_trim = Drifting(
            self.manual_df,
            jumpy_df,
            trim_end=True
        )
        corrected_trim_df, _, _ = drifting_trim.process_drift()

        # Test with trim_end=False
        drifting_no_trim = Drifting(
            self.manual_df,
            jumpy_df,
            trim_end=False
        )
        corrected_no_trim_df, _, _ = drifting_no_trim.process_drift()

        # Results should be different when trim_end is enabled
        self.assertFalse(corrected_trim_df.equals(corrected_no_trim_df))


if __name__ == '__main__':
    unittest.main()
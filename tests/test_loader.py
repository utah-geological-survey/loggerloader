import pytest
import pandas as pd
import numpy as np
from datetime import datetime

# Adjust the import based on your exact structure
try:
    from src.loggerloader.loader import jumpfix, Drifting, dataendclean
except ModuleNotFoundError:
    # Fallback if running standalone
    from loader import jumpfix, Drifting, dataendclean

# ==========================================
# FIXTURES: Reusable Mock Data
# ==========================================

@pytest.fixture
def normal_data():
    dates = pd.date_range("2024-01-01", periods=10)
    return pd.DataFrame(
        {"value": [1.0, 1.1, 1.2, 1.15, 1.25, 1.3, 1.35, 1.4, 1.45, 1.5]},
        index=dates,
    )

@pytest.fixture
def jump_data():
    dates = pd.date_range("2024-01-01", periods=10)
    return pd.DataFrame(
        {"value": [1.0, 1.1, 5.1, 5.2, 5.3, 8.3, 8.4, 8.5, 8.6, 8.7]}, index=dates
    )

@pytest.fixture
def nan_data():
    dates = pd.date_range("2024-01-01", periods=10)
    return pd.DataFrame(
        {"value": [1.0, np.nan, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9]},
        index=dates,
    )

@pytest.fixture
def manual_df():
    """Mock manual field measurements (e.g., e-tape readings)"""
    dates = pd.date_range(start="2023-01-01", periods=3, freq="MS") # Month start
    return pd.DataFrame({"measureddtw": [10.0, 11.0, 12.0]}, index=dates)

@pytest.fixture
def transducer_df():
    """Mock raw transducer measurements with linear drift"""
    dates = pd.date_range(start="2023-01-01", periods=90, freq="D")
    return pd.DataFrame({"corrwl": np.linspace(10.0, 13.0, 90)}, index=dates)

@pytest.fixture
def mock_solinst_csv_format():
    """
    A 'Format Fixture': Simulates the output dataframe format exactly 
    as returned by the new_csv_imp() function in loader.py.
    """
    dates = pd.date_range("2023-01-01 12:00", periods=5, freq="H")
    return pd.DataFrame({
        "Level": [15.2, 15.3, 15.2, 15.4, 15.3],
        "Temp": [12.1, 12.1, 12.2, 12.1, 12.0]
    }, index=dates)

# ==========================================
# TESTS FOR TIME SERIES JUMP DETECTION
# ==========================================

def test_jumpfix_normal_data(normal_data):
    result = jumpfix(normal_data, "value", threshold=1.0)
    pd.testing.assert_series_equal(result["value"], normal_data["value"])

def test_jumpfix_with_jumps(jump_data):
    result = jumpfix(jump_data, "value", threshold=1.0)
    expected_values = [1.0, 1.1, 1.1, 1.2, 1.3, 1.3, 1.4, 1.5, 1.6, 1.7]
    np.testing.assert_array_almost_equal(result["value"].values, expected_values, decimal=5)

def test_jumpfix_with_return_jumps(jump_data):
    result, jumps = jumpfix(jump_data, "value", threshold=1.0, return_jump=True)
    assert len(jumps) == 2, "Should detect exactly 2 major jumps"
    assert "jump_size" in jumps.columns

def test_jumpfix_with_nan(nan_data):
    result = jumpfix(nan_data, "value", threshold=1.0)
    assert pd.isna(result["value"].iloc[1]), "NaN should be preserved in position 1"

    non_nan_idx = ~nan_data["value"].isna()
    np.testing.assert_array_almost_equal(
        result["value"][non_nan_idx].values,
        nan_data["value"][non_nan_idx].values,
        decimal=5,
    )

def test_jumpfix_invalid_input(normal_data):
    with pytest.raises(TypeError):
        jumpfix([], "value")
    
    with pytest.raises(ValueError):
        jumpfix(normal_data, "nonexistent_column")
        
    invalid_index_df = pd.DataFrame({"value": [1, 2, 3]})
    with pytest.raises(TypeError):
        jumpfix(invalid_index_df, "value")

def test_jumpfix_edge_case():
    dates = pd.date_range("2024-01-01", periods=3)
    edge_data = pd.DataFrame({"value": [1.0, 2.0, 1.0]}, index=dates)
    result = jumpfix(edge_data, "value", threshold=0.5)
    
    actual_values = result["value"].values
    np.testing.assert_array_almost_equal(actual_values, [1.0, 1.0, 1.0], decimal=5)

# ==========================================
# TESTS FOR DRIFT CORRECTION
# ==========================================

def test_drifting_initialization(manual_df, transducer_df):
    drifting = Drifting(
        manual_df=manual_df,
        transducer_df=transducer_df,
        drifting_field="corrwl",
        man_field="measureddtw",
        daybuffer=3,
    )
    # Testing actual class properties from loader.py
    assert drifting.daybuffer == 3
    assert drifting.drifting_field == "corrwl"
    assert drifting.man_field == "measureddtw"
    assert "julian" in drifting.manual_df.columns
    assert "julian" in drifting.transducer_df.columns

def test_calculate_breakpoints(manual_df, transducer_df):
    drifting = Drifting(manual_df, transducer_df)
    drifting.breakpoints_calc()
    
    assert len(drifting.breakpoints) >= len(manual_df)
    assert list(drifting.breakpoints) == sorted(list(drifting.breakpoints))

def test_drift_correction_process(manual_df, transducer_df):
    drifting = Drifting(manual_df, transducer_df, output_field="waterelevation")
    corrected_df, summary_df, max_drift = drifting.process_drift()

    assert not corrected_df.empty
    assert "waterelevation" in corrected_df.columns
    assert "drift" in summary_df.columns

    # Verify drift logic: Uncorrected transducer drifted to 13.0, manual is 12.0
    # Corrected value should be pulled back to match manual
    final_idx = manual_df.index[-1]
    if final_idx in corrected_df.index:
        corrected_val = corrected_df.loc[final_idx, "waterelevation"]
        assert abs(corrected_val - 12.0) < 0.1 

def test_invalid_column_names(manual_df, transducer_df):
    drifting = Drifting(manual_df, transducer_df, drifting_field="nonexistent")
    # process_drift attempts to drop NA on the drifting field, expecting a KeyError
    with pytest.raises(KeyError):
        drifting.process_drift()

def test_trim_end_functionality(manual_df, transducer_df):
    jumpy_df = transducer_df.copy()
    jumpy_df.iloc[0, jumpy_df.columns.get_loc("corrwl")] += 5
    jumpy_df.iloc[-1, jumpy_df.columns.get_loc("corrwl")] += 5

    drifting_trim = Drifting(manual_df, jumpy_df, trim_end=True)
    corrected_trim, _, _ = drifting_trim.process_drift()
    
    drifting_no_trim = Drifting(manual_df, jumpy_df, trim_end=False)
    corrected_no_trim, _, _ = drifting_no_trim.process_drift()

    # The trimmed version should result in different length or endpoints than no_trim
    assert len(corrected_trim) != len(corrected_no_trim)

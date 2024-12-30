import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from nose.tools import assert_equal, assert_raises
from loggerloader.loader import detect_mean_offset

def test_detect_mean_offset():
    index = pd.date_range('2000-01-01', periods=100)
    data = pd.Series(np.random.randn(100), index=index)

    # Test case 1: offsets detected
    data[10] = data[10] + 5  # Introduce an offset
    offsets = detect_mean_offset(data, window_size=5, threshold=1, plot=False)
    assert_equal(offsets[0], data.index[10])
  
    # Test case 2: no offset detected
    data = pd.Series(np.random.randn(100), index=index)  # Create a new series with no offset
    offsets = detect_mean_offset(data, window_size=5, threshold=1, plot=False)
    assert_equal(len(offsets), 0)

    # Test case 3: window size larger than data length
    assert_raises(ValueError, detect_mean_offset, data, 200, 1, False)

    # Test case 4: window size equal to data length
    offsets = detect_mean_offset(data, window_size=100, threshold=1, plot=False)
    assert_equal(offsets.empty, True)

    # Test case 5: plotting test
    offsets = detect_mean_offset(data, window_size=5, threshold=1, plot=True)
    plt.savefig('plot.png')
    assert os.path.isfile('plot.png')
    os.remove('plot.png')

test_detect_mean_offset()
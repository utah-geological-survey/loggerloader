import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from nose.tools import assert_equal, assert_raises
from unittest.mock import patch
from loggerloader.loader import detect_mean_offset
import collections
collections.Callable = collections.abc.Callable

def test_detect_mean_offset():
    # create a simple time series
    data = pd.Series(np.random.randn(100), index=pd.date_range('1/1/2000', periods=100))

    # test for ValueError if window size is larger than data length
    assert_raises(ValueError, detect_mean_offset, data, 101, 1.0)

    # test for correct output when no offset is detected
    offset_indices = detect_mean_offset(data, 10, 1000.0, plot=False)
    assert_equal(len(offset_indices), 0)

    # add an offset to the data
    data[50:75] += 10.0
    # test for correct output when offset is detected
    offset_indices = detect_mean_offset(data, 10, 1.0, plot=False)
    assert offset_indices[0] >= data.index[50]
    assert offset_indices[-1] <= data.index[74]

    # test plot function called when plot=True with a mock
    with patch.object(plt, 'show') as mock:
        detect_mean_offset(data, 10, 1.0, plot=True)
    mock.assert_called_once()

test_detect_mean_offset()
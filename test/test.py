# -*- coding: utf-8 -*-
"""
Created on Sat Jan 23 13:03:00 2016
@author: p
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import pandas as pd
#import matplotlib
import numpy as np
import sys


try:
    from loggerloader.loader import *
except:
    from loggerloader import *

def testget_breakpoints():
    manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'],'man_read':[1,10,14,52,10,8]}
    man_df = pd.DataFrame(manual)
    man_df.set_index('dates',inplace=True)
    datefield = pd.date_range(start='1/1/1995',end='12/15/2006',freq='3D')
    df = pd.DataFrame({'dates':datefield,'data':np.random.rand(len(datefield))})
    df.set_index('dates',inplace=True)
    assert get_breakpoints(man_df,df,'data')[1] ==np.datetime64('1999-01-31T00:00:00.000000000')

def test_new_xle_imp():
    xle = './loggerloader/test/20160919_LittleHobble.xle'
    xle_df = NewTransImp(xle).well
    assert len(xle_df) > 0

def test_well_baro_merge():
    xle = "./test/ag13c 2016-08-02.xle"
    xle_df = NewTransImp(xle).well
    barofile = "./test/baro.csv"
    baro = pd.read_csv(barofile,index_col=0, parse_dates=True)
    baro['Level'] = baro['pw03']
    assert len(well_baro_merge(xle_df, baro, sampint=60)) > 10

def testcalc_slope_and_intercept():
    assert calc_slope_and_intercept(0, 0, 5, 5, 1, 1, 6, 6) == (0.0, 1, 1.0, 1.0, 0)

def testcalc_drift():
    df = pd.DataFrame({'date': pd.date_range(start='1900-01-01', periods=101, freq='1D'),
                            "data": [i * 0.1 + 2 for i in range(0, 101)]})
    df.set_index('date', inplace=True)
    df['julian'] = df.index.to_julian_date()
    assert calc_drift(df, 'data', 'gooddata', 0.05, 1)['gooddata'][-1] == 6.0
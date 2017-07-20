# -*- coding: utf-8 -*-
"""
Created on Sat Jan 23 13:03:00 2016

@author: p
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import loggerloader as wa
import pandas as pd
import matplotlib
import numpy as np


def test_new_xle_imp():
    xle = 'test/20160919_LittleHobble.xle'
    xle_df = wa.new_xle_imp(xle)
    assert len(xle_df) > 0 

def test_xle_head_table():
    xle_dir = 'test/'
    dir_df = wa.xle_head_table(xle_dir)
    assert len(xle_dir) > 0

def test_dataendclean():
    xle = 'test/20160919_LittleHobble.xle'
    df = wa.new_xle_imp(xle)
    x = 'Level'
    xle1 = wa.dataendclean(df, x)
    assert len(xle1) > 1
    
def test_smoother():
    xle = 'test/20160919_LittleHobble.xle'
    df = wa.new_xle_imp(xle)
    x = 'Level'
    xle1 = wa.smoother(df, x, sd=1)
    assert len(xle1) > 1
    
def test_hourly_resample():
    xle = 'test/20160919_LittleHobble.xle'
    df = wa.new_xle_imp(xle)
    xle1 = wa.hourly_resample(df, minutes=30)

def test_imp_new_well():
    inputfile = "test/ag13c 2016-08-02.xle"
    manualwls = "test/All tape measurements.csv"
    manual = pd.read_csv(manualwls, index_col="DateTime", engine="python")
    barofile = "test/baro.csv"
    baro = pd.read_csv(barofile,index_col=0, parse_dates=True)
    wellinfo = pd.read_csv("test/wellinfo4.csv")
    g, drift, wellname = wa.imp_new_well(inputfile, wellinfo, manual, baro)
    assert wellname == 'ag13c'
    
def test_well_baro_merge():
    xle = "test/ag13c 2016-08-02.xle"
    xle_df = wa.new_xle_imp(xle)
    barofile = "test/baro.csv"
    baro = pd.read_csv(barofile,index_col=0, parse_dates=True)
    baro['Level'] = baro['pw03']
    assert len(wa.well_baro_merge(xle_df, baro, sampint=60)) > 10

def test_fix_drift_linear():
    xle = "test/ag13c 2016-08-02.xle"
    xle_df = wa.new_xle_imp(xle)
    manualwls = "test/All tape measurements.csv"
    manual = pd.read_csv(manualwls, index_col="DateTime", engine="python")
    manual35 = manual[manual['WellID']==35]
    manual35.index = pd.to_datetime(manual35.index)
    manual35.index.name = 'dt'
    fd = wa.fix_drift_linear(xle_df, manual35, meas='Level', manmeas='MeasuredDTW', outcolname='DriftCorrection')
    assert 'DriftCorrection' in list(fd[0].columns)
    
def test_getwellid():
    inputfile = "test/ag13c 2016-08-02.xle"
    wellinfo = pd.read_csv("test/wellinfo4.csv")
    wid = wa.getwellid(inputfile, wellinfo)
    assert wid[1] == 35

def test_barodistance():
    wellinfo = pd.read_csv("test/wellinfo4.csv")
    bd = wa.barodistance(wellinfo)
    assert 'closest_baro' in list(bd.columns)

def test_imp_new_well_csv():
    inputfile = "test/ag14a 2016-08-02.csv"
    manualwls = "test/All tape measurements.csv"
    manual = pd.read_csv(manualwls, index_col="DateTime", engine="python")
    barofile = "test/baro.csv"
    baro = pd.read_csv(barofile,index_col=0, parse_dates=True)
    wellinfo = pd.read_csv("test/wellinfo4.csv")
    g, drift, wellname = wa.imp_new_well(inputfile, wellinfo, manual, baro)
    assert wellname == 'ag14a'

def test_jumpfix():
    xle = "test/ag13c 2016-08-02.xle"
    df = wa.new_xle_imp(xle)
    jf = wa.jumpfix(df, 'Level', threashold=0.005)
    assert jf['newVal'][-1] > 10



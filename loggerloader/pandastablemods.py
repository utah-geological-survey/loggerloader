
from __future__ import absolute_import, division, print_function
try:
    from tkinter import *
    from tkinter.ttk import *
    from tkinter import filedialog, messagebox, simpledialog
except:
    from Tkinter import *
    from ttk import *
    import tkFileDialog as filedialog
    import tkSimpleDialog as simpledialog
    import tkMessageBox as messagebox
import types, time
import numpy as np
import pandas as pd
try:
    from pandas import plotting
except ImportError:
    from pandas.tools import plotting
import matplotlib as mpl
#mpl.use("TkAgg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.lines import Line2D
import matplotlib.transforms as mtrans
from collections import OrderedDict
import operator

from pandastable.plotting import addFigure
import logging
from pandastable import *
from pandastable.dialogs import *
from pandastable.plotting import *

class MTable(Table):
    def __init__(self, parent=None, model=None, dataframe=None,
                   width=None, height=None,
                   rows=20, cols=5, showtoolbar=False, showstatusbar=False,
                   editable=True, enable_menus=True, **kwargs):
        Table.__init__(self, parent=parent, model=model, dataframe=dataframe,
                       width=width, height=height, rows=rows, cols=cols,
                       showtoolbar=showtoolbar, showstatusbar=showstatusbar,
               editable=editable, enable_menus=enable_menus, **kwargs)


    def showPlotViewer(self, parent=None, layout='horizontal', showdialogs=False):
        """Create plot frame"""

        if not hasattr(self, 'pf'):
            self.pf = PlotViewer(table=self, parent=parent, layout=layout, showdialogs=showdialogs)
        if hasattr(self, 'child') and self.child is not None:
            self.child.pf = self.pf
        return self.pf

class MPlotViewer(PlotViewer):
    def __init__(self, table, parent=None, layout='horizontal', showdialogs=True):
        PlotViewer.__init__(self, table=table, parent=parent, layout=layout, showdialogs=showdialogs)

    def setupGUI(self):
        """Add GUI elements"""

        self.m = PanedWindow(self.main, orient=self.orient)
        self.m.pack(fill=BOTH,expand=1)
        #frame for figure
        self.plotfr = Frame(self.m)
        #add it to the panedwindow
        self.fig, self.canvas = addFigure(self.plotfr)
        self.ax = self.fig.add_subplot(111)

        self.m.add(self.plotfr, weight=2)
        #frame for controls
        self.ctrlfr = Frame(self.main)
        self.m.add(self.ctrlfr)
        self.mplopts.kwds['kind'] = 'line'
        self.mplopts.kwds['by'] = 'line'
        #button frame
        bf = Frame(self.ctrlfr, padding=2)
        bf.pack(side=TOP,fill=BOTH)
        if self.toolslayout== 'vertical':
            side = TOP
        else:
            side = LEFT

        #add button toolbar
        addButton(bf, 'Plot', self.replot, images.plot(),
                  'plot current data', side=side, compound="left", width=20)
        addButton(bf, 'Apply Options', self.updatePlot, images.refresh(),
                  'refresh plot with current options', side=side, compound="left", width=20)
        addButton(bf, 'Clear', self.clear, images.plot_clear(),
                  'clear plot', side=side)
        addButton(bf, 'Hide', self.hide, images.cross(),
                  'hide plot frame', side=side)
        addButton(bf, 'Vertical', self.refreshLayout, images.tilehorizontal(),
                  'change plot tools orientation', side=side)
        addButton(bf, 'Save', self.savePlot, images.save(),
                  'save plot', side=side)

        #dicts to store global options, can be saved with projects
        self.globalvars = {}
        self.globalopts = OrderedDict({ 'dpi': 80, 'grid layout': False,'3D plot':False })
        from functools import partial
        for n in self.globalopts:
            val = self.globalopts[n]
            if type(val) is bool:
                v = self.globalvars[n] = BooleanVar()
                v.set(val)
                b = Checkbutton(bf,text=n, variable=v, command=partial(self.setGlobalOption, n))
            else:
                v = self.globalvars[n] = IntVar()
                v.set(val)
                Label(bf, text=n).pack(side=LEFT,fill=X,padx=2)
                b = Entry(bf,textvariable=v, width=5)
                v.trace("w", partial(self.setGlobalOption, n))
            b.pack(side=LEFT, padx=2)

        #self.addWidgets()
        self.mplopts.updateFromOptions()
        self.styleopts = ExtraOptions(parent=self)

        def onpick(event):
            print(event)

        from pandastable import handlers
        dr = handlers.DragHandler(self)
        dr.connect()
        #self.fig.canvas.mpl_connect('pick_event', onpick)
        #self.fig.canvas.mpl_connect('button_release_event', onpick)

        return

    def replot(self, data=None):
        """Re-plot using current parent table selection.
        Args:
        data: set current dataframe, otherwise use
        current table selection"""

        #print (self.table.getSelectedRows())
        if data is None:
            self.data = self.table.getSelectedDataFrame()
        else:
            self.data = data
        self.updateStyle()
        #self.applyPlotoptions()
        self.plot2D(redraw=True)
        return


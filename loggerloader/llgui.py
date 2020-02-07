import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
# Implement the default Matplotlib key bindings.
import matplotlib.animation as animation
import matplotlib.pyplot as plt
from matplotlib import style
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import os
import re
import glob

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkcalendar import Calendar, DateEntry
import pandastable
from pandastable import Table, TableModel, dialogs

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

style.use('ggplot')
import loggerloader as ll


class Feedback:

    def __init__(self, master):
        # create main window and configure size and title
        # tk.Tk.__init__(self, *args, **kwargs)
        master.geometry('1000x800')
        master.wm_title("Transducer Processing")
        self.root = master

        self.currentdir = os.path.expanduser('~')

        self.dropmenu(master)

        # Create side by side panel areas
        self.panedwindow = ttk.Panedwindow(master, orient='horizontal')
        self.panedwindow.pack(fill='both', expand=True)
        self.process_frame = ttk.Frame(self.panedwindow, width=150, height=400, relief='sunken')
        self.frame2 = ttk.Frame(self.panedwindow, width=400, height=400, relief='sunken')
        self.panedwindow.add(self.process_frame, weight=1)
        self.panedwindow.add(self.frame2, weight=4)

        # add tabs in the frame to the right
        self.notebook = ttk.Notebook(self.frame2)
        self.notebook.pack(fill='both', expand=True)
        self.notelist = {}

        # add tabs in the frame to the left
        self.processing_notebook = ttk.Notebook(self.process_frame)
        self.processing_notebook.pack(fill='both', expand=True)
        self.onewelltab = ttk.Frame(self.processing_notebook)
        self.bulkwelltab = ttk.Frame(self.processing_notebook)
        self.processing_notebook.add(self.onewelltab, text='Single-Well Process')
        self.processing_notebook.add(self.bulkwelltab, text='Bulk Well Process')

        # BULK UPLOAD TAB of left side of application -------------------------------------------------------
        # BulkUploader(self.bulkwelltab)
        dirselectframe = ttk.Frame(self.bulkwelltab)
        dirselectframe.pack()

        self.bulkdatastr, self.bulkdata, self.bulkdatatable, self.bulkcombo = {}, {}, {}, {}
        self.locidmatch = {}
        self.bulktransfilestr = {} #dictionary to store trans file names

        # select file for well-info-table
        well_info_frame = ttk.Frame(dirselectframe)
        well_info_frame.pack()
        key = 'well-info-table'
        self.bulkdatastr[key] = tk.StringVar(well_info_frame)
        self.bulkdatastr[key].set("../data_files/ugs_ngwmn_monitoring_locations.csv")
        df = pd.read_csv(self.bulkdatastr[key].get())
        df = df.reset_index()
        df = df[df['altlocationid'].notnull()]
        df['altlocationid'] = df['altlocationid'].apply(lambda x: int(x), 1)
        df = df.set_index(['altlocationid'])
        self.bulkdata[key] = df
        ttk.Label(well_info_frame, text='Input well info file (must be csv)').grid(row=0, column=0, columnspan=3)
        #ttk.Label(well_info_frame, text='must have altlocationid, locationname, stickup, barologgertype, and verticalmeasure').grid(row=1,column=0,columnspan=3)
        e = ttk.Entry(well_info_frame, textvariable=self.bulkdatastr[key], width=80)
        e.grid(row=1,column=0,columnspan=2)
        e.bind('<Double-ButtonRelease-1>', lambda f: self.open_file(well_info_frame))
        b = ttk.Button(well_info_frame, text='Process Well Info File', command=self.add_well_info_table)
        b.grid(row=1,column=2)

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # pick directory with transducer files and populate a scrollable window with combobox selections
        filefinderframe = ttk.Frame(dirselectframe)
        filefinderframe.pack()
        ttk.Label(filefinderframe, text='Pick directory with relevant well files.').pack()
        key = 'trans-dir'
        self.bulkdatastr[key] = tk.StringVar(filefinderframe, value=f'Double-Click for transducer file directory')
        self.filefnd = ttk.Entry(filefinderframe, textvariable=self.bulkdatastr[key], width=80)
        self.filefnd.pack()
        filefoundframe = ttk.Frame(dirselectframe)
        self.filefnd.bind('<Double-ButtonRelease-1>', lambda f: self.grab_dir(filefoundframe))
        #self.entry[key].bind('<3>', lambda k: self.wellbaroabb(key))


        filefoundframe.pack()

        #filefinderframe.pack()
        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        applymatchframe = ttk.Frame(dirselectframe)
        applymatchframe.pack()
        b = tk.Button(applymatchframe, text='Click when done matching files to well names')
        b.pack()
        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # SINGLE WELL PROCESSING TAB for left side of application ---------------------------------------------
        # Header image logo and Description seen by user
        self.frame_header = ttk.Frame(self.onewelltab)
        self.frame_header.pack(pady=5)
        self.logo = tk.PhotoImage(file="../data_files/GeologicalSurvey.png").subsample(10, 10)
        ttk.Label(self.frame_header, image=self.logo).grid(row=0, column=0, rowspan=2)
        ttk.Label(self.frame_header, wraplength=300, text="Processing transducer data").grid(row=0, column=1)

        # Data Entry Frame
        # initiate dictionaries to hold data by key
        self.datastr, self.data, self.datatable, self.entry = {}, {}, {}, {}

        self.filefinders('well')  # Select and import well data
        self.filefinders('baro')  # Select and import baro data

        # Align Data
        self.add_alignment_interface()

        self.add_manual_notepad()
        # validates time number inputs
        self.measvalidation = (self.manframe.register(self.only_meas), '%P')

        self.man_date, self.man_hour, self.man_min, self.man_meas, self.man_datetime = {}, {}, {}, {}, {}
        # labels and date, time, and measure entry for manual measurements
        self.date_hours_min(0)  # 1st manual measure
        self.date_hours_min(2)  # 2nd manual measure

        # units
        self.manunits = ttk.Combobox(self.manframe, width=5, values=['ft', 'm'], state="readonly")
        self.manunits.grid(row=1, column=5, rowspan=3)
        self.manunits.current(0)

        # locid
        ttk.Label(self.manframe, text="Locationid").grid(row=0, column=6)
        self.man_locid = ttk.Entry(self.manframe, width=11)
        self.man_locid.grid(row=1, column=6, rowspan=3)

        # Tab for entering manual data by file
        # TODO Auto align sheet fields to columns
        manfileframetext = """File with manual data must have datetime, reading, and locationid fields
Good for matching bulk manual data """

        ttk.Label(self.manfileframe, text=manfileframetext).grid(row=0, column=0, columnspan=4)
        self.datastr['manual'] = tk.StringVar(self.manfileframe, value='Double-Click for manual file')
        self.man_entry = ttk.Entry(self.manfileframe, textvariable=self.datastr['manual'], width=80, justify='left')
        self.man_entry.grid(row=2, column=0, columnspan=4)
        self.man_entry.bind('<Double-ButtonRelease-1>', self.mandiag)


        fillervals = ['datetime','meas','locid']
        self.combo, self.combo_choice = {}, {}
        combovals = {"Datetime":[3,0,15,fillervals,4,0],
                          "DTW":[3,1,15,fillervals,4,1],
                          "locationid":[3,2,15,fillervals,4,2],
                          "Pick id":[5,1,15,[1001,1002],5,2]}

        for key, vals in combovals.items():
            self.man_combos(key, vals)

        ttk.Label(self.manfileframe, text="units").grid(row=3, column=3)
        self.manunits = ttk.Combobox(self.manfileframe, width=5,
                                     values=['ft', 'm'], state="readonly")
        self.manunits.grid(row=4, column=3)
        self.manunits.current(0)

        b = ttk.Button(self.frame_step4, text='Process Manual Data', command=self.proc_man)
        b.grid(column=0, row=2, columnspan=3)

        self.fix_drift_interface()  # Fix Drift Button

        # Elevation Correction Interface
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X)
        frame_step6 = ttk.Frame(self.onewelltab)
        frame_step6.pack()
        ttk.Label(frame_step6, text='6. Align Elevation and Offset').grid(row=1, column=0, columnspan=4)
        ttk.Label(frame_step6, text='Ground Elev.').grid(row=2, column=0)
        ttk.Label(frame_step6, text='Stickup').grid(row=2, column=2)
        ttk.Label(frame_step6, text='Elev. Units').grid(row=2, column=1)
        ttk.Label(frame_step6, text='Stickup Units').grid(row=2, column=3)
        self.wellgroundelev = ttk.Entry(frame_step6, width=6)
        self.wellgroundelevunits = ttk.Combobox(frame_step6, width=5,
                                                values=['ft', 'm'], state="readonly")
        self.wellgroundelevunits.current(0)
        self.wellstickup = ttk.Entry(frame_step6, width=4)
        self.wellstickupunits = ttk.Combobox(frame_step6, width=5,
                                             values=['ft', 'm'], state="readonly")
        self.wellstickupunits.current(0)
        self.wellgroundelev.grid(row=3, column=0)
        self.wellgroundelevunits.grid(row=3, column=1)
        self.wellstickup.grid(row=3, column=2)
        self.wellstickupunits.grid(row=3, column=3)

        b = ttk.Button(frame_step6, text='Calculate Elevations', command=self.elevcalc)
        b.grid(row=4, column=0, columnspan=4,pady=5)

        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X)
        save_onewell_frame = ttk.Frame(self.onewelltab)
        save_onewell_frame.pack()
        b = ttk.Button(save_onewell_frame, text='Save csv', command=self.save_one_well)
        b.pack()

    def man_combos(self, key, vals):
        self.combo_choice[key] = tk.StringVar()
        ttk.Label(self.manfileframe, text=key).grid(row=vals[0], column=vals[1])
        self.combo[key] = ttk.Combobox(self.manfileframe, width=vals[2],
                                       textvariable=self.combo_choice[key],
                                       postcommand=lambda: self.man_col_select(self.combo[key]))
        self.combo[key].grid(row=vals[4], column=vals[5])

    def man_col_select(self, cmbo):
        if 'manual' in self.data.keys():
            mancols = list(self.data['manual'].columns.values)
            if cmbo == self.combo['Pick id']:
                locids = self.data['manual'][str(self.combo['locationid'].get())].unique()
                # TODO this will cause problems later; change to handle multiple types
                cmbo['values'] = list([f'{loc:0.0f}' for loc in locids])
            else:
                cmbo['values'] = mancols

            for col in mancols:
                # TODO move matching functions to happen with data import in mandiag
                if col in ['datetime', 'date', 'readingdate', 'Date']:
                    self.combo_choice["Datetime"].set('readingdate')
                    self.combo["Datetime"].current(mancols.index(col))

        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.mandiag(True)

    def date_hours_min(self, i):
        ttk.Label(self.manframe, text=f"Date of Measure {i + 1}").grid(row=i, column=0)
        ttk.Label(self.manframe, text="HH:MM").grid(row=i, column=1, columnspan=3, sticky='WENS')
        ttk.Label(self.manframe, text="Measure 1").grid(row=i, column=4)
        ttk.Label(self.manframe, text="Units").grid(row=i, column=5)
        # date picker
        self.man_date[i] = DateEntry(self.manframe, width=20, locale='en_US', date_pattern='MM/dd/yyyy')
        self.man_date[i].grid(row=i + 1, column=0, padx=2)
        # time picker
        self.man_hour[i] = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 24)]),
                                        state="readonly")
        self.man_hour[i].grid(row=i + 1, column=1)
        self.man_hour[i].current(0)
        ttk.Label(self.manframe, text=":").grid(row=i + 1, column=2)
        self.man_min[i] = ttk.Combobox(self.manframe, width=2,
                                       values=list([f'{i:02}' for i in range(0, 60)]),
                                       state="readonly")
        self.man_min[i].grid(row=i + 1, column=3)
        self.man_min[i].current(0)
        # measure
        self.man_meas[i] = ttk.Entry(self.manframe, validate="key", validatecommand=self.measvalidation, width=10)
        self.man_meas[i].grid(row=i + 1, column=4, padx=2)

    def add_manual_notepad(self):
        # -----------Manual Data-------------------------------------------------------------
        # Select Manual Table Interface
        ttk.Separator(self.onewelltab).pack(fill=tk.X, pady=5)
        self.frame_step4 = ttk.Frame(self.onewelltab)
        self.frame_step4.pack()
        ttk.Label(self.frame_step4, text="4. Select Manual Data:").grid(row=0, column=0, columnspan=3)
        self.manbook = ttk.Notebook(self.frame_step4)
        self.manbook.grid(row=1, column=0, columnspan=3)
        self.manframe = ttk.Frame(self.manbook)
        self.manfileframe = ttk.Frame(self.manbook)
        self.manbook.add(self.manframe, text='Manual Entry')
        self.manbook.add(self.manfileframe, text='Data Import')

    def filefinders(self, key):
        datasets = {"well": "1. Select Well Data:",
                    "baro": "2. Select Barometric Data:"}
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        filefinderframe = ttk.Frame(self.onewelltab)
        ttk.Label(filefinderframe, text=datasets[key]).pack()
        ttk.Label(filefinderframe, text='(Right click for refresh.)').pack()
        self.datastr[key] = tk.StringVar(filefinderframe, value=f'Double-Click for {key} file')
        self.entry[key] = ttk.Entry(filefinderframe, textvariable=self.datastr[key], width=80)
        self.entry[key].pack()
        self.entry[key].bind('<Double-ButtonRelease-1>', lambda k: self.wellbarodiag(key))
        self.entry[key].bind('<3>', lambda k: self.wellbaroabb(key))
        filefinderframe.pack()

    def fix_drift_interface(self):
        # Fix Drift Button
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X)
        frame_step5 = ttk.Frame(self.onewelltab)
        frame_step5.pack()
        ttk.Label(frame_step5, text='5. Fix Drift').grid(column=0, row=1, columnspan=3)
        self.max_drift = tk.StringVar(frame_step5, value="")
        ttk.Button(frame_step5, text='Fix Drift',
                   command=self.fix_drift).grid(column=0, row=2, columnspan=1)
        ttk.Label(frame_step5, text='Drift = ').grid(row=2, column=1)
        ttk.Label(frame_step5, textvariable=self.max_drift).grid(row=2, column=2)
        # self.locchk = ttk.Entry(self.frame_step5)
        # self.locchk.grid(column=1,row=0)

    def add_alignment_interface(self):
        # Align Manual and Baro Data
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        frame_step3 = ttk.Frame(self.onewelltab)
        frame_step3.pack()
        ttk.Label(frame_step3, text="3. Align Baro and Well Data:").grid(row=0, column=0, columnspan=3)
        ttk.Label(frame_step3, text='Pref. Data Freq.').grid(row=1, column=0, columnspan=2)
        # Boxes for data frequency
        self.freqint = ttk.Combobox(frame_step3, width=4, values=list(range(1, 120)))
        self.freqint.grid(row=2, column=0)
        self.freqint.current(59)
        self.freqtype = ttk.Combobox(frame_step3, width=4, values=['min'])
        self.freqtype.grid(row=2, column=1)
        self.freqtype.current(0)
        b = ttk.Button(frame_step3, text='Align Datasets',
                       command=self.alignedplot)
        b.grid(row=2, column=2)

    def elevcalc(self):
        key = 'wl-elev'
        mstickup = float(self.wellstickup.get())
        melev = float(self.wellgroundelev.get())
        if self.wellstickupunits.get() == 'm':
            mstickup = mstickup * 3.2808
        elif self.wellgroundelevunits.get() == 'm':
            melev = melev * 3.2808
        self.manelevs = ll.get_man_gw_elevs(self.datatable['manual'].model.df, mstickup, melev)
        df = ll.get_trans_gw_elevations(self.datatable['fixed-drift'].model.df, mstickup,
                                                     melev, self.combo["Pick id"].get(), level='corrwl', dtw='DTW_WL')
        self.data[key] = df.set_index('readingdate')
        graphframe, tableframe = self.note_tab_add(key)
        self.add_graph_table(key, tableframe, graphframe)
        print(self.manelevs)

    def fix_drift(self):
        key = 'fixed-drift'
        if 'well-baro' in self.datatable.keys():
            df, self.drift_info, mxdrft = ll.fix_drift(self.datatable['well-baro'].model.df,
                                                       self.datatable['manual'].model.df,
                                                       manmeas='dtwbelowcasing')
            self.max_drift.set(mxdrft)
            self.data[key] = df[['datetime', 'barometer', 'corrwl', 'DTW_WL']]

            graphframe, tableframe = self.note_tab_add(key)
            self.add_graph_table(key, tableframe, graphframe)
        else:
            tk.messagebox.showinfo(title='Yo!',message='Align the data first!')

    def proc_man(self):
        nbnum = self.manbook.index(self.manbook.select())
        key = 'manual'
        if nbnum == 0:
            for i in [0, 2]:
                self.man_datetime[i] = pd.to_datetime(
                    f'{self.man_date[i].get()} {self.man_hour[i].get()}:{self.man_min[i].get()}',
                    format='%m/%d/%Y %H:%M')

            df = pd.DataFrame({'readingdate': [self.man_datetime[0], self.man_datetime[2]],
                               'dtwbelowcasing': [float(self.man_meas[0].get()),
                                               float(self.man_meas[2].get())],
                               'locationid': [self.man_locid.get()] * 2,
                               'units': [self.manunits.get()] * 2})
            if self.manunits.get() == 'm':
                df['dtwbelowcasing'] = df['dtwbelowcasing'] * 3.28084
            self.data[key] = df.set_index(['readingdate'])
            print(self.data[key])
        elif nbnum == 1:
            df = self.data[key].rename(columns={self.combo['Datetime'].get(): 'readingdate',
                                                self.combo['DTW'].get(): 'dtwbelowcasing',
                                                self.combo['locationid'].get(): 'locationid'})
            df['units'] = self.manunits.get()
            if self.manunits.get() == 'm':
                df['dtwbelowcasing'] = df['dtwbelowcasing'] * 3.28084
            df = df.reset_index()
            df['readingdate'] = df['readingdate'].apply(lambda x: pd.to_datetime(x, infer_datetime_format=True,
                                                                                 errors='ignore'))
            df['dtwbelowcasing'] = df['dtwbelowcasing'].apply(lambda x: pd.to_numeric(x, errors='coerce'))
            df = df.set_index(['readingdate'])
            df = df[['dtwbelowcasing', 'locationid', 'units']]
            if 'well' in self.datatable.keys():
                df = df[df.index > self.datatable['well'].model.df.first_valid_index()-pd.DateOffset(days=8)]

            self.data[key] = df[df['locationid'] == int(self.combo['Pick id'].get())]


        graphframe, tableframe = self.note_tab_add(key)
        self.add_graph_table(key, tableframe, graphframe)

    def only_meas(self, value_if_allowed):
        try:
            float(value_if_allowed)
            bool = True
        except ValueError:
            bool = False
        return bool

    def decrease(self):
        x, y = self.line.get_data()
        self.line.set_ydata(y * 0.8)
        self.canvas.draw()

    def increase(self):
        x, y = self.line.get_data()
        self.line.set_ydata(y * 1.2)
        self.canvas.draw()

    def _quit(self):
        self.quit()  # stops mainloop
        self.destroy()  # this is necessary on Windows to prevent
        # Fatal Python Error: PyEval_RestoreThread: NULL tstate

    def on_key_press(self, event):
        print("you pressed {}".format(event.key))
        key_press_handler(event, self.canvas, self.toolbar)

    def note_tab_add(self, key, tabw=1, grph=4):
        """

        Args:
            key (str): name of dataset; ex 'well','baro','well-baro','manual','fixed-drift'

        Returns:

        """
        print(key)
        if key in self.notelist.keys():
            self.notebook.forget(self.notelist[key])
            self.notelist[key] = 'old'
        new_frame = ttk.Frame(self.notebook)
        self.notebook.add(new_frame, text=key)
        for t in range(len(self.notebook.tabs())):
            self.notelist[self.notebook.tab(t)['text']] = t
        self.notebook.select(t)

        panedframe = ttk.Panedwindow(new_frame, orient='vertical')
        panedframe.pack(fill='both', expand=True)
        tableframe = ttk.Frame(panedframe, relief='sunken')
        graphframe = ttk.Frame(panedframe, relief='sunken')
        panedframe.add(tableframe, weight=tabw)
        panedframe.add(graphframe, weight=grph)
        labframe = ttk.Frame(graphframe)
        labframe.pack()
        ttk.Label(labframe, text='Click on column of choice and then the Plot button!').pack()
        return graphframe, tableframe

    def add_graph_table(self, key, tableframe, graphframe):
        """

        Args:
            key (str): name of dataset; ex 'well','baro','well-baro','manual','fixed-drift'
            tableframe: parent tk frame for pandastable data table
            graphframe: parent tk frame for pandastable graph

        Returns:
            adds pandastable elements to a frame

        """
        graph_frame1 = ttk.Frame(graphframe)
        self.datatable[key] = Table(tableframe, dataframe=self.data[key], showtoolbar=True, showstatusbar=True)
        self.datatable[key].show()
        self.datatable[key].showIndex()
        self.datatable[key].update()
        self.datatable[key].showPlotViewer(parent=graph_frame1)
        canvas = self.datatable[key].showPlotViewer(parent=graph_frame1).canvas
        if key == 'well-baro':
            self.add_baro_axis(graph_frame1)
        elif key == 'fixed-drift':
            self.add_manual_points(key, graph_frame1)
        elif key == 'wl-elev':
            self.add_manual_points(key, graph_frame1)
        toolbar = NavigationToolbar2Tk(canvas, graph_frame1)
        toolbar.update()
        canvas.draw()
        canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        canvas.mpl_connect("key_press_event", self.on_key_press)
        graph_frame1.pack()

    def add_baro_axis(self, graph_frame1):
        key = 'well-baro'
        ax = self.datatable[key].showPlotViewer(parent=graph_frame1).ax
        lns1 = ax.plot(self.datatable[key].model.df['Level'], color='green', label='unprocessed')
        lns2 = ax.plot(self.datatable[key].model.df['corrwl'], color='blue', label='baro-removed')
        ax2 = ax.twinx()
        lns3 = ax2.plot(self.datatable[key].model.df['barometer'], color='red', label='baro')
        ax2.set_ylabel('barometer', color='red')
        ax.set_ylabel('well levels', color='blue')
        lns = lns1 + lns2 + lns3
        labs = [l.get_label() for l in lns]
        ax.legend(lns, labs, loc=0)

    def add_manual_points(self, key, graph_frame1):
        ax = self.datatable[key].showPlotViewer(parent=graph_frame1).ax
        if key == 'fixed-drift':
            ax.plot(self.datatable[key].model.df['DTW_WL'], color='green', label='unprocessed')
            ax.scatter(self.datatable['manual'].model.df.index, self.datatable['manual'].model.df['dtwbelowcasing'])
            ax.set_ylabel(f"Depth to Water (ft)")
        elif key == 'wl-elev':
            ax.plot(self.datatable[key].model.df['waterelevation'], color='green', label='unprocessed')
            ax.scatter(self.manelevs.index, self.manelevs['waterelevation'])
            ax.set_ylabel(f"Water Elevation (ft)")
        ax.set_xlim(self.datatable['manual'].model.df.first_valid_index() - pd.Timedelta('3 days'),
                    self.datatable['manual'].model.df.last_valid_index() + pd.Timedelta('3 days'), )

    def wellbaroabb(self, key):
        if self.datastr[key].get() == '' or type(self.datastr[key].get()) == tuple or self.datastr[key].get() == f'Double-Click for {key} file':
            pass
        else:
            if key in ('well','baro'):
                self.data[key] = ll.NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
            elif key == 'manual':
                filenm, file_extension = os.path.splitext(self.datastr[key].get())
                if file_extension in ('.xls', '.xlsx'):
                    self.data['manual'] = pd.read_excel(self.datastr[key].get())
                elif file_extension == '.csv':
                    self.data['manual'] = pd.read_csv(self.datastr[key].get())
            # add notepad tab
            graphframe, tableframe = self.note_tab_add(key)
            # add graph and table to new tab
            self.add_graph_table(key, tableframe, graphframe)

    def wellbarodiag(self, key):

        ftypelist = (("Solinst xle", "*.xle*"), ("Solinst csv", "*.csv"))

        self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir,
                                                         title=f"Select {key} file",
                                                         filetypes=ftypelist))
        self.currentdir = os.path.dirname(self.datastr[key].get())

        # Action if cancel in file dialog is pressed
        self.wellbaroabb(key)

    def alignedplot(self):
        """

        Returns: notepad tab with aligned data;

        """
        if 'well' in self.data.keys() and 'baro' in self.data.keys():
            key = 'well-baro'
            self.data[key] = ll.well_baro_merge(self.datatable['well'].model.df,
                                                self.datatable['baro'].model.df,
                                                sampint=self.freqint.get())
            graphframe, tableframe = self.note_tab_add(key)
            self.add_graph_table(key, tableframe, graphframe)

    def mandiag(self, event):
        if event:
            key = 'manual'
            ftypelist = (("csv", "*.csv*"), ("xlsx", "*.xlsx"), ("xls", ".xls"))
            self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir,
                                                             title=f"Select {key} file",
                                                             filetypes=ftypelist))
            self.currentdir = os.path.dirname(self.datastr[key].get())

            # https://stackoverflow.com/questions/45357174/tkinter-drop-down-menu-from-excel
            # TODO add excel sheet options to file selection
            filenm, file_extension = os.path.splitext(self.datastr[key].get())
            if file_extension in ('.xls', '.xlsx'):
                self.data['manual'] = pd.read_excel(self.datastr[key].get())
            elif file_extension == '.csv':
                self.data['manual'] = pd.read_csv(self.datastr[key].get())
            # self.graph_frame1.pack()

    def dropmenu(self, master):
        # menu bars at the top of the main window
        master.option_add('*tearOff', False)
        menubar = tk.Menu(master)
        master.config(menu=menubar)
        file = tk.Menu(menubar)
        edit = tk.Menu(menubar)
        help_ = tk.Menu(menubar)
        menubar.add_cascade(menu=file, label='File')
        menubar.add_cascade(menu=edit, label='Edit')
        menubar.add_cascade(menu=help_, label='Help')
        file.add_command(label='New', command=lambda: print('New File'))
        file.add_separator()
        file.add_command(label="Open Config File...", command=self.open)
        file.entryconfig('New', accelerator='Ctrl + N')
        save = tk.Menu(file)
        file.add_cascade(menu=save, label='Save')
        save.add_command(label="Save Well Config", command=self.save)
        save.add_command(label='Save As', command=lambda: print('save as'))
        save.add_command(label='Save All', command=lambda: print('saving'))
        file.add_command(label='Quit', command=self.root.destroy)

    def save(self):
        file = filedialog.asksaveasfile(mode="w", filetypes=[('text','.txt')], defaultextension=".txt")
        if file is None:
            print('no')
            return
        else:
            file.write("dic,name,value\n")
            for key in self.datastr.keys():
                file.write(f"datastr,{key},{self.datastr[key].get()}\n")
            for key in self.combo.keys():
                file.write(f"combo,{key},{self.combo[key].get()}\n")
            file.write(f"man notebook,manual tab,{self.manbook.index(self.manbook.select())}")
            file.close()
            return
            #f = filedialog.asksaveasfile(mode='w', defaultextension=".tproc")

    def open(self):
        filename = filedialog.askopenfilename(filetypes=[('text','.txt')])
        if filename is None:
            return
        else:
            df = pd.read_csv(filename).set_index(['name'])
            directs = df[df['dic']=='datastr']
            for i in directs.index:
                self.datastr[i].set(directs.loc[i,'value'])
                self.wellbaroabb(i)
            combs = df[df['dic']=='combo']
            for i in combs.index:
                self.combo_choice[i].set(combs.loc[i,'value'])
            self.manbook.select(df.loc['manual tab','dic'])

    def save_one_well(self):
        filename = filedialog.asksaveasfilename(confirmoverwrite=True)
        if filename is None:
            print('no')
            return
        else:
            df = self.datatable['wl-elev'].model.df

            df.to_csv(filename)
            return

    def open_file(self, master):
        """This function creates a file dialog to select the well-info-file and then uses the filename to
        make a pandas dataframe; this dataframe is fed to the add_well_info_table function to display it in the
        spreadsheet

        Args:
            master:

        Returns:

        """
        key = 'well-info-table'

        try:
            self.bulkdatastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir, title="Select well info file"))
            if self.bulkdatastr[key].get() == '' or type(self.bulkdatastr[key].get()) == tuple or \
                    self.bulkdatastr[key].get() == 'Double-Click for transducer file directory':
                pass
            else:
                self.currentdir = os.path.dirname(self.bulkdatastr[key].get())
                df = pd.read_csv(self.bulkdatastr[key].get())
                df = df[df['altlocationid'].notnull()]
                df['altlocationid'] = df['altlocationid'].apply(lambda x: int(x),1)
                df = df.set_index(['altlocationid']).sort_index()
                self.bulkdata[key] = df
        except KeyError:
            tk.messagebox.showerror(title='Need to rename columns',message="""This table needs fields with labels
            'altlocationid','stickup','locationname','verticalmeasure','barologgertype'.  They do not have to be
            in order.""")
    def add_well_info_table(self):
        """Creates well-info-table tab and table frame for bulk data uploads; this table is used to match filenames to
        locationids and is used to get elevation and stickup in bulk data

        Returns:

        """
        key = 'well-info-table'
        graphframe, tableframe = self.note_tab_add(key, tabw=5, grph=1)
        self.bulkdatatable[key] = Table(tableframe, dataframe=self.bulkdata[key], showtoolbar=True, showstatusbar=True)
        self.bulkdatatable[key].show()
        self.bulkdatatable[key].showIndex()
        self.bulkdatatable[key].update()

    def grab_dir(self, master):
        key = 'trans-dir'


        self.bulkdatastr[key].set(filedialog.askdirectory(initialdir=self.currentdir,
                                                          title="Select transducer directory"))
        if self.bulkdatastr[key].get() == '' or type(self.bulkdatastr[key].get()) == tuple or \
                self.bulkdatastr[key].get() == 'Double-Click for transducer file directory':
            pass
        else:
            self.currentdir = os.path.dirname(self.bulkdatastr[key].get())
            # https://stackoverflow.com/questions/45357174/tkinter-drop-down-menu-from-excel
            # TODO add excel sheet options to file selection
            filenm, file_extension = os.path.splitext(self.bulkdatastr[key].get())
            ttk.Label(master, text='Match id with list of files.').grid(row=0,column=0,columnspan=3)
            ttk.Label(master, text='Filename').grid(row=1, column=0)
            ttk.Label(master, text='Match Name').grid(row=1, column=1)
            ttk.Label(master, text='   Well ID').grid(row=1, column=2)
            #https://blog.tecladocode.com/tkinter-scrollable-frames/
            container = ttk.Frame(master)
            canvas = tk.Canvas(container)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            if 'well-info-table' in self.bulkdatatable.keys():
                df = self.bulkdatatable['well-info-table'].model.df
                df['locationnamelwr'] = df['locationname'].apply(lambda x: x.lower(),1)
                self.locdict = df['locationnamelwr'].to_dict()
                self.welldict = {y:x for x,y in self.locdict.items()}
                self.locnamedict = dict(zip(df['locationnamelwr'].values,df['locationname'].values))
                self.locnametoid = dict(zip(df['locationname'].values,df.index.values))
                self.welldict['eskdalemx'] = 73
                self.welldict['eskmx'] = 73
                self.welldict['edmx'] = 73
                self.locnamedict['eskdalemx'] = 'Eskdale MX'
                self.locnamedict['eskmx'] = 'Eskdale MX'
                self.locnamedict['edmx'] = 'Eskdale MX'
                self.welldict['tsmx'] = 69
                self.locnamedict['tsmx'] = 'Twin Springs MX'
                self.welldict['snakevnmx'] = 70
                self.welldict['svnmx'] = 70
                self.locnamedict['svnmx'] = 'Snake Valley North MX'
                self.locnamedict['snakevnmx'] = 'Snake Valley North MX'
                self.welldict['snakevsmx'] = 71
                self.welldict['svsmx'] = 71
                self.locnamedict['svsmx'] = 'Snake Valley South MX'
                self.locnamedict['snakevsmx'] = 'Snake Valley South MX'
                self.welldict['coyoteknollsmx'] = 46
                self.welldict['cksmx'] = 46
                self.welldict['ckmx'] = 46
                self.locnamedict['coyoteknollsmx'] = 'Coyote Knolls MX'
                self.locnamedict['cksmx'] = 'Coyote Knolls MX'
                self.locnamedict['ckmx'] = 'Coyote Knolls MX'
                self.welldict['sg23a'] = 72
                self.welldict['pw03baro'] = 9003
                self.locnamedict['pw03baro'] = 'PW03 Baro'
                self.welldict['pw10baro'] = 9027
                self.locnamedict['pw10baro'] = 'PW10 Baro'
                self.welldict['pw19baro'] = 9049
                self.locnamedict['pw19baro'] = 'PW19 Baro'
                self.welldict['sg27a'] = 68
                self.locnamedict['sg27a'] = 'SG27'
                self.welldict['pw15a'] = 39
                self.locnamedict['pw15a'] = 'AG15'
                self.welldict['callao'] = 136
                self.locnamedict['callao'] = 'Callao C119'
                self.welldict['ctvmx'] = 75
                self.locnamedict['ctvmx'] = 'Central Tule MX'
                self.welldict['centraltulemx'] = 75
                self.locnamedict['centraltulemx'] = 'Central Tule MX'
                self.welldict['pw20a'] = 51
                self.welldict['centraltulemx'] = 75
                self.welldict['ctmx'] = 75
            i = 0
            for file in glob.glob(self.bulkdatastr['trans-dir'].get() + '/*'):

                filestr = ll.getfilename(file)
                a = re.split('_|\s', filestr)[0].lower()
                ttk.Label(scrollable_frame, text=filestr).grid(row=i, column=0)
                self.locidmatch[filestr] = tk.StringVar(scrollable_frame)
                self.bulktransfilestr[filestr] = tk.StringVar(scrollable_frame)
                self.bulkcombo[filestr] = ttk.Combobox(scrollable_frame)
                self.bulkcombo[filestr].grid(row=i, column=1)
                e = ttk.Entry(scrollable_frame, textvariable = self.locidmatch[filestr], width=6)
                e.grid(row=i, column=2)
                self.bulkcombo[filestr]['values'] = list(df['locationname'].unique())
                if 'locdict' in self.__dict__.keys():
                    if a in self.locnamedict.keys():
                        self.bulktransfilestr[filestr].set(self.locnamedict[a])
                        self.bulkcombo[filestr].set(self.locnamedict[a])
                        self.locidmatch[filestr].set(self.welldict[a])

                        self.bulkcombo[filestr].bind("<<ComboboxSelected>>", lambda e: print(self.bulkcombo[filestr]))

                                                     #self.locidmatch[filestr].set(self.locnametoid[self.bulkcombo[filestr].get()]))
                i += 1
            #self.filefnd.bind('<Double-ButtonRelease-1>', lambda f: self.grab_dir(dirselectframe))

            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            container.grid(row=2,column=0,columnspan=3)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

    def test_print(self, event):
        print(event.widget['text'])

    def nameparser(self, filestr):
        a = re.split('_|-|\s',filestr)[0]



def main():
    root = tk.Tk()
    feedback = Feedback(root)
    root.mainloop()


# tkinter.mainloop()
# If you put root.destroy() here, it will cause an error if the window is
# closed with the window manager.
if __name__ == "__main__": main()

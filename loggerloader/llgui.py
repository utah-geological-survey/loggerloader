import matplotlib
import babel.numbers
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk, FigureCanvasTkAgg
# Implement the default Matplotlib key bindings.
from matplotlib import style
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, messagebox, ttk
from tkcalendar import DateEntry

import io
import os
import glob
import re
import xml.etree.ElementTree as eletree
import numpy as np
import datetime
from shutil import copyfile
from pylab import rcParams
from xml.etree.ElementTree import ParseError

import pandas as pd
import gzip
import pickle
import time
import platform

from pandastable import plotting, dialogs, util, logfile, Table, SimpleEditor, OrderedDict, MultipleValDialog, TableModel

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

rcParams['figure.figsize'] = 15, 10

try:
    pd.options.mode.chained_assignment = None
except AttributeError:
    pass


class Feedback:

    def __init__(self, master):
        # create main window and configure size and title
        # tk.Tk.__init__(self, *args, **kwargs)
        master.geometry('1400x800')
        master.wm_title("Transducer Processing")
        self.version = "0.9.8"
        self.root = master
        self.main = master
        self.master = master
        # Get platform into a variable
        self.setConfigDir()
        # if not hasattr(self,'defaultsavedir'):
        self.defaultsavedir = os.path.join(os.path.expanduser('~'))

        # self.sheetframes = {}
        self.loadAppOptions()
        # start logging
        self.start_logging()

        try:
            self.root.iconbitmap(r'../data_files/icon.ico')
        except:
            try:
                self.root.iconbitmap(r'G:/My Drive/Python/Pycharm/loggerloader/data_files/icon.ico')
            except:
                pass
        self.currentdir = os.path.expanduser('~')

        # self.dropmenu(master)
        self.createMenuBar()

        self.datastr, self.data, self.datatable, self.combo = {}, {}, {}, {}

        self.entry = {}
        self.locidmatch = {}
        self.bulktransfilestr = {}  # dictionary to store trans file names

        self.fileselectbutt = {}
        self.fileselectcombo = {}
        self.filetype = {}
        self.wellbaroxl = {}
        self.xlcols_date_combo = {}
        self.xlcols_value_combo = {}
        self.xlcols_temp_combo = {}

        self.wellbarocsv = {}

        # jump fix dictionaries
        self.dataminvar = {}
        self.datamaxvar = {}
        self.datamin = {}

        self.datamax = {}
        self.trimbutt = {}
        self.datajumptol = {}
        self.datajump = {}
        self.jumpbutt = {}

        # Create side by side panel areas
        self.panedwindow = ttk.Panedwindow(master, orient='horizontal')
        self.panedwindow.pack(fill='both', expand=True)
        self.process_frame = ttk.Frame(self.panedwindow, width=150, height=400, relief='sunken')
        self.frame2 = ttk.Frame(self.panedwindow, width=400, height=400, relief='sunken')
        self.panedwindow.add(self.process_frame, weight=2)
        self.panedwindow.add(self.frame2, weight=3)

        # add tabs in the frame to the right
        self.notebook = ttk.Notebook(self.frame2)
        self.notebook.pack(fill='both', expand=True)
        self.notelist = {}

        self.projopen = False
        self.newProject()

        # add tabs in the frame to the left
        self.processing_notebook = ttk.Notebook(self.process_frame)
        self.processing_notebook.pack(fill='both', expand=True)
        #self.onewelltab = ttk.Frame(self.processing_notebook)
        #https://stackoverflow.com/questions/3085696/adding-a-scrollbar-to-a-group-of-widgets-in-tkinter
        self.frame = ttk.Frame(self.processing_notebook)
        self.canvas = tk.Canvas(self.frame, borderwidth=0, width=150, height=800)
        self.onewelltab = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((4,4), window=self.onewelltab, anchor="nw", tags="self.frame")
        self.onewelltab.bind("<Configure>", self.onFrameConfigure)

        self.bulkwelltab = ttk.Frame(self.processing_notebook)
        self.processing_notebook.add(self.frame, text='Single-Well Process')
        self.processing_notebook.add(self.bulkwelltab, text='Bulk Well Process')
        self.processing_notebook.bind("<<NotebookTabChanged>>", self.tab_update)

        # SINGLE WELL PROCESSING TAB for left side of application ---------------------------------------------
        # Header image logo and Description seen by user
        frame_header = ttk.Frame(self.onewelltab)
        frame_header.pack(pady=5)
        # Included because some attachments fail when packaging code
        ttk.Label(frame_header, wraplength=450,
                  text=" Utah Geological Survey Scripts for Processing transducer data").grid(row=0, column=0)

        # Data Entry Frame
        self.filefinders('well')  # Select and import well data

        self.outlierremove('well')

        self.filefinders('baro')  # Select and import baro data
        self.outlierremove('baro')
        # Align Data
        self.add_alignment_interface()

        # -----------Manual Data------------------------------------
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
        # validates time number inputs
        self.measvalidation = (self.manframe.register(self.only_meas), '%P')

        self.man_date, self.man_hour, self.man_min, self.man_meas, self.man_datetime = {}, {}, {}, {}, {}
        # labels and date, time, and measure entry for manual measurements
        ttk.Label(self.manframe, text="Date of Measure").grid(row=0, column=1)
        ttk.Label(self.manframe, text="HH").grid(row=0, column=2, columnspan=1, sticky='WENS')
        ttk.Label(self.manframe, text=":").grid(row=0, column=3, columnspan=1, sticky='WENS')
        ttk.Label(self.manframe, text="MM").grid(row=0, column=4, columnspan=1, sticky='WENS')
        ttk.Label(self.manframe, text="Measure").grid(row=0, column=5)
        ttk.Label(self.manframe, text="Units").grid(row=0, column=6)
        self.date_hours_min(0)  # 1st manual measure
        self.date_hours_min(1)  # 2nd manual measure

        # units
        self.manunits = ttk.Combobox(self.manframe, width=5, values=['ft', 'm'], state="readonly")
        self.manunits.grid(row=1, column=6, rowspan=3)
        self.manunits.current(0)

        # locid
        ttk.Label(self.manframe, text="Locationid").grid(row=0, column=6)
        self.man_locid = ttk.Entry(self.manframe, width=11)
        self.man_locid.grid(row=1, column=6, rowspan=3)

        # Tab for entering manual data by file
        # TODO Auto align sheet fields to columns
        manfileframetext = """File with manual data must have datetime, reading, and locationid fields"""
        key = 'manual-single'
        ttk.Label(self.manfileframe, text=manfileframetext).grid(row=0, column=0, columnspan=4)
        self.datastr[key] = tk.StringVar(self.manfileframe)

        man_entry = ttk.Entry(self.manfileframe, textvariable=self.datastr[key], width=80, justify='left')

        man_entry.grid(row=2, column=0, columnspan=4)
        self.fillervals = ['readingdate', 'dtwbelowcasing', 'locid']

        man_entry.bind('<Double-ButtonRelease-1>', lambda event: self.mandiag(event, key='manual-single'))

        self.scombo, self.scombo_choice, self.scombo_label = {}, {}, {}
        self.scombovals = {"Datetime": [3, 0, 15, self.fillervals, 4, 0],
                           "DTW": [3, 1, 15, self.fillervals, 4, 1],
                           "locationid": [3, 2, 15, self.fillervals, 4, 2],
                           "Pick id": [5, 1, 15, [1001, 1002], 5, 2]}

        for ky, vals in self.scombovals.items():
            self.scombo_choice[ky] = tk.StringVar()
            self.scombo_label[ky] = ttk.Label(self.manfileframe, text=ky)
            self.scombo_label[ky].grid(row=vals[0], column=vals[1])

            self.scombo[ky] = ttk.Combobox(self.manfileframe, width=vals[2], values=self.fillervals,
                                           textvariable=self.scombo_choice[ky],
                                           postcommand=lambda: self.man_col_select_single(self.scombo[ky]))
            self.scombo[ky].grid(row=vals[4], column=vals[5])

        self.mandiag(False, key='manual-single')
        ttk.Label(self.manfileframe, text="units").grid(row=3, column=3)
        self.manunits = ttk.Combobox(self.manfileframe, width=5,
                                     values=['ft', 'm'], state="readonly")

        self.manunits.grid(row=4, column=3)
        self.manunits.current(0)

        b = ttk.Button(self.frame_step4,
                       text='Process Manual Data',
                       command=self.proc_man)
        b.grid(column=0, row=2, columnspan=3)

        self.fix_drift_interface()  # Fix Drift Button

        self.add_elevation_interface(self.onewelltab)

        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X)
        save_onewell_frame = ttk.Frame(self.onewelltab)
        save_onewell_frame.pack()
        b = ttk.Button(save_onewell_frame, text='Save csv', command=self.save_one_well)
        b.pack()

        # BULK UPLOAD TAB of left side of application -------------------------------------------------------
        # BulkUploader(self.bulkwelltab)
        dirselectframe = ttk.Frame(self.bulkwelltab)
        dirselectframe.pack()

        self.make_well_info_frame(dirselectframe)

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        # pick directory with transducer files and populate a scrollable window with combobox selections
        filefinderframe = ttk.Frame(dirselectframe)
        filefinderframe.pack()
        ttk.Label(filefinderframe, text='3. Pick directory with relevant well files.').grid(column=1, row=0,
                                                                                            columnspan=2)
        ttk.Label(filefinderframe, text='2. Pick Sampling Network').grid(column=0, row=0, columnspan=1)

        self.datastr['trans-dir'] = tk.StringVar(filefinderframe, value=f'Double-Click for transducer file directory')
        self.filefnd = ttk.Entry(filefinderframe, textvariable=self.datastr['trans-dir'], width=80, state='disabled')
        self.filefnd.grid(column=1, row=1, columnspan=2)

        self.combo_source = ttk.Combobox(filefinderframe,
                                         values=['Snake Valley Wells', 'Wetlands Piezos', 'WRI', 'Other'],
                                         state='disabled')
        self.combo_source.grid(column=0, row=1)
        self.combo_source.current(0)

        filefoundframe = ttk.Frame(dirselectframe)
        self.combo_source.bind("<<ComboboxSelected>>", lambda f: self.grab_trans_dir(filefoundframe))
        self.filefnd.bind('<Double-ButtonRelease-1>', lambda f: self.grab_trans_dir(filefoundframe))
        filefoundframe.pack()

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        applymatchframe = ttk.Frame(dirselectframe)
        applymatchframe.pack()
        self.inputforheadertable = {}

        self.bulk_match_button = tk.Button(applymatchframe,
                                           text='5. Click when done matching files to well names',
                                           command=lambda: self.make_file_info_table(master),
                                           state='disabled')
        self.bulk_match_button.pack()

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        bulk_align_frame = ttk.Frame(dirselectframe)
        bulk_align_frame.pack()
        self.align_bulk_wb_button = tk.Button(bulk_align_frame,
                                              text='6. Align Well-Baro Data',
                                              command=self.align_well_baro_bulk,
                                              state='disabled', fg='red')
        self.align_bulk_wb_button.grid(row=0, column=0)

        self.export_align = tk.IntVar()
        self.export_align_check = tk.Checkbutton(bulk_align_frame,
                                                 text="Export Aligned Data?",
                                                 variable=self.export_align,
                                                 state='disabled')
        self.export_align_check.grid(row=0, column=1)
        self.export_align_check.deselect()

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Label(dirselectframe, text='7. Import Manual Data').pack()
        # self.manfileframe(dirselectframe).pack()
        self.bulk_manfileframe = ttk.Frame(dirselectframe)
        self.bulk_manfileframe.pack()
        self.man_file_frame(self.bulk_manfileframe,key='bulk-manual')

        self.proc_man_bulk_button = tk.Button(self.bulk_manfileframe, text='Process Manual Data',
                                               command=self.proc_man_bulk, fg='red')
        self.proc_man_bulk_button.grid(column=1, row=5, columnspan=2)
        self.proc_man_bulk_button['state'] = 'disabled'

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        bulk_drift_frame = ttk.Frame(dirselectframe)
        bulk_drift_frame.pack()
        self.bfdb = ttk.Button(bulk_drift_frame, text='8. Fix Drift', command=self.bulk_fix_drift)
        self.bfdb.grid(column=0, row=0, columnspan=1, rowspan=2)
        self.bfdb['state'] = 'disabled'
        self.export_drift = tk.IntVar(value=1)
        self.export_drift_check = tk.Checkbutton(bulk_drift_frame,
                                                 text="Export Drift Data?",
                                                 variable=self.export_drift,
                                                 state='disabled')
        self.export_drift_check.grid(row=0, column=1, sticky=tk.W)
        self.export_drift_check.select()

        self.export_drift_graph = tk.IntVar(value=1)
        self.export_drift_graph_check = tk.Checkbutton(bulk_drift_frame,
                                                       text="Graph Data?",
                                                       variable=self.export_drift_graph,
                                                       state='disabled')
        self.export_drift_graph_check.grid(row=1, column=1, sticky=tk.W)
        self.export_drift_graph_check.select()

        ttk.Label(bulk_drift_frame, text='Max Allowed Drift (ft)').grid(row=0, column=2)
        self.max_allowed_drift = tk.DoubleVar(bulk_drift_frame, value=0.3)
        ent = ttk.Entry(bulk_drift_frame, textvariable=self.max_allowed_drift, width=10)
        ent.grid(row=1, column=2)

    def onFrameConfigure(self, event):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def man_file_frame(self, master, key='manual'):
        # self.manfileframe = ttk.Frame(master)

        manfileframetext = """File with manual data must have datetime, reading, and locationid fields"""

        ttk.Label(master, text=manfileframetext).grid(row=0, column=0, columnspan=4)
        self.datastr[key] = tk.StringVar(master)

        man_entry = ttk.Entry(master, textvariable=self.datastr[key], width=80, justify='left')
        man_entry.grid(row=2, column=0, columnspan=4)
        man_entry.bind('<Double-ButtonRelease-1>', lambda e: self.mandiag(e, key=key))

        fillervals = ['readingdate', 'dtwbelowcasing', 'locid']
        self.combo, self.combo_choice, self.combo_label = {}, {}, {}
        self.combovals = {"Datetime": [3, 0, 15, fillervals, 4, 0],
                          "DTW": [3, 1, 15, fillervals, 4, 1],
                          "locationid": [3, 2, 15, fillervals, 4, 2],
                          "Pick id": [5, 1, 15, [1001, 1002], 5, 2]}

        for ky, vals in self.combovals.items():
            self.man_combos(ky, vals, master)

        if self.processing_notebook.index(self.processing_notebook.select()) == 1:
            print('bulk')
            self.combo["Pick id"]["state"] = "disabled"
            self.combo["Pick id"].grid_forget()

        ttk.Label(master, text="units").grid(row=3, column=3)
        self.manunits = ttk.Combobox(master, width=5,
                                     values=['ft', 'm'], state="readonly")
        self.manunits.grid(row=4, column=3)
        self.manunits.current(0)

        # Populates Comboboxes with default file on G drive; if different drive, then passes
        try:
            self.data[key] = pd.read_csv(self.datastr[key].get())
            mancols = list(self.data[key].columns.values)
            for col in mancols:
                if col.lower() in ['datetime', 'date', 'readingdate']:
                    self.combo_choice["Datetime"].set(col)
                    # self.combo["Datetime"].current(mancols.index(col))
                elif col.lower() in ['dtw', 'waterlevel', 'depthtowater', 'water_level',
                                     'level', 'depth_to_water', 'water_depth', 'depth',
                                     'dtwbelowcasing', 'dtw_below_casing']:
                    self.combo_choice["DTW"].set(col)
                elif col.lower() in ['locationid', 'locid', 'id', 'location_id', 'lid']:
                    self.combo_choice['locationid'].set(col)
        except FileNotFoundError:
            pass

    def tab_update(self, event):
        index = event.widget.index('current')
        if 'combo_label' in self.__dict__:
            if index == 1:
                self.combo_label["Pick id"].grid_forget()
                self.combo["Pick id"].grid_forget()
            elif index == 0:
                print("0")

    def make_well_info_frame(self, master):
        # select file for well-info-table
        well_info_frame = ttk.Frame(master)
        well_info_frame.pack()
        key = 'well-info-table'
        self.datastr[key] = tk.StringVar(well_info_frame)
        self.datastr[key].set("ugs_ngwmn_monitoring_locations.csv")

        ttk.Label(well_info_frame, text='1. Input well info file (must be csv)').grid(row=0, column=0, columnspan=3)
        # ttk.Label(well_info_frame, text='must have altlocationid, locationname, stickup, barologgertype, and verticalmeasure').grid(row=1,column=0,columnspan=3)
        e = ttk.Entry(well_info_frame, textvariable=self.datastr[key], width=80)
        e.grid(row=1, column=0, columnspan=2)
        e.bind('<Double-ButtonRelease-1>', lambda f: self.open_file(well_info_frame))
        b = ttk.Button(well_info_frame, text='Process Well Info File', command=self.add_well_info_table)
        b.grid(row=1, column=2)

    def make_file_info_table(self, master):
        """this function creates the file info table in the bulk processing tab; it uses the matched comboboxes
        from grab_trans_dir function

        Args:
            master:

        Returns:

        """
        popup = tk.Toplevel()
        popup.geometry("400x100+200+200")
        tk.Label(popup, text="Examining Directory...").pack()
        pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
        pg.pack()

        key = 'file-info-table'
        # TODO Enter dict and file well info table screening here
        ht = HeaderTable(self.datastr['trans-dir'].get())
        filelist = ht.xle_csv_filelist()
        pg.config(maximum=len(filelist))
        fild = {}
        wdf = {}
        sv = tk.StringVar(popup, value='')
        ttk.Label(popup, textvariable=sv).pack()
        for file in filelist:
            popup.update()
            filestr = getfilename(file)
            # check to see if locationid was matched
            if self.locidmatch[filestr].get() == '' or self.locidmatch[filestr].get() is None:
                print(f"{filestr} not matched")
                pass
            else:
                file_extension = os.path.splitext(file)[1]
                base = os.path.basename(file)
                filid = self.locnametoid.get(filestr, None)
                print(filid)

                if file_extension == '.xle':
                    fild[file], df = ht.xle_head(file)
                elif file_extension == '.csv':
                    fild[file], df = ht.csv_head(file)
                fild[file]['locationid'] = pd.to_numeric(
                    self.locnametoid.get(self.combo.get(fild[file]['file_name'], None).get(), None), errors="coerce",
                    downcast="integer")
                wdf[fild[file]['locationid']] = df.sort_index()
                sv.set(base)
            pg.step()

        self.data['bulk-well'] = pd.concat(wdf, axis=0).sort_index()

        # concatinate file info
        df = pd.DataFrame.from_dict(fild, orient='index')
        # df['locationid'] = df['file_name'].apply(lambda x: f"{self.locnametoid.get(self.combo.get(x,None).get(),None)}",1)
        df['measuring_medium'] = df[['Model_number', 'Location', 'locationid']].apply(lambda x: self.detect_baro(x), 1)
        df = df.reset_index().set_index('file_name').rename(columns={'index': 'full_file_path'})

        graphframe, tableframe = self.note_tab_add(key, tabw=4, grph=1)
        # add graph and table to new tab
        # self.add_graph_table(key, tableframe, graphframe)
        self.datatable[key] = Table(tableframe, dataframe=df, showtoolbar=True, showstatusbar=True)
        self.datatable[key].show()
        self.datatable[key].showIndex()
        self.datatable[key].update()
        self.align_bulk_wb_button['state'] = 'normal'
        self.export_align_check['state'] = 'normal'
        # self.bulk_data_file_button['state'] = 'normal'

        popup.destroy()

    def detect_baro(self, x):
        if pd.isna(x[1]):
            x[1] = 'water'
        if x[0] == "M1.5" or 'baro' in x[1].lower() or x[2] in ('9003', '9049', '9024', '9025', '9027', '9063', '9067','9070', '9066'):
            return "air"
        else:
            return "water"

    def man_combos(self, lab, vals, master):
        """Generates Comboboxes for the manual file input sections"""
        self.combo_choice[lab] = tk.StringVar()
        self.combo_label[lab] = ttk.Label(master, text=lab)
        self.combo_label[lab].grid(row=vals[0], column=vals[1])
        self.combo[lab] = ttk.Combobox(master, width=vals[2],
                                       textvariable=self.combo_choice[lab],
                                       postcommand=lambda: self.man_col_select(self.combo[lab]))
        self.combo[lab].grid(row=vals[4], column=vals[5])

    def man_col_select(self, cmbo):
        if 'manual' in self.data.keys() or 'bulk-manual' in self.data.keys() or 'manual-single' in self.data.keys():
            if 'manual-single' in self.data.keys():
                key = 'manual-single'
            elif 'bulk-manual' in self.data.keys():
                key = 'bulk-manual'
            else:
                key = 'manual'
            mancols = list(self.data[key].columns.values)
            if cmbo == self.combo['Pick id']:
                locids = self.data[key][pd.to_numeric(self.combo['locationid'].get(),
                                                      errors='coerce',
                                                      downcast='integer')].unique()
                # TODO this will cause problems later; change to handle multiple types
                cmbo['values'] = list([pd.to_numeric(loc, downcast='integer', errors='coerce') for loc in locids])
            else:
                cmbo['values'] = mancols

        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.mandiag(True)

    def man_col_select_single(self, cmbo):
        if 'manual' in self.data.keys() or 'bulk-manual' in self.data.keys() or 'manual-single' in self.data.keys():
            if 'manual-single' in self.data.keys():
                key = 'manual-single'
            elif 'bulk-manual' in self.data.keys():
                key = 'bulk-manual'
            else:
                key = 'manual'
            mancols = list(self.data[key].columns.values)
            print(self.scombo['locationid'].get())
            if cmbo == self.scombo['Pick id']:
                locids = self.data[key][self.scombo['locationid'].get()].unique()
                # TODO this will cause problems later; change to handle multiple types
                cmbo['values'] = list([pd.to_numeric(loc, downcast='integer') for loc in locids])
            else:
                cmbo['values'] = [0]

        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.mandiag(True)

    def date_hours_min(self, i):
        ttk.Label(self.manframe, text=str(i + 1)).grid(row=i + 1, column=0)
        # date picker
        self.man_date[i] = DateEntry(self.manframe, width=20, locale='en_US', date_pattern='MM/dd/yyyy')
        self.man_date[i].grid(row=i + 1, column=1, padx=2)
        # time picker
        self.man_hour[i] = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 24)]),
                                        state="readonly")
        self.man_hour[i].grid(row=i + 1, column=2)
        self.man_hour[i].current(0)
        ttk.Label(self.manframe, text=":").grid(row=i + 1, column=3)
        self.man_min[i] = ttk.Combobox(self.manframe, width=2,
                                       values=list([f'{i:02}' for i in range(0, 60)]),
                                       state="readonly")
        self.man_min[i].grid(row=i + 1, column=4)
        self.man_min[i].current(0)
        # measure
        self.man_meas[i] = ttk.Entry(self.manframe, validate="key", validatecommand=self.measvalidation, width=10)
        self.man_meas[i].grid(row=i + 1, column=5, padx=2)

    def filefinders(self, key):
        """Adds the label and entry fields for single raw barometric or level files"""
        datasets = {"well": "1. Select Well Data:",
                    "baro": "2. Select Barometric Data:"}
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        filefinderframe = ttk.Frame(self.onewelltab)
        ttk.Label(filefinderframe, text=datasets[key]).grid(column=0, row=0, columnspan=3)
        ttk.Label(filefinderframe, text='(Right click for refresh.)').grid(column=2, row=0, columnspan=3)

        #ttk.Label(filefinderframe, text=datasets[key]).pack()
        #ttk.Label(filefinderframe, text='(Right click for refresh.)').pack()
        self.datastr[key] = tk.StringVar(filefinderframe, value=f'Double-Click for {key} file')
        self.entry[key] = ttk.Entry(filefinderframe, textvariable=self.datastr[key], width=60)
        self.entry[key].grid(column=0, row=1, columnspan=2)
        #self.entry[key].pack()
        self.entry[key].bind('<Double-ButtonRelease-1>', lambda k: self.wellbarodiag(key))

        self.filetype[key] = tk.StringVar(filefinderframe, value="xle")
        self.fileselectcombo[key] = ttk.Combobox(filefinderframe,width=10,
                                                 values=['xle','Global Water csv', 'Excel', 'csv'],
                                                 state="readonly", textvariable = self.filetype[key])

        self.fileselectcombo[key].grid(column=2, row=1, columnspan=2)
        #self.fileselectcombo[key].current(self.filetype)
        self.fileselectbutt[key] = ttk.Button(filefinderframe,
                                              text='Import data',
                                              command=lambda: self.wellbaroabb(key))
        self.fileselectbutt[key].grid(column=4,row=1,columnspan=1)

        #self.entry[key].bind('<3>', lambda k: self.wellbaroabb(key))
        filefinderframe.pack()

    def outlierremove(self, key):
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        frame_step1_5 = ttk.Frame(self.onewelltab)
        ttk.Label(frame_step1_5, text=f'{key} Fix Jumps and outliers (optional)').grid(column=0, row=0, columnspan=6)
        dataminlab = ttk.Label(frame_step1_5, text='Min. Allowed Value:')
        dataminlab.grid(column=0, row=1)

        self.dataminvar[key] = tk.DoubleVar(frame_step1_5, value=-10000.0)
        self.datamaxvar[key] = tk.DoubleVar(frame_step1_5, value=100000.0)
        self.datamin[key] = ttk.Entry(frame_step1_5, textvariable=self.dataminvar[key], width=10, state='disabled')
        self.datamin[key].grid(column=1, row=1)

        dataminlab = ttk.Label(frame_step1_5, text='Max. Allowed Value:')
        dataminlab.grid(column=2, row=1)
        self.datamax[key] = ttk.Entry(frame_step1_5, textvariable=self.datamaxvar[key], width=10, state='disabled')
        self.datamax[key].grid(column=3, row=1)
        self.trimbutt[key] = ttk.Button(frame_step1_5, text='Trim Extrema', command=lambda: self.trimextrema(key), state='disabled')
        self.trimbutt[key].grid(column=4, row=1)

        datajumplab = ttk.Label(frame_step1_5, text='Jump Tolerance:')
        datajumplab.grid(column=0, row=2)
        self.datajumptol[key] = tk.DoubleVar(frame_step1_5, value=100.0)
        self.datajump[key] = ttk.Entry(frame_step1_5, textvariable=self.datajumptol[key], width=10, state='disabled')
        self.datajump[key].grid(column=1, row=2)
        self.jumpbutt[key] = ttk.Button(frame_step1_5, text='Fix Jumps', command=lambda: self.fixjumps(key),
                                        state='disabled')
        self.jumpbutt[key].grid(column=2, row=2)
        frame_step1_5.pack()
        # self.data[key]

    def trimextrema(self,key):
        if key == 'well' and 'well' in self.data.keys():
            if 'Level' in self.data['well'].columns:
                self.data['well'] = self.data['well'][(self.data['well']['Level'] >= self.dataminvar[key].get()) & (
                            self.data['well']['Level'] <= self.datamaxvar[key].get())]
                graphframe, tableframe = self.note_tab_add('well')
                self.add_graph_table('well', tableframe, graphframe)
        elif key == 'baro' and 'baro' in self.data.keys():
            if 'Level' in self.data['baro'].columns:
                self.data['baro'] = jumpfix(self.data['baro'], 'Level', self.datajumptol[key].get())
                graphframe, tableframe = self.note_tab_add('baro')
                self.add_graph_table('baro', tableframe, graphframe)
                # self.datatable['well'].show()
                # self.datatable['well'].update()
                # self.datatable['well'].show()
        else:
            print('No column named Level')
            pass
        # TODO add dialog to select a column to adjust

    def fixjumps(self,key):
        if key == 'well' and 'well' in self.data.keys():
            if 'Level' in self.data['well'].columns:
                self.data['well'] = jumpfix(self.data['well'], 'Level', self.datajumptol[key].get())
                graphframe, tableframe = self.note_tab_add('well')
                self.add_graph_table('well', tableframe, graphframe)
        elif key == 'baro' and 'baro' in self.data.keys():
            if 'Level' in self.data['baro'].columns:
                self.data['baro'] = jumpfix(self.data['baro'], 'Level', self.datajumptol[key].get())
                graphframe, tableframe = self.note_tab_add('baro')
                self.add_graph_table('baro', tableframe, graphframe)
        else:
            print('No column named Level')
            pass
        # TODO add dialog to select a column to adjust

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
        ttk.Label(frame_step3, text="3. Align Baro and Well Data:").grid(row=0, column=0, columnspan=5)
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

        self.export_wb = tk.IntVar(value=1)
        self.export_single_well_baro = tk.Checkbutton(frame_step3,
                                                      text="Export Well-Baro Data?",
                                                      variable=self.export_wb)
        self.export_single_well_baro.grid(row=2, column=3, sticky=tk.W)
        self.export_single_well_baro.select()

        self.is_vented = tk.IntVar(value=0)
        self.trans_vented = tk.Checkbutton(frame_step3,
                                           text="Vented?",
                                           variable=self.is_vented)
        self.trans_vented.grid(row=2, column=4, sticky=tk.W)
        # self.trans_vented.select()

    def add_elevation_interface(self, master):
        #
        # Elevation Correction Interface
        ttk.Separator(master, orient=tk.HORIZONTAL).pack(fill=tk.X)
        frame_step6 = ttk.Frame(master)
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
        b.grid(row=4, column=0, columnspan=4, pady=5)

    def elevcalc(self):
        key = 'wl-elev'
        mstickup = float(self.wellstickup.get())
        melev = float(self.wellgroundelev.get())
        if self.wellstickupunits.get() == 'm':
            mstickup = mstickup * 3.2808
        elif self.wellgroundelevunits.get() == 'm':
            melev = melev * 3.2808

        # wlevels = ElevateWater(self.datatable['manual'].model.df, melev, mstickup)
        # self.manelevs = wlevels.manual_elevation()
        df = self.datatable['fixed-drift'].model.df
        # wlevels = ElevateWater(self.datatable['fixed-drift'].model.df, melev, mstickup)
        if 'manual-single' in self.data.keys():
            key2 = 'manual-single'
        elif 'bulk-manual' in self.data.keys():
            key2 = 'bulk-manual'
        else:
            key2 = 'manual'

        self.datatable[key2].model.df['waterelevation'] = self.datatable[key2].model.df[
                                                              'dtwbelowcasing'] + mstickup + melev
        self.datatable[key2].update()
        self.manelevs = self.datatable[key2].model.df
        df['waterelevation'] = self.datatable['fixed-drift'].model.df['DTW_WL'] + mstickup + melev

        self.data[key] = df
        graphframe, tableframe = self.note_tab_add(key)
        self.add_graph_table(key, tableframe, graphframe)
        print(self.manelevs)

    def fix_drift(self):
        key = 'fixed-drift'
        if 'well-baro' in self.datatable.keys():
            if 'manual-single' in self.data.keys():
                key2 = 'manual-single'
            elif 'bulk-manual' in self.data.keys():
                key2 = 'bulk-manual'
            else:
                key2 = 'manual'

            self.datatable[key2].model.df['dtwbelowcasing'] = self.datatable[key2].model.df[
                                                                  'dtwbelowcasing'] * -1
            self.datatable[key2].update()

            df, self.drift_info, mxdrft = Drifting(self.datatable[key2].model.df,
                                                      self.datatable['well-baro'].model.df,
                                                      drifting_field='corrwl',
                                                      man_field='dtwbelowcasing',
                                                      well_id= self.datatable[key2].model.df.loc[self.datatable[key2].model.df.first_valid_index(),'locationid'],
                                                      output_field='DTW_WL').process_drift()
            # df, self.drift_info, mxdrft = fix_drift(self.datatable['well-baro'].model.df,
            #                                           self.datatable['manual'].model.df,
            #                                           manmeas='dtwbelowcasing')
            self.max_drift.set(mxdrft)

            if 'Temperature' in df.columns:
                self.data[key] = df[['barometer', 'corrwl', 'DTW_WL','driftcorrection', 'Temperature']]
            else:
                self.data[key] = df[['barometer', 'corrwl', 'DTW_WL', 'driftcorrection']]

            graphframe, tableframe = self.note_tab_add(key)
            self.add_graph_table(key, tableframe, graphframe)
        else:
            tk.messagebox.showinfo(title='Yo!', message='Align the data first!')

    def bulk_fix_drift(self):
        popup = tk.Toplevel()
        popup.geometry("400x400+200+200")
        tk.Label(popup, text="Fixing Drift...").pack()
        pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
        pg.pack()
        bulkdrift = {}
        drift_info = {}
        info = self.datatable['well-info-table'].model.df
        try:
            pg.config(maximum=len(self.data['bulk-well-baro'].index.get_level_values(0).unique()))
        except KeyError:
            tk.messagebox.showinfo(title='Yo!', message='Align the data first!')
        sv = tk.StringVar(popup, value='')
        ttk.Label(popup, textvariable=sv).pack()
        # self.datatable['manual'].model.df['dtwbelowcasing'] = self.datatable['manual'].model.df['dtwbelowcasing'] *-1

        for i in self.data['bulk-well-baro'].index.get_level_values(0).unique():
            popup.update()
            if pd.notnull(i):
                if 'bulk-manual' in self.data.keys():
                    key2 = 'bulk-manual'
                elif 'manual-single' in self.data.keys():
                    key2 = 'manual-single'
                else:
                    key2 = 'manual'
                if int(i) in self.datatable[key2].model.df.index:
                    mandf = self.datatable[key2].model.df.loc[int(i)]
                    wellbaro = self.data['bulk-well-baro'].loc[int(i)]

                    try:
                        df, dfrinf, max_drift = Drifting(mandf,
                                                            wellbaro,
                                                            drifting_field='corrwl',
                                                            man_field='dtwbelowcasing',
                                                            output_field='DTW_WL').process_drift()

                        mstickup = info.loc[i, 'stickup']
                        melev = info.loc[i, 'verticalmeasure']
                        name = info.loc[i, 'locationname']
                        dfrinf['name'] = name
                        drift_info[i] = dfrinf  # .reset_index()
                        if max_drift > self.max_allowed_drift.get():
                            ttk.Label(popup, text=f'{name} drift too high at {max_drift}!').pack()
                            pass

                        else:
                            df['waterelevation'] = df['DTW_WL'] + mstickup + melev
                            df['name'] = name
                            df['locationid'] = i
                            bulkdrift[i] = df.reset_index()
                            # bulkdrift[i] = get_trans_gw_elevations(df, mstickup,  melev, site_number = i, level='corrwl', dtw='DTW_WL')
                        sv.set(f"{name} has a max drift of {max_drift}")
                    except KeyError as err:
                        sv.set("Need More Recent Manual Data")
                        print(err)
                        #sv.set(f"{err}")
                        pass
            pg.step()

        self.data['bulk-fix-drift'] = pd.concat(bulkdrift).set_index(['locationid','DateTime'])
        #self.data['bulk-fix-drift'] = self.data['bulk-fix-drift']
        key = 'drift-info'
        self.data[key] = pd.concat(drift_info, sort=True, ignore_index=True).set_index('name')
        graphframe, tableframe = self.note_tab_add(key)
        self.datatable[key] = Table(tableframe, dataframe=self.data[key], showtoolbar=True, showstatusbar=True)
        self.datatable[key].show()
        self.datatable[key].showIndex()
        self.datatable[key].update()
        popup.destroy()
        if self.export_drift.get() == 1:

            df = self.data['bulk-fix-drift']

            df = df.reset_index()
            print(df.columns)
            df = df.rename(columns={'DateTime': 'readingdate', 'Level': 'measuredlevel', 'Temperature': 'temperature',
                                    'DTW_WL': 'measureddtw'})
            df = df[['locationid', 'readingdate', 'measuredlevel', 'temperature',
                     'measureddtw', 'driftcorrection', 'waterelevation']]

            file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')], defaultextension=".csv")
            df.to_csv(file)

        if self.export_drift_graph.get() == 1:
            pdffile = filedialog.asksaveasfilename(filetypes=[('pdf', '.pdf')], defaultextension=".pdf")
            with PdfPages(pdffile) as pdf:
                popup = tk.Toplevel()
                popup.geometry("500x500+200+200")
                tk.Label(popup, text="Graphing Data...").pack()
                pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
                pg.pack()
                pg.config(maximum=len(self.data['bulk-fix-drift'].index.get_level_values(0).unique()))
                fig = plt.figure(figsize=(5, 5))
                canvas = FigureCanvasTkAgg(fig, master=popup)
                for ind in self.data['bulk-fix-drift'].index.get_level_values(0).unique():
                    popup.update()
                    if pd.notnull(ind):

                        ax = fig.add_subplot(111)
                        fig.canvas.draw()
                        df = self.data['bulk-fix-drift'].loc[ind]
                        df = df.dropna(subset=['waterelevation'])
                        if 'bulk-manual' in self.data.keys():
                            key2 = 'bulk-manual'
                        elif 'manual-single' in self.data.keys():
                            key2 = 'manual-single'
                        else:
                            key2 = 'manual'

                        try:
                            mandf = self.datatable[key2].model.df.loc[ind]
                        except KeyError:
                            mandf = self.datatable['manual-single'].model.df.loc[ind]
                        mandf = mandf.dropna(subset=['waterelevation'])

                        if len(df) > 0 and len(mandf) > 0:
                            title = info.loc[int(ind), 'locationname']
                            ax.plot(df.index, df['waterelevation'], color='blue')
                            ax.scatter(mandf.index, mandf['waterelevation'], color='red')

                            ax.set_ylabel('Water Level Elevation')
                            ax.set_ylim(min(df['waterelevation']) - 0.1, max(df['waterelevation']) + 0.1)
                            ax.set_xlim(df.first_valid_index() - pd.Timedelta(days=3),
                                        df.last_valid_index() + pd.Timedelta(days=3))
                            # ax.tick_params(axis='x', labelrotation=45)
                            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
                            canvas.draw()
                            plt.title(title)
                            pdf.savefig(fig)
                        plt.close()
                        fig.delaxes(ax)
                    pg.step()
                popup.destroy()

    def proc_man(self):
        nbnum = self.manbook.index(self.manbook.select())
        if 'manual-single' in self.data.keys():
            key = 'manual-single'
        elif 'bulk-manual' in self.data.keys():
            key = 'bulk-manual'
        else:
            key = 'manual'
        if nbnum == 0:
            for i in [0, 1]:
                self.man_datetime[i] = pd.to_datetime(
                    f'{self.man_date[i].get()} {self.man_hour[i].get()}:{self.man_min[i].get()}',
                    format='%m/%d/%Y %H:%M')

            df = pd.DataFrame({'readingdate': [self.man_datetime[0], self.man_datetime[1]],
                               'dtwbelowcasing': [float(self.man_meas[0].get()),
                                                  float(self.man_meas[1].get())],
                               'locationid': [self.man_locid.get()] * 2,
                               'units': [self.manunits.get()] * 2})
            if self.manunits.get() == 'm':
                df['dtwbelowcasing'] = df['dtwbelowcasing'] * 3.28084
            self.data[key] = df.set_index(['readingdate'])
            print(self.data[key])
        elif nbnum == 1:
            df = self.data[key].rename(columns={self.scombo['Datetime'].get(): 'readingdate',
                                                self.scombo['DTW'].get(): 'dtwbelowcasing',
                                                self.scombo['locationid'].get(): 'locationid'})
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
                df = df[df.index > self.datatable['well'].model.df.first_valid_index() - pd.DateOffset(days=8)]

            self.data[key] = df[df['locationid'] == pd.to_numeric(self.scombo['Pick id'].get(), downcast='integer')]

        graphframe, tableframe = self.note_tab_add(key)
        self.add_graph_table(key, tableframe, graphframe)

    def bulk_wlelev(self, x, inf, pg, pop):
        pop.update()
        wl = x[1] + inf.loc[x[0], 'stickup'] + inf.loc[x[0], 'verticalmeasure']
        pg.step()
        return wl

    def proc_man_bulk(self):
        key = 'bulk-manual'
        #if 'bulk-manual' in self.data.keys():
        #    key = 'bulk-manual'
        #elif 'manual-single' in self.data.keys():
        #    key = 'manual-single'
        #else:
        #    key = 'manual'

        try:
            df = self.data[key].rename(columns={self.combo['Datetime'].get(): 'readingdate',
                                                self.combo['DTW'].get(): 'dtwbelowcasing',
                                                self.combo['locationid'].get(): 'locationid'})
            df['units'] = self.manunits.get()
            if self.manunits.get() == 'm':
                df['dtwbelowcasing'] = df['dtwbelowcasing'] * 3.28084
            df = df.reset_index()
            df['readingdate'] = df['readingdate'].apply(lambda x: pd.to_datetime(x, infer_datetime_format=True,
                                                                                 errors='ignore'))
            df['dtwbelowcasing'] = df['dtwbelowcasing'].apply(lambda x: -1 * pd.to_numeric(x, errors='coerce'))
            # df = df.set_index(['locationid', 'readingdate'])
            # df = df['dtwbelowcasing']
            info = self.datatable['well-info-table'].model.df
            df = df[df['locationid'].isin(info.index)]

            popup = tk.Toplevel()
            popup.geometry("400x100+200+200")
            tk.Label(popup, text="Calculating manual elevations...").pack()
            pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
            pg.pack()
            pg.config(maximum=len(df.index.get_level_values(0)))

            df['waterelevation'] = df[['locationid', 'dtwbelowcasing']].apply(
                lambda x: self.bulk_wlelev(x, info, pg, popup), 1)
            df = df.set_index(['locationid', 'readingdate'])

            popup.destroy()
            self.data[key] = df
            graphframe, tableframe = self.note_tab_add(key)
            self.add_graph_table(key, tableframe, graphframe)
            self.export_drift_graph_check['state'] = 'normal'
            self.export_drift_check['state'] = 'normal'
            self.bfdb['state'] = 'normal'
            self.proc_man_bulk_button['fg'] = 'green'
        except KeyError as err:
            print(f"Key Error: {err}")
            tk.messagebox.showerror(title='Process Well Info Table First', message="Process Well Info Table First")

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
        elif key == 'bulk-baro':
            self.plot_bulk_baro(graph_frame1)
        toolbar = NavigationToolbar2Tk(canvas, graph_frame1)
        toolbar.update()
        canvas.draw()
        canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        canvas.mpl_connect("key_press_event", self.on_key_press)
        graph_frame1.pack()
        self.sheets[key] = self.datatable[key]

    def plot_bulk_baro(self, graph_frame1):
        key = 'bulk-baro'
        ax = self.datatable[key].showPlotViewer(parent=graph_frame1).ax
        for wellid in self.datatable[key].model.df.index.get_level_values(0).unique():
            ax.plot(self.datatable[key].model.df.loc[wellid, 'Level'], label=wellid)

        ax.set_ylabel('well levels', color='blue')

        ax.legend()

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
        if 'manual-single' in self.data.keys():
            key2 = 'manual-single'
        elif 'bulk-manual' in self.data.keys():
            key2 = 'bulk-manual'
        else:
            key2 = 'manual'
        if key == 'fixed-drift':

            ax.plot(self.datatable[key].model.df['DTW_WL'], color='green', label='unprocessed')
            ax.scatter(self.datatable[key2].model.df.index, self.datatable[key2].model.df['dtwbelowcasing'])
            ax.set_ylabel(f"Depth to Water (ft)")
        elif key == 'wl-elev':
            ax.plot(self.datatable[key].model.df['waterelevation'], color='green', label='unprocessed')
            ax.scatter(self.datatable[key2].model.df.index, self.datatable[key2].model.df['waterelevation'])
            ax.set_ylabel(f"Water Elevation (ft)")
        ax.set_xlim(self.datatable[key2].model.df.first_valid_index() - pd.Timedelta('3 days'),
                    self.datatable[key2].model.df.last_valid_index() + pd.Timedelta('3 days'), )

    def wellbaroabb(self, key):
        if self.datastr[key].get() == '' or type(self.datastr[key].get()) == tuple or self.datastr[
            key].get() == f'Double-Click for {key} file':
            pass
        else:
            if key in ('well'):
                #'xle','raw csv', 'Excel', 'modified csv'
                if self.fileselectcombo[key].get() in ['xle','Global Water csv']:
                    self.data[key] = NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                elif self.fileselectcombo[key].get() in ['Excel']:
                    #self.data[key] = pd.read_excel(self.datastr[key].get())
                    self.wellbaroxl[key] = pd.ExcelFile(self.datastr[key].get())

                    self.openNewWindowxl(key)
                elif self.fileselectcombo[key].get() in ['csv']:
                    self.wellbarocsv[key] = pd.read_csv(self.datastr[key].get())
                    self.openNewWindowcsv(key)

                filenm, self.file_extension = os.path.splitext(self.datastr[key].get())
                if key in self.datamin.keys():
                    self.datamin[key]['state'] = 'normal'
                    self.datamax[key]['state'] = 'normal'
                    self.trimbutt[key]['state'] = 'normal'
                    self.datajump[key]['state'] = 'normal'
                    self.jumpbutt[key]['state'] = 'normal'
                if 'Level' in self.data['well'].columns:
                    self.dataminvar[key].set(self.data['well']['Level'].min())
                    self.datamaxvar[key].set(self.data['well']['Level'].max())
            elif key in ('baro'):
                if self.fileselectcombo[key].get() in ['xle','Global Water csv']:
                    self.data[key] = NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                elif self.fileselectcombo[key].get() in ['Excel']:
                    #self.data[key] = pd.read_excel(self.datastr[key].get())
                    self.wellbaroxl[key] = pd.ExcelFile(self.datastr[key].get())

                    self.openNewWindowxl(key)
                elif self.fileselectcombo[key].get() in ['csv']:
                    self.wellbarocsv[key] = pd.read_csv(self.datastr[key].get())
                    self.openNewWindowcsv(key)

                #self.data[key] = NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                filenm, self.file_extension = os.path.splitext(self.datastr[key].get())
                if key in self.datamin.keys():
                    self.datamin[key]['state'] = 'normal'
                    self.datamax[key]['state'] = 'normal'
                    self.trimbutt[key]['state'] = 'normal'
                    self.datajump[key]['state'] = 'normal'
                    self.jumpbutt[key]['state'] = 'normal'
                if 'Level' in self.data[key].columns:
                    self.dataminvar[key].set(self.data[key]['Level'].min())
                    self.datamaxvar[key].set(self.data[key]['Level'].max())
            elif key in ('manual', 'bulk-manual', 'manual-single'):
                filenm, file_extension = os.path.splitext(self.datastr[key].get())
                if file_extension in ('.xls', '.xlsx'):
                    self.data[key] = pd.read_excel(self.datastr[key].get())
                elif file_extension == '.csv':
                    self.data[key] = pd.read_csv(self.datastr[key].get())
            # add notepad tab
            graphframe, tableframe = self.note_tab_add(key)
            # add graph and table to new tab
            self.add_graph_table(key, tableframe, graphframe)

    def openNewWindowcsv(self,key):

        # Toplevel object which will
        # be treated as a new window
        self.newWindow  = tk.Toplevel(self.master)

        # sets the title of the
        # Toplevel widget
        self.newWindow.title("New Window")

        # sets the geometry of toplevel
        self.newWindow.geometry("200x200")
        #df = pd.read
        # A Label widget to show in toplevel
        #self.data[key] =
        columns = list(self.wellbarocsv[key].columns.values)  # see all sheet names

        tk.Label(self.newWindow , text="Datetime Field").pack()
        self.xlcols_date_combo[key] = ttk.Combobox(self.newWindow , values=columns)
        self.xlcols_date_combo[key].pack()
        tk.Label(self.newWindow , text="Value Field").pack()
        self.xlcols_value_combo[key] = ttk.Combobox(self.newWindow , values=columns)
        self.xlcols_value_combo[key].pack()
        tk.Label(self.newWindow , text="Temperature Field (optional)").pack()
        self.xlcols_temp_combo[key] = ttk.Combobox(self.newWindow , values=columns)
        self.xlcols_temp_combo[key].pack()

        #tk.Label(newWindow, text=self.datastr[key].get()).pack()
        tk.Button(self.newWindow ,text='OoooK', command=lambda: self.xl_cols_match(key)).pack()


    def openNewWindowxl(self,key):

        # Toplevel object which will
        # be treated as a new window
        self.newWindow = tk.Toplevel(self.master)

        # sets the title of the
        # Toplevel widget
        self.newWindow.title("New Window")

        # sets the geometry of toplevel
        self.newWindow.geometry("200x200")
        #df = pd.read
        # A Label widget to show in toplevel
        #self.data[key] =
        sheets = self.wellbaroxl[key].sheet_names  # see all sheet names
        self.sheetcombo = {}
        self.sheetcombo[key] = ttk.Combobox(self.newWindow, values=sheets, state='read only')
        self.sheetcombo[key].pack()
        tk.Label(self.newWindow, text="Datetime Field").pack()
        self.xlcols_date_combo[key] = ttk.Combobox(self.newWindow)
        self.xlcols_date_combo[key].pack()
        tk.Label(self.newWindow, text="Value Field").pack()
        self.xlcols_value_combo[key] = ttk.Combobox(self.newWindow)
        self.xlcols_value_combo[key].pack()
        tk.Label(self.newWindow, text="Temperature Field (optional)").pack()
        self.xlcols_temp_combo[key] = ttk.Combobox(self.newWindow, textvariable='Temperature')
        self.xlcols_temp_combo[key].pack()
        # read a specific sheet to DataFrame
        self.sheetcombo[key].bind("<<ComboboxSelected>>",
                                 lambda event, key=key: self.parse_sheet(key))
        #tk.Label(newWindow, text=self.datastr[key].get()).pack()
        tk.Button(self.newWindow,text='OoooK', command=lambda: self.xl_cols_match(key)).pack()

    def parse_sheet(self, key):
        self.data[key] = self.wellbaroxl[key].parse(self.sheetcombo[key].get())
        #self.xlsheetcols =
        self.xlcols_date_combo[key]['values'] = list(self.data[key].columns.values)

        self.xlcols_value_combo[key]['values'] = list(self.data[key].columns.values)

        self.xlcols_temp_combo[key]['values'] = list(self.data[key].columns.values)

    def xl_cols_match(self, key):
        datecol = self.xlcols_date_combo[key].get()
        valcol = self.xlcols_value_combo[key].get()
        tempcol = self.xlcols_temp_combo[key].get()
        self.data[key] = self.data[key].rename(columns={datecol:'DateTime',
                                                        valcol:'Level',
                                                        tempcol:'Temperature'})
        self.data[key] = self.data[key].reset_index()
        self.data[key]['DateTime'] = pd.to_datetime(self.data[key]['DateTime'])
        self.data[key] = self.data[key].set_index('DateTime')

        #self.wellbaroabb(key)
        # add notepad tab
        graphframe, tableframe = self.note_tab_add(key)
        # add graph and table to new tab
        self.add_graph_table(key, tableframe, graphframe)

        self.newWindow.destroy()

    def wellbarodiag(self, key):

        ftypelist = (("Solinst xle", "*.xle*"), ("csv", "*.csv"),("Excel","*.xlsx"))
        self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir,
                                                         title=f"Select {key} file",
                                                         filetypes=ftypelist))
        self.currentdir = os.path.dirname(self.datastr[key].get())
        ext = os.path.splitext(self.datastr[key].get())[-1]
        extdir ={'.xle':'xle','.csv':'csv','.xlsx':'Excel'}
        #['xle','raw csv', 'Excel', 'solinst csv out']

        self.filetype[key].set(extdir.get(ext,'xle'))
        print(self.filetype[key].get())

        # Action if cancel in file dialog is pressed
        #self.wellbaroabb(key)

    def alignedplot(self):
        """

        Returns: notepad tab with aligned data;
        TODO Add File type combo to improve csv processing
        """
        if 'well' in self.data.keys() and 'baro' in self.data.keys():
            key = 'well-baro'
            if self.is_vented == 1:
                sol = True
            else:
                sol = False

            self.data[key] = well_baro_merge(self.datatable['well'].model.df,
                                                self.datatable['baro'].model.df,
                                                sampint=self.freqint.get(),
                                                vented=sol)
            graphframe, tableframe = self.note_tab_add(key)
            self.add_graph_table(key, tableframe, graphframe)

            if self.export_wb.get() == 1:
                df = self.data[key]
                df.index.name = 'locationid'
                df = df.reset_index()
                file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')], defaultextension=".csv")
                df.to_csv(file)

    def align_well_baro_bulk(self):
        # TODO add feature to recognize global water transducers
        if 'bulk-well' in self.data.keys():
            files = self.datatable['file-info-table'].model.df
            info = self.datatable['well-info-table'].model.df
            wellids = self.data['bulk-well'].index.get_level_values(0).unique()
            mergedf = {}
            popup = tk.Toplevel()
            popup.geometry("400x100+200+200")
            tk.Label(popup, text="Aligning datasets...").pack()
            pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
            pg.pack()
            pg.config(maximum=len(wellids))
            sv = tk.StringVar(popup, value='')
            ttk.Label(popup, textvariable=sv).pack()

            for wellid in wellids:
                popup.update()
                if wellid is not None and pd.notna(wellid) and pd.notnull(wellid):
                    if info.loc[int(wellid), 'barologgertype'] != "None" and info.loc[
                        int(wellid), 'barologgertype'] != "":
                        baroid = pd.to_numeric(info.loc[int(wellid), 'barologgertype'],
                                               downcast='integer', errors='coerce')
                        medium = files[files['locationid'] == wellid]['measuring_medium'].values[0]
                        name = info.loc[int(wellid), "locationname"]

                        ttype = files[files['locationid'] == wellid]['trans type'].values[0]

                        if ttype == 'Solinst':
                            sol = False
                        elif ttype == 'Global Water':
                            sol = True
                        else:
                            sol = False

                        if baroid in files['locationid'].unique() and medium == 'water':
                            mergedf[int(wellid)] = well_baro_merge(self.data['bulk-well'].loc[int(wellid)],
                                                                      self.data['bulk-well'].loc[int(baroid)],
                                                                      vented=sol)
                else:
                    print(f'no baroid for well {wellid}')
                    name = 'No Name'

                sv.set(f"aligning {name} = {wellid}")
                pg.step()
            popup.destroy()
            df = pd.concat(mergedf, names=['locationid'])

            df = df.reset_index()
            df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
            df = df.set_index(['locationid', 'DateTime'])
            df = df[['Level', 'Temperature', 'barometer', 'dbp', 'dwl', 'corrwl']]
            self.data['bulk-well-baro'] = df
            self.align_bulk_wb_button['fg'] = 'green'

            if self.export_align.get() == 1:
                file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')], defaultextension=".csv")
                self.data['bulk-well-baro'].to_csv(file)

    def mandiag(self, event, key='manual'):
        if event:
            self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir,
                                                             title=f"Select {key} file",
                                                             filetypes=[('csv', '.csv')],
                                                             defaultextension=".csv"))

            self.currentdir = os.path.dirname(self.datastr[key].get())

            # https://stackoverflow.com/questions/45357174/tkinter-drop-down-menu-from-excel
            # TODO add excel sheet options to file selection

        # self.graph_frame1.pack()
        if self.datastr[key].get() == '' or self.datastr[key].get() == f'Double-Click for {key} file':
            self.datastr[key].set(f'Double-Click for {key} file')
        else:
            try:
                filenm, file_extension = os.path.splitext(self.datastr[key].get())
                if file_extension in ('.xls', '.xlsx'):
                    self.data[key] = pd.read_excel(self.datastr[key].get())
                elif file_extension == '.csv':
                    self.data[key] = pd.read_csv(self.datastr[key].get())
                print('file read')
                mancols = list(self.data[key].columns.values)
                self.fillervals = mancols
                for col in mancols:
                    if col.lower() in ['datetime', 'date', 'readingdate']:
                        if key == 'manual':
                            self.combo_choice["Datetime"].set(col)
                        else:
                            self.scombo_choice["Datetime"].set(col)
                        # self.combo["Datetime"].current(mancols.index(col))
                    elif col.lower() in ['dtw', 'waterlevel', 'depthtowater', 'water_level',
                                         'level', 'depth_to_water', 'water_depth', 'depth',
                                         'dtwbelowcasing', 'dtw_below_casing']:
                        if key == 'manual' or key=='bulk-manual':
                            self.combo_choice["DTW"].set(col)
                        else:
                            self.scombo_choice["DTW"].set(col)
                    elif col.lower() in ['locationid', 'locid', 'id', 'location_id', 'lid']:
                        if key == 'manual' or key =='bulk-manual':
                            self.combo_choice['locationid'].set(col)
                        else:
                            self.scombo_choice['locationid'].set(col)
            except FileNotFoundError:
                pass

    def save_one_well(self):
        filename = filedialog.asksaveasfilename(confirmoverwrite=True)
        if filename is None:
            print('no')
            return
        else:
            df = self.datatable['wl-elev'].model.df
            df['measureddtw'] = -1*df['DTW_WL']
            df = df.rename(columns={'Temperature':'temperature',
                                    'corrwl':'measuredlevel'})
            df = df.drop(['DTW_WL'], axis=1)
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
            self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir, title="Select well info file"))
            if self.datastr[key].get() == '' or type(self.datastr[key].get()) == tuple or \
                    self.datastr[key].get() == 'Double-Click for transducer file directory':
                pass
            else:
                self.add_well_info_table()

        except KeyError:
            tk.messagebox.showerror(title='Need to rename columns', message="""This table needs fields with labels
            'altlocationid','stickup','locationname','verticalmeasure','barologgertype'.  They do not have to be
            in order.""")

    def add_well_info_table(self):
        """Creates well-info-table tab and table frame for bulk data uploads; this table is used to match filenames to
        locationids and is used to get elevation and stickup in bulk data

        Returns:

        """
        key = 'well-info-table'

        self.currentdir = os.path.dirname(self.datastr[key].get())
        df = pd.read_csv(self.datastr[key].get())
        for col in df.columns:
            df = df.rename(columns={col: col.lower()})
        df = df[df['altlocationid'].notnull()]
        df['altlocationid'] = df['altlocationid'].apply(
            lambda x: int(pd.to_numeric(x, downcast='integer', errors='coerce')),
            1)
        df = df.set_index(['altlocationid']).sort_index()
        # df.index = df.index.astype('int64')
        self.data[key] = df

        graphframe, tableframe = self.note_tab_add(key, tabw=5, grph=1)
        self.datatable[key] = Table(tableframe, dataframe=self.data[key], showtoolbar=True, showstatusbar=True)
        self.datatable[key].show()
        self.datatable[key].showIndex()
        self.datatable[key].update()

        self.filefnd['state'] = 'normal'
        self.combo_source['state'] = 'normal'
        self.proc_man_bulk_button['state'] = 'normal'

    def grab_trans_dir(self, master):
        """grabs directory containing transducer files and inputs filenames into a scrollable canvas with comboboxes to
        match up well names with locationids.

        Args:
            master:

        Returns:
        Dictionary of matches between files and locationids
        TODO make this work for and wri files
        #https://stackoverflow.com/questions/28736028/python-tkinter-reference-in-comboboxes-created-in-for-loop
        """
        key = 'trans-dir'

        self.datastr[key].set(filedialog.askdirectory(initialdir=self.currentdir,
                                                      title="Select transducer directory"))
        if self.datastr[key].get() == '' or type(self.datastr[key].get()) == tuple or \
                self.datastr[key].get() == 'Double-Click for transducer file directory':
            pass
        else:
            ttk.Separator(master, orient=tk.HORIZONTAL).grid(row=0, column=0, columnspan=3, sticky='ew', pady=5)
            self.currentdir = os.path.dirname(self.datastr[key].get())
            # https://stackoverflow.com/questions/45357174/tkinter-drop-down-menu-from-excel
            # TODO add excel sheet options to file selection
            filenm, file_extension = os.path.splitext(self.datastr[key].get())
            ttk.Label(master, text='4. Match id with list of files.').grid(row=1, column=0, columnspan=3)
            ttk.Label(master, text='Filename').grid(row=2, column=0)
            ttk.Label(master, text='Match Name').grid(row=2, column=1)
            ttk.Label(master, text='Well ID').grid(row=2, column=2, sticky=tk.W)
            # https://blog.tecladocode.com/tkinter-scrollable-frames/
            container = ttk.Frame(master)
            canvas = tk.Canvas(container)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollbarx = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
            scrollable_frame = ttk.Frame(canvas)
            if 'well-info-table' in self.datatable.keys():
                df = self.datatable['well-info-table'].model.df
                df['locationnamelwr'] = df['locationname'].apply(lambda x: x.lower(), 1)

                self.locdict = df['locationnamelwr'].to_dict()
                self.welldict = {y: x for x, y in self.locdict.items()}
                self.locnamedict = dict(zip(df['locationnamelwr'].values, df['locationname'].values))
                self.locnametoid = dict(zip(df['locationname'].values, df.index.values))

            syndict = {73: ['Eskdale MX', ['eskmx', 'eskdalemx', 'edmx']],
                       69: ['Twin Springs MX', ['tsmx', 'twinmx', 'twin', 'twin springs mx']],
                       70: ['Snake Valley North MX', ['svnmx', 'snakevnmx', 'northmx']],
                       71: ['Snake Valley South MX', ['svsmx', 'snakevsmx', 'southmx']],
                       46: ['Coyote Knolls MX', ['cksmx', 'ckmx', 'coyoteknollsmx', 'pw17mx']],
                       72: ['Needle Point 23a', ['needle', 'sg23a', 'needpnt']],
                       74: ['Shell-Baker', ['shell', 'shellbaker']],
                       9003: ['PW03 Baro', ['pw03baro']],
                       9027: ['PW10 Baro', ['pw10baro']],
                       9049: ['PW19 Baro', ['pw19baro']],
                       68: ['SG27', ['sg27a']],
                       39: ['AG15', ['pw15', 'ag15', 'pw15a', 'ag15a']],
                       136: ['Callao C119', ['callao', 'callaoag']],
                       75: ['Central Tule MX', ['ctvmx', 'centraltulemx', 'ctulemx', 'ctmx']],
                       51: ['PW20', ['pw20a']]}

            for key, value in syndict.items():
                for syn in value[1]:
                    self.welldict[syn] = key
                    self.locnamedict[syn] = value[0]
            i = 0
            self.filetrace = {}
            for file in glob.glob(self.datastr['trans-dir'].get() + '/*'):
                filew_ext = os.path.basename(file)
                filestr = getfilename(file)
                self.filetrace[filestr] = file
                if self.combo_source.get() == 'Snake Valley Wells':
                    a = re.split('_|\s', filestr)[0].lower()
                elif self.combo_source.get() == 'Wetlands Piezos':
                    try:
                        b = filestr.replace('-_', '-').split('_')[-4].split('-')[-1]
                        a = self.locdict[int(b)]
                    except:
                        a = filestr.lower()
                else:
                    a = filestr.lower()
                ttk.Label(scrollable_frame, text=filestr, width=35).grid(row=i, column=0)
                self.locidmatch[filestr] = tk.StringVar(scrollable_frame)
                self.bulktransfilestr[filestr] = tk.StringVar(scrollable_frame)
                self.combo[filestr] = ttk.Combobox(scrollable_frame)
                self.combo[filestr].grid(row=i, column=1)
                e = ttk.Entry(scrollable_frame, textvariable=self.locidmatch[filestr], width=6)
                e.grid(row=i, column=2)
                # populate each combobox with locationnames from the well info table
                self.combo[filestr]['values'] = list(df.sort_values(['locationname'])['locationname'].unique())
                if 'locdict' in self.__dict__.keys():
                    # this fills in the boxes with best guess names
                    if a in self.locnamedict.keys():
                        self.bulktransfilestr[filestr].set(self.locnamedict[a])
                        self.combo[filestr].set(self.locnamedict[a])
                        self.locidmatch[filestr].set(self.welldict[a])
                        self.inputforheadertable[filew_ext] = self.welldict[a]

                    # this fills in the id number if a name is selected
                    self.combo[filestr].bind("<<ComboboxSelected>>",
                                             lambda event,
                                                    filestr=filestr: self.update_location_dicts(filestr))

                i += 1
            # self.filefnd.bind('<Double-ButtonRelease-1>', lambda f: self.grab_dir(dirselectframe))
            self.bulk_match_button["state"] = "normal"
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            # scrollable_frame.pack(fill='both',side='left')
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

            canvas.configure(yscrollcommand=scrollbar.set, xscrollcommand=scrollbarx.set)
            container.grid(row=3, column=0, columnspan=3)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            scrollbarx.pack(side="bottom", fill="x")

    def update_location_dicts(self, filestr):

        self.locidmatch[filestr].set(self.locnametoid[self.combo[filestr].get()])

    def dropmenu(self, master):
        # menu bars at the top of the main window
        self.root = master
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
        self.save_obj = {}

    def save(self):
        file = filedialog.asksaveasfile(mode="w", filetypes=[('text', '.txt')], defaultextension=".txt")
        if file is None:
            print('No File Selected')
            return
        else:
            file.write("name, key, value\n")
            for key, value in self.datastr.items():
                file.write(f"datastr,{key},{value}\n")
            for key, value in self.combo.items():
                file.write(f"combo, {key},{value}\n")
            for key, value in self.tabstate.items():
                file.write(f"tabstate, {key},{value}\n")
            file.close()
            return

    def open(self):
        filename = filedialog.askopenfilename(filetypes=[('text', '.txt')])
        if filename is None or filename == '':
            return
        else:
            df = pd.read_csv(filename)
            df[['name', 'key', 'value']].apply(lambda x: self.select_type(x), 1)

    def select_type(self, x):
        name = x[0]
        key = x[1]
        obj = x[2]
        if name == 'datastr':
            self.datastr[key] = obj
        elif name == 'combo':
            self.combo[key] = obj
        elif name == 'tabstate':
            self.tabstate[key] = obj
        else:
            pass

    #### dataexplore-----------------------------------------------------------------------------------------------------
    def currentTablePrefs(self):
        """Preferences dialog"""

        table = self.getCurrentTable()
        table.showPreferences()
        return

    def setConfigDir(self):
        """Set up config folder"""

        homepath = os.path.join(os.path.expanduser('~'))
        path = '.dataexplore'
        self.configpath = os.path.join(homepath, path)
        self.pluginpath = os.path.join(self.configpath, 'plugins')
        if not os.path.exists(self.configpath):
            os.mkdir(self.configpath)
            os.makedirs(self.pluginpath)
        return

    def setStyles(self):
        """Set theme and widget styles"""

        style = self.style = tk.Style(self)
        available_themes = self.style.theme_names()

        self.bg = bg = self.style.lookup('TLabel.label', 'background')
        style.configure('Horizontal.TScale', background=bg)
        # set common background style for all widgets because of color issues
        # if plf in ['linux','darwin']:
        #    self.option_add("*background", bg)
        dialogs.applyStyle(self.menu)
        return

    def start_logging(self):
        import logging
        logging.basicConfig(filename=logfile, format='%(asctime)s %(message)s')

    def createMenuBar(self):
        """Create the menu bar for the application. """

        self.menu = tk.Menu(self.main)
        file_menu = tk.Menu(self.menu, tearoff=0)
        # add recent first
        self.createRecentMenu(file_menu)
        filemenuitems = {'01New Project': {'cmd': self.newProject},
                         '02Open Project': {'cmd': lambda: self.loadProject(asksave=True)},
                         '03Close': {'cmd': self.closeProject},
                         '04Save': {'cmd': self.saveProject},
                         '05Save As': {'cmd': self.saveasProject},
                         '06sep': '',
                         '07Import CSV': {'cmd': self.importCSV},
                         '08Import from URL': {'cmd': self.importURL},
                         '08Import Excel': {'cmd': self.importExcel},
                         '09Export CSV': {'cmd': self.exportCSV},
                         '10sep': '',
                         '11Quit': {'cmd': self.quit}}

        self.file_menu = self.createPulldown(self.menu, filemenuitems, var=file_menu)
        self.menu.add_cascade(label='File', menu=self.file_menu['var'])

        editmenuitems = {'01Undo Last Change': {'cmd': self.undo},
                         '02Copy Table': {'cmd': self.copyTable},
                         '03Find/Replace': {'cmd': self.findText},
                         '04Preferences': {'cmd': self.currentTablePrefs}
                         }
        self.edit_menu = self.createPulldown(self.menu, editmenuitems)
        self.menu.add_cascade(label='Edit', menu=self.edit_menu['var'])

        self.sheet_menu = {'01Add Sheet': {'cmd': lambda: self.addSheet(select=True)},
                           '02Remove Sheet': {'cmd': lambda: self.deleteSheet(ask=True)},
                           '03Copy Sheet': {'cmd': self.copySheet},
                           '04Rename Sheet': {'cmd': self.renameSheet},
                           }
        self.sheet_menu = self.createPulldown(self.menu, self.sheet_menu)
        self.menu.add_cascade(label='Sheet', menu=self.sheet_menu['var'])

        self.view_menu = {'01Zoom In': {'cmd': lambda: self._call('zoomIn')},
                          '02Zoom Out': {'cmd': lambda: self._call('zoomOut')},
                          '03Wrap Columns': {'cmd': lambda: self._call('setWrap')},
                          '04sep': '',
                          '05Dark Theme': {'cmd': lambda: self._call('setTheme', name='dark')},
                          '06Bold Theme': {'cmd': lambda: self._call('setTheme', name='bold')},
                          '07Default Theme': {'cmd': lambda: self._call('setTheme', name='default')},
                          }
        self.view_menu = self.createPulldown(self.menu, self.view_menu)
        self.menu.add_cascade(label='View', menu=self.view_menu['var'])

        self.table_menu = {'01Describe Table': {'cmd': self.describe},
                           '02Convert Column Names': {'cmd': lambda: self._call('convertColumnNames')},
                           '03Convert Numeric': {'cmd': lambda: self._call('convertNumeric')},
                           '04Clean Data': {'cmd': lambda: self._call('cleanData')},
                           '05Find Duplicates': {'cmd': lambda: self._call('findDuplicates')},
                           '06Correlation Matrix': {'cmd': lambda: self._call('corrMatrix')},
                           '07Concatenate Tables': {'cmd': self.concat},
                           '08Table to Text': {'cmd': lambda: self._call('showasText')},
                           '09Table Info': {'cmd': lambda: self._call('showInfo')},
                           '10sep': '',
                           '11Transform Values': {'cmd': lambda: self._call('transform')},
                           '12Group-Aggregate': {'cmd': lambda: self._call('aggregate')},
                           '13Cross Tabulation': {'cmd': lambda: self._call('crosstab')},
                           '14Merge/Concat Tables': {'cmd': lambda: self._call('doCombine')},
                           '15Pivot Table': {'cmd': lambda: self._call('pivot')},
                           '16Melt Table': {'cmd': lambda: self._call('melt')},
                           '17Time Series Resampling': {'cmd': lambda: self._call('resample')}
                           }
        self.table_menu = self.createPulldown(self.menu, self.table_menu)
        self.menu.add_cascade(label='Tools', menu=self.table_menu['var'])

        self.plots_menu = {'01Store plot': {'cmd': self.addPlot},
                           '02Clear plots': {'cmd': self.updatePlotsMenu},
                           '03PDF report': {'cmd': self.pdfReport},
                           '04sep': ''}
        self.plots_menu = self.createPulldown(self.menu, self.plots_menu)
        self.menu.add_cascade(label='Plots', menu=self.plots_menu['var'])

        self.help_menu = {'01Online Help': {'cmd': self.online_documentation},
                          '02View Error Log': {'cmd': self.showErrorLog},
                          '03About': {'cmd': self.about}}
        self.help_menu = self.createPulldown(self.menu, self.help_menu)
        self.menu.add_cascade(label='Help', menu=self.help_menu['var'])

        self.main.config(menu=self.menu)
        return

    def showErrorLog(self):
        """Open log file"""

        f = open(logfile, 'r')
        s = ''.join(f.readlines())
        w = tk.Toplevel(self)
        w.grab_set()
        w.transient(self)
        ed = SimpleEditor(w)
        ed.pack(in_=w, fill=tk.BOTH, expand=tk.Y)
        ed.text.insert(tk.END, s)
        return

    def createRecentMenu(self, menu):
        """Recent projects menu"""

        from functools import partial
        recent = self.appoptions['recent']
        recentmenu = tk.Menu(menu)
        menu.add_cascade(label="Open Recent", menu=recentmenu)
        for r in recent:
            recentmenu.add_command(label=r, command=partial(self.loadProject, r))
        return

    def bring_to_foreground(self, set_focus=False):
        self.main.deiconify()
        self.main.attributes('-topmost', True)
        self.main.after_idle(self.main.attributes, '-topmost', False)
        self.main.lift()

        if set_focus:
            # Looks like at least on Windows the following is required for the window
            # to also get focus (deiconify, ..., iconify, deiconify)
            import platform
            if platform.system() != "Linux":
                # http://stackoverflow.com/a/13867710/261181
                self.main.iconify()
                self.main.deiconify()
        return

    def getBestGeometry(self):
        """Calculate optimal geometry from screen size"""

        ws = self.main.winfo_screenwidth()
        hs = self.main.winfo_screenheight()
        self.w = w = ws / 1.4;
        h = hs * 0.7
        x = (ws / 2) - (w / 2);
        y = (hs / 2) - (h / 2)
        g = '%dx%d+%d+%d' % (w, h, x, y)
        return g

    def setGeometry(self):
        self.winsize = self.getBestGeometry()
        self.main.geometry(self.winsize)
        return

    def createPulldown(self, menu, dict, var=None):
        """Create pulldown menu, returns a dict.
        Args:
            menu: parent menu bar
            dict: dictionary of the form -
            {'01item name':{'cmd':function name, 'sc': shortcut key}}
            var: an already created menu
        """

        if var is None:
            var = tk.Menu(menu, tearoff=0)
        items = list(dict.keys())
        items.sort()
        for item in items:
            if item[-3:] == 'sep':
                var.add_separator()
            else:
                command = dict[item]['cmd']
                label = '%-25s' % (item[2:])
                if 'img' in dict[item]:
                    img = dict[item]['img']
                else:
                    img = None
                if 'sc' in dict[item]:
                    sc = dict[item]['sc']
                    # bind command
                    # self.main.bind(sc, command)
                else:
                    sc = None
                var.add('command', label=label, command=command, image=img,
                        compound="left")  # , accelerator=sc)
        dict['var'] = var
        return dict

    def progressDialog(self):

        t = tk.Toplevel(self)
        pb = tk.Progressbar(t, mode="indeterminate")
        pb.pack(side="bottom", fill=tk.X)
        t.title('Progress')
        t.transient(self)
        t.grab_set()
        t.resizable(width=False, height=False)
        return pb

    def loadMeta(self, table, meta):
        """Load meta data for a sheet, this includes plot options and
        table selections"""

        tablesettings = meta['table']
        if 'childtable' in meta:
            childtable = meta['childtable']
            childsettings = meta['childselected']
        else:
            childtable = None
        # load plot options
        opts = {'mplopts': table.pf.mplopts,
                'mplopts3d': table.pf.mplopts3d,
                'labelopts': table.pf.labelopts
                }
        for m in opts:
            if m in meta and meta[m] is not None:
                # util.setAttributes(opts[m], meta[m])
                opts[m].updateFromOptions(meta[m])
                # check options loaded for missing values
                # avoids breaking file saves when options changed
                defaults = plotting.get_defaults(m)
                for key in defaults:
                    if key not in opts[m].opts:
                        opts[m].opts[key] = defaults[key]

        # load table settings
        util.setAttributes(table, tablesettings)
        # load plotviewer
        if 'plotviewer' in meta:
            # print (meta['plotviewer'])
            util.setAttributes(table.pf, meta['plotviewer'])
            table.pf.updateWidgets()

        if childtable is not None:
            table.createChildTable(df=childtable)
            util.setAttributes(table.child, childsettings)

        # redraw col selections
        if type(table.multiplecollist) is tuple:
            table.multiplecollist = list(table.multiplecollist)
        table.drawMultipleCols()
        return

    def saveMeta(self, table):
        """Save meta data such as current plot options"""

        meta = {}
        # save plot options
        meta['mplopts'] = table.pf.mplopts.kwds
        meta['mplopts3d'] = table.pf.mplopts3d.kwds
        meta['labelopts'] = table.pf.labelopts.kwds
        # print (table.pf.mplopts.kwds)

        # save table selections
        meta['table'] = util.getAttributes(table)
        meta['plotviewer'] = util.getAttributes(table.pf)
        # print (meta['plotviewer'])
        # save row colors since its a dataframe and isn't picked up by getattributes currently
        meta['table']['rowcolors'] = table.rowcolors
        # save child table if present
        if table.child != None:
            meta['childtable'] = table.child.model.df
            meta['childselected'] = util.getAttributes(table.child)

        return meta

    def saveAppOptions(self):
        """Save global app options to config dir"""

        appfile = os.path.join(self.configpath, 'app.p')
        file = open(appfile, 'wb')
        pickle.dump(self.appoptions, file, protocol=2)
        file.close()
        return

    def loadAppOptions(self):
        """Load global app options if present"""

        appfile = os.path.join(self.configpath, 'app.p')
        if os.path.exists(appfile):
            self.appoptions = pickle.load(open(appfile, 'rb'))
        else:
            self.appoptions = {}
            self.appoptions['recent'] = []
        return

    def newProject(self, data=None, df=None):
        """Create a new project from data or empty"""

        w = self.closeProject()
        if w == None:
            return
        self.sheets = OrderedDict()
        self.sheetframes = {}  # store references to enclosing widgets
        self.openplugins = {}  # refs to running plugins

        self.data, self.datatable = {}, {}
        self.datastr = {}
        self.entry = {}
        self.locidmatch = {}
        self.bulktransfilestr = {}  # dictionary to store trans file names

        self.filetype = {}
        self.wellbaroxl = {}

        self.wellbarocsv = {}

        # jump fix dictionaries
        self.dataminvar = {}
        self.datamaxvar = {}
        self.datamin = {}

        self.datamax = {}
        self.trimbutt = {}
        self.datajumptol = {}
        self.datajump = {}
        self.jumpbutt = {}

        self.updatePlotsMenu()
        for n in self.notebook.tabs():
            self.notebook.forget(n)
        if data != None:
            for s in sorted(data.keys()):
                if s == 'meta':
                    continue
                df = data[s]['table']
                if 'meta' in data[s]:
                    meta = data[s]['meta']
                else:
                    meta = None
                # try:
                self.addSheet(s, df, meta)
                '''except Exception as e:
                    print ('error reading in options?')
                    print (e)'''
        else:
            pass
        self.filename = None
        self.projopen = True
        self.main.title(f'LoggerLoader v.{self.version} (alpha)')
        return

    def loadProject(self, filename=None, asksave=False):
        """Open project file"""

        w = True
        if asksave == True:
            w = self.closeProject()
        if w == None:
            return

        if filename == None:
            filename = filedialog.askopenfilename(defaultextension='.dexpl"',
                                                  initialdir=self.defaultsavedir,
                                                  filetypes=[("project", "*.dexpl"),
                                                             ("All files", "*.*")],
                                                  parent=self.main)
        if not filename:
            return
        if not os.path.exists(filename):
            print('no such file')
            self.removeRecent(filename)
            return
        ext = os.path.splitext(filename)[1]
        if ext != '.dexpl':
            print('does not appear to be a project file')
            return
        if os.path.isfile(filename):
            # new format uses pickle
            try:
                data = pickle.load(gzip.GzipFile(filename, 'r'))
            except OSError as oe:
                msg = 'DataExplore can no longer open the old format project files.\n' \
                      'if you really need the file revert to pandastable<=0.12.1 and save the data.'
                messagebox.showwarning("Project open error", msg)
                return
            # create backup file before we change anything
            # backupfile = filename+'.bak'
            # pd.to_msgpack(backupfile, data, encoding='utf-8')
        else:
            print('no such file')
            self.quit()
            return
        self.newProject(data)
        self.filename = filename
        self.main.title('%s - DataExplore' % filename)
        self.projopen = True
        self.defaultsavedir = os.path.dirname(os.path.abspath(filename))
        self.addRecent(filename)
        return

    def removeRecent(self, filename):
        """Remove file from recent list"""

        recent = self.appoptions['recent']
        if filename in recent:
            recent.remove(filename)
            self.saveAppOptions()
        return

    def addRecent(self, filename):
        """Add file name to recent projects"""

        recent = self.appoptions['recent']
        if not os.path.abspath(filename) in recent:
            if len(recent) >= 5:
                recent.pop(0)
            recent.append(os.path.abspath(filename))
            self.saveAppOptions()
        return

    def saveProject(self, filename=None):
        """Save project"""

        if filename != None:
            self.filename = filename
        if not hasattr(self, 'filename') or self.filename == None:
            self.saveasProject()
        else:
            self.doSaveProject(self.filename)
        return

    def saveasProject(self):
        """Save as a new filename"""

        filename = filedialog.asksaveasfilename(parent=self.main,
                                                defaultextension='.dexpl',
                                                initialdir=self.defaultsavedir,
                                                filetypes=[("project", "*.dexpl")])
        if not filename:
            return
        self.filename = filename
        self.defaultsavedir = os.path.dirname(os.path.abspath(filename))
        self.doSaveProject(self.filename)
        self.addRecent(filename)
        return

    def doSaveProject(self, filename):
        """Save sheets as dict in msgpack"""

        self._checkTables()
        data = {}
        for i in self.sheets:
            table = self.sheets[i]
            data[i] = {}
            data[i]['table'] = table.model.df
            data[i]['meta'] = self.saveMeta(table)

        # pd.to_msgpack(filename, data, encoding='utf-8')
        # changed to pickle format
        file = gzip.GzipFile(filename, 'w')
        pickle.dump(data, file)
        return

    def _checkTables(self):
        """Check tables before saving that so we are not saving
        filtered copies"""

        for s in self.sheets:
            t = self.sheets[s]
            if t.filtered == True:
                t.showAll()
        return

    def closeProject(self):
        """Close"""

        if self.projopen == False:
            w = False
        else:
            w = messagebox.askyesnocancel("Close Project",
                                          "Save this project?",
                                          parent=self.master)
        if w == None:
            return
        elif w == True:
            self.saveProject()
        else:
            pass
        for n in self.notebook.tabs():
            self.notebook.forget(n)
        self.filename = None
        self.projopen = False
        self.main.title('DataExplore')
        return w

    def importCSV(self):
        """Import csv to a new sheet"""

        self.addSheet(select=True)
        table = self.getCurrentTable()
        table.importCSV(dialog=True)
        return

    def importURL(self):
        """Import CSV from URL"""

        url = simpledialog.askstring("Import url", "Input CSV URL",
                                     parent=self.master)
        if url is not None:
            name = os.path.basename(url)
            df = pd.read_csv(url)
            self.addSheet(sheetname=name, df=df, select=True)
        return

    def exportCSV(self):
        """Import csv to a new sheet"""

        table = self.getCurrentTable()
        table.doExport()
        return

    def importExcel(self, filename=None):
        if filename is None:
            filename = filedialog.askopenfilename(parent=self.master,
                                                  defaultextension='.xls',
                                                  initialdir=os.getcwd(),
                                                  filetypes=[("xls", "*.xls"),
                                                             ("xlsx", "*.xlsx"),
                                                             ("All files", "*.*")])

        data = pd.read_excel(filename, sheetname=None)
        for n in data:
            self.addSheet(n, df=data[n], select=True)
        return

    def load_dataframe(self, df, name=None, select=False):
        """Load a DataFrame into a new sheet
           Args:
            df: dataframe
            name: name of new sheet
            select: set new sheet as selected
        """

        if hasattr(self, 'sheets'):
            self.addSheet(sheetname=name, df=df, select=select)
        else:
            data = {name: {'table': df}}
            self.newProject(data)
        return

    def load_msgpack(self, filename):
        """Load a msgpack file"""

        size = round((os.path.getsize(filename) / 1.0485e6), 2)
        print(size)
        df = pd.read_msgpack(filename)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name)
        return

    def load_pickle(self, filename):
        """Load a pickle file"""

        df = pd.read_pickle(filename)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name)
        return

    def getData(self, name):
        """Get predefined data from dataset folder"""

        filename = os.path.join(self.modulepath, 'datasets', name)
        df = pd.read_csv(filename, index_col=0)
        name = os.path.splitext(os.path.basename(filename))[0]
        self.load_dataframe(df, name, select=True)
        return

    def addSheet(self, sheetname=None, df=None, meta=None, select=False):
        """Add a sheet with new or existing data"""

        names = [self.notebook.tab(i, "text") for i in self.notebook.tabs()]

        def checkName(name):
            if name == '':
                messagebox.showwarning("Whoops", "Name should not be blank.")
                return 0
            if name in names:
                messagebox.showwarning("Name exists", "Sheet name already exists!")
                return 0

        noshts = len(self.notebook.tabs())
        if sheetname == None:
            sheetname = simpledialog.askstring("New sheet name?", "Enter sheet name:",
                                               initialvalue='sheet' + str(noshts + 1))
        if sheetname == None:
            return
        if checkName(sheetname) == 0:
            return
        # Create the table
        main = ttk.PanedWindow(orient=tk.HORIZONTAL)
        self.sheetframes[sheetname] = main
        self.notebook.add(main, text=sheetname)
        f1 = ttk.Frame(main)
        table = Table(f1, dataframe=df, showtoolbar=1, showstatusbar=1)
        f2 = ttk.Frame(main)
        # show the plot frame
        pf = table.showPlotViewer(f2, layout='horizontal')
        # load meta data
        if meta != None:
            self.loadMeta(table, meta)
        # add table last so we have save options loaded already
        main.add(f1, weight=3)
        table.show()
        main.add(f2, weight=4)

        if table.plotted == 'main':
            table.plotSelected()
        elif table.plotted == 'child' and table.child != None:
            table.child.plotSelected()
        self.saved = 0
        self.currenttable = table
        # attach menu state of undo item so that it's disabled after an undo
        # table.undo_callback = lambda: self.toggleUndoMenu('active')
        self.sheets[sheetname] = table

        if select == True:
            ind = self.notebook.index('end') - 1
            s = self.notebook.tabs()[ind]
            self.notebook.select(s)
        return sheetname

    def deleteSheet(self, ask=False):
        """Delete a sheet"""

        s = self.notebook.index(self.notebook.select())
        name = self.notebook.tab(s, 'text')
        w = True
        if ask == True:
            w = messagebox.askyesno("Delete Sheet",
                                    "Remove this sheet?",
                                    parent=self.master)
        if w == False:
            return
        self.notebook.forget(s)
        del self.sheets[name]
        del self.sheetframes[name]
        return

    def copySheet(self, newname=None):
        """Copy a sheet"""

        currenttable = self.getCurrentTable()
        newdata = currenttable.model.df
        meta = self.saveMeta(currenttable)
        self.addSheet(newname, df=newdata, meta=meta)
        return

    def renameSheet(self):
        """Rename a sheet"""

        s = self.notebook.tab(self.notebook.select(), 'text')
        newname = simpledialog.askstring("New sheet name?",
                                         "Enter new sheet name:",
                                         initialvalue=s)
        if newname == None:
            return
        self.copySheet(newname)
        self.deleteSheet()
        return

    def editSheetDescription(self):
        """Add some meta data about the sheet"""
        w = tk.Toplevel(self.main)
        w.grab_set()
        w.transient(self)
        ed = SimpleEditor(w, height=25)
        ed.pack(in_=w, fill=tk.BOTH, expand=tk.Y)
        # ed.text.insert(END, buf.getvalue())
        return

    def getCurrentSheet(self):
        """Get current sheet name"""

        s = self.notebook.index(self.notebook.select())
        name = self.notebook.tab(s, 'text')
        return name

    def getCurrentTable(self):

        s = self.notebook.index(self.notebook.select())
        name = self.notebook.tab(s, 'text')
        table = self.sheets[name]
        return table

    def getSheetList(self):
        return list(self.sheets.keys())

    def describe(self):
        """Describe dataframe"""

        table = self.getCurrentTable()
        df = table.model.df
        d = df.describe()
        table.createChildTable(d, index=True)
        return

    def findText(self):

        table = self.getCurrentTable()
        table.findText()
        return

    def concat(self):
        """Concat 2 tables"""

        vals = list(self.sheets.keys())
        if len(vals) <= 1:
            return
        d = MultipleValDialog(title='Concat',
                              initialvalues=(vals, vals),
                              labels=('Table 1', 'Table 2'),
                              types=('combobox', 'combobox'),
                              parent=self.master)
        if d.result == None:
            return
        else:
            s1 = d.results[0]
            s2 = d.results[1]
        if s1 == s2:
            return
        df1 = self.sheets[s1].model.df
        df2 = self.sheets[s2].model.df
        m = pd.concat([df1, df2])
        self.addSheet('concat-%s-%s' % (s1, s2), m)
        return

    def getStackedData(self):

        df = TableModel.getStackedData()
        self.addSheet(sheetname='stacked-data', df=df)
        return

    def copyTable(self, subtable=False):
        """Copy current table dataframe"""

        table = self.getCurrentTable()
        table.model.df.to_clipboard()
        return

    def pasteTable(self, subtable=False):
        """Paste copied dataframe into current table"""

        # add warning?
        if self.clipboarddf is None:
            return
        df = self.clipboarddf
        table = self.getCurrentTable()
        if subtable == True:
            table.createChildTable(df)
        else:
            model = TableModel(df)
            table.updateModel(model)
        return

    def hidePlot(self):
        name = self.getCurrentSheet()
        pw = self.sheetframes[name]
        pw.forget(1)
        return

    def showPlot(self):
        name = self.getCurrentSheet()
        table = self.sheets[name]
        pw = self.sheetframes[name]
        pw.add(table.pf, weight=2)
        return

    def addPlot(self):
        """Store the current plot so it can be re-loaded"""

        import pickle
        name = self.getCurrentSheet()
        table = self.sheets[name]
        fig = table.pf.fig
        t = time.strftime("%H:%M:%S")
        label = name + '-' + t
        # dump and reload the figure to get a new object
        p = pickle.dumps(fig)
        fig = pickle.loads(p)
        self.plots[label] = fig

        def func(label):
            fig = self.plots[label]
            win = tk.Toplevel()
            win.title(label)
            plotting.addFigure(win, fig)

        menu = self.plots_menu['var']
        menu.add_command(label=label, command=lambda: func(label))
        return

    def updatePlotsMenu(self, clear=True):
        """Clear stored plots"""

        if clear == True:
            self.plots = {}
        menu = self.plots_menu['var']
        menu.delete(4, menu.index(tk.END))
        return

    def pdfReport(self):
        """Create pdf report from stored plots"""

        from matplotlib.backends.backend_pdf import PdfPages
        filename = filedialog.asksaveasfilename(parent=self.main,
                                                defaultextension='.pdf',
                                                initialdir=self.defaultsavedir,
                                                filetypes=[("pdf", "*.pdf")])
        if not filename:
            return
        pdf_pages = PdfPages(filename)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        for p in self.plots:
            fig = self.plots[p]
            canvas = FigureCanvasTkAgg(fig, master=self)
            pdf_pages.savefig(fig)
        pdf_pages.close()
        return

    def undo(self):
        """Restores last version of current table"""

        table = self.getCurrentTable()
        table.undo()
        # self.toggleUndoMenu('disabled')
        return

    def toggleUndoMenu(self, state='active'):
        menu = self.edit_menu['var']
        menu.entryconfigure(0, state=state)
        return

    def _call(self, func, **args):
        """Call a table function from it's string name"""

        table = self.getCurrentTable()
        getattr(table, func)(**args)
        return

    def about(self):
        """About dialog"""

        abwin = tk.Toplevel()
        x = 400
        y = 400
        w = 600
        h = 600
        abwin.geometry('+%d+%d' % (x + w / 2 - 200, y + h / 2 - 200))
        abwin.title('About')
        abwin.transient()
        abwin.grab_set()
        abwin.resizable(width=False, height=False)
        #abwin.configure(background=self.bg)
        #label.grid(row=0, column=0, sticky='ew', padx=4, pady=4)
        pandasver = pd.__version__
        pythonver = platform.python_version()
        mplver = matplotlib.__version__
        ttl = tk.Label(abwin, text=f'Logger Loader v.{self.version}', font = 'Helvetica 18 bold')
        ttl.pack()
        #ttl.grid(row=1, column=0, sticky='news', pady=1, padx=4)

        fm1 = tk.Frame(abwin)
        fm1.pack()
        text1a = 'Processing scripts Written By Paul Inkenbrandt, '
        text1b = 'Utah Geological Survey'
        t1a = tk.Label(fm1, text=text1a)
        t1a.pack(side=tk.LEFT)
        t1b = tk.Label(fm1, text=text1b, fg="blue", cursor="hand2")
        t1b.pack(side=tk.LEFT)
        t1b.bind("<Button-1>", lambda e: self.callback("https://geology.utah.gov"))
        fm2 = tk.Frame(abwin)
        fm2.pack()
        text2a = 'Graphing and Table functions from '
        text2b = 'pandastable by Damien Farrell'
        t2a = tk.Label(fm2, text=text2a)
        t2a.pack(side=tk.LEFT)
        t2b = tk.Label(fm2, text=text2b, fg="blue", cursor="hand2")
        t2b.pack(side=tk.LEFT)
        t2b.bind("<Button-1>", lambda e: self.callback("https://github.com/dmnfarrell/pandastable"))
        text3 = 'This program is free software; you can redistribute it and/or\n' \
               + 'modify it under the terms of the GNU General Public License\n' \
               + 'as published by the Free Software Foundation; either version 3\n' \
               + 'of the License, or (at your option) any later version.'
        lic = tk.Label(abwin, text=text3)
        lic.pack()
        text4 = f'Using Python v{pythonver}'
        pyver = tk.Label(abwin, text=text4, fg="blue", cursor="hand2")
        pyver.pack()
        pyver.bind("<Button-1>", lambda e: self.callback("https://www.python.org/"))
        text5 = f'pandas v{pandasver}'
        pdver = tk.Label(abwin, text=text5, fg="blue", cursor="hand2")
        pdver.pack()
        pdver.bind("<Button-1>", lambda e: self.callback("https://pandas.pydata.org/"))
        text6 = f'matplotlib v{mplver}'
        pltver = tk.Label(abwin, text=text6, fg="blue", cursor="hand2")
        pltver.pack()
        pltver.bind("<Button-1>", lambda e: self.callback("https://matplotlib.org/"))
        #tmp.grid(row=2, column=0, sticky='news', pady=1, padx=4)
        return

    def callback(self, url):
        webbrowser.open_new(url)

    def online_documentation(self, event=None):
        """Open the online documentation"""
        link = 'https://github.com/utah-geological-survey/loggerloader/wiki'
        self.callback(link)
        return

    def quit(self):
        self.main.destroy()
        return

def main():
    root = tk.Tk()
    feedback = Feedback(root)
    root.mainloop()

###################################################################################################################
# MAIN CODE


#####################################################################################################################
def elevatewater(df, elevation, stickup,
                 dtw_field='dtwbelowcasing', wtr_elev_field='waterelevation', flip=False):
    """treats both manual and transducer data; easiest to calculate manual elevations first
    and do fix-drift class on raw well pressure

    Args:
        df: pandas dataframe containing water elevation data
        elevation: ground elevation at wellsite
        stickup: stickup of casing above ground surface; can be float or series
        dtw_field: field in df that denotes depth to water (should be negative for below ground)
        wtr_elev_field: field to store groundwater elevation in
        flip = if True, multiplies dataset by -1; use this if inputing pressure data

    Notes:
        increase in pressure = increase in water elevation;
        increase in pressure = decrease in depth to water;
        increase in depth to water = decrease in water elevation;

    Examples:
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'dtwbelowcasing':[1,10,14,52,10,8]}
        >>> df = pd.DataFrame(manual)
        >>> ew = ElevateWater(df, 4000, 1)
        >>> ew.stickup
        1
        >>> ew.elevation
        4000
    """

    if flip:
        df[dtw_field] = df[dtw_field] * -1
    else:
        pass

    df[wtr_elev_field] = df[dtw_field] + elevation + stickup
    return df


class Drifting(object):

    def __init__(self, manual_df, transducer_df, drifting_field='corrwl', man_field='measureddtw', daybuffer=3,
                 output_field='waterelevation', trim_end=False, well_id=None, engine=None):
        """Remove transducer drift from nonvented transducer data. Faster and should produce same output as fix_drift_stepwise

        Args:
            well (pd.DataFrame): Pandas DataFrame of merged water level and barometric data; index must be datetime
            manualfile (pandas.core.frame.DataFrame): Pandas DataFrame of manual measurements
            corrwl (str): name of column in well DataFrame containing transducer data to be corrected
            manmeas (str): name of column in manualfile Dataframe containing manual measurement data
            outcolname (str): name of column resulting from correction
            wellid (int): unique id for well being analyzed; defaults to None
            conn_file_root: database connection engine; defaults to None
            well_table (str): name of table in database that contains well information; Defaults to None
            search_tol (int): Amount of time, in days to search for readings in the database; Defaults to 3
            trim_end (bool): Removes jumps from ends of data breakpoints that exceed a threshold; Defaults to True

        Returns:
            (tuple): tuple containing:

                - wellbarofixed (pandas.core.frame.DataFrame):
                    corrected water levels with bp removed
                - driftinfo (pandas.core.frame.DataFrame):
                    dataframe of correction parameters
                - max_drift (float):
                    maximum drift for all breakpoints

        Examples:

            >>> manual = {'dates':['6/11/1991','2/1/1999'],'measureddtw':[1,10]}
            >>> man_df = pd.DataFrame(manual)
            >>> man_df.set_index('dates',inplace=True)
            >>> datefield = pd.date_range(start='6/11/1991',end='2/1/1999',freq='12H')
            >>> df = pd.DataFrame({'dates':datefield,'corrwl':np.sin(range(0,len(datefield)))})
            >>> df.set_index('dates',inplace=True)
            >>> wbf, fd = fix_drift(df, man_df, corrwl='corrwl', manmeas='measureddtw', outcolname='DTW_WL')
            Processing dates 1991-06-11T00:00:00.000000000 to 1999-02-01T00:00:00.000000000
            First man = 1.000, Last man = 10.000
                First man date = 1991-06-11 00:00,
                Last man date = 1999-02-01 00:00
                -------------------
                First trans = 0.000, Last trans = -0.380
                First trans date = 1991-06-11 00:00
                Last trans date = :1999-01-31 12:00
            Slope = -0.003 and Intercept = -1.000
        """

        self.slope_man = {}
        self.slope_trans = {}
        self.first_offset = {}
        self.last_offset = {}
        self.slope = {}
        self.intercept = {}
        self.drift = {}
        self.first_man = {}
        self.first_trans = {}
        self.last_man = {}
        self.last_trans = {}
        self.bracketedwls = {}
        self.drift_features = {}
        self.first_man_date = {}
        self.last_man_date = {}
        self.first_trans_date = {}
        self.last_trans_date = {}
        self.first_man_julian_date = {}
        self.last_man_julian_date = {}
        self.first_trans_julian_date = {}
        self.last_trans_julian_date = {}
        self.well_id = well_id
        self.engine = engine
        self.breakpoints = []
        self.levdt = {}
        self.lev = {}
        self.daybuffer = daybuffer
        self.wellbarofixed = pd.DataFrame()
        self.drift_sum_table = pd.DataFrame()
        self.trim_end = trim_end

        self.manual_df = self.datesort(manual_df)
        self.manual_df['julian'] = self.manual_df.index.to_julian_date()

        self.transducer_df = self.datesort(transducer_df)
        self.transducer_df['julian'] = self.transducer_df.index.to_julian_date()

        self.drifting_field = drifting_field
        self.man_field = man_field
        self.output_field = output_field

    def process_drift(self):
        self.breakpoints_calc()
        for i in range(len(self.breakpoints) - 1):
            # self.bracketed_wls(i)
            self.beginning_end(i)
            if len(self.bracketedwls[i]) > 0:
                if self.trim_end:
                    self.bracketedwls[i] = dataendclean(self.bracketedwls[i], self.drifting_field, jumptol=0.5)
                #self.endpoint_import(i)
                self.endpoint_status(i)
                self.slope_intercept(i)
                self.drift_add(i)
                self.drift_data(i)
                self.drift_print(i)
        self.combine_brackets()
        self.drift_summary()
        return self.wellbarofixed, self.drift_sum_table, self.max_drift

    def beginning_end(self, i):
        df = self.transducer_df[
            (self.transducer_df.index >= self.breakpoints[i]) & (self.transducer_df.index < self.breakpoints[i + 1])]
        df = df.dropna(subset=[self.drifting_field])
        df = df.sort_index()
        # print(i)
        # print(df)
        if len(df) > 0:
            self.manual_df['datetime'] = self.manual_df.index

            self.first_man_julian_date[i] = self.fcl(self.manual_df['julian'], self.breakpoints[i])
            self.last_man_julian_date[i] = self.fcl(self.manual_df['julian'], self.breakpoints[i + 1])
            self.first_man_date[i] = self.fcl(self.manual_df['datetime'], self.breakpoints[i])
            self.last_man_date[i] = self.fcl(self.manual_df['datetime'], self.breakpoints[i + 1])
            self.first_man[i] = self.fcl(self.manual_df[self.man_field],
                                         self.breakpoints[i])  # first manual measurement
            self.last_man[i] = self.fcl(self.manual_df[self.man_field],
                                        self.breakpoints[i + 1])  # last manual measurement

            self.first_trans[i] = df.loc[df.first_valid_index(), self.drifting_field]
            self.last_trans[i] = df.loc[df.last_valid_index(), self.drifting_field]
            self.first_trans_julian_date[i] = df.loc[df.first_valid_index(), 'julian']
            self.last_trans_julian_date[i] = df.loc[df.last_valid_index(), 'julian']
            self.first_trans_date[i] = df.first_valid_index()
            self.last_trans_date[i] = df.last_valid_index()
            self.bracketedwls[i] = df
        else:
            self.bracketedwls[i] = df
            pass

    @staticmethod
    def fcl(df, dtobj):
        """
        Finds closest date index in a dataframe to a date object

        Args:
            df (pd.DataFrame):
                DataFrame
            dtobj (datetime.datetime):
                date object

        taken from: http://stackoverflow.com/questions/15115547/find-closest-row-of-dataframe-to-given-time-in-pandas
        """
        return df.iloc[np.argmin(np.abs(pd.to_datetime(df.index) - dtobj))]  # remove to_pydatetime()

    @staticmethod
    def datesort(df):
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def breakpoints_calc(self):
        """Finds break-point dates in transducer file that align with manual measurements
        and mark end and beginning times of measurement.
        The transducer file will be split into chunks based on these dates to be processed for drift and corrected.

        Returns:
            list of breakpoints for the transducer file

        Examples:

            >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'],'man_read':[1,10,14,52,10,8]}
            >>> man_df = pd.DataFrame(manual)
            >>> man_df.set_index('dates',inplace=True)
            >>> datefield = pd.date_range(start='1/1/1995',end='12/15/2006',freq='3D')
            >>> df = pd.DataFrame({'dates':datefield,'data':np.random.rand(len(datefield))})
            >>> df.set_index('dates',inplace=True)
            >>> drft = Drifting(man_df,df,'data','man_read')
            >>> drft.get_breakpoints(man_df,df,'data')[1]
            numpy.datetime64('1999-02-01T00:00:00.000000000')
        """

        wellnona = self.transducer_df.dropna(subset=[self.drifting_field]).sort_index()
        wellnona = wellnona[wellnona.index.notnull()]
        self.manual_df = self.manual_df[self.manual_df.index.notnull()].dropna(subset=[self.man_field]).sort_index()

        self.manual_df = self.manual_df[
            (self.manual_df.index >= wellnona.first_valid_index() - pd.Timedelta(f'{self.daybuffer:.0f}D'))]

        if len(self.manual_df) > 0:

            # add first transducer time if it preceeds first manual measurement
            if self.manual_df.first_valid_index() > wellnona.first_valid_index():
                self.breakpoints.append(wellnona.first_valid_index())

            # add all manual measurements
            for ind in self.manual_df.index:
                # breakpoints.append(fcl(wellnona, manualfile.index[i]).name)
                self.breakpoints.append(ind)

            # add last transducer time if it is after last manual measurement
            if self.manual_df.last_valid_index() < wellnona.last_valid_index():
                self.breakpoints.append(wellnona.last_valid_index())

            # convert to datetime
            self.breakpoints = pd.Series(self.breakpoints)
            self.breakpoints = pd.to_datetime(self.breakpoints)
            # sort values in chronological order
            self.breakpoints = self.breakpoints.sort_values().drop_duplicates()
            # remove all duplicates
            self.breakpoints = self.breakpoints[~self.breakpoints.index.duplicated(keep='first')]
            # convert to list
            self.breakpoints = self.breakpoints.values
        else:
            print("No Breakpoints can be established as manual data do not align with imported data")

    def drift_summary(self):
        self.drift_sum_table = pd.DataFrame(self.drift_features).T
        self.max_drift = self.drift_sum_table['drift'].abs().max()

    def slope_intercept(self, i):
        """
        Calculates slope and offset (y-intercept) between manual measurements and transducer readings.
        Julian date can be any numeric datetime.
        Use df.index.to_julian_date() function in pandas to convert from a datetime index to julian date

        Args:
            first_man (float): first manual reading
            first_man_julian_date (float): julian date of first manual reading
            last_man (float): last (most recent) manual reading
            last_man_julian_date (float):  julian date of last (most recent) manual reading
            first_trans (float): first transducer reading
            first_trans_julian_date (float):  julian date of first manual reading
            last_trans (float): last (most recent) transducer reading
            last_trans_julian_date (float): julian date of last transducer reading

        Returns:
            slope, intercept, manual slope, transducer slope, drift

        Examples:

            >>> calc_slope_and_intercept(0,0,5,5,1,1,6,6)
            (0.0, 1, 1.0, 1.0)

            >>> calc_slope_and_intercept(0,0,5,5,7,0,0,7)
            (-2.0, 7, 1.0, -1.0)
        """
        self.slope_man[i] = 0
        self.slope_trans[i] = 0
        self.first_offset[i] = 0
        self.last_offset[i] = 0

        # if there is not a manual measurement at the start of the period,
        # set separation between trans and man to 0
        if self.first_man[i] is None:
            try:
                self.last_offset[i] = self.last_trans[i] - self.last_man[i]
            except TypeError:
                print('Errorr')
                self.last_offset[i] = 0

            self.first_man_julian_date[i] = self.first_trans_julian_date[i]
            self.first_man[i] = self.first_trans[i]

        # if there is not a manual measurement at the end of the period, use
        elif self.last_man[i] is None:
            self.first_offset[i] = self.first_trans[i] - self.first_man[i]
            self.last_man_julian_date[i] = self.last_trans_julian_date[i]
            self.last_man[i] = self.last_trans[i]

        # If manual measurements exist for both the end and beginning of the period
        else:
            self.first_offset[i] = self.first_trans[i] - self.first_man[i]
            self.last_offset[i] = self.last_trans[i] - self.last_man[i]
            self.slope_man[i] = (self.first_man[i] - self.last_man[i]) / (
                    self.first_man_julian_date[i] - self.last_man_julian_date[i])
            self.slope_trans[i] = (self.first_trans[i] - self.last_trans[i]) / (
                    self.first_trans_julian_date[i] - self.last_trans_julian_date[i])

        self.slope[i] = self.slope_trans[i] - self.slope_man[i]

        if self.first_offset[i] == 0:
            self.intercept[i] = self.last_offset[i]
        else:
            self.intercept[i] = self.first_offset[i]

        return self.slope[i], self.intercept[i], self.slope_man[i], self.slope_trans[i]

    def drift_add(self, i):
        """
        Uses slope and offset from `slope_intercept` to correct for transducer drift

        Args:
            df (pd.DataFrame): transducer readings table
            corrwl (str): Name of column in df to calculate drift
            outcolname (str): Name of results column for the data
            m (float): slope of drift (from calc_slope_and_intercept)
            b (float): intercept of drift (from calc_slope_and_intercept)

        Returns:
            pandas dataframe: drift columns and data column corrected for drift (outcolname)

        Examples:

            >>> df = pd.DataFrame({'date':pd.date_range(start='1900-01-01',periods=101,freq='1D'),
            "data":[i*0.1+2 for i in range(0,101)]});
            >>> df.set_index('date',inplace=True);
            >>> df['julian'] = df.index.to_julian_date();
            >>> print(calc_drift(df,'data','gooddata',0.05,1)['gooddata'][-1])
            6.0
        """
        # datechange = amount of time between manual measurements
        df = self.bracketedwls[i]

        total_date_change = self.last_trans_julian_date[i] - self.first_trans_julian_date[i]
        self.drift[i] = self.slope[i] * total_date_change
        df['datechange'] = df['julian'] - self.first_trans_julian_date[i]

        df['driftcorrection'] = df['datechange'].apply(lambda x: x * self.slope[i], 1)
        df['driftcorrwoffset'] = df['driftcorrection'] + self.intercept[i]
        df[self.output_field] = df[self.drifting_field] - df['driftcorrwoffset']
        df = df.drop(['datechange'], axis=1)
        self.bracketedwls[i] = df

        return df, self.drift[i]

    def drift_data(self, i):
        """Packages all drift calculations into a dictionary. Used by `fix_drift` function.

        Args:
            first_man (float): First manual measurement
            first_man_date (datetime): Date of first manual measurement
            last_man (float): Last manual measurement
            last_man_date (datetime): Date of last manual measurement
            first_trans (float): First Transducer Reading
            first_trans_date (datetime): Date of first transducer reading
            last_trans (float): Last transducer reading
            last_trans_date (datetime): Date of last transducer reading
            b (float): Offset (y-intercept) from calc_slope_and_intercept
            m (float): slope from calc_slope_and_intercept
            slope_man (float): Slope of manual measurements
            slope_trans (float): Slope of transducer measurments
            drift (float): drift from calc slope and intercept

        Returns:
            dictionary drift_features with standardized keys
        """

        self.drift_features[i] = {'t_beg': self.first_trans_date[i],
                                  'man_beg': self.first_man_date[i],
                                  't_end': self.last_trans_date[i],
                                  'man_end': self.last_man_date[i],
                                  'slope_man': self.slope_man[i],
                                  'slope_trans': self.slope_trans[i],
                                  'intercept': self.intercept[i],
                                  'slope': self.slope[i],
                                  'first_meas': self.first_man[i],
                                  'last_meas': self.last_man[i],
                                  'first_trans': self.first_trans[i],
                                  'last_trans': self.last_trans[i], 'drift': self.drift[i]}

    @staticmethod
    def ine(x, dtype):
        if x is None or pd.isna(x):
            return ''
        else:
            if dtype == 'f':
                return '9.3f'
            elif dtype == 'd':
                return '%Y-%m-%d %H:%M'
            elif dtype == 'sf':
                return '.3f'
            elif dtype == 'sl':
                return '9.5f'
            else:
                return ''

    def drift_print(self, i):
        a1 = self.first_man[i]
        a2 = self.last_man[i]
        b1 = self.first_man_date[i]
        b2 = self.last_man_date[i]
        c1 = self.first_trans[i]
        c2 = self.last_trans[i]
        d1 = self.first_trans_date[i]
        d2 = self.last_trans_date[i]
        e1 = self.slope_man[i]
        e2 = self.slope_trans[i]
        if self.well_id:
            print(f'Well ID {self.well_id}')
        print("_____________________________________________________________________________________")
        print("-----------|    First Day     |   First   |     Last Day     |   Last    |   Slope   |")
        print(
            f"    Manual | {'   No Data      ' if pd.isna(b1) else b1:{self.ine(b1, 'd')}} | {a1:{self.ine(a1, 'f')}} | {'   No Data        ' if pd.isna(b2) else b2:{self.ine(b2, 'd')}} | {a2:{self.ine(a2, 'f')}} | {e1:{self.ine(e1, 'sl')}} |")
        print(
            f"Transducer | {d1:{self.ine(d1, 'd')}} | {c1:{self.ine(c1, 'f')}} | {d2:{self.ine(d2, 'd')}} | {c2:{self.ine(c2, 'f')}} | {e2:{self.ine(e2, 'sl')}} |")
        print("---------------------------------------------------------------------------------------------")
        print(
            f"Slope = {self.slope[i]:{self.ine(self.slope[i], 'sf')}} and Intercept = {self.intercept[i]:{self.ine(self.intercept[i], 'sf')}}")
        print(f"Drift = {self.drift[i]:}")
        print(" -------------------")

    def endpoint_status(self, i):
        if np.abs(self.first_man_date[i] - self.first_trans_date[i]) > pd.Timedelta(f'{self.daybuffer:.0f}D'):
            print(f'No initial actual manual measurement within {self.daybuffer:} days of {self.first_trans_date[i]:}.')

            if (len(self.levdt) > 0) and (pd.notna(self.levdt[i])):
                if (self.first_trans_date[i] - datetime.timedelta(days=self.daybuffer) < pd.to_datetime(self.levdt[i])):
                    print("Pulling first manual measurement from database")
                    self.first_man[i] = self.lev[i]
                    self.first_man_julian_date[i] = pd.to_datetime(self.levdt[i]).to_julian_date()
            else:
                print('No initial transducer measurement within {:} days of {:}.'.format(self.daybuffer,
                                                                                         self.first_man_date[i]))
                self.first_man[i] = None
                self.first_man_date[i] = None

        if np.abs(self.last_trans_date[i] - self.last_man_date[i]) > pd.Timedelta(f'{self.daybuffer:.0f}D'):
            print(f'No final manual measurement within {self.daybuffer:} days of {self.last_trans_date[i]:}.')
            self.last_man[i] = None
            self.last_man_date[i] = None

        # intercept of line = value of first manual measurement
        if pd.isna(self.first_man[i]):
            print('First manual measurement missing between {:} and {:}'.format(self.breakpoints[i],
                                                                                self.breakpoints[i + 1]))

        elif pd.isna(self.last_man[i]):
            print('Last manual measurement missing between {:} and {:}'.format(self.breakpoints[i],
                                                                               self.breakpoints[i + 1]))

    def combine_brackets(self):
        dtnm = self.bracketedwls[0].index.name
        # print(dtnm)
        df = pd.concat(self.bracketedwls, sort=True)
        df = df.reset_index()
        df = df.set_index(dtnm)
        self.wellbarofixed = df.sort_index()


def get_stickup(stdata, site_number, stable_elev=True, man=None):
    """
    Finds well stickup based on stable elev field

    Args:
        stdata (pd.DataFrame): pandas dataframe of well data (well_table)
        site_number (int): LocationID of site (wellid)
        stable_elev (bool): True if elevation should come from stdata table; Defaults to True
        man (pd.DataFrame): defaults to None; dataframe of manual readings

    Returns:
        stickup height (float)

    Examples:

        >>> stdata = pd.DataFrame({'wellid':[200],'stickup':[0.5],'wellname':['foo']})
        >>> get_stickup(stdata, 200)
        0.5

        >>> stdata = pd.DataFrame({'wellid':[200],'stickup':[None],'wellname':['foo']})
        >>> get_stickup(stdata, 200)
        Well ID 200 missing stickup!
        0

        >>> stdata = pd.DataFrame({'wellid':[10],'stickup':[0.5],'wellname':['foo']})
        >>> manual = {'dates':['6/11/1991','2/1/1999','8/5/2001','7/14/2000','8/19/2002','4/2/2005'], 'measureddtw':[1,10,14,52,10,8],'locationid':[10,10,10,10,10,10],'current_stickup_height':[0.8,0.1,0.2,0.5,0.5,0.7]}
        >>> man_df = pd.DataFrame(manual)
        >>> get_stickup(stdata, 10, stable_elev=False, man=man_df)
        0.7
    """
    if stable_elev:
        # Selects well stickup from well table; if its not in the well table, then sets value to zero
        if pd.isna(stdata['stickup'].values[0]):
            stickup = 0
            print('Well ID {:} missing stickup!'.format(site_number))
        else:
            stickup = float(stdata['stickup'].values[0])
    else:
        # uses measured stickup data from manual table
        stickup = man.loc[man.last_valid_index(), 'current_stickup_height']
    return stickup


def trans_type(well_file):
    """Uses information from the raw transducer file to determine the type of transducer used.

    Args:
        well_file: full path to raw transducer file

    Returns:
        transducer type
    """
    if os.path.splitext(well_file)[1] == '.xle':
        t_type = 'Solinst'
    elif os.path.splitext(well_file)[1] == '.lev':
        t_type = 'Solinst'
    else:
        t_type = 'Global Water'

    print('Trans type for well is {:}.'.format(t_type))
    return t_type


def first_last_indices(df, tmzone=None):
    """Gets first and last index in a dataset; capable of considering time series with timezone information

    Args:
        df (pd.DataFrame): dataframe with indices
        tmzone (str): timzone code of data if timezone specified; defaults to None

    Returns:
        first index, last index

    """
    df.sort_index(inplace=True)

    if tmzone is None:
        first_index = df.first_valid_index()
        last_index = df.last_valid_index()

    else:
        if df.index[0].utcoffset() is None:
            first_index = df.first_valid_index().tz_localize(tmzone, ambiguous="NaT")
            last_index = df.last_valid_index().tz_localize(tmzone, ambiguous="NaT")
        elif df.index[0].utcoffset().total_seconds() == 0.0:
            first_index = df.first_valid_index().tz_convert(tmzone)
            last_index = df.last_valid_index().tz_convert(tmzone)
        else:
            first_index = df.first_valid_index()
            last_index = df.last_valid_index()
    return first_index, last_index




def barodistance(wellinfo):
    """Determines Closest Barometer to Each Well using wellinfo DataFrame"""
    barometers = {'barom': ['pw03', 'pw10', 'pw19'], 'X': [240327.49, 271127.67, 305088.9],
                  'Y': [4314993.95, 4356071.98, 4389630.71], 'Z': [1623.079737, 1605.187759, 1412.673738]}
    barolocal = pd.DataFrame(barometers)
    barolocal = barolocal.reset_index()
    barolocal.set_index('barom', inplace=True)

    wellinfo['pw03'] = np.sqrt((barolocal.loc['pw03', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw03', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw03', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw10'] = np.sqrt((barolocal.loc['pw10', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw10', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw10', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['pw19'] = np.sqrt((barolocal.loc['pw19', 'X'] - wellinfo['UTMEasting']) ** 2 +
                               (barolocal.loc['pw19', 'Y'] - wellinfo['UTMNorthing']) ** 2 +
                               (barolocal.loc['pw19', 'Z'] - wellinfo['G_Elev_m']) ** 2)
    wellinfo['closest_baro'] = wellinfo[['pw03', 'pw10', 'pw19']].T.idxmin()
    return wellinfo


# -----------------------------------------------------------------------------------------------------------------------
# These scripts remove outlier data and filter the time series of jumps and erratic measurements

def dataendclean(df, x, inplace=False, jumptol=1.0):
    """Trims off ends and beginnings of datasets that exceed 2.0 standard deviations of the first and last 50 values

    Args:
        df (pandas.core.frame.DataFrame): Pandas DataFrame
        x (str): Column name of data to be trimmed contained in df
        inplace (bool): if DataFrame should be duplicated
        jumptol (float): acceptable amount of offset in feet caused by the transducer being out of water at time of measurement; default is 1

    Returns:
        (pandas.core.frame.DataFrame) df trimmed data


    This function printmess a message if data are trimmed.
    """
    # Examine Mean Values
    if inplace:
        df = df
    else:
        df = df.copy()

    jump = df[abs(df.loc[:, x].diff()) > jumptol]
    try:
        for i in range(len(jump)):
            if jump.index[i] < df.index[50]:
                df = df[df.index > jump.index[i]]
                print("Dropped from beginning to " + str(jump.index[i]))
            if jump.index[i] > df.index[-50]:
                df = df[df.index < jump.index[i]]
                print("Dropped from end to " + str(jump.index[i]))
    except IndexError:
        print('No Jumps')
    return df


def smoother(df, p, win=30, sd=3):
    """Remove outliers from a pandas dataframe column and fill with interpolated values.
    warning: this will fill all NaN values in the DataFrame with the interpolate function

    Args:
        df (pandas.core.frame.DataFrame):
            Pandas DataFrame of interest
        p (string):
            column in dataframe with outliers
        win (int):
            size of window in days (default 30)
        sd (int):
            number of standard deviations allowed (default 3)

    Returns:
        Pandas DataFrame with outliers removed
    """
    df1 = df
    df1.loc[:, 'dp' + p] = df1.loc[:, p].diff()
    df1.loc[:, 'ma' + p] = df1.loc[:, 'dp' + p].rolling(window=win, center=True).mean()
    df1.loc[:, 'mst' + p] = df1.loc[:, 'dp' + p].rolling(window=win, center=True).std()
    for i in df.index:
        try:
            if abs(df1.loc[i, 'dp' + p] - df1.loc[i, 'ma' + p]) >= abs(df1.loc[i, 'mst' + p] * sd):
                df.loc[i, p] = np.nan
            else:
                df.loc[i, p] = df.loc[i, p]
        except ValueError:
            try:
                if abs(df1.loc[i, 'dp' + p] - df1.loc[i, 'ma' + p]) >= abs(df1.loc[:, 'dp' + p].std() * sd):
                    df.loc[i, p] = np.nan
                else:
                    df.loc[i, p] = df.loc[i, p]
            except ValueError:
                df.loc[i, p] = df.loc[i, p]

    try:
        df1 = df1.drop(['dp' + p, 'ma' + p, 'mst' + p], axis=1)
    except(NameError, ValueError):
        pass
    del df1
    try:
        df = df.drop(['dp' + p, 'ma' + p, 'mst' + p], axis=1)
    except(NameError, ValueError):
        pass
    df = df.interpolate(method='time', limit=30)
    df = df[1:-1]
    return df


def rollmeandiff(df1, p1, df2, p2, win):
    """Returns the rolling mean difference of two columns from two different dataframes
    Args:
        df1 (object):
            dataframe 1
        p1 (str):
            column in df1
        df2 (object):
            dataframe 2
        p2 (str):
            column in df2
        win (int):
            window in days

    Return:
        diff (float):
            difference
    """
    win = win * 60 * 24
    df1 = df1.resample('1T').mean()
    df1 = df1.interpolate(method='time')
    df2 = df2.resample('1T').mean()
    df2 = df2.interpolate(method='time')
    df1['rm' + p1] = df1[p1].rolling(window=win, center=True).mean()
    df2['rm' + p2] = df2[p2].rolling(window=win, center=True).mean()
    df3 = pd.merge(df1, df2, left_index=True, right_index=True, how='outer')
    df3 = df3[np.isfinite(df3['rm' + p1])]
    df4 = df3[np.isfinite(df3['rm' + p2])]
    df5 = df4['rm' + p1] - df4['rm' + p2]
    diff = round(df5.mean(), 3)
    del (df3, df4, df5)
    return diff


def jumpfix(df, meas, threashold=0.005, return_jump=False):
    """Removes jumps or jolts in time series data (where offset is lasting)
    Args:
        df (object):
            dataframe to manipulate
        meas (str):
            name of field with jolts
        threashold (float):
            size of jolt to search for
        return_jump (bool):
            return the pandas dataframe of jumps corrected in data; defaults to false
    Returns:
        df1: dataframe of corrected data
        jump: dataframe of jumps corrected in data
    """
    df1 = df.copy(deep=True)
    df1['delta' + meas] = df1.loc[:, meas].diff()
    jump = df1[abs(df1['delta' + meas]) > threashold]
    jump['cumul'] = jump.loc[:, 'delta' + meas].cumsum()
    df1['newVal'] = df1.loc[:, meas]

    for i in range(len(jump)):
        jt = jump.index[i]
        ja = jump['cumul'][i]
        df1.loc[jt:, 'newVal'] = df1[meas].apply(lambda x: x - ja, 1)
    df1[meas] = df1['newVal']
    if return_jump:
        print(jump)
        return df1, jump
    else:
        return df1


# -----------------------------------------------------------------------------------------------------------------------
# The following scripts align and remove barometric pressure data

def correct_be(site_number, well_table, welldata, be=None, meas='corrwl', baro='barometer'):
    if be:
        be = float(be)
    else:
        stdata = well_table[well_table['wellid'] == site_number]
        be = stdata['BaroEfficiency'].values[0]
    if be is None:
        be = 0
    else:
        be = float(be)

    if be == 0:
        welldata['baroefficiencylevel'] = welldata[meas]
    else:
        welldata['baroefficiencylevel'] = welldata[[meas, baro]].apply(lambda x: x[0] + be * x[1], 1)

    return welldata, be


def hourly_resample(df, bse=0, minutes=60):
    """
    resamples data to hourly on the hour
    Args:
        df:
            pandas dataframe containing time series needing resampling
        bse (int):
            base time to set in minutes; optional; default is zero (on the hour);
        minutes (int):
            sampling recurrence interval in minutes; optional; default is 60 (hourly samples)
    Returns:
        A Pandas DataFrame that has been resampled to every hour, at the minute defined by the base (bse)
    Description:
        see http://pandas.pydata.org/pandas-docs/dev/generated/pandas.DataFrame.resample.html for more info
        This function uses pandas powerful time-series manipulation to upsample to every minute, then downsample to
        every hour, on the hour.
        This function will need adjustment if you do not want it to return hourly samples, or iusgsGisf you are
        sampling more frequently than once per minute.
        see http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases
    """

    df = df.resample('1T').mean().interpolate(method='time', limit=90)

    if minutes == 60:
        sampfrq = '1H'
    else:
        sampfrq = str(minutes) + 'T'

    df = df.resample(sampfrq, closed='right', label='right', offset=f'{bse:0.0f}min').asfreq()
    return df


def well_baro_merge(wellfile, barofile, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl',
                    vented=False, sampint=60):
    """Remove barometric pressure from nonvented transducers.
    Args:
        wellfile (pd.DataFrame):
            Pandas DataFrame of water level data labeled 'Level'; index must be datetime
        barofile (pd.DataFrame):
            Pandas DataFrame barometric data labeled 'Level'; index must be datetime
        sampint (int):
            sampling interval in minutes; default 60

    Returns:
        wellbaro (Pandas DataFrame):
           corrected water levels with bp removed
    """

    # resample data to make sample interval consistent
    baro = hourly_resample(barofile, bse=0, minutes=sampint)
    well = hourly_resample(wellfile, bse=0, minutes=sampint)

    # reassign `Level` to reduce ambiguity
    baro = baro.rename(columns={barocolumn: 'barometer'})

    if 'temp' in baro.columns:
        baro = baro.drop('temp', axis=1)
    elif 'Temperature' in baro.columns:
        baro = baro.drop('Temperature', axis=1)
    elif 'temperature' in baro.columns:
        baro = baro.drop('temperature', axis=1)

    if vented:
        wellbaro = well
        wellbaro[outcolumn] = wellbaro[wellcolumn]
    else:
        # combine baro and well data for easy calculations, graphing, and manipulation
        wellbaro = pd.merge(well, baro, left_index=True, right_index=True, how='left')
        wellbaro = wellbaro.dropna(subset=['barometer', wellcolumn], how='any')
        wellbaro['dbp'] = wellbaro['barometer'].diff()
        wellbaro['dwl'] = wellbaro[wellcolumn].diff()
        # printmes(wellbaro)
        first_well = wellbaro[wellcolumn][0]
        wellbaro[outcolumn] = wellbaro[['dbp', 'dwl']].apply(lambda x: x[1] - x[0], 1).cumsum() + first_well
        wellbaro.loc[wellbaro.index[0], outcolumn] = first_well
    return wellbaro


def fcl(df, dtobj):
    """
    Finds closest date index in a dataframe to a date object

    Args:
        df (pd.DataFrame):
            DataFrame
        dtobj (datetime.datetime):
            date object

    taken from: http://stackoverflow.com/questions/15115547/find-closest-row-of-dataframe-to-given-time-in-pandas
    """
    return df.iloc[np.argmin(np.abs(pd.to_datetime(df.index) - dtobj))]  # remove to_pydatetime()


def compilefiles(searchdir, copydir, filecontains, filetypes=('lev', 'xle')):
    filecontains = list(filecontains)
    filetypes = list(filetypes)
    for pack in os.walk(searchdir):
        for name in filecontains:
            for i in glob.glob(pack[0] + '/' + '*{:}*'.format(name)):
                if i.split('.')[-1] in filetypes:
                    dater = str(datetime.datetime.fromtimestamp(os.path.getmtime(i)).strftime('%Y-%m-%d'))
                    rightfile = dater + "_" + os.path.basename(i)
                    if not os.path.exists(copydir):
                        print('Creating {:}'.format(copydir))
                        os.makedirs(copydir)
                    else:
                        pass
                    if os.path.isfile(os.path.join(copydir, rightfile)):
                        pass
                    else:
                        print(os.path.join(copydir, rightfile))
                        try:
                            copyfile(i, os.path.join(copydir, rightfile))
                        except:
                            pass
    print('Copy Complete!')
    return


def compilation(inputfile, trm=True):
    """This function reads multiple xle transducer files in a directory and generates a compiled Pandas DataFrame.
    Args:
        inputfile (file):
            complete file path to input files; use * for wildcard in file name
        trm (bool):
            whether or not to trim the end
    Returns:
        outfile (object):
            Pandas DataFrame of compiled data
    Example::
        >>> compilation('O:/Snake Valley Water/Transducer Data/Raw_data_archive/all/LEV/*baro*')
        picks any file containing 'baro'
    """

    # create empty dictionary to hold DataFrames
    f = {}

    # generate list of relevant files
    filelist = glob.glob(inputfile)

    # iterate through list of relevant files
    for infile in filelist:
        # run computations using lev files
        filename, file_extension = os.path.splitext(infile)
        if file_extension in ['.csv', '.lev', '.xle']:
            print(infile)
            nti = NewTransImp(infile, trim_end=trm).well
            f[getfilename(infile)] = nti
    # concatenate all of the DataFrames in dictionary f to one DataFrame: g
    g = pd.concat(f)
    # remove multiindex and replace with index=Datetime
    g = g.reset_index()
    g['DateTime'] = g['DateTime'].apply(lambda x: pd.to_datetime(x, errors='coerce'), 1)
    g = g.set_index(['DateTime'])
    # drop old indexes
    g = g.drop(['level_0'], axis=1)
    # remove duplicates based on index then sort by index
    g['ind'] = g.index
    g = g.drop_duplicates(subset='ind')
    g = g.drop('ind', axis=1)
    g = g.sort_index()
    return g


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# Raw transducer import functions - these convert raw lev, xle, and csv files to Pandas Dataframes for processing


class NewTransImp(object):
    """This class uses an imports and cleans the ends of transducer file.

    Args:
        infile (file):
            complete file path to input file
        xle (bool):
            if true, then the file type should be xle; else it should be csv

    Returns:
        A Pandas DataFrame containing the transducer data
    """

    def __init__(self, infile, trim_end=True, jumptol=1.0):
        """

        :param infile: complete file path to input file
        :param trim_end: turns on the dataendclean function
        :param jumptol: minimum amount of jump to search for that was caused by an out-of-water experience
        """
        self.well = None
        self.infile = infile
        file_ext = os.path.splitext(self.infile)[1]
        try:
            if file_ext == '.xle':
                try:
                    self.well = self.new_xle_imp()
                except (ParseError, KeyError):
                    self.well = self.old_xle_imp()
            elif file_ext == '.lev':
                self.well = self.new_lev_imp()
            elif file_ext == '.csv':
                self.well = self.new_csv_imp()
            else:
                print('filetype not recognized')
                self.well = None

            if self.well is None:
                pass
            elif trim_end:
                self.well = dataendclean(self.well, 'Level', jumptol=jumptol)
            else:
                pass
            return

        except AttributeError:
            print('Bad File')
            return

    def new_csv_imp(self):
        """This function uses an exact file path to upload a csv transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with open(self.infile, "r") as fd:
            txt = fd.readlines()
            if len(txt) > 1:
                if 'Serial' in txt[0]:
                    print('{:} is Solinst'.format(self.infile))
                    if 'UNIT: ' in txt[7]:
                        level_units = str(txt[7])[5:].strip().lower()
                    if 'UNIT: ' in txt[12]:
                        temp_units = str(txt[12])[5:].strip().lower()
                    f = pd.read_csv(self.infile, skiprows=13, parse_dates=[[0, 1]], usecols=[0, 1, 3, 4])
                    print(f.columns)
                    f['DateTime'] = pd.to_datetime(f['Date_Time'], errors='coerce')
                    f.set_index('DateTime', inplace=True)
                    f.drop('Date_Time', axis=1, inplace=True)
                    f.rename(columns={'LEVEL': 'Level', 'TEMP': 'Temp'}, inplace=True)
                    level = 'Level'
                    temp = 'Temp'

                    if level_units == "feet" or level_units == "ft":
                        f[level] = pd.to_numeric(f[level])
                    elif level_units == "kpa":
                        f[level] = pd.to_numeric(f[level]) * 0.33456
                        print("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "mbar":
                        f[level] = pd.to_numeric(f[level]) * 0.0334552565551
                    elif level_units == "psi":
                        f[level] = pd.to_numeric(f[level]) * 2.306726
                        print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "m" or level_units == "meters":
                        f[level] = pd.to_numeric(f[level]) * 3.28084
                        print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
                    elif level_units == "???":
                        f[level] = pd.to_numeric(f[level])
                        print("Units in ???, {:} is messed up...".format(
                            os.path.basename(self.infile)))
                    else:
                        f[level] = pd.to_numeric(f[level])
                        print("Unknown units, no conversion")

                    if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                        f[temp] = f[temp]
                    elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                        print('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
                        f[temp] = (f[temp] - 32.0) * 5.0 / 9.0
                    return f

                elif 'Date' in txt[1]:
                    print('{:} is Global'.format(self.infile))
                    f = pd.read_csv(self.infile, skiprows=1, parse_dates={'DateTime': [0, 1]})
                    # f = f.reset_index()
                    # f['DateTime'] = pd.to_datetime(f.columns[0], errors='coerce')
                    f = f[f.DateTime.notnull()]
                    if ' Feet' in list(f.columns.values):
                        f['Level'] = f[' Feet']
                        f.drop([' Feet'], inplace=True, axis=1)
                    elif 'Feet' in list(f.columns.values):
                        f['Level'] = f['Feet']
                        f.drop(['Feet'], inplace=True, axis=1)
                    else:
                        f['Level'] = f.iloc[:, 1]
                    # Remove first and/or last measurements if the transducer was out of the water
                    # f = dataendclean(f, 'Level')
                    flist = f.columns.tolist()
                    if ' Temp C' in flist:
                        f['Temperature'] = f[' Temp C']
                        f['Temp'] = f['Temperature']
                        f.drop([' Temp C', 'Temperature'], inplace=True, axis=1)
                    elif ' Temp F' in flist:
                        f['Temperature'] = (f[' Temp F'] - 32) * 5 / 9
                        f['Temp'] = f['Temperature']
                        f.drop([' Temp F', 'Temperature'], inplace=True, axis=1)
                    else:
                        f['Temp'] = np.nan
                    f.set_index(['DateTime'], inplace=True)
                    f['date'] = f.index.to_julian_date().values
                    f['datediff'] = f['date'].diff()
                    f = f[f['datediff'] > 0]
                    f = f[f['datediff'] < 1]
                    # bse = int(pd.to_datetime(f.index).minute[0])
                    # f = hourly_resample(f, bse)
                    f.rename(columns={' Volts': 'Volts'}, inplace=True)
                    for col in [u'date', u'datediff', u'Date_ Time', u'Date_Time']:
                        if col in f.columns:
                            f = f.drop(col, axis=1)
                    return f
            else:
                print('{:} is unrecognized'.format(self.infile))

    def new_lev_imp(self):
        with open(self.infile, "r") as fd:
            txt = fd.readlines()

        try:
            data_ind = txt.index('[Data]\n')
            # inst_info_ind = txt.index('[Instrument info from data header]\n')
            ch1_ind = txt.index('[CHANNEL 1 from data header]\n')
            ch2_ind = txt.index('[CHANNEL 2 from data header]\n')
            level = txt[ch1_ind + 1].split('=')[-1].strip().title()
            level_units = txt[ch1_ind + 2].split('=')[-1].strip().lower()
            temp = txt[ch2_ind + 1].split('=')[-1].strip().title()
            temp_units = txt[ch2_ind + 2].split('=')[-1].strip().lower()
            # serial_num = txt[inst_info_ind+1].split('=')[-1].strip().strip(".")
            # inst_num = txt[inst_info_ind+2].split('=')[-1].strip()
            # location = txt[inst_info_ind+3].split('=')[-1].strip()
            # start_time = txt[inst_info_ind+6].split('=')[-1].strip()
            # stop_time = txt[inst_info_ind+7].split('=')[-1].strip()

            df = pd.read_table(self.infile, parse_dates=[[0, 1]], sep='\s+', skiprows=data_ind + 2,
                               names=['Date', 'Time', level, temp],
                               skipfooter=1, engine='python')
            df.rename(columns={'Date_Time': 'DateTime'}, inplace=True)
            df.set_index('DateTime', inplace=True)

            if level_units == "feet" or level_units == "ft":
                df[level] = pd.to_numeric(df[level])
            elif level_units == "kpa":
                df[level] = pd.to_numeric(df[level]) * 0.33456
                print("Units in kpa, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "mbar":
                df[level] = pd.to_numeric(df[level]) * 0.0334552565551
            elif level_units == "psi":
                df[level] = pd.to_numeric(df[level]) * 2.306726
                print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            elif level_units == "m" or level_units == "meters":
                df[level] = pd.to_numeric(df[level]) * 3.28084
                print("Units in psi, converting {:} to ft...".format(os.path.basename(self.infile)))
            else:
                df[level] = pd.to_numeric(df[level])
                print("Unknown units, no conversion")

            if temp_units == 'Deg C' or temp_units == u'\N{DEGREE SIGN}' + u'C':
                df[temp] = df[temp]
            elif temp_units == 'Deg F' or temp_units == u'\N{DEGREE SIGN}' + u'F':
                print('Temp in F, converting {:} to C...'.format(os.path.basename(self.infile)))
                df[temp] = (df[temp] - 32.0) * 5.0 / 9.0
            df['name'] = self.infile
            return df
        except ValueError:
            print('File {:} has formatting issues'.format(self.infile))

    def old_xle_imp(self):
        """This function uses an exact file path to upload a xle transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with io.open(self.infile, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = eletree.fromstring(contents)

        dfdata = []
        for child in tree[5]:
            dfdata.append([child[i].text for i in range(len(child))])
        f = pd.DataFrame(dfdata, columns=[tree[5][0][i].tag for i in range(len(tree[5][0]))])

        try:
            ch1ID = tree[3][0].text.title()  # Level
        except AttributeError:
            ch1ID = "Level"

        ch1Unit = tree[3][1].text.lower()

        if ch1Unit == "feet" or ch1Unit == "ft":
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
        elif ch1Unit == "kpa":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.33456
        elif ch1Unit == "mbar":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 0.0334552565551
        elif ch1Unit == "psi":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 2.306726
        elif ch1Unit == "m" or ch1Unit == "meters":
            print("CH. 1 units in {:}, converting {:} to ft...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1']) * 3.28084
        elif ch1Unit == "???":
            print("CH. 1 units in {:}, {:} messed up...".format(ch1Unit, os.path.basename(self.infile)))
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
        else:
            f[str(ch1ID).title()] = pd.to_numeric(f['ch1'])
            print("Unknown units {:}, no conversion for {:}...".format(ch1Unit, os.path.basename(self.infile)))

        if 'ch2' in f.columns:
            try:
                ch2ID = tree[4][0].text.title()  # Level
            except AttributeError:
                ch2ID = "Temperature"

            ch2Unit = tree[4][1].text
            numCh2 = pd.to_numeric(f['ch2'])

            if ch2Unit == 'Deg C' or ch2Unit == 'Deg_C' or ch2Unit == u'\N{DEGREE SIGN}' + u'C':
                f[str(ch2ID).title()] = numCh2
            elif ch2Unit == 'Deg F' or ch2Unit == u'\N{DEGREE SIGN}' + u'F':
                print("CH. 2 units in {:}, converting {:} to C...".format(ch2Unit, os.path.basename(self.infile)))
                f[str(ch2ID).title()] = (numCh2 - 32) * 5 / 9
            else:
                print("Unknown temp units {:}, no conversion for {:}...".format(ch2Unit, os.path.basename(self.infile)))
                f[str(ch2ID).title()] = numCh2
        else:
            print('No channel 2 for {:}'.format(self.infile))

        if 'ch3' in f.columns:
            ch3ID = tree[5][0].text.title()  # Level
            ch3Unit = tree[5][1].text
            f[str(ch3ID).title()] = pd.to_numeric(f['ch3'])

        # add extension-free file name to dataframe
        f['name'] = self.infile.split('\\').pop().split('/').pop().rsplit('.', 1)[0]
        # combine Date and Time fields into one field
        f['DateTime'] = pd.to_datetime(f.apply(lambda x: x['Date'] + ' ' + x['Time'], 1))
        f[str(ch1ID).title()] = pd.to_numeric(f[str(ch1ID).title()])

        f = f.reset_index()
        f = f.set_index('DateTime')
        f['Level'] = f[str(ch1ID).title()]

        droplist = ['Date', 'Time', 'ch1', 'ch2', 'index', 'ms']
        for item in droplist:
            if item in f.columns:
                f = f.drop(item, axis=1)

        return f

    def new_xle_imp(self):
        tree = eletree.parse(self.infile, parser=eletree.XMLParser(encoding="ISO-8859-1"))
        root = tree.getroot()

        ch1id = root.find('./Identification')
        dfdata = {}
        for item in root.findall('./Data/Log'):
            dfdata[item.attrib['id']] = {}
            for child in item:
                dfdata[item.attrib['id']][child.tag] = child.text
                # print([child[i].text for i in range(len(child))])
        ch = {}
        for child in root:
            if 'Ch' in child.tag:
                ch[child.tag[:3].lower()] = {}
                for item in child:
                    if item.text is not None:
                        ch[child.tag[:3].lower()][item.tag] = item.text

        f = pd.DataFrame.from_dict(dfdata, orient='index')
        f['DateTime'] = pd.to_datetime(f.apply(lambda x: x['Date'] + ' ' + x['Time'], 1))
        f = f.reset_index()
        f = f.set_index('DateTime')
        levelconv = {'feet': 1, 'ft': 1, 'kpa': 0.33456, 'mbar': 0.033455256555148,
                     'm': 3.28084, 'meters': 3.28084, 'psi': 2.306726}
        for col in f:
            if col in ch.keys():
                if col == 'ch1':
                    chname = 'Level'
                elif col == 'ch2':
                    chname = 'Temperature'
                elif 'Identification' in ch[col].keys():
                    chname = ch[col]['Identification'].title()

                chunit = ch[col]['Unit']
                f = f.rename(columns={col: chname})
                f[chname] = pd.to_numeric(f[chname])
                if chname == 'Level':
                    f[chname] = f[chname] * levelconv.get(chunit.lower(), 1)
                    print(f"CH. 1 units in {chunit}, converting to ft...")
                elif chname == 'Temperature' or chname == 'Temp':
                    if chunit[
                        -1] == 'F' or chunit.title() == 'Fahrenheit' or chunit.title() == 'Deg F' or chunit.title() == 'Deg_F':
                        f[chname] = (f[chname] - 32.0) * 5 / 9
                        print(f"CH. 2 units in {chunit}, converting to deg C...")
            elif col in ['ms', 'Date', 'Time', 'index']:
                f = f.drop(col, axis=1)
        f['name'] = self.infile.split('\\').pop().split('/').pop().rsplit('.', 1)[0]
        return f


# ----------------------------------------------------------------------------------------------------------------------
# Summary scripts - these extract transducer headers and summarize them in tables


def getfilename(path):
    """This function extracts the file name without file path or extension

    Args:
        path (file):
            full path and file (including extension of file)

    Returns:
        name of file as string
    """
    return path.split('\\').pop().split('/').pop().rsplit('.', 1)[0]


def compile_end_beg_dates(infile):
    """ Searches through directory and compiles transducer files, returning a dataframe of the file name,
    beginning measurement, and ending measurement. Complements xle_head_table, which derives these dates from an
    xle header.
    Args:
        infile (directory):
            folder containing transducer files
    Returns:
        A Pandas DataFrame containing the file name, beginning measurement date, and end measurement date
    Example::
        >>> compile_end_beg_dates('C:/folder_with_xles/')


    """
    filelist = glob.glob(infile + "/*")
    f = {}

    # iterate through list of relevant files
    for infile in filelist:
        f[getfilename(infile)] = NewTransImp(infile).well

    dflist = []
    for key, val in f.items():
        if val is not None:
            dflist.append((key, val.index[0], val.index[-1]))

    df = pd.DataFrame(dflist, columns=['filename', 'beginning', 'end'])
    return df


class HeaderTable(object):
    def __init__(self, folder, filedict=None, filelist=None, workspace=None,
                 conn_file_root=None,
                 loc_table="ugs_ngwmn_monitoring_locations"):
        """

        Args:
            folder: directory containing transducer files
            filedict: dictionary matching filename to locationid
            filelist: list of files in folder
            workspace:
            loc_table: Table of location table in the SDE
        """
        self.folder = folder

        if filelist:
            self.filelist = filelist
        else:
            self.filelist = glob.glob(self.folder + "/*")

        self.filedict = filedict

        if workspace:
            self.workspace = workspace
        else:
            self.workspace = folder

    def get_ftype(self, x):
        if x[1] == 'Solinst':
            ft = '.xle'
        else:
            ft = '.csv'
        return self.filedict.get(x[0] + ft)

    # examine and tabulate header information from files

    def file_summary_table(self):
        # create temp directory and populate it with relevant files
        self.filelist = self.xle_csv_filelist()
        fild = {}
        for file in self.filelist:
            file_extension = os.path.splitext(file)[1]

            if file_extension == '.xle':
                fild[file], dta = self.xle_head(file)
            elif file_extension == '.csv':
                fild[file], dta = self.csv_head(file)

        df = pd.DataFrame.from_dict(fild, orient='index')
        return df

    def make_well_table(self):
        file_info_table = self.file_summary_table()
        for i in ['Latitude', 'Longitude']:
            if i in file_info_table.columns:
                file_info_table.drop(i, axis=1, inplace=True)
        df = self.loc_table
        well_table = pd.merge(file_info_table, df, right_on='locationname', left_on='wellname', how='left')
        well_table.set_index('altlocationid', inplace=True)
        well_table['wellid'] = well_table.index
        well_table.dropna(subset=['wellname'], inplace=True)
        well_table.to_csv(self.folder + '/file_info_table.csv')
        print("Header Table with well information created at {:}/file_info_table.csv".format(self.folder))
        return well_table

    def xle_csv_filelist(self):
        exts = ('//*.xle', '//*.csv')  # the tuple of file types
        files_grabbed = []
        for ext in exts:
            files_grabbed += (glob.glob(self.folder + ext))
        return files_grabbed

    def xle_head(self, file):
        """Creates a Pandas DataFrame containing header information from all xle files in a folder

        Returns:
            A Pandas DataFrame containing the transducer header data

        Example:
            >>> xle_head_table('C:/folder_with_xles/')
        """
        # open text file
        df1 = {}
        df1['file_name'] = getfilename(file)
        with io.open(file, 'r', encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = eletree.fromstring(contents)

            for child in tree[1]:
                df1[child.tag] = child.text

            for child in tree[2]:
                df1[child.tag] = child.text

        df1['trans type'] = 'Solinst'
        xledata = NewTransImp(file).well.sort_index()
        df1['beginning'] = xledata.first_valid_index()
        df1['end'] = xledata.last_valid_index()
        # df = pd.DataFrame.from_dict(df1, orient='index').T
        return df1, xledata

    def csv_head(self, file):
        cfile = {}
        csvdata = pd.DataFrame()
        try:
            cfile['file_name'] = getfilename(file)
            csvdata = NewTransImp(file).well.sort_index()
            if "Volts" in csvdata.columns:
                cfile['Battery_level'] = int(
                    round(csvdata.loc[csvdata.index[-1], 'Volts'] / csvdata.loc[csvdata.index[0], 'Volts'] * 100, 0))
            cfile['Sample_rate'] = (csvdata.index[1] - csvdata.index[0]).seconds * 100
            # cfile['filename'] = file
            cfile['beginning'] = csvdata.first_valid_index()
            cfile['end'] = csvdata.last_valid_index()
            # cfile['last_reading_date'] = csvdata.last_valid_index()
            cfile['Location'] = ' '.join(cfile['file_name'].split(' ')[:-1])
            cfile['trans type'] = 'Global Water'
            cfile['Num_log'] = len(csvdata)
            # df = pd.DataFrame.from_dict(cfile, orient='index').T

        except (KeyError, AttributeError):
            pass

        return cfile, csvdata

def getwellid(infile, wellinfo):
    """Specialized function that uses a well info table and file name to lookup a well's id number"""
    m = re.search("\d", getfilename(infile))
    s = re.search("\s", getfilename(infile))
    if m.start() > 3:
        wellname = getfilename(infile)[0:m.start()].strip().lower()
    else:
        wellname = getfilename(infile)[0:s.start()].strip().lower()
    wellid = wellinfo[wellinfo['Well'] == wellname]['wellid'].values[0]
    return wellname, wellid






if __name__ == "__main__": main()

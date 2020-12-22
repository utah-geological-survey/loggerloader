import matplotlib

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

import pandas as pd
import os
import re
import glob
import gzip
import pickle
import time
import platform

from pandastable import plotting, dialogs, util, logfile, Table, SimpleEditor, OrderedDict, MultipleValDialog, TableModel

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
#style.use('ggplot')
import loggerloader as ll


class Feedback:

    def __init__(self, master):
        # create main window and configure size and title
        # tk.Tk.__init__(self, *args, **kwargs)
        master.geometry('1400x800')
        master.wm_title("Transducer Processing")
        with open(os.path.join(r'C:\Users\Hutto\PycharmProjects\loggerloader', 'VERSION')) as version_file:
            self.version = version_file.read().strip()
        self.version
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
        #self.datastr[key].set('G:/Shared drives/UGS_Groundwater/Projects/Transducers/manmeas.csv')

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
        #self.datastr[key].set('G:/Shared drives/UGS_Groundwater/Projects/Transducers/manmeas.csv')

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
        self.datastr[key].set(
            "G:/Shared drives/UGS_Groundwater/Projects/Transducers/ugs_ngwmn_monitoring_locations.csv")

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
        ht = ll.HeaderTable(self.datastr['trans-dir'].get())
        filelist = ht.xle_csv_filelist()
        pg.config(maximum=len(filelist))
        fild = {}
        wdf = {}
        sv = tk.StringVar(popup, value='')
        ttk.Label(popup, textvariable=sv).pack()
        for file in filelist:
            popup.update()
            filestr = ll.getfilename(file)
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

    def outlierremove(self, key):
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        frame_step1_5 = ttk.Frame(self.onewelltab)
        ttk.Label(frame_step1_5, text='1a. Fix Jumps and outliers (optional)').grid(column=0, row=0, columnspan=6)
        dataminlab = ttk.Label(frame_step1_5, text='Min. Allowed Value:')
        dataminlab.grid(column=0, row=1)

        self.dataminvar = tk.DoubleVar(frame_step1_5, value=-10000.0)
        self.datamaxvar = tk.DoubleVar(frame_step1_5, value=100000.0)
        self.datamin = ttk.Entry(frame_step1_5, textvariable=self.dataminvar, width=10, state='disabled')
        self.datamin.grid(column=1, row=1)

        dataminlab = ttk.Label(frame_step1_5, text='Max. Allowed Value:')
        dataminlab.grid(column=2, row=1)
        self.datamax = ttk.Entry(frame_step1_5, textvariable=self.datamaxvar, width=10, state='disabled')
        self.datamax.grid(column=3, row=1)
        self.trimbutt = ttk.Button(frame_step1_5, text='Trim Extrema', command=self.trimextrema, state='disabled')
        self.trimbutt.grid(column=4, row=1)

        datajumplab = ttk.Label(frame_step1_5, text='Jump Tolerance:')
        datajumplab.grid(column=0, row=2)
        self.datajumptol = tk.DoubleVar(frame_step1_5, value=100.0)
        self.datajump = ttk.Entry(frame_step1_5, textvariable=self.datajumptol, width=10, state='disabled')
        self.datajump.grid(column=1, row=2)
        self.jumpbutt = ttk.Button(frame_step1_5, text='Fix Jumps', command=self.fixjumps, state='disabled')
        self.jumpbutt.grid(column=2, row=2)
        frame_step1_5.pack()
        # self.data[key]

    def trimextrema(self):
        if 'well' in self.data.keys():
            if 'Level' in self.data['well'].columns:
                self.data['well'] = self.data['well'][(self.data['well']['Level'] >= self.dataminvar.get()) & (
                            self.data['well']['Level'] <= self.datamaxvar.get())]
                graphframe, tableframe = self.note_tab_add('well')
                self.add_graph_table('well', tableframe, graphframe)
                # self.datatable['well'].show()
                # self.datatable['well'].update()
                # self.datatable['well'].show()
        else:
            print('No column named Level')
            pass
        # TODO add dialog to select a column to adjust

    def fixjumps(self):
        if 'well' in self.data.keys():
            if 'Level' in self.data['well'].columns:
                self.data['well'] = ll.jumpfix(self.data['well'], 'Level', self.datajumptol.get())
                graphframe, tableframe = self.note_tab_add('well')
                self.add_graph_table('well', tableframe, graphframe)
                # self.datatable['well'].show()
                # self.datatable['well'].update()
                # self.datatable['well'].show()
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

        # wlevels = ll.ElevateWater(self.datatable['manual'].model.df, melev, mstickup)
        # self.manelevs = wlevels.manual_elevation()
        df = self.datatable['fixed-drift'].model.df
        # wlevels = ll.ElevateWater(self.datatable['fixed-drift'].model.df, melev, mstickup)
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

            df, self.drift_info, mxdrft = ll.Drifting(self.datatable[key2].model.df,
                                                      self.datatable['well-baro'].model.df,
                                                      drifting_field='corrwl',
                                                      man_field='dtwbelowcasing',
                                                      well_id= self.datatable[key2].model.df.loc[0,'locationid'],
                                                      output_field='DTW_WL').process_drift()
            # df, self.drift_info, mxdrft = ll.fix_drift(self.datatable['well-baro'].model.df,
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
                        df, dfrinf, max_drift = ll.Drifting(mandf,
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
                            # bulkdrift[i] = ll.get_trans_gw_elevations(df, mstickup,  melev, site_number = i, level='corrwl', dtw='DTW_WL')
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
                self.data[key] = ll.NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                filenm, self.file_extension = os.path.splitext(self.datastr[key].get())
                self.datamin['state'] = 'normal'
                self.datamax['state'] = 'normal'
                self.trimbutt['state'] = 'normal'
                self.datajump['state'] = 'normal'
                self.jumpbutt['state'] = 'normal'
                if 'Level' in self.data['well'].columns:
                    self.dataminvar.set(self.data['well']['Level'].min())
                    self.datamaxvar.set(self.data['well']['Level'].max())
            elif key in ('baro'):
                self.data[key] = ll.NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                filenm, self.file_extension = os.path.splitext(self.datastr[key].get())
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
        TODO Add File type combo to improve csv processing
        """
        if 'well' in self.data.keys() and 'baro' in self.data.keys():
            key = 'well-baro'
            if self.is_vented == 1:
                sol = True
            else:
                sol = False

            self.data[key] = ll.well_baro_merge(self.datatable['well'].model.df,
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
                            mergedf[int(wellid)] = ll.well_baro_merge(self.data['bulk-well'].loc[int(wellid)],
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
                filestr = ll.getfilename(file)
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
        logo = "C:/Users/Hutto/PycharmProjects/loggerloader/data_files/GeologicalSurvey.png"
        #orig = Image.open(logo)
        ph = tk.PhotoImage(file=logo)
        #resized = orig.resize((100,110), Image.ANTIALIAS)
        #ph = ImageTk.PhotoImage(resized, abwin)
        label = tk.Label(abwin, image=ph)
        label.image = ph
        label.pack()
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

if __name__ == "__main__": main()

import matplotlib

from tksheet import Sheet

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
from matplotlib.figure import Figure

# Implement the default Matplotlib key bindings.

from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, messagebox, ttk
from tkcalendar import DateEntry

from pylab import rcParams

import platform


#from pandas.plotting import register_matplotlib_converters

try:
    from loader import *
except:
    from .loader import *

try:
    import pyi_splash

    # Update the text on the splash screen
    pyi_splash.update_text("PyInstaller is a great software!")
    pyi_splash.update_text("Second time's a charm!")

    # Close the splash screen. It does not matter when the call
    # to this function is made, the splash screen remains open until
    # this function is called or the Python program is terminated.
    pyi_splash.close()
except:
    pass
#register_matplotlib_converters()

rcParams['figure.figsize'] = 15, 10

try:
    pd.options.mode.chained_assignment = None
except AttributeError:
    pass


class Feedback:

    def __init__(self, master):
        # create main window and configure size and title
        # tk.Tk.__init__(self)
        master.geometry('1400x800')
        master.wm_title("Transducer Processing")

        plt.style.use('default')

        self.version = "2.0.0"

        self.root = master
        self.main = master
        self.master = master

        # Create a style
        style = ttk.Style(master)

        # Import the tcl file
        try:
            master.tk.call("source", "../themes/forest-light.tcl")
            style.theme_use("forest-light")
        except:
            try:
                master.tk.call("source", "./themes/forest-light.tcl")
                style.theme_use("forest-light")
            except:
                pass

        # Set the theme with the theme_use method


        # Get platform into a variable
        self.setConfigDir()
        # if not hasattr(self,'defaultsavedir'):
        self.defaultsavedir = os.path.join(os.path.expanduser('~'))

        #self.loadAppOptions()

        # start logging
        # self.start_logging()

        try:
            self.root.iconbitmap(r'../data_files/icon.ico')
        except:
            try:
                print('no')
                self.root.iconbitmap(r'G:/My Drive/Python/Pycharm/loggerloader/data_files/icon.ico')
            except:
                pass
        self.currentdir = os.path.expanduser('~')

        self.create_menu_bar()

        self.sheettheme = "light blue"

        ## -- MAKE EMPTY DICTIONARIES TO HOLD CLASS OBJECTS -- ##

        self.datastr, self.data, self.datatable, self.combo = {}, {}, {}, {}

        self.field = None
        self.toolbar = None

        self.entry = {}
        self.locidmatch = {}
        self.bulktransfilestr = {}  # dictionary to store trans file names

        # selecting files
        self.fileselectbutt = {}
        self.fileselectcombo = {}
        self.filetype = {}

        # matching sheets and columns
        self.wellbaroxl = {}
        self.xlcols_date_combo = {}
        self.xlcols_value_combo = {}
        self.xlcols_temp_combo = {}
        self.xlcols_cond_combo = {}

        # generating right-hand tables and charts
        self.graphframe = {}
        self.tableframe = {}
        self.graph_frame1 = {}
        self.graphcanvas = {}

        self.wellbarocsv = {}

        # jump fix dictionaries
        self.dataminvar = None
        self.datamaxvar = None
        self.datamin = None

        self.datamax = None
        self.trimbutt = None
        self.datajumptol = None
        self.datajump = None
        self.jumpbutt = None

        self.fig = {}
        self.ax = {}

        ## -- WIDGET AREA -- ##

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

        # These lines tell the script which tab is selected
        self.selected_tab = None
        self.notebook.bind("<<NotebookTabChanged>>", self.nbselect)

        self.projopen = False
        # self.newProject()

        # add tabs in the frame to the left
        self.processing_notebook = ttk.Notebook(self.process_frame)
        self.processing_notebook.pack(fill='both', expand=True)
        # self.onewelltab = ttk.Frame(self.processing_notebook)
        # https://stackoverflow.com/questions/3085696/adding-a-scrollbar-to-a-group-of-widgets-in-tkinter
        self.frame = ttk.Frame(self.processing_notebook)
        self.canvas = tk.Canvas(self.frame, borderwidth=0, width=150, height=800)
        self.onewelltab = ttk.Frame(self.canvas)

        self.vsb = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((4, 4), window=self.onewelltab, anchor="nw", tags="self.frame")
        self.onewelltab.bind("<Configure>", self.onFrameConfigure)

        self.bulkwelltab = ttk.Frame(self.processing_notebook)
        self.manyfiletab = ttk.Frame(self.processing_notebook)

        self.processing_notebook.add(self.frame, text='Single-Well Process')
        self.processing_notebook.add(self.bulkwelltab, text='Bulk Well Process')
        self.processing_notebook.add(self.manyfiletab, text='One Well Many files')
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

        self.bulk_match_button = ttk.Button(applymatchframe,
                                            text='5. Click when done matching files to well names',
                                            command=lambda: self.make_file_info_table(master),
                                            state='disabled')
        self.bulk_match_button.pack()

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        bulk_align_frame = ttk.Frame(dirselectframe)
        bulk_align_frame.pack()
        self.align_bulk_wb_button = ttk.Button(bulk_align_frame,
                                               text='6. Align Well-Baro Data',
                                               command=self.align_well_baro_bulk,
                                               state='disabled', )
        self.align_bulk_wb_button.grid(row=0, column=0)

        self.export_align = tk.IntVar()
        self.export_align_check = ttk.Checkbutton(bulk_align_frame,
                                                  text="Export Aligned Data?",
                                                  variable=self.export_align,
                                                  state='disabled')
        self.export_align_check.grid(row=0, column=1)
        self.export_align.set(0)
        # self.export_align_check.deselect()

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        ttk.Label(dirselectframe, text='7. Import Manual Data').pack()
        # self.manfileframe(dirselectframe).pack()
        self.bulk_manfileframe = ttk.Frame(dirselectframe)
        self.bulk_manfileframe.pack()
        self.man_file_frame(self.bulk_manfileframe, key='bulk-manual')

        self.proc_man_bulk_button = ttk.Button(self.bulk_manfileframe, text='Process Manual Data',
                                               command=self.proc_man_bulk)
        self.proc_man_bulk_button.grid(column=1, row=5, columnspan=2)
        self.proc_man_bulk_button['state'] = 'disabled'

        ttk.Separator(dirselectframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        bulk_drift_frame = ttk.Frame(dirselectframe)
        bulk_drift_frame.pack()
        self.bfdb = ttk.Button(bulk_drift_frame, text='8. Fix Drift', command=self.bulk_fix_drift)
        self.bfdb.grid(column=0, row=0, columnspan=1, rowspan=2)
        self.bfdb['state'] = 'disabled'
        self.export_drift = tk.IntVar(value=1)
        self.export_drift_check = ttk.Checkbutton(bulk_drift_frame,
                                                  text="Export Drift Data?",
                                                  variable=self.export_drift,
                                                  state='disabled')
        self.export_drift_check.grid(row=0, column=1, sticky=tk.W)
        # self.export_drift_check.select()

        self.export_drift_graph = tk.IntVar(value=1)
        self.export_drift_graph_check = ttk.Checkbutton(bulk_drift_frame,
                                                        text="Graph Data?",
                                                        variable=self.export_drift_graph,
                                                        state='disabled')
        self.export_drift_graph_check.grid(row=1, column=1, sticky=tk.W)
        # self.export_drift_graph_check.select()

        ttk.Label(bulk_drift_frame, text='Max Allowed Drift (ft)').grid(row=0, column=2)
        self.max_allowed_drift = tk.DoubleVar(bulk_drift_frame, value=0.3)
        ent = ttk.Entry(bulk_drift_frame, textvariable=self.max_allowed_drift, width=10)
        ent.grid(row=1, column=2)

    def onFrameConfigure(self, event):
        """Reset the scroll region to encompass the inner frame"""
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
        self.selected_tab = 'well-info-table'
        self.datastr[self.selected_tab] = tk.StringVar(well_info_frame)
        self.datastr[self.selected_tab].set("ugs_ngwmn_monitoring_locations.csv")

        ttk.Label(well_info_frame, text='1. Input well info file (must be csv)').grid(row=0, column=0, columnspan=3)

        e = ttk.Entry(well_info_frame, textvariable=self.datastr[self.selected_tab], width=80)
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
        ttk.Label(popup, text="Examining Directory...").pack()
        pg = ttk.Progressbar(popup, orient=tk.HORIZONTAL, mode='determinate', length=200)
        pg.pack()

        key = 'file-info-table'
        self.selected_tab = key
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
        self.data[key] = df
        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key, tabw=4, grph=1)
        # add graph and table to new tab

        self.datatable[key] = Sheet(self.tableframe[key], data=df.values.tolist())

        self.datatable[key].change_theme(theme=self.sheettheme)
        self.datatable[key].headers(self.data[key].columns)
        self.datatable[key].enable_bindings()

        self.datatable[key].pack(fill="both", expand=True)
        self.align_bulk_wb_button['state'] = 'normal'
        self.export_align_check['state'] = 'normal'
        # self.bulk_data_file_button['state'] = 'normal'

        popup.destroy()

    def detect_baro(self, x):
        """Finds the barometers in the well-info-table"""
        if pd.isna(x[1]):
            x[1] = 'water'
        if x[0] == "M1.5" or 'baro' in x[1].lower() or x[2] in (
                '9003', '9049', '9024', '9060', '9025', '9027', '9063', '9067', '9070', '9066'):
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
        self.selected_tab = key
        datasets = {"well": "1. Select Well Data:",
                    "baro": "2. Select Barometric Data:"}
        ttk.Separator(self.onewelltab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        filefinderframe = ttk.Frame(self.onewelltab)
        ttk.Label(filefinderframe, text=datasets[key]).grid(column=0, row=0, columnspan=3)
        ttk.Label(filefinderframe, text='(Right click for refresh.)').grid(column=2, row=0, columnspan=3)

        self.datastr[key] = tk.StringVar(filefinderframe, value=f'Double-Click for {key} file')
        self.entry[key] = ttk.Entry(filefinderframe, textvariable=self.datastr[key], width=60)
        self.entry[key].grid(column=0, row=1, columnspan=2)

        self.entry[key].bind('<Double-ButtonRelease-1>', lambda k: self.wellbarodiag(key))

        self.filetype[key] = tk.StringVar(filefinderframe, value="xle")
        self.fileselectcombo[key] = ttk.Combobox(filefinderframe, width=10,
                                                 values=['xle', 'Global Water csv', 'Excel', 'csv', 'Troll htm',
                                                         'Troll csv'],
                                                 state="readonly", textvariable=self.filetype[key])

        self.fileselectcombo[key].grid(column=2, row=1, columnspan=2)
        # self.fileselectcombo[key].current(self.filetype)
        self.fileselectbutt[key] = ttk.Button(filefinderframe,
                                              text='Import data',
                                              command=lambda: self.wellbaroabb(key))
        self.fileselectbutt[key].grid(column=4, row=1, columnspan=1)

        # self.entry[key].bind('<3>', lambda k: self.wellbaroabb(key))
        filefinderframe.pack()

    def jump_fix_popup(self):
        if self.selected_tab:
            key = self.selected_tab
        else:
            key = 'well'

        key = self.selected_tab
        popup = tk.Toplevel()
        popup.geometry("550x150+200+200")

        #ttk.Separator(popup, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        frame_step1_5 = ttk.Frame(popup)
        ttk.Label(frame_step1_5, text='Fix Jumps and outliers (optional)').grid(column=0, row=0, columnspan=6)
        datajumplab = ttk.Label(frame_step1_5, text='Jump Tolerance:')
        datajumplab.grid(column=0, row=2)
        self.datajumptol = tk.DoubleVar(frame_step1_5, value=100.0)
        self.datajump = ttk.Entry(frame_step1_5, textvariable=self.datajumptol, width=10)
        self.datajump.grid(column=1, row=2)
        self.jumpbutt = ttk.Button(frame_step1_5, text='Fix Jumps', command=self.fixjumps)
        self.jumpbutt.grid(column=2, row=2)
        frame_step1_5.pack()
        self.datajumptol.set(self.data[key][self.field].std()*5)

    def placeholder_func(self):
        pass

    def trim_extrema_popup(self):
        if self.selected_tab:
            key = self.selected_tab
        else:
            key = 'well'

        key = self.selected_tab
        popup = tk.Toplevel()
        popup.geometry("250x200+200+200")

        #ttk.Separator(popup, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        frame_step1_5 = ttk.Frame(popup)
        ttk.Label(frame_step1_5, text=f'Remove extreme values').grid(column=0, row=0, columnspan=2)
        dataminlab = ttk.Label(frame_step1_5, text='Min Allowed Value:')
        ttk.Label(frame_step1_5, text=f'from sheet {self.selected_tab} & column {self.field}').grid(column=0, row=1, columnspan=2)
        dataminlab.grid(column=0, row=2, columspan= 2)

        self.dataminvar = tk.DoubleVar(frame_step1_5, value=-10000.0)
        self.datamaxvar = tk.DoubleVar(frame_step1_5, value=100000.0)
        self.datamin = ttk.Entry(frame_step1_5, textvariable=self.dataminvar, width=10, state='disabled')
        self.datamin.grid(column=1, row=2)

        dataminlab = ttk.Label(frame_step1_5, text='Max Allowed Value:')
        dataminlab.grid(column=0, row=3)
        self.datamax = ttk.Entry(frame_step1_5, textvariable=self.datamaxvar, width=10, state='disabled')
        self.datamax.grid(column=1, row=3)
        self.trimbutt = ttk.Button(frame_step1_5, text='Trim Extrema', command=self.trimextrema)
        self.trimbutt.grid(column=0, row=4,columnspan=2)

        frame_step1_5.pack()
        self.dataminvar.set(self.data[key][self.field].mean() - self.data[key][self.field].std()*4)
        self.datamaxvar.set(self.data[key][self.field].mean() + self.data[key][self.field].std()*4)
        # self.data[key]

    def trimextrema(self):
        key = self.selected_tab
        if key in self.data.keys():
            if self.field:
                self.data[key] = self.data[key][(self.data[key][self.field] >= self.dataminvar.get()) & (
                        self.data[key][self.field] <= self.datamaxvar.get())]
                self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
                self.add_graph_table(key)

        else:
            print('No column selected')
            pass


    def fixjumps(self):
        key = self.selected_tab
        if key in self.data.keys():
            if self.field:
                self.data[key] = jumpfix(self.data[key], self.field, self.datajumptol.get())
                self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
                self.add_graph_table(key)
        else:
            print('No column named Level')
            pass


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

        ttk.Label(frame_step3, text='Well field').grid(row=1, column=0, columnspan=1)
        self.wellalignfieldbox = ttk.Combobox(frame_step3, width=5, values=['Level'])
        self.wellalignfieldbox.grid(row=1, column=2)
        self.wellalignfieldbox.current(0)

        ttk.Label(frame_step3, text='Baro field').grid(row=1, column=3, columnspan=1)
        self.baroalignfieldbox = ttk.Combobox(frame_step3, width=5, values=['Level'])
        self.baroalignfieldbox.grid(row=1, column=4)
        self.baroalignfieldbox.current(0)

        ttk.Label(frame_step3, text='Pref. Data Freq.').grid(row=2, column=0, columnspan=2)
        # Boxes for data frequency
        self.freqint = ttk.Combobox(frame_step3, width=4, values=list(range(1, 120)))
        self.freqint.grid(row=3, column=0)
        self.freqint.current(59)
        self.freqtype = ttk.Combobox(frame_step3, width=4, values=['min'])
        self.freqtype.grid(row=3, column=1)
        self.freqtype.current(0)
        b = ttk.Button(frame_step3, text='Align Datasets',
                       command=self.alignedplot)
        b.grid(row=3, column=2)

        self.export_wb = tk.IntVar(value=1)
        self.export_single_well_baro = ttk.Checkbutton(frame_step3,
                                                       text="Export Well-Baro Data?",
                                                       variable=self.export_wb)
        self.export_single_well_baro.grid(row=3, column=3, sticky=tk.W)
        # self.export_single_well_baro.select()

        self.is_vented = tk.IntVar(value=0)
        self.trans_vented = ttk.Checkbutton(frame_step3,
                                            text="Vented?",
                                            variable=self.is_vented)
        self.trans_vented.grid(row=3, column=4, sticky=tk.W)
        self.is_vented.set(0)
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

        self.end_edit_cell(key='fixed-drift')
        df = self.data['fixed-drift']

        if 'manual-single' in self.data.keys():
            key2 = 'manual-single'
        elif 'bulk-manual' in self.data.keys():
            key2 = 'bulk-manual'
        else:
            key2 = 'manual'

        self.end_edit_cell(key=key2)
        self.data[key2]['waterelevation'] = self.data[key2]['dtwbelowcasing'] + mstickup + melev
        self.datatable[key2].update()
        self.manelevs = self.data[key2]
        df['waterelevation'] = self.data['fixed-drift']['DTW_WL'] + mstickup + melev

        self.data[key] = df
        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
        self.add_graph_table(key)
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

            self.end_edit_cell(key=key2)
            self.data[key2]['dtwbelowcasing'] = self.data[key2]['dtwbelowcasing'] * -1
            # self.end_edit_cell(key=key2)
            # self.datatable[key2].update()

            wellid = self.data[key2].loc[self.data[key2].first_valid_index(), 'locationid']
            df, self.drift_info, mxdrft = Drifting(self.data[key2],
                                                   self.data['well-baro'],
                                                   drifting_field='corrwl',
                                                   man_field='dtwbelowcasing',
                                                   well_id=wellid,
                                                   output_field='DTW_WL').process_drift()

            self.max_drift.set(mxdrft)

            if 'Temperature' in df.columns:
                self.data[key] = df[['barometer', 'corrwl', 'DTW_WL', 'driftcorrection', 'Temperature']]
            else:
                self.data[key] = df[['barometer', 'corrwl', 'DTW_WL', 'driftcorrection']]

            self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
            self.add_graph_table(key)
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
        info = self.data['well-info-table']
        try:
            pg.config(maximum=len(self.data['bulk-well-baro'].index.get_level_values(0).unique()))
        except KeyError:
            tk.messagebox.showinfo(title='Yo!', message='Align the data first!')
        sv = tk.StringVar(popup, value='')
        ttk.Label(popup, textvariable=sv).pack()

        if 'bulk-manual' in self.data.keys():
            key2 = 'bulk-manual'
        elif 'manual-single' in self.data.keys():
            key2 = 'manual-single'
        else:
            key2 = 'manual'

        # Check effect of this comment;
        #  Uncommented on 5/26/2021 in attempt to make consistent with single-well
        #  Recommented as caused high drift

        for i in self.data['bulk-well-baro'].index.get_level_values(0).unique():
            popup.update()
            if pd.notnull(i):

                if int(i) in self.data[key2].index:
                    mandf = self.data[key2].loc[int(i)]
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

                        sv.set(f"{name} has a max drift of {max_drift}")
                    except KeyError as err:
                        sv.set("Need More Recent Manual Data")
                        print(err)
                        # sv.set(f"{err}")
                        pass
            pg.step()

        self.data['bulk-fix-drift'] = pd.concat(bulkdrift).set_index(['locationid', 'DateTime'])
        # self.data['bulk-fix-drift'] = self.data['bulk-fix-drift']
        key = 'drift-info'
        self.data[key] = pd.concat(drift_info, sort=True, ignore_index=True).set_index('name')
        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)

        self.datatable[key] = Sheet(self.tableframe[key], data=self.data[key].reset_index().values.tolist())

        self.datatable[key].change_theme(theme=self.sheettheme)
        self.datatable[key].headers(self.data[key].reset_index().columns)

        self.datatable[key].pack(fill="both", expand=True)

        self.datatable[key].enable_bindings()
        popup.destroy()

        if self.export_drift.get() == 1:
            dfdrft = self.data['drift-info']
            dfdrft = dfdrft.reset_index()
            file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')],
                                                defaultextension=".csv",
                                                title='Output Drift File Location')
            dfdrft.to_csv(file)

        df = self.data['bulk-fix-drift']
        df = df.reset_index()
        print(df.columns)
        df = df.rename(columns={'DateTime': 'readingdate', 'Level': 'measuredlevel', 'Temperature': 'temperature',
                                'DTW_WL': 'measureddtw'})
        df = df[['locationid', 'readingdate', 'measuredlevel', 'temperature',
                 'measureddtw', 'driftcorrection', 'waterelevation']]

        file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')], defaultextension=".csv",
                                            title='Bulk processing output destination')
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
                plt.rcParams["font.size"] = "8"
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
                            mandf = self.data[key2].loc[ind]
                        except KeyError:
                            mandf = self.data['manual-single'].loc[ind]
                        mandf = mandf.dropna(subset=['waterelevation'])

                        if len(df) > 0 and len(mandf) > 0:
                            title = info.loc[int(ind), 'locationname']
                            ax.plot(df.index, df['waterelevation'], color='blue')
                            ax.scatter(mandf.index, mandf['waterelevation'], color='red')

                            ax.set_ylabel('Water Level Elevation')
                            ax.set_ylim(min(df['waterelevation']) - 0.1, max(df['waterelevation']) + 0.1)
                            ax.set_xlim(df.first_valid_index() - pd.Timedelta(days=3),
                                        df.last_valid_index() + pd.Timedelta(days=3))
                            ax.set_title(title)
                            plt.tight_layout()
                            # ax.tick_params(axis='x', labelrotation=45)
                            canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
                            canvas.draw()

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
                self.end_edit_cell(key='well')
                df = df[df.index > self.data['well'].first_valid_index() - pd.DateOffset(days=8)]

            self.data[key] = df[df['locationid'] == pd.to_numeric(self.scombo['Pick id'].get(), downcast='integer')]

        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
        self.add_graph_table(key)

    def bulk_wlelev(self, x, inf, pg, pop):
        pop.update()
        wl = x[1] + inf.loc[x[0], 'stickup'] + inf.loc[x[0], 'verticalmeasure']
        pg.step()
        return wl

    def proc_man_bulk(self):
        key = 'bulk-manual'
        # if 'bulk-manual' in self.data.keys():
        #    key = 'bulk-manual'
        # elif 'manual-single' in self.data.keys():
        #    key = 'manual-single'
        # else:
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
            info = self.data['well-info-table']
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
            self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
            self.add_graph_table(key)
            self.export_drift_graph_check['state'] = 'normal'
            self.export_drift_check['state'] = 'normal'
            self.bfdb['state'] = 'normal'
            # self.proc_man_bulk_button['fg'] = 'green'
        except KeyError as err:
            print(f"Key Error: {err}")
            tk.messagebox.showerror(title='Process Well Info Table First', message="Process Well Info Table First")

    def only_meas(self, value_if_allowed):
        try:
            float(value_if_allowed)
            return True
        except ValueError:
            return False

    def _quit(self):
        self.quit()  # stops mainloop
        self.destroy()  # this is necessary on Windows to prevent
        # Fatal Python Error: PyEval_RestoreThread: NULL tstate

    def on_key_press(self, event):
        print("you pressed {}".format(event.key))
        key_press_handler(event, self.canvas, self.toolbar)

    def note_tab_add(self, key, tabw=2, grph=3):
        """

        Args:
            key (str): name of dataset; ex 'well','baro','well-baro','manual','fixed-drift'

        Returns:

        """
        # print(key)
        self.selected_tab = key

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
        self.tableframe[key] = ttk.Frame(panedframe, relief='sunken')
        self.graphframe[key] = ttk.Frame(panedframe, relief='sunken')

        panedframe.add(self.tableframe[key], weight=tabw)
        panedframe.add(self.graphframe[key], weight=grph)
        labframe = ttk.Frame(self.graphframe[key])
        labframe.pack()
        ttk.Label(labframe, text='Click on column of choice and then the Plot button!').pack()
        return self.graphframe[key], self.tableframe[key]

    def make_chart(self, event, key):

        self.end_edit_cell(key=key)

        self.field = list(self.data[key].columns)[event[1] - 1]

        #self.datajumptol.set(self.data[key][self.field].std()*5)
        #self.dataminvar.set(self.data[key][self.field].mean() - self.data[key][self.field].std()*4)
        #self.datamaxvar.set(self.data[key][self.field].mean() + self.data[key][self.field].std()*4)
        print(self.field)

        # remove old widgets
        if key in self.graphcanvas.keys():
            self.graphcanvas[key].destroy()

        if self.toolbar:
            self.toolbar.destroy()
        plt.clf()
        # create new elements

        fig = Figure(figsize=(5.5, 4))

        a = fig.add_subplot(211)
        x = self.data[key].index
        y = self.data[key][self.field]
        a.plot(x, y)

        a.set_ylabel(self.field)
        for label in a.get_xticklabels():
            label.set_ha("right")
            label.set_rotation(45)

        a.set_xlabel("Date")
        # fig.set_tight_layout(True)

        canvas = FigureCanvasTkAgg(fig, self.graph_frame1[key])

        self.toolbar = NavigationToolbar2Tk(canvas, self.graph_frame1[key])
        # toolbar.update()

        self.graphcanvas[key] = canvas.get_tk_widget()
        self.graphcanvas[key].pack(fill=tk.BOTH)


    def end_edit_cell(self, event=None, key=None):
        df = pd.DataFrame(self.datatable[key].get_sheet_data(return_copy=True, get_header=False, get_index=False))
        df.index = self.data[key].index

        if len(df.columns) == len(self.data[key].columns):
            df.columns = self.data[key].columns
        elif len(df.columns) - 1 == len(self.data[key].columns):
            df = df.iloc[:, 1:]
            df.columns = self.data[key].columns
        else:
            pass
            print('Column transfer mismatch')

        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except ValueError:
                pass

        self.data[key] = df
        self.datatable[key].redraw(redraw_header=True, redraw_row_index=True)

        if event:
            return event.text

    def add_graph_table(self, key):
        """

        Args:
            key (str): name of dataset; ex 'well','baro','well-baro','manual','fixed-drift'

        Returns:
            adds pandastable elements to a frame

        """
        self.selected_tab = key
        self.graph_frame1[key] = ttk.Frame(self.graphframe[key])

        self.datatable[key] = Sheet(self.tableframe[key], data=self.data[key].reset_index().values.tolist())

        self.datatable[key].change_theme(theme=self.sheettheme)
        self.datatable[key].headers(self.data[key].reset_index().columns)
        self.datatable[key].enable_bindings()

        self.datatable[key].pack(fill="both", expand=True)

        self.datatable[key].extra_bindings([("column_select", lambda event: self.make_chart(event, key=key)),
                                            ("end_edit_cell", lambda event: self.end_edit_cell(event, key=key))])
        self.datatable[key].popup_menu_add_command("---------", self.placeholder_func)
        self.datatable[key].popup_menu_add_command("Trim Extrema", self.trim_extrema_popup)
        self.datatable[key].popup_menu_add_command("Jump Fix", self.jump_fix_popup)
        self.graph_frame1[key].pack()

        if key == 'well':
            self.wellalignfieldbox['values'] = list(self.data[key].columns)
        elif key == 'baro':
            self.baroalignfieldbox['values'] = list(self.data[key].columns)

    def plot_bulk_baro(self, graph_frame1):
        key = 'bulk-baro'
        ax = self.datatable[key].showPlotViewer(parent=graph_frame1).ax
        for wellid in self.data[key].index.get_level_values(0).unique():
            ax.plot(self.data[key].loc[wellid, 'Level'], label=wellid)

        ax.set_ylabel('well levels', color='blue')

        ax.legend()

    def add_baro_axis(self, graph_frame1):
        key = 'well-baro'
        ax = self.datatable[key].showPlotViewer(parent=graph_frame1).ax
        lns1 = ax.plot(self.data[key]['Level'], color='green', label='unprocessed')
        lns2 = ax.plot(self.data[key]['corrwl'], color='blue', label='baro-removed')
        ax2 = ax.twinx()
        lns3 = ax2.plot(self.data[key]['barometer'], color='red', label='baro')
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

            ax.plot(self.data[key]['DTW_WL'], color='green', label='unprocessed')
            ax.scatter(self.data[key2].index, self.data[key2]['dtwbelowcasing'])
            ax.set_ylabel(f"Depth to Water (ft)")
        elif key == 'wl-elev':
            ax.plot(self.data[key]['waterelevation'], color='green', label='unprocessed')
            ax.scatter(self.data[key2].index, self.data[key2]['waterelevation'])
            ax.set_ylabel(f"Water Elevation (ft)")
        ax.set_xlim(self.data[key2].first_valid_index() - pd.Timedelta('3 days'),
                    self.data[key2].last_valid_index() + pd.Timedelta('3 days'), )

    def wellbaroabb(self, key):
        if self.datastr[key].get() == '' or type(self.datastr[key].get()) == tuple or self.datastr[
            key].get() == f'Double-Click for {key} file':
            pass
        else:
            if key in ['well','baro']:
                # 'xle','raw csv', 'Excel', 'modified csv'
                if self.fileselectcombo[key].get() in ['xle', 'Global Water csv']:
                    self.data[key] = NewTransImp(self.datastr[key].get()).well.drop(['name'], axis=1)
                elif self.fileselectcombo[key].get() in ['Excel']:
                    # self.data[key] = pd.read_excel(self.datastr[key].get())
                    self.wellbaroxl[key] = pd.ExcelFile(self.datastr[key].get())

                    self.openNewWindowxl(key)
                elif self.fileselectcombo[key].get() in ['csv']:
                    self.data[key] = pd.read_csv(self.datastr[key].get())
                    self.openNewWindowcsv(key)
                elif self.fileselectcombo[key].get() in ['Troll htm']:
                    self.data[key] = read_troll_htm(self.datastr[key].get())
                elif self.fileselectcombo[key].get() in ['Troll csv']:
                    self.data[key] = read_troll_csv(self.datastr[key].get())

                filenm, self.file_extension = os.path.splitext(self.datastr[key].get())

                if key in self.data.keys() and self.datajumptol:
                    #self.datamin['state'] = 'normal'
                    #self.datamax['state'] = 'normal'
                    #self.trimbutt['state'] = 'normal'
                    #self.datajump['state'] = 'normal'
                    #self.jumpbutt['state'] = 'normal'
                    if self.field in self.data[key].columns:
                        self.datajumptol.set(self.data[key][self.field].std() * 5)
                        self.dataminvar.set(self.data[key][self.field].mean() - self.data[key][self.field].std() * 4)
                        self.datamaxvar.set(self.data[key][self.field].mean() + self.data[key][self.field].std() * 4)

            elif key in ('manual', 'bulk-manual', 'manual-single'):
                filenm, file_extension = os.path.splitext(self.datastr[key].get())
                if file_extension in ('.xls', '.xlsx'):
                    self.data[key] = pd.read_excel(self.datastr[key].get())
                elif file_extension == '.csv':
                    self.data[key] = pd.read_csv(self.datastr[key].get())
            # add notepad tab
            self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
            # add graph and table to new tab
            self.add_graph_table(key)

    def openNewWindowcsv(self, key):

        # Toplevel object which will
        # be treated as a new window
        self.newWindow = tk.Toplevel(self.master)

        # sets the title of the
        # Toplevel widget
        self.newWindow.title("Match CSV Info")

        # sets the geometry of toplevel
        self.newWindow.geometry("250x350")
        # df = pd.read
        # A Label widget to show in toplevel
        # self.data[key] =
        columns = list(self.data[key].columns.values)  # see all sheet names

        tk.Label(self.newWindow, text="Datetime Field").pack()
        self.xlcols_date_combo[key] = ttk.Combobox(self.newWindow, values=columns)
        self.xlcols_date_combo[key].pack()
        tk.Label(self.newWindow, text="Value Field").pack()
        self.xlcols_value_combo[key] = ttk.Combobox(self.newWindow, values=columns)
        self.xlcols_value_combo[key].pack()
        tk.Label(self.newWindow, text="Temperature Field (optional)").pack()
        self.xlcols_temp_combo[key] = ttk.Combobox(self.newWindow, values=columns)
        self.xlcols_temp_combo[key].pack()
        tk.Label(self.newWindow, text="Conductivity Field (optional)").pack()
        self.xlcols_cond_combo[key] = ttk.Combobox(self.newWindow, values=columns)
        self.xlcols_cond_combo[key].pack()

        # tk.Label(newWindow, text=self.datastr[key].get()).pack()
        tk.Button(self.newWindow, text='OoooK', command=lambda: self.xl_cols_match(key)).pack()

    def openNewWindowxl(self, key):

        # Toplevel object which will
        # be treated as a new window
        self.newWindow = tk.Toplevel(self.master)

        # sets the title of the
        # Toplevel widget
        self.newWindow.title("Pick Excel Sheet and Columns")

        # sets the geometry of toplevel
        self.newWindow.geometry("250x400")
        # df = pd.read
        # A Label widget to show in toplevel
        # self.data[key] =
        tk.Label(self.newWindow, text="Excel Sheet with Data").pack()
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
        tk.Label(self.newWindow, text="Conductivity Field (optional)").pack()
        self.xlcols_cond_combo[key] = ttk.Combobox(self.newWindow, textvariable='Conductivity')
        self.xlcols_cond_combo[key].pack()
        # read a specific sheet to DataFrame
        self.sheetcombo[key].bind("<<ComboboxSelected>>",
                                  lambda event, key=key: self.parse_sheet(key))
        # tk.Label(newWindow, text=self.datastr[key].get()).pack()
        tk.Button(self.newWindow, text='OoooK', command=lambda: self.xl_cols_match(key)).pack()

    def parse_sheet(self, key):
        self.data[key] = self.wellbaroxl[key].parse(self.sheetcombo[key].get())
        # self.xlsheetcols =
        self.xlcols_date_combo[key]['values'] = list(self.data[key].columns.values)
        self.xlcols_value_combo[key]['values'] = list(self.data[key].columns.values)
        self.xlcols_temp_combo[key]['values'] = list(self.data[key].columns.values)
        self.xlcols_cond_combo[key]['values'] = list(self.data[key].columns.values)

    def xl_cols_match(self, key):
        datecol = self.xlcols_date_combo[key].get()
        valcol = self.xlcols_value_combo[key].get()
        tempcol = self.xlcols_temp_combo[key].get()
        condcol = self.xlcols_cond_combo[key].get()
        self.data[key] = self.data[key].rename(columns={datecol: 'DateTime',
                                                        valcol: 'Level',
                                                        tempcol: 'Temperature',condcol:'Cond'})
        self.data[key] = self.data[key].reset_index()
        self.data[key]['DateTime'] = pd.to_datetime(self.data[key]['DateTime'])
        self.data[key] = self.data[key].set_index('DateTime')

        # self.wellbaroabb(key)
        # add notepad tab
        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
        # add graph and table to new tab
        self.add_graph_table(key)

        self.newWindow.destroy()

    def wellbarodiag(self, key):

        ftypelist = (("Solinst xle", "*.xle*"), ("csv", "*.csv"), ("Excel", "*.xlsx"), ("Troll htm", "*.htm*"))
        self.datastr[key].set(filedialog.askopenfilename(initialdir=self.currentdir,
                                                         title=f"Select {key} file",
                                                         filetypes=ftypelist))
        self.currentdir = os.path.dirname(self.datastr[key].get())
        ext = os.path.splitext(self.datastr[key].get())[-1]
        extdir = {'.xle': 'xle', '.csv': 'csv', '.xlsx': 'Excel', '.htm': 'Troll htm'}
        # ['xle','raw csv', 'Excel', 'solinst csv out']

        self.filetype[key].set(extdir.get(ext, 'xle'))
        print(self.filetype[key].get())

        # Action if cancel in file dialog is pressed
        # self.wellbaroabb(key)

    def alignedplot(self):
        """

        Returns: notepad tab with aligned data;
        TODO Add File type combo to improve csv processing
        """
        if 'well' in self.data.keys() and 'baro' in self.data.keys():
            key = 'well-baro'
            if self.is_vented.get() == 1:
                sol = True
            else:
                sol = False

            # dfwell = pd.DataFrame()
            self.end_edit_cell(key='well')
            self.end_edit_cell(key='baro')

            self.data[key] = well_baro_merge(self.data['well'],
                                             self.data['baro'],
                                             wellcolumn=self.wellalignfieldbox.get(),
                                             barocolumn=self.baroalignfieldbox.get(),
                                             sampint=int(self.freqint.get()),
                                             vented=sol)
            self.graphframe[key], self.tableframe[key] = self.note_tab_add(key)
            self.add_graph_table(key)

            if self.export_wb.get() == 1:
                df = self.data[key]
                df.index.name = 'locationid'
                df = df.reset_index()
                file = filedialog.asksaveasfilename(filetypes=[('csv', '.csv')], defaultextension=".csv")
                df.to_csv(file)


    def align_well_baro_bulk(self):
        # TODO add feature to recognize global water transducers
        if 'bulk-well' in self.data.keys():
            files = self.data['file-info-table']
            info = self.data['well-info-table']
            wellids = self.data['bulk-well'].index.get_level_values(0).unique()
            mergedf = {}
            popup = tk.Toplevel()
            popup.geometry("400x100+200+200")
            ttk.Label(popup, text="Aligning datasets...").pack()
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
                        # medium = files[files['locationid'] == wellid]['measuring_medium'].values[0]
                        stattype = info.loc[int(wellid), 'locationtype']
                        # print(stattype)
                        name = info.loc[int(wellid), "locationname"]

                        ttype = files[files['locationid'] == wellid]['trans type'].values[0]

                        if ttype == 'Solinst':
                            sol = False
                        elif ttype == 'Global Water':
                            sol = True
                        else:
                            sol = False

                        if baroid in files['locationid'].unique() and (
                                int(wellid) < 9000 or int(wellid) >= 10000) and len(
                            self.data['bulk-well'].loc[int(wellid)]) > 0:
                            try:

                                dat = well_baro_merge(self.data['bulk-well'].loc[int(wellid)],
                                                      self.data['bulk-well'].loc[int(baroid)],
                                                      vented=sol)
                                dat.index.name = 'DateTime'
                            except IndexError:
                                print(f"No match for wellid {wellid}, {baroid}")
                                print(f"{self.data['bulk-well'].loc[int(wellid)].first_valid_index()}")
                                print(f"{self.data['bulk-well'].loc[int(baroid)].first_valid_index()}")
                                dat = pd.DataFrame(columns=['Blank1', 'Blank2'])
                                pass
                            if len(dat) > 1 and dat.index.name == 'DateTime':
                                mergedf[int(wellid)] = dat

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
            # self.align_bulk_wb_button['fg'] = 'green'

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
                        if key == 'manual' or key == 'bulk-manual':
                            self.combo_choice["DTW"].set(col)
                        else:
                            self.scombo_choice["DTW"].set(col)
                    elif col.lower() in ['locationid', 'locid', 'id', 'location_id', 'lid']:
                        if key == 'manual' or key == 'bulk-manual':
                            self.combo_choice['locationid'].set(col)
                        else:
                            self.scombo_choice['locationid'].set(col)
            except FileNotFoundError:
                pass

    def save_one_well(self):
        filename = filedialog.asksaveasfilename(filetypes=[('csv', '.csv'), ('Excel', '.xlsx')],
                                                defaultextension=".csv",
                                                confirmoverwrite=True)
        if filename is None:
            print('no')
            return
        else:
            self.end_edit_cell(key='wl-elev')
            df = self.data['wl-elev']
            df['measureddtw'] = -1 * df['DTW_WL']
            df = df.rename(columns={'Temperature': 'temperature',
                                    'corrwl': 'measuredlevel'})
            df = df.drop(['DTW_WL'], axis=1)
            filename, file_extension = os.path.splitext(filename)
            if file_extension == '.csv':
                df.to_csv(filename + ".csv")
            else:
                df.to_excel(filename + ".xlsx")
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

        self.graphframe[key], self.tableframe[key] = self.note_tab_add(key, tabw=5, grph=1)
        self.datatable[key] = Sheet(self.tableframe[key], data=self.data[key].values.tolist())
        # self.datatable[key].show()

        self.datatable[key].change_theme(theme=self.sheettheme)
        self.datatable[key].headers(self.data[key].reset_index().columns)
        self.datatable[key].enable_bindings()

        self.datatable[key].pack(fill="both", expand=True)

        # self.datatable[key].showIndex()
        # self.datatable[key].update()

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
                self.end_edit_cell(key='well-info-table')
                df = self.data['well-info-table']
                df['locationnamelwr'] = df['locationname'].apply(lambda x: x.lower(), 1)

                self.locdict = df['locationnamelwr'].to_dict()
                self.welldict = {y: x for x, y in self.locdict.items()}
                self.locnamedict = dict(zip(df['locationnamelwr'].values, df['locationname'].values))
                self.locnametoid = dict(zip(df['locationname'].values, df.index.values))

            syndict = {73: ['Eskdale MX', ['eskmx', 'eskdalemx', 'edmx']],
                       69: ['Twin Springs MX', ['tsmx', 'twinmx', 'twin', 'twin springs mx', 'twinspringsmx']],
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
                       51: ['PW20', ['pw20a']],
                       5053: ['Sliver Creek MX', ['scmx']],
                       5052: ['USGS Snake Creek Well', ['usgsscw','snakecreek','Snake Creek Well']],
                       5055: ['(C-13-17)03bcb-1 Simm', ['rsimm']],
                       5056: ['(C-11-17)12dcb-1 Callao South', ['Callao South']],
                       6001: ['T2', ['T2']],
                       6002: ['T5', ['T5']]

                       }

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


    def create_menu_bar(self):
        """Create the menu bar for the application. """

        self.menu = tk.Menu(self.main)
        file_menu = tk.Menu(self.menu, tearoff=0)
        # add recent first

        filemenuitems = {'01Quit': {'cmd': self.quit}}
        self.file_menu = self.create_pulldown(self.menu, filemenuitems, var=file_menu)
        self.menu.add_cascade(label='File', menu=self.file_menu['var'])

        self.help_menu = {'01Online Help': {'cmd': self.online_documentation},
                          '02About': {'cmd': self.about}}
        self.help_menu = self.create_pulldown(self.menu, self.help_menu)
        self.menu.add_cascade(label='Help', menu=self.help_menu['var'])

        self.main.config(menu=self.menu)
        return

    def create_pulldown(self, menu, dict, var=None):
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

    def exitProgram(self):
        exit()

    def nbselect(self, event):
        codedtabname = self.notebook.select()
        self.selected_tab = self.notebook.tab(codedtabname, "text")
        print(self.selected_tab)





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

        for p in self.fig:
            fig = self.fig[p]
            canvas = FigureCanvasTkAgg(fig, master=self)
            pdf_pages.savefig(fig)
        pdf_pages.close()
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
        # abwin.configure(background=self.bg)
        # label.grid(row=0, column=0, sticky='ew', padx=4, pady=4)
        pandasver = pd.__version__
        pythonver = platform.python_version()
        mplver = matplotlib.__version__
        ttl = tk.Label(abwin, text=f'Logger Loader v.{self.version}', font='Helvetica 18 bold')
        ttl.pack()
        # ttl.grid(row=1, column=0, sticky='news', pady=1, padx=4)

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
        text2b = 'tksheet by ragardner'
        t2a = tk.Label(fm2, text=text2a)
        t2a.pack(side=tk.LEFT)
        t2b = tk.Label(fm2, text=text2b, fg="blue", cursor="hand2")
        t2b.pack(side=tk.LEFT)
        t2b.bind("<Button-1>", lambda e: self.callback("https://github.com/ragardner/tksheet"))
        fm3ab = tk.Frame(abwin)
        fm3ab.pack()
        text3a = 'UI Themes from '
        text3b = 'Forest-ttk-theme by rdbende'
        t3a = tk.Label(fm3ab, text=text3a)
        t3a.pack(side=tk.LEFT)
        t3b = tk.Label(fm3ab, text=text3b, fg="blue", cursor="hand2")
        t3b.pack(side=tk.LEFT)
        t3b.bind("<Button-1>", lambda e: self.callback("https://github.com/rdbende/Forest-ttk-theme"))

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
        # tmp.grid(row=2, column=0, sticky='news', pady=1, padx=4)
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


if __name__ == "__main__":
    main()

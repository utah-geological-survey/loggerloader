import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
# Implement the default Matplotlib key bindings.
import matplotlib.animation as animation
from matplotlib import style
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import os
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkcalendar import Calendar, DateEntry
import pandastable

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

style.use('ggplot')
import loggerloader as ll

class Feedback:

    def __init__(self, master):
        # create main window and configure size and title
        master.geometry('1000x800')
        master.wm_title("Transducer Processing")
        self.root = master

        self.currentdir = os.path.expanduser('~')

        # menu bars at the top of the main window
        master.option_add('*tearOff', False)
        menubar = Menu(master)
        master.config(menu=menubar)
        file = Menu(menubar)
        edit = Menu(menubar)
        help_ = Menu(menubar)
        menubar.add_cascade(menu=file, label='File')
        menubar.add_cascade(menu=edit, label='edit')
        menubar.add_cascade(menu=help_, label='Help')
        file.add_command(label='New', command=lambda: print('New File'))
        file.add_separator()
        file.add_command(label="Open...", command=lambda: print('Opening'))
        file.add_command(label="Save", command=lambda: print('Save File'))
        file.entryconfig('New', accelerator='Ctrl + N')
        save = Menu(file)
        file.add_cascade(menu=save, label='Save')
        save.add_command(label='Save As', command=lambda: print('save as'))
        save.add_command(label='Save All', command=lambda: print('saving'))

        # Create side by side panel areas
        self.panedwindow = ttk.Panedwindow(master, orient=HORIZONTAL)
        self.panedwindow.pack(fill=BOTH, expand=True)
        self.frame1 = ttk.Frame(self.panedwindow, width=150, height=400, relief=SUNKEN)
        self.frame2 = ttk.Frame(self.panedwindow, width=400, height=400, relief=SUNKEN)
        self.panedwindow.add(self.frame1, weight=1)
        self.panedwindow.add(self.frame2, weight=4)

        # Header image logo and Description seen by user
        self.frame_header = ttk.Frame(self.frame1)
        self.frame_header.pack(pady=5)
        self.logo = PhotoImage(file = "./GeologicalSurvey.png").subsample(10,10)
        ttk.Label(self.frame_header, image = self.logo).grid(row = 0, column = 0, rowspan=2)
        ttk.Label(self.frame_header, wraplength=300, text = "Processing transducer data").grid(row= 0, column=1)

        # Data Entry Frame
        self.frame_content = ttk.Frame(self.frame1)
        self.frame_content.pack()

        # Select Well Table Interface
        ttk.Label(self.frame_content, text= "1. Select Well Data:").grid(row=0, column=0, columnspan=3)
        self.well_string = StringVar(self.frame_content, value='Double-Click for file')
        self.well_entry = ttk.Entry(self.frame_content, textvariable=self.well_string, width=80, justify=LEFT)
        self.well_entry.grid(row=1, column=0, columnspan=3)
        self.well_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.opendiag(framename='Raw Well'))

        # Select Baro Table Interface
        ttk.Label(self.frame_content, text="2. Select Barometric Data:").grid(row=2, column=0, columnspan=3)
        self.baro_string = StringVar(self.frame_content, value='Double-Click for file')
        self.baro_entry = ttk.Entry(self.frame_content, textvariable=self.baro_string, width=80, justify=LEFT)
        self.baro_entry.grid(row=3, column=0, columnspan=3)
        self.baro_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.opendiag(framename='Raw Baro'))

        # Align Manual and Baro Data
        self.frame_step3 = ttk.Frame(self.frame_content)
        self.frame_step3.grid(row=4, column=0, columnspan=3)
        ttk.Label(self.frame_step3, text="3. Align Baro and Well Data:").grid(row=0, column=0, columnspan=3)
        ttk.Label(self.frame_step3, text='Pref. Data Freq.').grid(row=1, column=0, columnspan=2)
        # Boxes for data frequency
        self.freqint = ttk.Combobox(self.frame_step3, width=4, values=list(range(1,120)))
        self.freqint.grid(row=2,column=0)
        self.freqint.current(59)
        self.freqtype = ttk.Combobox(self.frame_step3, width=4, values=['M'])
        self.freqtype.grid(row=2, column=1)
        self.freqtype.current(0)
        self.alignpro = ttk.Button(self.frame_step3,text='Align Datasets',command=self.aligndata)
        self.alignpro.grid(row=2, column=2)

        #-----------Manual Data-------------------------------------------------------------
        # Select Manual Table Interface
        self.frame_step4 = ttk.Frame(self.frame_content)
        self.frame_step4.grid(row=5, column=0, columnspan=3)
        ttk.Label(self.frame_step4, text="4. Select Manual Data:").grid(row=0, column=0, columnspan=3)
        self.manbook = ttk.Notebook(self.frame_step4)
        self.manbook.grid(row=1, column=0, columnspan=3)
        self.manframe = ttk.Frame(self.manbook)
        self.manfileframe = ttk.Frame(self.manbook)
        self.manbook.add(self.manframe, text='Manual Entry')
        self.manbook.add(self.manfileframe, text='Data Import')
        # validates time number inputs
        measvalidation= (self.manframe.register(self.only_meas),'%P')

        # measure 1 manually input manual data ---------------------------------
        # labels
        ttk.Label(self.manframe, text="Date of Measure 1").grid(row=0, column=0)
        ttk.Label(self.manframe, text="HH:MM").grid(row=0, column=1, columnspan=3, sticky='WENS')
        ttk.Label(self.manframe, text="Measure 1").grid(row=0, column=4)
        ttk.Label(self.manframe, text="Units").grid(row=0, column=5)
        # date picker
        self.man_date1entry = DateEntry(self.manframe, width=20, locale='en_US', date_pattern='MM/dd/yyyy')
        self.man_date1entry.grid(row=1, column=0,padx=2)
        # time picker
        self.hour1 = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 24)]),
                                  state="readonly")
        self.hour1.grid(row=1, column=1)
        self.hour1.current(0)
        ttk.Label(self.manframe, text=":").grid(row=1, column=2)
        self.min1 = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 60)]),
                                 state="readonly")
        self.min1.grid(row=1, column=3)
        self.min1.current(0)
        # measure
        self.man_meas1entry = ttk.Entry(self.manframe, validate="key", validatecommand=measvalidation, width=10)
        self.man_meas1entry.grid(row=1, column=4, padx=2)
        # units
        self.manunits = ttk.Combobox(self.manframe, width=5, values=['ft','m'],state="readonly")
        self.manunits.grid(row=1, column=5, rowspan=3)
        self.manunits.current(0)
        # locid
        ttk.Label(self.manframe, text="Locationid").grid(row=0, column=6)
        self.man_locid = ttk.Entry(self.manframe, width=11)
        self.man_locid.grid(row=1, column=6, rowspan=3)

        # measure 2 manually input manual data -----------------------------------
        ttk.Label(self.manframe, text= "Date of Measure 2").grid(row=2, column=0)
        ttk.Label(self.manframe, text="HH:MM").grid(row=2, column=1, columnspan=3, sticky='WENS')
        ttk.Label(self.manframe, text="Measure 2").grid(row=2, column=4)

        # date picker
        self.man_date2entry = DateEntry(self.manframe, width=20, locale='en_US', date_pattern='MM/dd/yyyy')
        self.man_date2entry.grid(row=3, column=0,padx=2)

        # time picker
        self.hour2 = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 24)]),
                                  state="readonly")
        self.hour2.grid(row=3, column=1)
        self.hour2.current(0)
        ttk.Label(self.manframe, text=":").grid(row=3, column=2)
        self.min2 = ttk.Combobox(self.manframe, width=2, values=list([f'{i:02}' for i in range(0, 60)]),
                                 state="readonly")
        self.min2.grid(row=3, column=3)
        self.min2.current(0)

        # measure
        self.man_meas2entry = ttk.Entry(self.manframe, validate="key", validatecommand=measvalidation, width=10)
        self.man_meas2entry.grid(row=3, column=4,padx=2)

        # Tab for entering manual data by file
        #TODO Auto align sheet fields to columns
        ttk.Label(self.manfileframe,
                  text="File with manual data must have datetime, reading, and locationid fields").grid(row=0,
                                                                                                        column=0,
                                                                                                        columnspan=4)
        ttk.Label(self.manfileframe,
                  text="Good for matching bulk manual data").grid(row=1, column=0, columnspan=4)

        self.man_string = StringVar(self.manfileframe, value='Double-Click for file')
        self.man_entry = ttk.Entry(self.manfileframe, textvariable=self.man_string, width=80, justify=LEFT)
        self.man_entry.grid(row=2, column=0, columnspan=4)
        self.man_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.opendiag(framename='Man Data'))

        ttk.Label(self.manfileframe,  text="Datetime").grid(row=3, column=0)
        self.mandatetime = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.mandatetime))
        self.mandatetime.grid(row=4, column=0)

        ttk.Label(self.manfileframe, text="DTW").grid(row=3, column=1)
        self.manmeas = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.manmeas))
        self.manmeas.grid(row=4, column=1)

        ttk.Label(self.manfileframe, text="locationid").grid(row=3, column=2)
        self.manlocid = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.manlocid))
        self.manlocid.grid(row=4, column=2)

        ttk.Label(self.manfileframe, text="Which locationid?").grid(row=5, column=1)
        #self.real_locid = StringVar(self.manfileframe)
        self.reallocid = ttk.Combobox(self.manfileframe, width=15,
                                    values=['1001','1002'],
                                    postcommand=lambda: self.man_col_select_loc(self.reallocid))
        self.reallocid.grid(row=5, column=2)

        ttk.Label(self.manfileframe, text="units").grid(row=3, column=3)
        self.manunits = ttk.Combobox(self.manfileframe, width=5,
                                    values=['ft','m'], state="readonly")
        self.manunits.grid(row=4, column=3)
        self.manunits.current(0)

        ttk.Button(self.frame_step4, text='Process Manual Data',
                   command=self.proc_man).grid(column=0,row=2,columnspan=3)

        # Fix Drift Button
        self.frame_step5 = ttk.Frame(self.frame_content)
        self.frame_step5.grid(row=6, column=0, columnspan=3)
        ttk.Label(self.frame_step5, text='5. Fix Drift').grid(column=0,row=0,columnspan=3)

        self.max_drift = StringVar(self.frame_step5,value="")
        ttk.Button(self.frame_step5, text='Fix Drift',
                   command=self.fix_drift).grid(column=0,row=1,columnspan=1)
        ttk.Label(self.frame_step5, text='Drift = ').grid(row=1, column=1)
        ttk.Label(self.frame_step5, textvariable=self.max_drift).grid(row=1, column=2)
        #self.locchk = ttk.Entry(self.frame_step5)
        #self.locchk.grid(column=1,row=0)

        # Fix Drift Button
        self.frame_step6 = ttk.Frame(self.frame_content)
        self.frame_step6.grid(row=7, column=0, columnspan=3)
        ttk.Label(self.frame_step6, text='6. Align Elevation and Offset').grid(row=0,column=0, columnspan = 4)
        ttk.Label(self.frame_step6, text='Ground Elev.').grid(row=1, column=0)
        ttk.Label(self.frame_step6, text='Stickup').grid(row=1, column=2)
        ttk.Label(self.frame_step6, text='Elev. Units').grid(row=1, column=1)
        ttk.Label(self.frame_step6, text='Stickup Units').grid(row=1, column=3)
        self.wellgroundelev = ttk.Entry(self.frame_step6,width=6)
        self.wellgroundelevunits = ttk.Combobox(self.frame_step6, width=5,
                                    values=['ft','m'], state="readonly")
        self.wellgroundelevunits.current(0)
        self.wellstickup = ttk.Entry(self.frame_step6,width=4)
        self.wellstickupunits = ttk.Combobox(self.frame_step6, width=5,
                                    values=['ft','m'], state="readonly")
        self.wellgroundelevunits.current(0)
        self.wellgroundelev.grid(row=2,column=0)
        self.wellgroundelevunits.grid(row=2,column=1)
        self.wellstickup.grid(row=2,column=2)
        self.wellstickupunits.grid(row=2,column=3)

        self.calc_elev = ttk.Button(self.frame_step6, text='Calculate Elevations', command=self.elevcalc)
        self.calc_elev.grid(row=3,column=0,columnspan=3)

        # add tabs in the frame to the right
        self.notebook = ttk.Notebook(self.frame2)
        self.notebook.pack(fill=BOTH, expand=True)
        self.notelist = {}
        #self.frame4 = ttk.Frame(self.notebook)
        #self.frame5 = ttk.Frame(self.notebook)
        #self.notebook.add(self.frame4, text='Table')
        #self.notebook.add(self.frame5, text='Plot Well Data')
        #self.notebook.select(1)
        #self.frame5.pack()

    def animate(self, frame, fig, ax, framename):
        if "welldata" in self.__dict__.keys():
            self.welldata.redraw()
            #self.welldata.update()
        animation.FuncAnimation(fig, lambda: self.make_graph_frame(fig, ax, framename=framename), interval=1000)


    def elevcalc(self):
        mstickup = self.wellstickup.get()
        melev = self.wellgroundelev.get()
        if self.wellstickupunits.get() == 'm':
            mstickup = mstickup * 3.2808
        elif self.wellgroundelevunits.get() == 'm':
           melev = melev * 3.2808
        self.manelevs = ll.get_man_gw_elevs(self.man_entry_df,mstickup, melev)
        self.transelevs = ll.get_trans_gw_elevations()
        print(self.manelevs)

    def fix_drift(self):
        self.wellbarofixed, self.drift_info, mxdrft = ll.fix_drift(self.alignwellbaro,self.man_entry_df)
        self.max_drift.set(mxdrft)
        self.wellbarofixed = self.wellbarofixed[['datetime','barometer','corrwl','DTW_WL']]
        df = self.wellbarofixed
        framename = 'Fixed Drift'
        new_frame = ttk.Frame(self.notebook)
        self.notebook.add(new_frame, text=framename)
        panedframe = ttk.Panedwindow(new_frame, orient=VERTICAL)
        panedframe.pack(fill=BOTH, expand=True)
        tableframe = ttk.Frame(panedframe, relief=SUNKEN)
        graphframe = ttk.Frame(panedframe, relief=SUNKEN)
        panedframe.add(tableframe, weight=1)
        panedframe.add(graphframe, weight=4)
        pt = pandastable.Table(tableframe, dataframe=df,
                               showtoolbar=True, showstatusbar=True)
        pt.show()
        self.make_graph_frame(graphframe, framename=framename)

    def aligndata(self):
        self.alignwellbaro = ll.well_baro_merge(self.welldata, self.barodata, sampint=self.freqint.get())
        framename = 'Well Baro'
        new_frame = ttk.Frame(self.notebook)
        self.notebook.add(new_frame, text=framename)
        panedframe = ttk.Panedwindow(new_frame, orient=VERTICAL)
        panedframe.pack(fill=BOTH, expand=True)
        tableframe = ttk.Frame(panedframe, relief=SUNKEN)
        graphframe = ttk.Frame(panedframe, relief=SUNKEN)
        panedframe.add(tableframe, weight=1)
        panedframe.add(graphframe, weight=4)
        pt = pandastable.Table(tableframe, dataframe=self.alignwellbaro.reset_index(),
                               showtoolbar=True, showstatusbar=True)
        pt.show()
        self.make_graph_frame(graphframe, framename=framename)


    def proc_man(self):
        nbnum = self.manbook.index(self.manbook.select())
        if nbnum == 0:
            man1_datetime = pd.to_datetime(f'{self.man_date1entry.get()} {self.hour1.get()}:{self.min1.get()}',
                                                format='%m/%d/%Y %H:%M')
            man2_datetime = pd.to_datetime(f'{self.man_date2entry.get()} {self.hour2.get()}:{self.min2.get()}',
                                                format='%m/%d/%Y %H:%M')
            df = pd.DataFrame({'readingdate':[man1_datetime,man2_datetime],
                                              'measureddtw':[self.man_meas1entry.get(),
                                                          self.man_meas2entry.get()],
                                              'locationid':[self.man_locid.get()]*2,
                                              'units':[self.manunits.get()]*2})
            if self.manunits.get()=='m':
                df['measureddtw'] = df['measureddtw']*3.28084
            self.man_entry_df = df.set_index(['readingdate'])
            print(self.man_entry_df)
        elif nbnum == 1:
            df = self.mandata.rename(columns={self.mandatetime.get():'readingdate',
                                                     self.manmeas.get():'measureddtw',
                                                     self.manlocid.get():'locationid'})
            df['units']=self.manunits.get()
            if self.manunits.get()=='m':
                df['measureddtw'] = df['measureddtw']*3.28084
            df = df.set_index(['readingdate'])
            self.man_entry_df = df[['measureddtw','locationid','units']]
            self.man_entry_df = self.man_entry_df[self.man_entry_df['locationid']==int(self.reallocid.get())]

        if 'man_entry_df' in self.__dict__.keys():
            framename = 'Man Data'
            #TODO destroy framename by the same name
            new_frame = ttk.Frame(self.notebook)
            self.notebook.add(new_frame, text=framename)
            panedframe = ttk.Panedwindow(new_frame, orient=VERTICAL)
            panedframe.pack(fill=BOTH, expand=True)
            tableframe = ttk.Frame(panedframe, relief=SUNKEN)
            graphframe = ttk.Frame(panedframe, relief=SUNKEN)
            panedframe.add(tableframe, weight=1)
            panedframe.add(graphframe, weight=4)
            pt = pandastable.Table(tableframe, dataframe=self.man_entry_df.reset_index(),
                                   showtoolbar=True, showstatusbar=True)
            pt.show()
            self.make_graph_frame(graphframe, framename=framename, plotvar='measureddtw')

    def combodateassign(self, cmbo):
        print(cmbo.get())

    def man_col_select(self, cmbo):
        if 'mandata' in self.__dict__.keys():
            mancols = list(self.mandata.columns.values)
            cmbo['values'] = mancols

            for col in mancols:
                if col in ['datetime', 'date', 'readingdate', 'Date']:
                    self.mandatetime.current(mancols.index(col))
        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.opendiag(framename='Man Data')


    def man_col_select_loc(self, cmbo):
        if 'mandata' in self.__dict__.keys():
            locids = self.mandata[str(self.manlocid.get())].unique()
            #TODO this will cause problems later; change to handle multiple types
            cmbo['values'] = list([f'{loc:0.0f}' for loc in locids])
        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.opendiag(framename='Man Data')

    def only_meas(self, value_if_allowed):
        try:
            float(value_if_allowed)
            bool = True
        except ValueError:
            bool = False
        return bool


    def destroy_graph(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()



    def make_graph_frame(self, fig, ax, framename, plotvar='Level'):
        # populate main graph tab
        # Create Tab Buttons
        #self.graph_button_frame1 = ttk.Frame(frame)
        #self.button_left = Button(self.graph_button_frame1, text="< Decrease Slope", command=self.decrease)
        #self.button_left.pack(side="left")
        #self.button_right = Button(self.graph_button_frame1, text="Increase Slope >", command=self.increase)
        #self.button_right.pack(side="left")
        #self.graph_button_frame1.pack()
        #if framename not in('Raw Baro', 'Manual'):


        ax.clear()
        if framename == 'Raw Baro':
            if 'barodata' in self.__dict__.keys():
                self.barodata.redraw()
                self.barodata.update()
                ax.plot(self.barodata.model.df.set_index(['DateTime']).index, self.barodata.model.df['Level'])
                ax.set_ylabel("Pressure")
        elif framename == 'Raw Well':
            if 'welldata' in self.__dict__.keys():
                self.welldata.redraw()
                self.welldata.update()
                ax.plot(self.welldata.model.df.set_index(['DateTime']).index, self.welldata.model.df['Level'])
                ax.set_ylabel("Pressure")
        elif framename == 'Man Data':
            if 'man_entry_df' in self.__dict__.keys():
                df = self.man_entry_df
                ax.scatter(df.index, df[plotvar])
                ax.set_ylabel(f"Depth To Water {self.manunits.get()}")
        elif framename == 'Well Baro':
            if 'alignwellbaro' in self.__dict__.keys():
                df = self.alignwellbaro
                plotvar = 'corrwl'
                ax.plot(df.index, df[plotvar], color='red', label='Well')
                ax.set_ylabel('Well Pressure', color='red')
                ax2 = ax.twinx()
                ax2.plot(df.index, df['barometer'], color='blue', label='Baro')
                ax2.set_ylabel('Baro Pressure', color='blue')
        elif framename == 'Fixed Drift':
            if 'wellbarofixed' in self.__dict__.keys():
                df1 = self.wellbarofixed.set_index('datetime')
                plotvar = 'DTW_WL'
                ax.plot(df1.index, df1[plotvar], color='red', label='Well')
                df2 = self.man_entry_df
                ax.scatter(df2.index, df2['measureddtw'])
                ax.set_ylabel(f"Depth To Water {self.manunits.get()}")
                ax.set_xlim(df1.first_valid_index()-pd.Timedelta('3 days'),
                            df1.last_valid_index()+pd.Timedelta('3 days'),)


        #self.line, = ax.plot(df.index, df[plotvar])
        #ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M')
        ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M')
        graphpage(self.graph_frame1, fig)
        #self.canvas = FigureCanvasTkAgg(fig, master=self.graph_frame1)
        #toolbar = NavigationToolbar2Tk(self.canvas, self.graph_frame1)
        #toolbar.update()
        #self.canvas.draw()
        #self.canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        #self.canvas.mpl_connect("key_press_event", self.on_key_press)



    def decrease(self):
        x, y = self.line.get_data()
        self.line.set_ydata(y*0.8)
        self.canvas.draw()

    def increase(self):
        x, y = self.line.get_data()
        self.line.set_ydata(y*1.2)
        self.canvas.draw()

    def _quit(self):
        self.quit()     # stops mainloop
        self.destroy()  # this is necessary on Windows to prevent
                    # Fatal Python Error: PyEval_RestoreThread: NULL tstate

    def opendiag(self, framename='New'):
        if framename in ('Raw Well','Raw Baro'):
            ftypelist = (("Solinst xle","*.xle*"),("Solinst csv","*.csv"))
        else:
            ftypelist = (("csv","*.csv*"),("xlsx","*.xlsx"),("xls",".xls"))
        #if event:
        filename = filedialog.askopenfilename(initialdir = self.currentdir, title = "Select file", filetypes = ftypelist)
        self.currentdir = os.path.dirname(filename)
        if filename == '' or type(filename) == tuple:
            pass
        else:
            if framename in ('Raw Well','Raw Baro'):
                if framename in self.notelist.keys():
                    self.notebook.forget(self.notelist[framename])
                    self.notelist[framename] = 'old'
                new_frame = ttk.Frame(self.notebook)
                self.notebook.add(new_frame, text=framename)
                for t in range(len(self.notebook.tabs())):
                    self.notelist[self.notebook.tab(t)['text']] = t

                print(self.notelist)
                panedframe = ttk.Panedwindow(new_frame, orient=VERTICAL)
                panedframe.pack(fill=BOTH, expand=True)
                tableframe = ttk.Frame(panedframe, relief=SUNKEN)
                graphframe = ttk.Frame(panedframe, relief=SUNKEN)
                panedframe.add(tableframe, weight=1)
                panedframe.add(graphframe, weight=4)
                butframe = ttk.Frame(graphframe)
                butframe.pack()
                df = ll.NewTransImp(filename).well.drop(['name'], axis=1)
                self.graph_frame1 = ttk.Frame(graphframe)

                fig = Figure()
                ax = fig.add_subplot(111)


                if framename == 'Raw Well':
                    self.welldata = pandastable.Table(tableframe, dataframe=df.reset_index(), showtoolbar=True, showstatusbar=True)
                    self.well_string.set(filename)
                    self.welldata.show()
                elif framename == 'Raw Baro':
                    self.barodata = pandastable.Table(tableframe, dataframe=df.reset_index(), showtoolbar=True, showstatusbar=True)
                    self.baro_string.set(filename)
                    self.barodata.show()
                self.make_graph_frame(fig,ax,framename=framename)

                self.anigraph = ttk.Button(butframe, text="Refresh Graph",
                                           command=self.make_graph_frame(fig, ax, framename=framename))
                self.anigraph.pack()
                self.graph_frame1.pack()
            elif framename == 'Man Data':
                #https://stackoverflow.com/questions/45357174/tkinter-drop-down-menu-from-excel
                #TODO add excel sheet options to file selection
                filenm, file_extension = os.path.splitext(filename)
                self.man_string.set(filename)
                if file_extension in ('.xls', '.xlsx'):
                    self.mandata = pd.read_excel(filename)
                elif file_extension == '.csv':
                    self.mandata = pd.read_csv(filename)



class graphpage(Frame):
    def __init__(self, parent, fig):
        Frame.__init__(self, parent)
        label = Label(self, text='Graph')
        label.pack(pady=10, padx=10)
        self.canvas = FigureCanvasTkAgg(fig, master=parent)
        toolbar = NavigationToolbar2Tk(self.canvas, parent)
        toolbar.update()
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        self.canvas.mpl_connect("key_press_event", self.on_key_press)

    def on_key_press(self, event):
        print("you pressed {}".format(event.key))
        key_press_handler(event, self.canvas, self.toolbar)




def main():
    root = Tk()
    feedback = Feedback(root)
    root.mainloop()

#tkinter.mainloop()
# If you put root.destroy() here, it will cause an error if the window is
# closed with the window manager.
if __name__ == "__main__": main()
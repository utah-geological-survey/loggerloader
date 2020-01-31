from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
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
        self.well_entry = ttk.Entry(self.frame_content, textvariable=self.well_string,width=80, justify=LEFT)
        self.well_entry.grid(row=1, column=0, columnspan=3)
        self.well_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.graphframe(framename='Raw Well'))

        # Select Baro Table Interface
        ttk.Label(self.frame_content, text="2. Select Barometric Data:").grid(row=2, column=0, columnspan=3)
        self.baro_string = StringVar(self.frame_content, value='Double-Click for file')
        self.baro_entry = ttk.Entry(self.frame_content, textvariable=self.baro_string, width=80, justify=LEFT)
        self.baro_entry.grid(row=3, column=0, columnspan=3)
        self.baro_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.graphframe(framename='Raw Baro'))

        # Select Manual Table Interface
        ttk.Label(self.frame_content, text="3. Select Manual Data:").grid(row=4,column=0,columnspan=3)
        self.manbook = ttk.Notebook(self.frame_content)
        self.manbook.grid(row=5, column=0, columnspan=3)
        self.manframe = ttk.Frame(self.manbook)
        self.manfileframe = ttk.Frame(self.manbook)
        self.manbook.add(self.manframe, text='Manual Entry')
        self.manbook.add(self.manfileframe, text='Data Import')
        # validates time number inputs
        validation = self.manframe.register(self.only_numbers)

        # measure 2 manually input manual data ---------------------------------
        # labels
        ttk.Label(self.manframe, text= "Date of Measure 1").grid(row=0, column=0)
        ttk.Label(self.manframe, text="HH:MM").grid(row=0, column=1, columnspan=2)
        ttk.Label(self.manframe, text="Measure 1").grid(row=0, column=4)
        # date picker
        man_date1entry = DateEntry(self.manframe, width=20, locale='en_US', date_pattern='MM/dd/yyyy')
        man_date1entry.grid(row=1, column=0,padx=2)
        # time picker
        hour1 = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=5)
        min1 = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=5)
        hour1.grid(row=1,column=1)
        ttk.Label(self.manframe, text=":").grid(row=1, column=2)
        min1.grid(row=1,column=3)
        # measure
        man_meas1entry = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=10)
        man_meas1entry.grid(row=1, column=4,padx=2)

        # measure 2 manually input manual data -----------------------------------
        ttk.Label(self.manframe, text= "Date of Measure 2").grid(row=2, column=0)
        ttk.Label(self.manframe, text="HH:MM").grid(row=3, column=1, columnspan=2)
        ttk.Label(self.manframe, text="Measure 2").grid(row=2, column=4)
        # date picker
        man_date2entry = DateEntry(self.manframe, width=20,
                                   locale='en_US', date_pattern='MM/dd/yyyy')
        man_date2entry.grid(row=3, column=0,padx=2)
        # time picker
        hour2 = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=5)
        min2 = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=5)
        hour2.grid(row=3,column=1)
        ttk.Label(self.manframe, text=":").grid(row=3, column=2)
        min2.grid(row=3,column=3)
        # measure
        man_meas2entry = ttk.Entry(self.manframe, validate="key", validatecommand=(validation, '%S'), width=10)
        man_meas2entry.grid(row=3, column=4,padx=2)

        # Tab for entering manual data by file
        ttk.Label(self.manfileframe,
                  text="File with manual data must have datetime, reading, and locationid fields").grid(row=0,
                                                                                                        column=0,
                                                                                                        columnspan=4)
        ttk.Label(self.manfileframe,
                  text="Good for matching bulk manual data").grid(row=1, column=0, columnspan=4)

        self.man_string = StringVar(self.manfileframe, value='Double-Click for file')
        self.man_entry = ttk.Entry(self.manfileframe, textvariable=self.man_string, width=80, justify=LEFT)
        self.man_entry.grid(row=2, column=0, columnspan=4)
        self.man_entry.bind('<Double-ButtonRelease-1>', lambda fn: self.graphframe(framename='Man Data'))

        ttk.Label(self.manfileframe,  text="Datetime").grid(row=3, column=0)
        self.mandatetime = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.mandatetime))
        self.mandatetime.grid(row=4, column=0)
        self.mandatetime.bind("<<ComboboxSelected>>", lambda cmb: self.combodateassign(self.mandatetime))

        ttk.Label(self.manfileframe, text="DTW").grid(row=3, column=1)
        self.manmeas = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.manmeas))
        self.manmeas.grid(row=4, column=1)
        self.manmeas.bind("<<ComboboxSelected>>", lambda cmb: self.combodateassign(self.manmeas))

        ttk.Label(self.manfileframe, text="locationid").grid(row=3, column=2)
        self.manlocid = ttk.Combobox(self.manfileframe, width=15,
                                    values=['datetime','meas','locid'],
                                    postcommand=lambda: self.man_col_select(self.manlocid))
        self.manlocid.grid(row=4, column=2)
        self.manlocid.bind("<<ComboboxSelected>>", lambda cmb: self.combodateassign(self.manlocid))

        ttk.Label(self.manfileframe, text="units").grid(row=3, column=3)
        self.manunits = ttk.Combobox(self.manfileframe, width=5,
                                    values=['ft','m'],state="readonly")
        self.manunits.grid(row=4, column=3)

        #self.well_entry.grid(row=2, column=1, columnspan=2)
        #self.well_file = ttk.Entry(self.frame_content, width=24).grid(row=0,column=1)

        # add tabs in the frame to the right
        self.notebook = ttk.Notebook(self.frame2)
        self.notebook.pack(fill=BOTH, expand=True)
        self.frame4 = ttk.Frame(self.notebook)
        self.frame5 = ttk.Frame(self.notebook)
        self.notebook.add(self.frame4, text='Table')
        self.notebook.add(self.frame5, text='Plot Well Data')
        self.notebook.select(1)
        #self.frame5.pack()

    def combodateassign(self, cmbo):
        print(cmbo.get())

    def man_col_select(self, cmbo):
        if 'mandata' in self.__dict__.keys():
            cmbo['values'] = list(self.mandata.columns.values)
        else:
            messagebox.showinfo(title='Attention', message='Select a manual file!')
            self.browsemanfunc(True)

    def only_numbers(self, char):
        return char.isdigit()

    def destroy_graph(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

    def make_graph(self, frame, plotvar='Level', framename='Raw Well'):
        # populate main graph tab
        # Create Tab Buttons
        self.graph_button_frame1 = ttk.Frame(frame)
        self.button_left = Button(self.graph_button_frame1, text="< Decrease Slope", command=self.decrease)
        self.button_left.pack(side="left")
        self.button_right = Button(self.graph_button_frame1,text="Increase Slope >", command=self.increase)
        self.button_right.pack(side="left")
        self.graph_button_frame1.pack()

        # Create Main Graph
        self.graph_frame1 = ttk.Frame(frame)
        self.graph_frame1.pack()

        if framename not in('Raw Baro', 'Manual'):
            fig = Figure()
            ax = fig.add_subplot(111)

        if 'welldata' in self.__dict__.keys():
            df = self.welldata
        else:
            df = pd.DataFrame({'a':pd.date_range('2019-01-01','2019-01-04',freq='1D'),
                                      'Level':[8,9,8,8]})

        self.line, = ax.plot(df.index, df[plotvar])
        ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M')
        self.canvas = FigureCanvasTkAgg(fig, master=self.graph_frame1)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.graph_frame1)
        self.toolbar.update()
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=1)

        self.canvas.mpl_connect("key_press_event", self.on_key_press)

    def on_key_press(self, event):
        print("you pressed {}".format(event.key))
        key_press_handler(event, self.canvas, self.toolbar)

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

    def graphframe(self, framename='New'):
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
            new_frame = ttk.Frame(self.notebook)
            self.notebook.add(new_frame, text=framename)
            panedframe = ttk.Panedwindow(new_frame, orient=VERTICAL)
            panedframe.pack(fill=BOTH, expand=True)
            tableframe = ttk.Frame(panedframe, relief=SUNKEN)
            graphframe = ttk.Frame(panedframe, relief=SUNKEN)
            panedframe.add(tableframe, weight=1)
            panedframe.add(graphframe, weight=4)

            if framename in ('Raw Well','Raw Baro'):
                df = ll.NewTransImp(filename).well.drop(['name'], axis=1)
                if framename == 'Raw Well':
                    self.welldata = df
                    self.well_string.set(filename)
                elif framename == 'Raw Baro':
                    self.barodata = df
                    self.baro_string.set(filename)
                #pt = pandastable.Table(tableframe, dataframe=df, showtoolbar=True, showstatusbar=True)
                #pt.show()
                self.make_graph(graphframe)
            elif framename == 'Man Data':
                filenm, file_extension = os.path.splitext(filename)
                self.man_string.set(filename)
                if file_extension in ('.xls', '.xlsx'):
                    self.mandata = pd.read_excel(filename)
                elif file_extension == '.csv':
                    self.mandata = pd.read_csv(filename)

def main():
    root = Tk()
    feedback = Feedback(root)
    root.mainloop()

#tkinter.mainloop()
# If you put root.destroy() here, it will cause an error if the window is
# closed with the window manager.
if __name__ == "__main__": main()
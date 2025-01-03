import matplotlib
import matplotlib.pyplot as plt
from pylab import rcParams
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
matplotlib.use("TkAgg")
from tksheet import Sheet
import pandas as pd

import sys
import os
from typing import Any, Dict, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


try:
    from loader import NewTransImp, drop_duplicates_keep_max_by_field, jumpfix
    from plotly_tk_vis import PlotlyTkinterWidget
except:
    from .loader import NewTransImp, drop_duplicates_keep_max_by_field, jumpfix
    from .plotly_tk_vis import PlotlyTkinterWidget


rcParams['figure.figsize'] = 15, 10



def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ViewManager:
    """Manages view-related functionality"""

    def __init__(self, master, data_model):
        self.master = master
        self.data_model = data_model
        self.graphframe = {}
        self.tableframe = {}
        self.graph_frame1 = {}
        self.graphcanvas = {}
        self.selected_tab = None
        self.field = None

    def set_styles(self):
        plt.style.use('default')
        # Create a style
        self.style = ttk.Style(self.master)

        # Import the tcl file
        try:
            self.master.tk.call("source", resource_path("themes/forest-dark.tcl"))
            self.master.tk.call("source", resource_path("themes/forest-light.tcl"))
            self.style.theme_use("forest-light")
        except:
            try:
                self.master.tk.call("source", resource_path("themes/forest-dark.tcl"))
                self.master.tk.call("source", resource_path("themes/forest-light.tcl"))

                self.style.theme_use("forest-light")
            except:
                pass
        self.sheettheme = "light blue"

    def add_icon(self):
        try:
            self.master.iconbitmap(resource_path('data_files/icon.ico'))
        except:
            try:
                self.master.iconbitmap(r'G:/My Drive/Python/Pycharm/loggerloader/data_files/icon.ico')
            except:
                pass


    def create_main_interface(self):
        """Create main application interface"""
        # Create main paned window
        self.paned_window = ttk.Panedwindow(self.master, orient='horizontal')
        self.paned_window.pack(fill='both', expand=True)

        # Create processing frame
        self.process_frame = ttk.Frame(self.paned_window,
                                       width=200,
                                       height=400,
                                       relief='sunken')


        self.process_frame.pack(fill='both', expand=True)
        # Create results frame
        self.results_frame = ttk.Frame(self.paned_window,
                                       width=200,
                                       height=400,
                                       relief='sunken')

        self.results_frame.pack(fill='both', expand=True)

        # processing notebooks use both the process and results frames
        self.create_processing_notebook()
        self.create_notebook()

        # Add frames to paned window
        self.paned_window.add(self.process_frame, weight=2)
        self.paned_window.add(self.results_frame, weight=3)




    def create_notebook(self):
        """Create main notebook interface"""
        self.notebook = ttk.Notebook(self.results_frame)
        self.notebook.pack(fill='both', expand=True)
        self.notelist = {}
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)


    def create_processing_notebook(self):
        """Create processing notebook interface"""
        self.processing_notebook = ttk.Notebook(self.process_frame)
        self.processing_notebook.pack(fill='both', expand=True)

        # Create frames for different processing views
        self.create_single_well_frame()
        self.create_bulk_well_frame()
        self.create_many_files_frame()

    def create_single_well_frame(self):
        """Create frame for single well processing"""
        frame = ttk.Frame(self.processing_notebook)
        self.single_well_view = WellDataView(frame, self.results_frame)
        self.processing_notebook.add(frame, text='Single-Well Process')

    def create_bulk_well_frame(self):
        """Create frame for bulk well processing"""
        frame = ttk.Frame(self.processing_notebook)
        self.bulk_well_view = BulkWellView(frame, self.data_model)
        self.processing_notebook.add(frame, text='Bulk Well Process')

    def create_many_files_frame(self):
        """Create frame for processing many files"""
        frame = ttk.Frame(self.processing_notebook)
        self.many_files_view = ManyFilesView(frame, self.data_model)
        self.processing_notebook.add(frame, text='One Well Many files')

    def on_tab_changed(self, event):
        """Handle tab change events"""
        tab = event.widget.select()
        self.selected_tab = event.widget.tab(tab, "text")


class WellDataView:
    """View for displaying and editing well data"""

    def __init__(self, master, results):
        self.master = master
        self.right_frame = results
        self.data = {}  # Store dataframes
        self.datatable = {}  # Store sheet widgets
        self.selected_tab = None
        self.field = None

        # Create controller
        self.controller = WellDataController(self)

        self.create_widgets()

    def create_widgets(self):
        # Create paned window to split left/right panels
        self.panedwindow = ttk.Panedwindow(self.master, orient='horizontal')
        self.panedwindow.pack(fill='both', expand=True)

        # Left panel for controls and charts
        self.left_frame = ttk.Frame(self.panedwindow)

        # Right panel for data sheet
        #self.right_frame = ttk.Frame(self.panedwindow)

        self.panedwindow.add(self.left_frame, weight=1)
        #self.panedwindow.add(self.right_frame, weight=1)

        # Add controls to left frame
        self.create_control_widgets()

        # Create notebook for table tabs on right
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill='both', expand=True)
        self.notelist = {}

        # These lines tell which tab is selected
        self.notebook.bind("<<NotebookTabChanged>>", self.nbselect)

    def create_control_widgets(self):
        """Create control widgets in left panel"""
        # Header
        header_frame = ttk.Frame(self.left_frame)
        header_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(header_frame, text="Well Data").pack(side='left')

        # Data entry frame
        entry_frame = ttk.Frame(self.left_frame)
        entry_frame.pack(fill='x', padx=5)

        # Well ID entry
        ttk.Label(entry_frame, text="Well ID:").grid(row=0, column=0, padx=5)
        self.well_id_var = tk.StringVar()
        ttk.Entry(entry_frame, textvariable=self.well_id_var).grid(row=0, column=1)

        # Elevation entry
        ttk.Label(entry_frame, text="Elevation (ft):").grid(row=1, column=0, padx=5)
        self.elevation_var = tk.DoubleVar()
        ttk.Entry(entry_frame, textvariable=self.elevation_var).grid(row=1, column=1)

        # Stickup entry
        ttk.Label(entry_frame, text="Stickup (ft):").grid(row=2, column=0, padx=5)
        self.stickup_var = tk.DoubleVar()
        ttk.Entry(entry_frame, textvariable=self.stickup_var).grid(row=2, column=1)

        # Buttons
        button_frame = ttk.Frame(self.left_frame)
        button_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(button_frame, text="Import Well Data",
                   command=self.controller.import_well_data).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Import Baro Data",
                   command=self.controller.import_baro_data).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Process Data",
                   command=self.controller.process_data).pack(side='left', padx=5)

        # Chart notebook in left panel
        self.chart_notebook = ttk.Notebook(self.left_frame)
        self.chart_notebook.pack(fill='both', expand=True)

        # Matplotlib frame (default view)
        self.matplotlib_frame = ttk.Frame(self.chart_notebook)
        self.chart_notebook.add(self.matplotlib_frame, text='Default View')

        # Plotly frame (interactive view)
        self.plotly_frame = ttk.Frame(self.chart_notebook)
        self.chart_notebook.add(self.plotly_frame, text='Interactive View')

        # Initialize chart manager
        self.chart_manager = ChartManager(self.matplotlib_frame, self.plotly_frame)

    def update_plot(self, data, key="well"):
        """Update plots and sheet display"""
        try:

            # Store the data
            self.data = data

            # Update charts
            self.chart_manager.update_charts(data)

            # Create/update sheet display
            self.selected_tab = key

            # Create new notebook tab frame if needed
            if key not in self.notelist:
                new_frame = ttk.Frame(self.notebook)
                self.notebook.add(new_frame, text=key)
                self.notelist[key] = len(self.notebook.tabs()) - 1

            # Select the tab
            self.notebook.select(self.notelist[key])

            # Create sheet in the tab
            tab_frame = self.notebook.select()
            self.datatable[key] = Sheet(tab_frame,
                                        data=self.data.reset_index().values.tolist(),
                                        theme="light blue")

            self.datatable[key].change_theme(theme="light blue")
            self.datatable[key].headers(self.data.reset_index().columns)
            self.datatable[key].enable_bindings()

            self.datatable[key].pack(fill="both", expand=True)

            # Bind sheet interactions
            self.datatable[key].extra_bindings([
                ("column_select", lambda event: self.make_chart(event, key=key)),
                ("end_edit_cell", lambda event: self.end_edit_cell(event, key=key))
            ])

        except Exception as e:
            self.show_error(f"Error updating display: {str(e)}")

    def show_error(self, message: str):
        """Display error message"""
        messagebox.showerror("Error", message)

    def nbselect(self, event):
        """Handle notebook tab changes"""
        codedtabname = self.notebook.select()
        self.selected_tab = self.notebook.tab(codedtabname, "text")
        if self.selected_tab in self.data:
            self.chart_manager.update_charts(self.data[self.selected_tab])

    def make_chart(self, event=None, key=None):
        """Update chart when column is selected in sheet"""
        if event:
            self.field = list(self.data[key].columns)[event[1] - 1]
            self.chart_manager.update_charts(self.data[key])

    def end_edit_cell(self, event=None, key=None):
        """Handle cell edits in sheet"""
        if key in self.datatable.keys():
            df = pd.DataFrame(self.datatable[key].get_sheet_data(get_header=False, get_index=False))
            df.index = self.data[key].index

            if len(df.columns) == len(self.data[key].columns):
                df.columns = self.data[key].columns
            elif len(df.columns) - 1 == len(self.data[key].columns):
                df = df.iloc[:, 1:]
                df.columns = self.data[key].columns

            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except ValueError:
                    pass

            self.data[key] = df
            self.datatable[key].redraw(redraw_header=True, redraw_row_index=True)


class WellDataController:
    """Controls well data operations"""

    def __init__(self, view: WellDataView):
        self.view = view
        self.data = None
        self.well_data = None
        self.baro_data = None

    def import_data(self):
        """Import well data from file"""
        try:
            # Get file path
            filelist = filedialog.askopenfilenames(
                parent=self.view.master,
                title='Choose well data file(s)'
            )

            raw_trans_files = {}
            file_data_df = {}

            for i, file in enumerate(filelist):
                df = NewTransImp(file).well
                raw_trans_files[i] = df

                # Calculate file statistics
                first_date = df.first_valid_index()
                last_date = df.last_valid_index()
                file_mean = df['Level'].mean()
                file_std = df['Level'].std()
                file_max = df['Level'].max()
                file_min = df['Level'].min()
                file_range = file_max - file_min
                file_len = df.count(numeric_only=True)
                hours_dur = (last_date - first_date).total_seconds() / 3600

                file_data_df[i] = pd.Series({
                    'first_date': first_date,
                    'last_date': last_date,
                    'file_mean': file_mean,
                    'file_std': file_std,
                    'file_range': file_range,
                    'file_len': file_len,
                    'hours_dur': hours_dur,
                    'file_name': file,
                })

            self.data = pd.concat(raw_trans_files).reset_index().set_index('DateTime')
            self.file_data = pd.concat(file_data_df)

        except Exception as e:
            self.view.show_error(f"Error importing data: {str(e)}")

    def import_baro_data(self):
        """Import barometric data"""
        try:
            self.import_data()
            # Update view
            self.baro_data = self.data
            self.view.update_plot(self.baro_data, key='Baro')

            self.baro_file_data = self.file_data
        except Exception as e:
            self.view.show_error(f"Error importing barometric data: {str(e)}")

    def import_well_data(self):
        """Import barometric data"""
        try:
            self.import_data()
            self.well_data = self.data
            self.well_file_data = self.file_data
            # Update view
            self.view.update_plot(self.well_data, key='well')

        except Exception as e:
            self.view.show_error(f"Error importing barometric data: {str(e)}")

    def process_data(self):
        """Process well data with barometric correction"""
        try:
            if self.well_data is None:
                raise ValueError("No well data loaded")
            if self.baro_data is None:
                raise ValueError("No barometric data loaded")

            # Apply baro correction and processing steps...
            processed_data = self.well_data.copy()  # Placeholder

            # Update view with processed data
            self.view.update_plot(processed_data, "processed")

        except Exception as e:
            self.view.show_error(f"Error processing data: {str(e)}")


class BulkWellView:
    """View for processing multiple wells in bulk"""

    def __init__(self, master, data_model):
        self.master = master
        self.data_model = data_model
        self.create_widgets()

    def create_widgets(self):
        """Create widgets for bulk processing"""
        ttk.Label(self.master, text="Bulk Well Processing").pack()

        # Well info frame
        info_frame = ttk.LabelFrame(self.master, text="Well Information")
        info_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(info_frame, text="Import Well Info",
                   command=self.import_well_info).pack(side='left', padx=5)

        # Processing frame
        process_frame = ttk.LabelFrame(self.master, text="Bulk Processing")
        process_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(process_frame, text="Process All Wells",
                   command=self.process_wells).pack(side='left', padx=5)


    def import_well_info(self):
        # Implementation for importing well info
        pass

    def process_wells(self):
        # Implementation for processing wells
        pass

class ManyFilesView:
    """View for processing many files for one well"""

    def __init__(self, master, data_model):
        self.master = master
        self.data_model = data_model
        self.create_widgets()

    def create_widgets(self):
        """Create widgets for many files processing"""
        ttk.Label(self.master, text="Process Multiple Files").pack()

        # File selection frame
        file_frame = ttk.LabelFrame(self.master, text="File Selection")
        file_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(file_frame, text="Select Files",
                   command=self.import_data).pack(side='left', padx=5)

        # Processing frame
        process_frame = ttk.LabelFrame(self.master, text="Processing")
        process_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(process_frame, text="Process Files",
                   command=self.process_files).pack(side='left', padx=5)

    def import_data(self):
        """Import well data from one or multiple files"""
        # Create and show the multi-file import dialog
        filelist = filedialog.askopenfilenames(parent=self.master, title='Choose a file')

        raw_trans_files = {}
        file_data_df = {}

        for i, file in enumerate(filelist):
            df = NewTransImp(file).well
            raw_trans_files[i] = df
            first_date = df.first_valid_index()
            last_date = df.last_valid_index()
            file_mean = df['Level'].mean()
            file_std = df['Level'].std()
            file_max = df['Level'].max()
            file_min = df['Level'].min()
            file_range = file_max - file_min
            file_len = df.count(numeric_only=True)
            hours_dur = (last_date - first_date).total_seconds() / 3600
            file_data_df[i] = pd.Series({'first_date' :first_date,
                                         'last_date' :last_date,
                                         'file_mean' :file_mean,
                                         'file_std' :file_std,
                                         'file_range' :file_range,
                                         'file_len' :file_len,
                                         'hours_dur' :hours_dur,
                                         'file_name' :file,
                                         })
        self.data = pd.concat(raw_trans_files)
        self.file_data = pd.concat(file_data_df)

    def update_visualization(self, data: pd.DataFrame):
        """Update visualization with current options"""
        self.view.ax.clear()

        chart_type = self.view.chart_type_var.get()
        y_scale = self.view.y_scale_var.get()

        if chart_type in ['line', 'both']:
            self.view.ax.plot(data.index, data['level'],
                              label='Water Level', color='blue')

        if chart_type in ['scatter', 'both']:
            self.view.ax.scatter(data.index, data['level'],
                                 label='Measurements', color='red', alpha=0.5)

        if 'level_smoothed' in data.columns:
            self.view.ax.plot(data.index, data['level_smoothed'],
                              label='Smoothed', color='green', linestyle='--')

        self.view.ax.set_yscale(y_scale)
        self.view.ax.grid(True)
        self.view.ax.legend()
        self.view.ax.set_title(f"Well {self.well_data.well_id} Data")
        self.view.fig.autofmt_xdate()

        self.view.canvas.draw()


    def select_files(self):
        # Implementation for selecting files
        pass

    def process_files(self):
        # Implementation for processing files
        pass




class ChartManager:
    """Manages both matplotlib and plotly charts with smart column detection"""

    def __init__(self, matplotlib_frame, plotly_frame):
        self.matplotlib_frame = matplotlib_frame
        self.plotly_frame = plotly_frame

        # Initialize matplotlib
        self.fig = Figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=matplotlib_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Add matplotlib toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, matplotlib_frame)
        self.toolbar.update()

        # Initialize plotly widget
        self.plotly_widget = PlotlyTkinterWidget(plotly_frame)

        # Define common column names
        self.well_fields = ['Level', 'level', 'WaterLevel', 'water_level', 'well_level']
        self.baro_fields = ['barometer', 'Barometer', 'baro', 'BarometricPressure']
        self.corrected_fields = ['corrwl', 'CorrectedLevel', 'corrected_level']

    def detect_columns(self, data):
        """Detect measurement columns in the data"""
        well_field = None
        baro_field = None
        corrected_field = None

        # Detect well field
        for field in self.well_fields:
            if field in data.columns:
                well_field = field
                break

        # Detect barometric field
        for field in self.baro_fields:
            if field in data.columns:
                baro_field = field
                break

        # Detect corrected field
        for field in self.corrected_fields:
            if field in data.columns:
                corrected_field = field
                break

        return well_field, baro_field, corrected_field

    def update_charts(self, data):
        """Update both matplotlib and plotly charts"""
        # Print available columns for debugging
        print("Available columns:", data.columns.tolist())

        # Detect columns
        well_field, baro_field, corrected_field = self.detect_columns(data)

        # Update matplotlib
        self.ax.clear()

        if well_field or baro_field or corrected_field:
            # Plot well level
            if well_field:
                self.ax.plot(data.index, data[well_field],
                             label='Well Level', color='blue')

            # Plot barometric level on secondary y-axis
            if baro_field:
                ax2 = self.ax.twinx()
                ax2.plot(data.index, data[baro_field],
                         label='Barometric', color='red')
                ax2.set_ylabel('Barometric Level', color='red')

            # Plot corrected level
            if corrected_field:
                self.ax.plot(data.index, data[corrected_field],
                             label='Corrected', color='green')

        else:
            # If no recognized columns found, plot first numeric column
            numeric_cols = data.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) > 0:
                self.ax.plot(data.index, data[numeric_cols[0]],
                             label=numeric_cols[0])
            else:
                raise ValueError("No numeric columns found in data")

        # Format matplotlib chart
        self.ax.set_xlabel('Date')
        self.ax.set_ylabel('Water Level')
        self.ax.grid(True)
        self.fig.legend()
        self.fig.autofmt_xdate()
        self.canvas.draw()

        # Update plotly
        if well_field or baro_field or corrected_field:
            self.plotly_widget.plot_water_levels(
                data,
                well_field=well_field,
            )
        else:
            if len(numeric_cols) > 0:
                self.plotly_widget.plot_single_series(
                    data,
                    numeric_cols[0],
                    "Measurement Data"
                )

    def clear(self):
        """Clear both charts"""
        self.ax.clear()
        self.canvas.draw()
        # Plotly widget will clear on next update
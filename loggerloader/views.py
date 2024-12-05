import matplotlib
import matplotlib.pyplot as plt
from pylab import rcParams
matplotlib.use("TkAgg")

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
        self.create_processing_notebook()

        # Create results frame
        self.results_frame = ttk.Frame(self.paned_window,
                                       width=200,
                                       height=400,
                                       relief='sunken')
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
        # self.single_well_view = SingleWellView(frame, controller=self.data_model)
        self.single_well_view = WellDataView(frame)
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


class WellDataView  :# (ttk.Frame):
    """View for displaying and editing well data"""

    def __init__(self, master):
        # super().__init__(master)
        self.master = master
        self.controller = WellDataController
        self.create_widgets()

    def set_controller(self, controller):
        """Set the controller for this view"""
        self.controller = controller

    def create_widgets(self):
        # Header
        header_frame = ttk.Frame(self.master)
        header_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(header_frame, text="Well Data").pack(side='left')

        # Data entry frame
        entry_frame = ttk.Frame(self.master)
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
        button_frame = ttk.Frame(self.master)
        button_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(button_frame, text="Import Well Data",
                   command=self.import_data).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Process Data",
                   command=self.process_data).pack(side='left', padx=5)

        # Create visualization frame
        self.viz_frame = ttk.Frame(self.master)
        self.viz_frame.pack(fill='both', expand=True)

        # Create Plotly widget
        self.plot_widget = PlotlyTkinterWidget(self.viz_frame)


    def import_data(self):
        """Import well data from one or multiple files"""
        try:
            # Get file path

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
                file_data_df[i] = pd.Series({'first_date': first_date,
                                             'last_date': last_date,
                                             'file_mean': file_mean,
                                             'file_std': file_std,
                                             'file_range': file_range,
                                             'file_len': file_len,
                                             'hours_dur': hours_dur,
                                             'file_name': file,
                                             })
            self.data = pd.concat(raw_trans_files).reset_index().set_index('DateTime').sort_index()
            self.data = drop_duplicates_keep_max_by_field(self.data ,'Level')
            self.data = jumpfix(self.data, 'Level')
            self.file_data = pd.concat(file_data_df)
            # Update view
            self.update_plot(self.data)

        except Exception as e:
            self.show_error(f"Error importing data: {str(e)}")

    def process_data(self):
        """Process well data"""
        try:
            if self.controller:
                self.controller.process_data()
            else:
                self.show_error("Controller not set")

        except Exception as e:
            self.show_error(f"Error processing data: {str(e)}")

    def update_plot(self, data):
        """Update the plot with new data"""
        try:
            # Use Plotly widget to update plot
            self.plot_widget.plot_water_levels(
                data,
                well_field='Level'
            )

        except Exception as e:
            self.show_error(f"Error updating plot: {str(e)}")

    def show_error(self, message: str):
        """Display error message"""
        tk.messagebox.showerror("Error", message)

    def get_well_id(self):
        """Get well ID from entry"""
        return self.well_id_var.get()

    def get_elevation(self):
        """Get elevation from entry"""
        try:
            return self.elevation_var.get()
        except:
            return 0.0

    def get_stickup(self):
        """Get stickup from entry"""
        try:
            return self.stickup_var.get()
        except:
            return 0.0

class WellDataController:
    """Controls well data operations"""

    def __init__(self, view: WellDataView):
        self.view = view
        # self.processor = DataProcessor()
        self.well_data: pd.DataFrame = None
        self.baro_data: Optional[pd.DataFrame] = None

    def import_data(self):
        """Import well data from one or multiple files"""
        try:
            # Get file path

            # Create and show the multi-file import dialog
            filelist = filedialog.askopenfilenames(parent=WellDataView.master, title='Choose a file')

            raw_trans_files = {}
            file_data_df = {}

            for i, file in enumerate(filelist):
                print(file)
                df = NewTransImp(file).well
                print(df.head())
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
                file_data_df[i] = pd.Series({'first_date': first_date,
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

            # Update view
            self.view.update_plot(self.data['Level'])

        except Exception as e:
            self.view.show_error(f"Error importing data: {str(e)}")

    def import_baro_data(self):
        """Import barometric data"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select Barometric Data File",
                filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
            )

            if not file_path:
                return

            if file_path.endswith('.csv'):
                self.baro_data = pd.read_csv(file_path, parse_dates=['datetime'])
            else:
                self.baro_data = pd.read_excel(file_path, parse_dates=['datetime'])

            self.baro_data.set_index('datetime', inplace=True)

        except Exception as e:
            self.view.show_error(f"Error importing barometric data: {str(e)}")

    def process_data(self):
        """Process well data with barometric correction"""
        try:
            if self.well_data is None:
                raise ValueError("No well data loaded")
            if self.baro_data is None:
                raise ValueError("No barometric data loaded")

            # Align data
            aligned_data = self.processor.align_data(
                self.well_data.measurements,
                self.baro_data
            )

            # Apply correction
            processed_data = self.processor.apply_baro_correction(aligned_data)

            # Update view
            self.view.update_plot(processed_data)

        except Exception as e:
            self.view.show_error(f"Error processing data: {str(e)}")
class SingleWellView:
    """View for processing single well data"""


    def __init__(self, master, controller=None):
        super().__init__(master)
        self.controller = controller
        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(header_frame, text="Well Data").pack(side='left')

        # Data entry frame
        entry_frame = ttk.Frame(self)
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
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(button_frame, text="Import Data",
                   command=self.import_data).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Process Data",
                   command=self.process_data).pack(side='left', padx=5)

        # Create visualization frame
        self.viz_frame = ttk.Frame(self)
        self.viz_frame.pack(fill='both', expand=True)

        # Create Plotly widget
        self.plot_widget = PlotlyTkinterWidget(self.viz_frame)

    def import_data(self):
        """Import well data from file"""
        try:
            if self.controller:
                self.controller.import_data()

        except Exception as e:
            self.show_error(f"Error importing data: {str(e)}")

    def process_data(self):
        """Process well data"""
        try:
            if self.controller:
                self.controller.process_data()

        except Exception as e:
            self.show_error(f"Error processing data: {str(e)}")

    def update_plot(self, data):
        """Update the plot with new data"""
        try:
            # Use Plotly widget to update plot
            self.plot_widget.plot_water_levels(
                data,
                well_field='Level')

        except Exception as e:
            self.show_error(f"Error updating plot: {str(e)}")

    def show_error(self, message: str):
        """Display error message"""
        tk.messagebox.showerror("Error", message)

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
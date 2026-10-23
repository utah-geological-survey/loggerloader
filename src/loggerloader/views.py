import matplotlib
import matplotlib.pyplot as plt
from pylab import rcParams
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure
matplotlib.use("TkAgg")
from tksheet import Sheet
import pandas as pd

import sys
import os
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


from loggerloader.loader import NewTransImp, Drifting, fix_unit_change, read_troll_csv, well_baro_merge
from loggerloader.plotly_tk_vis import PlotlyTkinterWidget
from loggerloader.workflow import (ColumnMatchDialog, SingleWellWorkflow, FILE_TYPES,
                                   normalize_id, run_step)


rcParams['figure.figsize'] = 15, 10

FEET_PER_METER = 3.28084

# Field charted first when a table is shown
DEFAULT_FIELDS = {
    'well-baro': 'corrwl',
    'fixed-drift': 'DTW_WL',
    'wl-elev': 'waterelevation',
    'manual': 'dtwbelowcasing',
}

# in_units_out_units -> multiplier (from llgui's convertunits)
CONVERSION_FACTORS = {
    'psi_ft': 2.3072493927233, 'mmHg_ft': 0.044603347619955, 'ft_ft': 1.0,
    'bar_ft': 33.455256555148, 'kPa_ft': 0.33455256555148,
    'psi_psi': 1.0, 'mmHg_psi': 0.0193368, 'ft_psi': 0.43352750192825,
    'bar_psi': 14.5038, 'kPa_psi': 0.145038,
    'mmHg_mmHg': 1.0, 'psi_mmHg': 51.7149, 'ft_mmHg': 22.41984185852,
    'bar_bar': 1.0, 'mmHg_bar': 0.00133322, 'kPa_bar': 0.01, 'ft_bar': 0.029890669,
    'psi_bar': 0.0689476,
}


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def numeric_columns(df):
    return list(df.select_dtypes(include='number').columns)


def default_field(key, df):
    """Column to chart when a table is first shown"""
    cols = numeric_columns(df)
    for field in (DEFAULT_FIELDS.get(key), 'Level'):
        if field in cols:
            return field
    return cols[0] if cols else None


def file_summary(df, filename):
    """One row of statistics about an imported file"""
    first_date, last_date = df.first_valid_index(), df.last_valid_index()
    level = df['Level'] if 'Level' in df.columns else pd.Series(dtype=float)
    return {
        'file_name': str(filename),
        'first_date': first_date,
        'last_date': last_date,
        'records': len(df),
        'hours_dur': (last_date - first_date).total_seconds() / 3600 if len(df) else 0,
        'file_mean': level.mean(),
        'file_std': level.std(),
        'file_range': level.max() - level.min(),
    }


def plot_table(ax, key, data, field=None, manual=None, flip_y=False, grid=True, legend=True):
    """Draw a table on a matplotlib axis, the way llgui charted each step.

    Returns False if the table has nothing to chart (e.g. drift-info).
    """
    if data is None or data.empty or not isinstance(data.index, pd.DatetimeIndex):
        ax.text(0.5, 0.5, f"No chart for {key}", ha='center', va='center', transform=ax.transAxes)
        ax.set_axis_off()
        return False

    x = data.index
    if key == 'well-baro':
        if 'Level' in data.columns:
            ax.plot(x, data['Level'], label='Raw Data')
        if 'corrwl' in data.columns:
            ax.plot(x, data['corrwl'], label='Corrected Data')
        ax.set_ylabel('Level (ft)')
        if 'barometer' in data.columns:
            baro_ax = ax.twinx()
            baro_ax.plot(x, data['barometer'], label='Barometer', color='red')
            baro_ax.set_ylabel('Barometer (ft)', color='red')
            ax.plot([], [], label='Barometer', color='red')
    elif key == 'fixed-drift' and 'DTW_WL' in data.columns:
        ax.plot(x, data['DTW_WL'], label='Drift-corrected')
        if manual is not None and 'dtwbelowcasing' in manual.columns:
            ax.scatter(manual.index, -manual['dtwbelowcasing'], color='red', label='Manual', zorder=3)
        ax.set_ylabel('Depth to water (ft, negative down)')
    elif key == 'wl-elev' and 'waterelevation' in data.columns:
        ax.plot(x, data['waterelevation'], label='Water elevation')
        if manual is not None and 'waterelevation' in manual.columns:
            ax.scatter(manual.index, manual['waterelevation'], color='red', label='Manual', zorder=3)
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        ax.set_ylabel('Water elevation (ft)')
    elif key == 'manual' and 'dtwbelowcasing' in data.columns:
        ax.scatter(x, data['dtwbelowcasing'], color='red', label='Depth to water')
        ax.set_ylabel('Depth to water (ft)')
    else:
        field = field if field in numeric_columns(data) else default_field(key, data)
        if field is None:
            ax.text(0.5, 0.5, f"No numeric columns in {key}", ha='center', va='center',
                    transform=ax.transAxes)
            ax.set_axis_off()
            return False
        ax.plot(x, data[field], label=field)
        ax.set_ylabel(field)

    ax.set_title(key)
    ax.set_xlabel('Date')
    if flip_y:
        ax.invert_yaxis()
    if grid:
        ax.grid(True)
    if legend and ax.get_legend_handles_labels()[0]:
        ax.legend(loc='best')
    return True


class ViewManager:
    """Manages view-related functionality"""

    def __init__(self, master, data_model):
        self.master = master
        self.data_model = data_model
        self.selected_tab = None
        self.field = None
        self.sheettheme = "light blue"

    def set_styles(self):
        plt.style.use('default')
        # Create a style
        self.style = ttk.Style(self.master)

        # Import the tcl file
        try:
            self.master.tk.call("source", resource_path("themes/forest-dark.tcl"))
            self.master.tk.call("source", resource_path("themes/forest-light.tcl"))
            self.style.theme_use("forest-light")
        except tk.TclError:
            pass
        self.sheettheme = "light blue"

    def set_theme(self, mode="light"):
        """Switch between the forest light and dark themes"""
        if mode == "system":
            mode = "light"
        dark = mode == "dark"
        try:
            self.style.theme_use("forest-dark" if dark else "forest-light")
        except tk.TclError:
            return
        self.sheettheme = "dark green" if dark else "light blue"
        plt.style.use('dark_background' if dark else 'default')
        if hasattr(self, 'single_well_view'):
            self.single_well_view.set_sheet_theme(self.sheettheme)

    def add_icon(self):
        try:
            self.master.iconbitmap(resource_path('data_files/icon.ico'))
        except tk.TclError:
            pass

    def create_main_interface(self):
        """Create main application interface"""
        # Create main paned window
        self.paned_window = ttk.Panedwindow(self.master, orient='horizontal')
        self.paned_window.pack(fill='both', expand=True)

        # Processing steps and charts on the left, tables on the right
        self.process_frame = ttk.Frame(self.paned_window, width=200, height=400, relief='sunken')
        self.results_frame = ttk.Frame(self.paned_window, width=200, height=400, relief='sunken')

        self.create_processing_notebook()

        self.paned_window.add(self.process_frame, weight=2)
        self.paned_window.add(self.results_frame, weight=3)

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
        self.single_well_view.sheettheme = self.sheettheme
        self.processing_notebook.add(frame, text='Single-Well Process')

    def create_bulk_well_frame(self):
        """Create frame for bulk well processing"""
        from loggerloader.bulk import BulkWellView  # bulk imports from this module

        frame = ttk.Frame(self.processing_notebook)
        self.bulk_well_view = BulkWellView(frame, self.single_well_view)
        self.processing_notebook.add(frame, text='Bulk Well Process')

    def create_many_files_frame(self):
        """Create frame for processing many files"""
        frame = ttk.Frame(self.processing_notebook)
        self.many_files_view = ManyFilesView(frame, self.single_well_view)
        self.processing_notebook.add(frame, text='One Well Many files')


class WellDataView:
    """Single-well steps and chart on the left; one table tab per dataset on the right.

    ``data`` maps a table name (well, baro, well-baro, manual, drift-info,
    fixed-drift, wl-elev, ...) to its DataFrame.
    """

    def __init__(self, master, results):
        self.master = master
        self.right_frame = results
        self.data = {}  # Store dataframes
        self.datatable = {}  # Store sheet widgets
        self.tabs = {}  # Store notebook tab frames
        self.selected_tab = None
        self.field = None
        self.sheettheme = "light blue"

        # Create controller
        self.controller = WellDataController(self)

        self.create_widgets()

    def create_widgets(self):
        # Numbered processing steps
        self.workflow = SingleWellWorkflow(self.master, self)

        # Chart notebook below the steps
        self.chart_notebook = ttk.Notebook(self.master)
        self.chart_notebook.pack(fill='both', expand=True)

        self.matplotlib_frame = ttk.Frame(self.chart_notebook)
        self.chart_notebook.add(self.matplotlib_frame, text='Default View')
        self.plotly_frame = ttk.Frame(self.chart_notebook)
        self.chart_notebook.add(self.plotly_frame, text='Interactive View')

        self.chart_manager = ChartManager(self.matplotlib_frame, self.plotly_frame)

        # Notebook of table tabs on the right
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.pack(fill='both', expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.nbselect)

    # --- tables --- #

    def set_table(self, key, df, select=True):
        """Store a table, show it in its tab, and chart it"""
        self.data[key] = df
        values = df.reset_index().values.tolist()
        headers = [str(c) for c in df.reset_index().columns]

        if key in self.datatable:
            self.datatable[key].set_sheet_data(data=values, reset_col_positions=True,
                                               reset_row_positions=True, redraw=False)
            self.datatable[key].headers(headers)
            self.datatable[key].redraw()
        else:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=key)
            self.tabs[key] = frame
            sheet = Sheet(frame, data=values, headers=headers, theme=self.sheettheme)
            sheet.enable_bindings()
            sheet.pack(fill="both", expand=True)
            sheet.extra_bindings([
                ("column_select", lambda event, k=key: self.column_selected(event, k)),
                ("end_edit_cell", lambda event, k=key: self.end_edit_cell(event, k)),
                ("end_paste", lambda event, k=key: self.end_edit_cell(event, k)),
                ("end_delete", lambda event, k=key: self.end_edit_cell(event, k)),
                ("end_undo", lambda event, k=key: self.end_edit_cell(event, k)),
                ("end_rc_delete_row", lambda event, k=key: self.end_edit_cell(event, k)),
            ])
            self.datatable[key] = sheet

        if key in ('well', 'baro'):
            self.workflow.refresh_fields()

        if select:
            self.selected_tab = key
            if self.field not in numeric_columns(df):
                self.field = default_field(key, df)
            self.notebook.select(self.tabs[key])
            self.redraw()

    def clear_tables(self):
        """Remove every table (used when opening a project)"""
        for frame in self.tabs.values():
            self.notebook.forget(frame)
            frame.destroy()
        self.data, self.datatable, self.tabs = {}, {}, {}
        self.selected_tab = None
        self.chart_manager.clear()

    def remove_table(self, key):
        """Remove one table and its tab, if it exists"""
        frame = self.tabs.pop(key, None)
        if frame is not None:
            self.notebook.forget(frame)
            frame.destroy()
        self.data.pop(key, None)
        self.datatable.pop(key, None)
        if self.selected_tab == key:
            self.selected_tab = None

    def current_table(self):
        """(key, DataFrame) of the selected tab, or (None, None)"""
        if self.selected_tab in self.data:
            return self.selected_tab, self.data[self.selected_tab]
        return None, None

    def set_sheet_theme(self, theme):
        self.sheettheme = theme
        for sheet in self.datatable.values():
            sheet.change_theme(theme=theme, redraw=True)
        self.redraw()

    def redraw(self):
        key, df = self.current_table()
        if key is not None:
            self.chart_manager.draw(key, df, self.field, manual=self.data.get('manual'))

    def show_error(self, message: str):
        """Display error message"""
        messagebox.showerror("Error", message)

    # --- sheet events --- #

    def nbselect(self, event):
        """Chart the table whose tab was selected"""
        if not self.notebook.tabs():
            return
        key = self.notebook.tab(self.notebook.select(), "text")
        if key in self.data and key != self.selected_tab:
            self.selected_tab = key
            if self.field not in numeric_columns(self.data[key]):
                self.field = default_field(key, self.data[key])
            self.redraw()

    def column_selected(self, event, key):
        """Chart the column clicked in the sheet"""
        df = self.data[key]
        columns = list(df.reset_index().columns)
        try:
            col = event.selected.column
        except AttributeError:
            return
        if 0 <= col < len(columns) and columns[col] in numeric_columns(df):
            self.field = columns[col]
            self.selected_tab = key
            self.redraw()

    def end_edit_cell(self, event=None, key=None):
        """Copy sheet edits back into the DataFrame, keeping each column's type"""
        if key not in self.datatable:
            return
        original = self.data[key]
        flat_original = original.reset_index()
        rows = self.datatable[key].get_sheet_data()
        flat = pd.DataFrame(rows, columns=flat_original.columns[:len(rows[0])] if rows else flat_original.columns)
        for col in flat.columns:
            if pd.api.types.is_datetime64_any_dtype(flat_original[col]):
                flat[col] = pd.to_datetime(flat[col], errors='coerce')
            elif pd.api.types.is_numeric_dtype(flat_original[col]):
                flat[col] = pd.to_numeric(flat[col], errors='coerce')
        index_names = [n if n is not None else 'index' for n in original.index.names]
        df = flat.set_index(index_names)
        df.index.names = original.index.names
        self.data[key] = df
        if key == self.selected_tab:
            self.redraw()


class WellDataController:
    """Single-well processing (ported from llgui), called by SingleWellWorkflow"""

    def __init__(self, view: WellDataView):
        self.view = view
        self.file_data = None
        self.on_file_imported = None  # optional callback(filename)

    @property
    def data(self):
        return self.view.data

    # --- 1-2. import --- #

    def load_file(self, filename, filetype='auto'):
        """Read one file as a DataFrame indexed by DateTime; None if the user cancels"""
        if filetype == 'table':
            df = ColumnMatchDialog(self.view.master, filename).result
        elif filetype == 'troll-csv':
            df = read_troll_csv(filename)
        else:
            df = NewTransImp(filename).well
            if df is None:
                raise ValueError(f"Could not read {Path(filename).name} as a transducer file.")
        if df is not None and 'filename' not in df.columns:
            df['filename'] = Path(filename).stem
        return df

    def import_files(self, key, filelist=None, filetype='auto'):
        """Read and combine one or more files into the `key` table"""
        if filelist is None:
            filelist = filedialog.askopenfilenames(
                parent=self.view.master,
                title=f'Choose {key} data file(s)',
                filetypes=[('Logger files', '*.xle *.lev *.csv *.htm *.html *.xlsx *.xls'),
                           ('All files', '*.*')])
        if not filelist:
            return False

        frames, info = [], []
        for filename in filelist:
            df = self.load_file(filename, filetype)
            if df is None:
                return False
            frames.append(df)
            info.append(file_summary(df, filename))

        data = pd.concat(frames).sort_index()
        data = data[~data.index.duplicated(keep='first')]
        data.index.name = 'DateTime'
        self.file_data = pd.DataFrame(info)
        self.view.set_table(key, data)
        if self.on_file_imported:
            for filename in filelist:
                self.on_file_imported(filename)
        return True

    def import_well_data(self, filelist=None, filetype='auto'):
        return bool(run_step(self.import_files, 'well', filelist, filetype))

    def import_baro_data(self, filelist=None, filetype='auto'):
        return bool(run_step(self.import_files, 'baro', filelist, filetype))

    # --- 3. align --- #

    def align(self, well_field='Level', baro_field='Level', freq=60, vented=False):
        """Remove barometric pressure from the well data (llgui's alignedplot)"""
        if 'well' not in self.data:
            raise ValueError("Import well data first (step 1).")
        if not vented and 'baro' not in self.data:
            raise ValueError("Import barometric data first (step 2), or check 'Vented?'.")
        well = self.data['well']
        baro = self.data.get('baro', well)
        if well_field not in well.columns:
            raise ValueError(f"The well data has no '{well_field}' column.")
        if not vented and baro_field not in baro.columns:
            raise ValueError(f"The barometric data has no '{baro_field}' column.")
        try:
            df = well_baro_merge(well, baro, wellcolumn=well_field, barocolumn=baro_field,
                                 sampint=int(freq), vented=vented)
        except IndexError:
            raise ValueError("The well and barometric data do not overlap.")
        if df.empty:
            raise ValueError("The well and barometric data do not overlap.")
        self.view.set_table('well-baro', df)
        return df

    # --- 4. manual measurements --- #

    def manual_from_entry(self, readings, units='ft', locid=''):
        """Manual table from typed (datetime, depth to water) readings"""
        df = pd.DataFrame({
            'readingdate': [when for when, _ in readings],
            'dtwbelowcasing': [float(dtw) for _, dtw in readings],
            'locationid': locid,
            'units': units,
        })
        if units == 'm':
            df['dtwbelowcasing'] = df['dtwbelowcasing'] * FEET_PER_METER
        df = df.set_index('readingdate').sort_index()
        self.view.set_table('manual', df)
        return df

    def manual_from_table(self, table, date_col, dtw_col, locid_col, pick_id='', units='ft'):
        """Manual table from an imported file of readings for one location"""
        for label, col in (('datetime', date_col), ('depth to water', dtw_col), ('location id', locid_col)):
            if col not in table.columns:
                raise ValueError(f"Choose the {label} column.")
        df = table.rename(columns={date_col: 'readingdate', dtw_col: 'dtwbelowcasing',
                                   locid_col: 'locationid'})
        df = df[['readingdate', 'dtwbelowcasing', 'locationid']].copy()
        df['readingdate'] = pd.to_datetime(df['readingdate'], errors='coerce')
        df['dtwbelowcasing'] = pd.to_numeric(df['dtwbelowcasing'], errors='coerce')
        df = df.dropna(subset=['readingdate', 'dtwbelowcasing'])

        ids = df['locationid'].map(normalize_id)
        if pick_id:
            df = df[ids == normalize_id(pick_id)]
        elif ids.nunique() > 1:
            raise ValueError("The file has several location ids; choose one in 'Pick id'.")

        # Only readings near the transducer record, as in llgui
        if 'well' in self.data and len(self.data['well']):
            well = self.data['well']
            buffer = pd.DateOffset(days=8)
            df = df[(df['readingdate'] > well.first_valid_index() - buffer) &
                    (df['readingdate'] < well.last_valid_index() + buffer)]
        if df.empty:
            raise ValueError("No manual readings match that location and the well data's dates.")

        if units == 'm':
            df['dtwbelowcasing'] = df['dtwbelowcasing'] * FEET_PER_METER
        df['units'] = units
        df = df.set_index('readingdate').sort_index()
        self.view.set_table('manual', df)
        return df

    # --- 5. drift --- #

    def fix_drift(self):
        """Fit the barometrically corrected levels to the manual readings; returns max drift"""
        if 'well-baro' not in self.data:
            raise ValueError("Align the data first (step 3).")
        if 'manual' not in self.data:
            raise ValueError("Process manual data first (step 4).")
        manual = self.data['manual'].copy()
        # Drifting expects depths as negative numbers (below the casing)
        manual['dtwbelowcasing'] = manual['dtwbelowcasing'] * -1
        wellid = manual['locationid'].iloc[0] if 'locationid' in manual.columns else None
        df, drift_info, max_drift = Drifting(manual, self.data['well-baro'].copy(),
                                             drifting_field='corrwl',
                                             man_field='dtwbelowcasing',
                                             well_id=wellid,
                                             output_field='DTW_WL').process_drift()
        cols = [c for c in ('barometer', 'corrwl', 'DTW_WL', 'driftcorrection', 'Temperature')
                if c in df.columns]
        self.view.set_table('drift-info', drift_info, select=False)
        self.view.set_table('fixed-drift', df[cols])
        return max_drift

    # --- 6. elevation --- #

    def calc_elevations(self, ground, ground_units='ft', stickup=0.0, stickup_units='ft'):
        """Water elevations for the drift-corrected and manual data (llgui's elevcalc)"""
        if 'fixed-drift' not in self.data:
            raise ValueError("Fix drift first (step 5).")
        if ground_units == 'm':
            ground = ground * FEET_PER_METER
        if stickup_units == 'm':
            stickup = stickup * FEET_PER_METER

        if 'manual' in self.data:
            manual = self.data['manual'].copy()
            manual['waterelevation'] = ground + stickup - manual['dtwbelowcasing']
            self.view.set_table('manual', manual, select=False)

        df = self.data['fixed-drift'].copy()
        df['waterelevation'] = df['DTW_WL'] + stickup + ground
        self.view.set_table('wl-elev', df)
        return df

    def save_one_well(self, filename):
        """Write the elevation table in the database's column names"""
        df = self.data['wl-elev'].copy()
        df['measureddtw'] = -1 * df['DTW_WL']
        df = df.rename(columns={'Temperature': 'temperature', 'corrwl': 'measuredlevel'})
        df = df.drop(['DTW_WL'], axis=1).reset_index()
        if Path(filename).suffix.lower() in ('.xlsx', '.xls'):
            df.to_excel(filename, index=False)
        else:
            df.to_csv(filename, index=False)
        return filename

    # --- data tools --- #

    def convert_units(self, key, field, in_units, out_units, out_field):
        """Add out_field holding field converted from in_units to out_units"""
        df = self.data[key].copy()
        if in_units == 'C':
            df[out_field] = df[field] * 1.8 + 32.0 if out_units == 'F' else df[field]
        elif in_units == 'F':
            df[out_field] = (df[field] - 32.0) * 5.0 / 9.0 if out_units == 'C' else df[field]
        elif f'{in_units}_{out_units}' in CONVERSION_FACTORS:
            df[out_field] = df[field] * CONVERSION_FACTORS[f'{in_units}_{out_units}']
        else:
            raise ValueError(f"Can't convert {in_units} to {out_units}.")
        self.view.set_table(key, df)
        return df


class ManyFilesView:
    """Combine many files from one logger into the single-well well or baro table"""

    def __init__(self, master, well_view: WellDataView):
        self.master = master
        self.well_view = well_view
        self.frames = []
        self.create_widgets()

    def create_widgets(self):
        """Create widgets for many files processing"""
        file_frame = ttk.LabelFrame(self.master, text="1. Choose files from one logger")
        file_frame.pack(fill='x', padx=5, pady=5)
        self.filetype = ttk.Combobox(file_frame, values=list(FILE_TYPES), state='readonly', width=30)
        self.filetype.current(0)
        self.filetype.pack(side='left', padx=5)
        ttk.Button(file_frame, text="Select Files...", command=self.select_files).pack(side='left', padx=5)

        columns = ('file', 'first', 'last', 'records', 'mean')
        self.file_list = ttk.Treeview(self.master, columns=columns, show='headings', height=8)
        for col, width in zip(columns, (200, 130, 130, 70, 70)):
            self.file_list.heading(col, text=col.title())
            self.file_list.column(col, width=width, stretch=col == 'file')
        self.file_list.pack(fill='both', expand=True, padx=5)

        process_frame = ttk.LabelFrame(self.master, text="2. Combine")
        process_frame.pack(fill='x', padx=5, pady=5)
        self.fix_units = tk.BooleanVar(process_frame, value=False)
        ttk.Checkbutton(process_frame, text='Fix unit changes between files',
                        variable=self.fix_units).grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(process_frame, text='Send to').grid(row=1, column=0, sticky='w')
        self.target = ttk.Combobox(process_frame, values=['well', 'baro'], state='readonly', width=8)
        self.target.current(0)
        self.target.grid(row=1, column=1, sticky='w', padx=5)
        ttk.Button(process_frame, text="Combine Files",
                   command=self.process_files).grid(row=1, column=2, padx=5)
        self.status = tk.StringVar(process_frame, value='')
        ttk.Label(process_frame, textvariable=self.status, foreground='gray').grid(
            row=2, column=0, columnspan=3, sticky='w')

    def get_state(self):
        return {'fix_units': self.fix_units.get(), 'target': self.target.get()}

    def set_state(self, state):
        self.fix_units.set(state.get('fix_units', False))
        if state.get('target') in ('well', 'baro'):
            self.target.set(state['target'])

    def select_files(self, filelist=None):
        if filelist is None:
            filelist = filedialog.askopenfilenames(parent=self.master, title='Choose files from one logger')
        if not filelist:
            return False
        filetype = FILE_TYPES[self.filetype.get()]
        frames = []
        for filename in filelist:
            df = run_step(self.well_view.controller.load_file, filename, filetype)
            if df is None:
                return False
            if len(df):
                frames.append((filename, df))
        self.frames = sorted(frames, key=lambda item: item[1].first_valid_index())

        self.file_list.delete(*self.file_list.get_children())
        for filename, df in self.frames:
            info = file_summary(df, filename)
            self.file_list.insert('', 'end', values=(
                Path(filename).name, f"{info['first_date']:%Y-%m-%d %H:%M}",
                f"{info['last_date']:%Y-%m-%d %H:%M}", info['records'],
                '' if pd.isna(info['file_mean']) else f"{info['file_mean']:.3f}"))
        self.status.set(f'{len(self.frames)} file(s) loaded')
        return True

    def process_files(self):
        if not self.frames:
            messagebox.showwarning("Many Files", "Select files first.")
            return None
        frames = [df.copy() for _, df in self.frames]
        if self.fix_units.get():
            # llgui's fixstatjumps: scale each file to match the units of the one before it
            for i in range(1, len(frames)):
                if 'Level' in frames[i].columns and 'Level' in frames[i - 1].columns:
                    frames[i] = fix_unit_change(frames[i - 1], frames[i], field='Level')
        data = pd.concat(frames).sort_index()
        data = data[~data.index.duplicated(keep='first')]
        data.index.name = 'DateTime'
        target = self.target.get()
        self.well_view.set_table(target, data)
        self.well_view.workflow.file_status[target].set(f'{len(frames)} combined files')
        self.status.set(f'Sent {len(data)} rows to {target}')
        return data


class ChartManager:
    """Matplotlib chart of the selected table, plus an interactive plotly copy"""

    def __init__(self, matplotlib_frame, plotly_frame):
        self.matplotlib_frame = matplotlib_frame
        self.plotly_frame = plotly_frame

        # Chart options (View > Chart Options)
        self.grid = tk.BooleanVar(matplotlib_frame, value=True)
        self.legend = tk.BooleanVar(matplotlib_frame, value=True)
        self.flip_y = tk.BooleanVar(matplotlib_frame, value=False)

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

        self.last = None  # (key, data, field, manual) of the last draw

    def draw(self, key, data, field=None, manual=None):
        """Chart a table in both views"""
        self.last = (key, data, field, manual)
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        plotted = plot_table(self.ax, key, data, field, manual,
                             flip_y=self.flip_y.get(), grid=self.grid.get(), legend=self.legend.get())
        if plotted:
            self.fig.autofmt_xdate()
        self.canvas.draw()

        field = field if field in numeric_columns(data) else default_field(key, data)
        if plotted and field:
            self.plotly_widget.plot_water_levels(data, well_field=field)

    def refresh(self):
        """Redraw the last chart, e.g. after changing chart options"""
        if self.last is not None:
            self.draw(*self.last)

    def clear(self):
        """Clear both charts"""
        self.last = None
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.canvas.draw()

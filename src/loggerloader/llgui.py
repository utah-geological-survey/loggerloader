import matplotlib
import numpy as np
import pandas as pd
from pathlib import Path
from tksheet import Sheet
matplotlib.use("TkAgg")


import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from pylab import rcParams


import logging

from loggerloader.config import Configuration
from loggerloader.loader import jumpfix
from loggerloader.menu import ApplicationMenu
from loggerloader.project import EXTENSION, load_project, save_project
from loggerloader.qaqc import DEFAULT_SPIKE_THRESHOLDS, detect_transducer_spikes
from loggerloader.views import ViewManager, numeric_columns, plot_table
from loggerloader.workflow import run_step, unit_converter_popup


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


rcParams['figure.figsize'] = 15, 10

PROJECT_TYPES = [('Logger Loader project', f'*{EXTENSION}'), ('All files', '*.*')]


class DataModel:
    """Handles data storage and manipulation"""

    def __init__(self):
        self.data: pd.DataFrame = None
        self.well_data: pd.DataFrame = None
        self.baro_data: pd.DataFrame = None
        self.datatable = {}
        self.bcombo = {}
        self.locidmatch = {}
        self.bulktransfilestr = {}
        self.beg_end = {}

    def store_data(self, data):
        """Store data with given key"""
        self.data = data

    def get_data(self):
        """Retrieve data for given key"""
        return self.data

    def clear_data(self):
        """Clear data for given key"""
        if self.data is not None:
            self.data = None


class LoggerLoaderApp:
    """Main application class"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Logger Loader")
        self.root.geometry("1400x800")

        # Set up logging
        self.setup_logging()

        # Initialize components
        self.config = Configuration()
        self.project_path = None
        self.data_model = DataModel()
        self.view_manager = ViewManager(self.root, self.data_model)
        self.view_manager.set_styles()
        self.view_manager.add_icon()

        # Create interface (the menu binds to the chart options, so it comes second)
        self.view_manager.create_main_interface()
        self.well_view = self.view_manager.single_well_view
        self.chart_manager = self.well_view.chart_manager
        self.menu = ApplicationMenu(self.root, self)
        self.well_view.controller.on_file_imported = self.menu.add_recent_file

        saved_theme = self.menu.settings.get('theme', 'light')
        if saved_theme != 'light':
            self.set_theme(saved_theme)

    def setup_logging(self):
        """Set up application logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('LoggerLoader')

    def set_theme(self, mode):
        """Called from the View > Theme menu"""
        self.view_manager.set_theme(mode)
        self.menu.settings['theme'] = mode
        self.menu.save_settings()

    def refresh_chart(self):
        """Redraw the chart after a View > Chart Options change"""
        self.chart_manager.refresh()

    # --- helpers --- #

    def current_table(self, need_field=True):
        """(key, DataFrame, field) of the selected table tab, warning if there is none"""
        key, df = self.well_view.current_table()
        if key is None:
            messagebox.showwarning("Logger Loader", "Import data or select a table tab first.")
            return None, None, None
        field = self.well_view.field
        if need_field and field not in numeric_columns(df):
            messagebox.showwarning("Logger Loader", "Click a numeric column header in the table first.")
            return None, None, None
        if need_field and not isinstance(df.index, pd.DatetimeIndex):
            messagebox.showwarning("Logger Loader", f"{key} is not a time series.")
            return None, None, None
        return key, df, field

    def update_title(self):
        name = Path(self.project_path).name if self.project_path else 'untitled'
        self.root.title(f"Logger Loader - {name}")

    # --- File menu --- #

    def import_data(self, kind):
        """File > Import: well, baro, or manual data into the single-well steps"""
        workflow = self.well_view.workflow
        if kind in ('well', 'baro'):
            workflow.choose_file(kind)
        elif kind == 'manual':
            workflow.load_manual_file()

    def export_data(self, kind='processed'):
        """File > Export > Processed Data: every table to Excel, or the selected table to csv"""
        if not self.well_view.data:
            messagebox.showwarning("Export", "There is no data to export.")
            return
        filename = filedialog.asksaveasfilename(
            title='Export data',
            filetypes=[('Excel, all tables', '*.xlsx'), ('csv, selected table', '*.csv')],
            defaultextension='.xlsx', confirmoverwrite=True)
        if not filename:
            return
        if Path(filename).suffix.lower() == '.csv':
            key, df = self.well_view.current_table()
            if key is None:
                messagebox.showwarning("Export", "Select a table tab to export as csv.")
                return
            run_step(df.to_csv, filename)
        else:
            def write_all():
                with pd.ExcelWriter(filename) as writer:
                    for key, df in self.well_view.data.items():
                        df.to_excel(writer, sheet_name=key[:31])
            run_step(write_all)

    def export_charts(self):
        """File > Export > Charts: save the current chart as an image or pdf"""
        if self.chart_manager.last is None:
            messagebox.showwarning("Export", "There is no chart to export.")
            return
        filename = filedialog.asksaveasfilename(
            title='Export chart',
            filetypes=[('PNG image', '*.png'), ('PDF', '*.pdf'), ('SVG image', '*.svg')],
            defaultextension='.png', confirmoverwrite=True)
        if filename:
            run_step(self.chart_manager.fig.savefig, filename, dpi=150, bbox_inches='tight')

    def generate_report(self):
        """File > Export > Report: a pdf with a summary page and a chart of every table"""
        data = self.well_view.data
        if not data:
            messagebox.showwarning("Report", "There is no data to report.")
            return
        filename = filedialog.asksaveasfilename(title='Save report', filetypes=[('PDF', '*.pdf')],
                                                defaultextension='.pdf', confirmoverwrite=True)
        if filename:
            run_step(self.write_report, filename)

    def write_report(self, filename):
        data = self.well_view.data
        state = self.well_view.workflow.get_state()
        with PdfPages(filename) as pdf:
            fig = Figure(figsize=(11, 8.5))
            ax = fig.add_subplot(111)
            ax.set_axis_off()
            lines = ["Logger Loader report", "",
                     f"Well file(s): {state['file_status']['well']}",
                     f"Baro file(s): {state['file_status']['baro']}",
                     f"Max drift: {state['max_drift'] or 'n/a'}",
                     f"Ground elevation: {state['ground_elev'] or 'n/a'} {state['ground_units']}",
                     f"Stickup: {state['stickup']} {state['stickup_units']}", "",
                     "Tables: " + ", ".join(f"{k} ({len(v)} rows)" for k, v in data.items())]
            ax.text(0, 1, "\n".join(lines), va='top', fontsize=12, family='monospace', wrap=True)
            pdf.savefig(fig)

            for key, df in data.items():
                fig = Figure(figsize=(11, 8.5))
                ax = fig.add_subplot(111)
                if key == 'drift-info':
                    ax.set_axis_off()
                    shown = df.T.astype(str)
                    table = ax.table(cellText=shown.values, rowLabels=list(shown.index),
                                     colLabels=[str(c) for c in shown.columns], loc='center')
                    table.auto_set_font_size(False)
                    table.set_fontsize(8)
                    ax.set_title('drift-info')
                elif not plot_table(ax, key, df, manual=data.get('manual'),
                                    flip_y=self.chart_manager.flip_y.get(),
                                    grid=self.chart_manager.grid.get(),
                                    legend=self.chart_manager.legend.get()):
                    continue
                else:
                    fig.autofmt_xdate()
                pdf.savefig(fig)
        return filename

    # --- projects --- #

    def save_project(self):
        """File > Save Project"""
        if self.project_path:
            return self.write_project(self.project_path)
        return self.save_project_as()

    def save_project_as(self):
        """File > Save Project As..."""
        filename = filedialog.asksaveasfilename(title='Save project', filetypes=PROJECT_TYPES,
                                                defaultextension=EXTENSION, confirmoverwrite=True)
        if filename:
            return self.write_project(filename)
        return None

    def write_project(self, filename):
        view = self.well_view
        tables = {'data': dict(view.data)}
        if view.workflow.manual_table is not None:
            tables['inputs'] = {'manual-file': view.workflow.manual_table}
        settings = {
            'workflow': view.workflow.get_state(),
            'many_files': self.view_manager.many_files_view.get_state(),
            'view': {
                'selected_tab': view.selected_tab,
                'field': view.field,
                'flip_y': self.chart_manager.flip_y.get(),
                'grid': self.chart_manager.grid.get(),
                'legend': self.chart_manager.legend.get(),
            },
        }
        if run_step(lambda: save_project(filename, tables, settings) or True) is None:
            return None
        self.project_path = filename
        self.menu.add_recent_file(str(filename))
        self.update_title()
        return filename

    def open_project(self, filename=None):
        """File > Open Project..."""
        if filename is None:
            filename = filedialog.askopenfilename(title='Open project', filetypes=PROJECT_TYPES)
        if not filename:
            return False
        loaded = run_step(load_project, filename)
        if loaded is None:
            return False
        tables, settings = loaded

        view = self.well_view
        view.clear_tables()
        for key, df in tables.get('data', {}).items():
            view.set_table(key, df, select=False)
        view.workflow.set_state(settings.get('workflow', {}),
                                manual_table=tables.get('inputs', {}).get('manual-file'))
        self.view_manager.many_files_view.set_state(settings.get('many_files', {}))

        options = settings.get('view', {})
        for name in ('flip_y', 'grid', 'legend'):
            if name in options:
                getattr(self.chart_manager, name).set(bool(options[name]))
        key = options.get('selected_tab')
        if key not in view.data and view.data:
            key = next(iter(view.data))
        if key:
            view.field = options.get('field')
            view.set_table(key, view.data[key])

        self.project_path = filename
        self.menu.add_recent_file(str(filename))
        self.update_title()
        return True

    def open_recent(self, filename):
        """File > Recent Files"""
        if not Path(filename).exists():
            messagebox.showwarning("Recent Files", f"{filename} no longer exists.")
            if filename in self.menu.recent_files:
                self.menu.recent_files.remove(filename)
                self.menu.update_recent_files()
                self.menu.save_settings()
            return False
        if Path(filename).suffix.lower() == EXTENSION:
            return self.open_project(filename)
        kind = self.ask_import_kind(filename)
        workflow = self.well_view.workflow
        if kind == 'manual':
            return workflow.load_manual_file(filename)
        if kind in ('well', 'baro'):
            return workflow.choose_file(kind, [filename])
        return False

    def ask_import_kind(self, filename):
        """Ask whether a recent data file is well, baro, or manual data; None if cancelled"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Open Recent File")
        dialog.transient(self.root)
        choice = tk.StringVar(dialog, value='')
        ttk.Label(dialog, text=f"Import {Path(filename).name} as:").pack(padx=10, pady=5)
        buttons = ttk.Frame(dialog)
        buttons.pack(padx=10, pady=5)
        for label, kind in (("Well data", 'well'), ("Barometric data", 'baro'),
                            ("Manual measurements", 'manual'), ("Cancel", '')):
            ttk.Button(buttons, text=label,
                       command=lambda k=kind: (choice.set(k), dialog.destroy())).pack(side='left', padx=3)
        dialog.grab_set()
        dialog.wait_window()
        return choice.get() or None

    # --- Edit > Clean Data --- #

    def clean_data(self, kind):
        """Edit > Clean Data: outliers, gaps, smooth, trim, or units on the selected table"""
        key, df, field = self.current_table()
        if key is None:
            return
        settings = self.config.processing
        new_df = None

        if kind == 'outliers':
            default = DEFAULT_SPIKE_THRESHOLDS.get(field)
            if default is None:
                default = round(settings.outlier_threshold * df[field].diff().std(), 4)
            threshold = simpledialog.askfloat(
                "Remove Outliers", f"Remove {field} values that differ from the local median by more than:",
                initialvalue=default, minvalue=0.0, parent=self.root)
            if threshold is None:
                return
            result = run_step(detect_transducer_spikes, df, field, threshold=threshold,
                              window=settings.smoothing_window if settings.smoothing_window > 2 else 5,
                              action='drop', drop_near_manual_only=False)
            if result is None:
                return
            new_df, summary = result
            messagebox.showinfo("Remove Outliers", f"Removed {len(df) - len(new_df)} of {len(df)} rows.")

        elif kind == 'gaps':
            interval, limit = settings.sampling_interval, settings.interpolation_limit
            if not messagebox.askyesno(
                    "Fix Gaps",
                    f"Resample {key} to every {interval} minutes and interpolate gaps of up to "
                    f"{limit} minutes?\n(Change these in Tools > Options.)"):
                return
            new_df = self.fill_gaps(df, interval, limit)
            messagebox.showinfo("Fix Gaps", f"{key} now has {len(new_df)} rows (was {len(df)}).")

        elif kind == 'smooth':
            window = settings.smoothing_window
            new_df = df.copy()
            new_df[f'{field}_smooth'] = df[field].rolling(window, center=True, min_periods=1).median()

        elif kind == 'trim':
            mean, std = df[field].mean(), df[field].std()
            low = simpledialog.askfloat("Trim Extrema", f"Minimum allowed {field}:",
                                        initialvalue=round(mean - 4 * std, 3), parent=self.root)
            if low is None:
                return
            high = simpledialog.askfloat("Trim Extrema", f"Maximum allowed {field}:",
                                         initialvalue=round(mean + 4 * std, 3), parent=self.root)
            if high is None:
                return
            new_df = df[(df[field] >= low) & (df[field] <= high)]

        elif kind == 'units':
            unit_converter_popup(self.well_view, key, field)
            return

        if new_df is not None:
            self.well_view.set_table(key, new_df)

    @staticmethod
    def fill_gaps(df, interval, limit):
        """Resample to a regular interval and time-interpolate gaps up to `limit` minutes"""
        freq = f'{int(interval)}min'
        numeric = df.select_dtypes(include='number')
        filled = numeric.resample(freq).mean().interpolate(
            method='time', limit=max(1, int(limit // interval)), limit_area='inside')
        other = df.drop(columns=numeric.columns)
        if len(other.columns):
            filled = filled.join(other.resample(freq).first().ffill())
        filled = filled.dropna(how='all', subset=list(numeric.columns))
        return filled[[c for c in df.columns if c in filled.columns]]

    # --- Tools > Analysis --- #

    def analyze(self, kind):
        """Tools > Analysis: jump fix, statistics, trend, or a custom column"""
        key, df, field = self.current_table(need_field=kind != 'custom')
        if key is None:
            return

        if kind == 'jump':
            default = round(df[field].diff().abs().std() * 5, 4)
            threshold = simpledialog.askfloat("Jump Fix", f"Correct jumps in {field} larger than:",
                                              initialvalue=default, minvalue=0.0, parent=self.root)
            if threshold is None:
                return
            fixed = run_step(jumpfix, df, field, threshold=threshold)
            if fixed is not None:
                self.well_view.set_table(key, fixed.drop(columns=['delta'], errors='ignore'))

        elif kind == 'basic':
            self.show_statistics(key, df)

        elif kind == 'trend':
            values = df[field].dropna()
            if len(values) < 2:
                messagebox.showwarning("Trend Analysis", f"{field} needs at least two values.")
                return
            days = np.asarray((values.index - values.index[0]).total_seconds()) / 86400
            slope, intercept = np.polyfit(days, values.values, 1)
            predicted = slope * days + intercept
            ss_res = ((values.values - predicted) ** 2).sum()
            ss_tot = ((values.values - values.values.mean()) ** 2).sum()
            r2 = 1 - ss_res / ss_tot if ss_tot else float('nan')
            messagebox.showinfo("Trend Analysis", (
                f"{key} {field}\n"
                f"{values.index[0]:%Y-%m-%d} to {values.index[-1]:%Y-%m-%d} ({days[-1]:.1f} days)\n\n"
                f"Linear trend: {slope:.5f} per day ({slope * 365.25:.3f} per year)\n"
                f"R squared: {r2:.3f}\n"
                f"Net change: {values.iloc[-1] - values.iloc[0]:.3f}"))

        elif kind == 'custom':
            expression = simpledialog.askstring(
                "Custom Analysis",
                f"New column from a pandas expression on {key}, e.g.\n"
                f"  Level_m = Level * 0.3048",
                parent=self.root)
            if not expression:
                return
            result = run_step(df.eval, expression)
            if isinstance(result, pd.DataFrame):
                self.well_view.set_table(key, result)
            elif result is not None:
                messagebox.showinfo("Custom Analysis", f"{expression}\n= {result}")

    def show_statistics(self, key, df):
        """Window of summary statistics for each numeric column"""
        numeric = df.select_dtypes(include='number')
        if numeric.empty:
            messagebox.showwarning("Basic Statistics", f"{key} has no numeric columns.")
            return
        stats = numeric.describe().T
        stats['missing'] = numeric.isna().sum()
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            stats['first'] = numeric.apply(lambda s: s.first_valid_index())
            stats['last'] = numeric.apply(lambda s: s.last_valid_index())
            interval = pd.Series(df.index).diff().median()
        else:
            interval = None

        window = tk.Toplevel(self.root)
        window.title(f"Statistics - {key}")
        window.geometry("900x300")
        if interval is not None:
            ttk.Label(window, text=f"{len(df)} rows, median interval {interval}").pack(anchor='w', padx=5)
        shown = stats.reset_index().rename(columns={'index': 'column'})
        sheet = Sheet(window, data=shown.round(4).astype(str).values.tolist(),
                      headers=list(shown.columns), theme=self.view_manager.sheettheme)
        sheet.enable_bindings('copy', 'single_select', 'column_width_resize')
        sheet.pack(fill='both', expand=True)

    def run(self):
        """Start the application"""
        self.root.mainloop()


def main():
    app = LoggerLoaderApp()
    app.run()


if __name__ == "__main__":
    main()

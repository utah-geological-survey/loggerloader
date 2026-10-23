"""Single-well processing steps and dialogs for the V2 GUI, ported from llgui.

The steps follow llgui's single-well tab:
    1-2. import well and baro data
    3.   align them (remove barometric pressure)
    4.   enter or import manual depth-to-water readings
    5.   fix transducer drift against the manual readings
    6.   convert to water elevations and save
"""
from pathlib import Path

import pandas as pd

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkcalendar import DateEntry


# Display name -> filetype understood by WellDataController.load_file
FILE_TYPES = {
    'Transducer (xle, lev, csv, htm)': 'auto',
    'Troll csv': 'troll-csv',
    'Other csv/Excel (match columns)': 'table',
}

DATE_NAMES = ['datetime', 'date', 'readingdate', 'date_time', 'dateandtime', 'timestamp']
DTW_NAMES = ['dtw', 'waterlevel', 'depthtowater', 'water_level', 'level', 'depth_to_water',
             'water_depth', 'depth', 'dtwbelowcasing', 'dtw_below_casing', 'water level (ft)']
LOCID_NAMES = ['locationid', 'locid', 'id', 'location_id', 'lid', 'location id']
VALUE_NAMES = ['level', 'value', 'pressure', 'waterlevel', 'water_level', 'head']
TEMP_NAMES = ['temperature', 'temp', 'temp_c', 'temperature_c']
COND_NAMES = ['cond', 'conductivity', 'specific_conductivity', 'spc', 'ec']

TEMPERATURE_UNITS = ['C', 'F']
PRESSURE_UNITS = ['psi', 'mmHg', 'ft', 'bar']


def read_table(filename, sheet_name=0):
    """Read a csv or Excel table into a DataFrame"""
    if Path(filename).suffix.lower() in ('.xlsx', '.xls'):
        return pd.read_excel(filename, sheet_name=sheet_name)
    return pd.read_csv(filename)


def normalize_id(value):
    """Location ids as text, so 71, 71.0 and '71' all match"""
    if pd.isna(value):
        return ''
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else str(number)
    except (TypeError, ValueError):
        return str(value).strip()


def guess_column(columns, names):
    """First column whose lower-cased name is in names, else ''"""
    return next((c for c in columns if str(c).strip().lower() in names), '')


def run_step(func, *args, **kwargs):
    """Run a workflow step, showing its error instead of raising; returns None on failure"""
    try:
        return func(*args, **kwargs)
    except ValueError as e:
        messagebox.showwarning("Logger Loader", str(e))
    except Exception as e:
        messagebox.showerror("Error", f"{type(e).__name__}: {e}")
    return None


class ColumnMatchDialog:
    """Pick the sheet and the date/level/temperature/conductivity columns of a generic table.

    llgui's 'Match CSV Info' and 'Pick Excel Sheet and Columns' windows. ``result``
    is a DataFrame indexed by DateTime with Level (and Temperature/Cond), or None if cancelled.
    """

    def __init__(self, parent, filename):
        self.filename = filename
        self.result = None
        self.is_excel = Path(filename).suffix.lower() in ('.xlsx', '.xls')
        self.table = None

        self.top = tk.Toplevel(parent)
        self.top.title("Match Columns")
        self.top.transient(parent.winfo_toplevel())

        ttk.Label(self.top, text=Path(filename).name).grid(row=0, column=0, columnspan=2, pady=5)
        row = 1
        if self.is_excel:
            sheets = pd.ExcelFile(filename).sheet_names
            ttk.Label(self.top, text="Excel sheet").grid(row=row, column=0, sticky='w', padx=5)
            self.sheet = ttk.Combobox(self.top, values=sheets, state='readonly')
            self.sheet.grid(row=row, column=1, padx=5)
            self.sheet.bind("<<ComboboxSelected>>", lambda e: self.load_sheet(self.sheet.get()))
            row += 1

        self.combos = {}
        for label in ("Datetime", "Value (Level)", "Temperature (optional)", "Conductivity (optional)"):
            ttk.Label(self.top, text=label).grid(row=row, column=0, sticky='w', padx=5)
            self.combos[label] = ttk.Combobox(self.top, width=25)
            self.combos[label].grid(row=row, column=1, padx=5, pady=2)
            row += 1

        buttons = ttk.Frame(self.top)
        buttons.grid(row=row, column=0, columnspan=2, pady=5)
        ttk.Button(buttons, text="OK", command=self.ok).pack(side='left', padx=5)
        ttk.Button(buttons, text="Cancel", command=self.top.destroy).pack(side='left', padx=5)

        if self.is_excel:
            self.sheet.current(0)
            self.load_sheet(self.sheet.get())
        else:
            self.load_sheet(0)

        self.top.grab_set()
        self.top.wait_window()

    def load_sheet(self, sheet):
        self.table = read_table(self.filename, sheet)
        cols = list(self.table.columns)
        guesses = (DATE_NAMES, VALUE_NAMES, TEMP_NAMES, COND_NAMES)
        for combo, names in zip(self.combos.values(), guesses):
            combo['values'] = [''] + cols
            combo.set(guess_column(cols, names))

    def ok(self):
        date, value, temp, cond = (c.get() for c in self.combos.values())
        try:
            self.result = self.match(self.table, date, value, temp, cond)
        except ValueError as e:
            messagebox.showwarning("Match Columns", str(e), parent=self.top)
            return
        self.top.destroy()

    @staticmethod
    def match(table, date_col, value_col, temp_col='', cond_col=''):
        """Rename the chosen columns to DateTime/Level/Temperature/Cond and index by DateTime"""
        if date_col not in table.columns or value_col not in table.columns:
            raise ValueError("Choose the datetime and value columns.")
        names = {date_col: 'DateTime', value_col: 'Level', temp_col: 'Temperature', cond_col: 'Cond'}
        df = table[[c for c in names if c in table.columns]].rename(columns=names)
        df['DateTime'] = pd.to_datetime(df['DateTime'], errors='coerce')
        for col in df.columns.drop('DateTime'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['DateTime', 'Level']).set_index('DateTime').sort_index()
        if df.empty:
            raise ValueError("No rows have a valid date and value.")
        return df


def unit_converter_popup(view, key, field):
    """llgui's 'Convert Units' window: adds a column with field converted to new units"""
    popup = tk.Toplevel(view.master)
    popup.title("Convert Units")
    popup.geometry("300x260+200+200")
    ttk.Label(popup, text='Adds a column with converted units of').pack()
    ttk.Label(popup, text=f'{key} {field}').pack()

    ttk.Label(popup, text='Units of selected column').pack()
    in_units = ttk.Combobox(popup, values=TEMPERATURE_UNITS + PRESSURE_UNITS + ['kPa'], state='readonly')
    in_units.pack()
    ttk.Label(popup, text='Desired units of new column').pack()
    out_units = ttk.Combobox(popup, values=PRESSURE_UNITS, state='readonly')
    out_units.set('ft')
    out_units.pack()
    ttk.Label(popup, text='New column name').pack()
    out_field = ttk.Combobox(popup)
    out_field.pack()

    def refresh(event=None):
        if in_units.get() in TEMPERATURE_UNITS:
            out_units['values'] = TEMPERATURE_UNITS
            if out_units.get() not in TEMPERATURE_UNITS:
                out_units.set('F' if in_units.get() == 'C' else 'C')
        else:
            out_units['values'] = PRESSURE_UNITS
            if out_units.get() not in PRESSURE_UNITS:
                out_units.set('ft')
        out_field['values'] = [f'{field}_{out_units.get()}', field, 'Level']
        out_field.set(f'{field}_{out_units.get()}')

    in_units.bind("<<ComboboxSelected>>", refresh)
    out_units.bind("<<ComboboxSelected>>", refresh)

    def convert():
        if not in_units.get() or not out_field.get():
            messagebox.showwarning("Convert Units", "Choose the units and a column name.", parent=popup)
            return
        if run_step(view.controller.convert_units, key, field,
                    in_units.get(), out_units.get(), out_field.get()) is not None:
            popup.destroy()

    ttk.Button(popup, text='Convert', command=convert).pack(pady=5)
    return popup


class SingleWellWorkflow:
    """Notebook of llgui's numbered single-well steps"""

    def __init__(self, master, view):
        self.view = view
        self.controller = view.controller
        self.manual_table = None

        self.steps = ttk.Notebook(master)
        self.steps.pack(fill='x', padx=5, pady=5)
        self.import_tab = self.add_step('1-2 Import', self.build_import)
        self.align_tab = self.add_step('3 Align', self.build_align)
        self.manual_tab = self.add_step('4 Manual', self.build_manual)
        self.drift_tab = self.add_step('5 Drift', self.build_drift)
        self.elev_tab = self.add_step('6 Elevation', self.build_elevation)

    def add_step(self, text, builder):
        frame = ttk.Frame(self.steps, padding=5)
        self.steps.add(frame, text=text)
        builder(frame)
        return frame

    def goto(self, tab):
        self.steps.select(tab)

    # --- project save/open --- #

    def get_state(self):
        """Everything typed or chosen in the steps, as json-able values"""
        return {
            'step': self.steps.index(self.steps.select()),
            'filetype': {k: box.get() for k, box in self.filetype.items()},
            'file_status': {k: var.get() for k, var in self.file_status.items()},
            'well_field': self.well_field.get(), 'baro_field': self.baro_field.get(),
            'freq': self.freq.get(), 'vented': self.vented.get(),
            'manual_mode': self.manbook.index(self.manbook.select()),
            'manual_entry': [{'date': self.man_date[i].get_date().isoformat(),
                              'hour': self.man_hour[i].get(), 'minute': self.man_min[i].get(),
                              'measure': self.man_meas[i].get()} for i in range(2)],
            'manual_locid': self.man_locid.get(),
            'manual_columns': {k: box.get() for k, box in self.man_cols.items()},
            'manual_file_status': self.man_file_status.get(),
            'manual_units': self.man_units.get(),
            'max_drift': self.max_drift.get(),
            'ground_elev': self.ground_elev.get(), 'ground_units': self.ground_units.get(),
            'stickup': self.stickup.get(), 'stickup_units': self.stickup_units.get(),
        }

    @staticmethod
    def _set_entry(entry, value):
        entry.delete(0, 'end')
        entry.insert(0, value)

    def set_state(self, state, manual_table=None):
        """Restore get_state() output; missing keys keep their current values"""
        for k, value in state.get('filetype', {}).items():
            if k in self.filetype and value in FILE_TYPES:
                self.filetype[k].set(value)
        for k, value in state.get('file_status', {}).items():
            if k in self.file_status:
                self.file_status[k].set(value)
        for name in ('well_field', 'baro_field', 'freq', 'manual_units', 'ground_units', 'stickup_units'):
            box = getattr(self, {'manual_units': 'man_units'}.get(name, name))
            if name in state:
                box.set(state[name])
        self.vented.set(state.get('vented', self.vented.get()))
        for i, reading in enumerate(state.get('manual_entry', [])[:2]):
            try:
                self.man_date[i].set_date(pd.Timestamp(reading['date']).date())
            except (KeyError, ValueError):
                pass
            self.man_hour[i].set(reading.get('hour', '00'))
            self.man_min[i].set(reading.get('minute', '00'))
            self._set_entry(self.man_meas[i], reading.get('measure', ''))
        self._set_entry(self.man_locid, state.get('manual_locid', ''))
        self.manual_table = manual_table
        cols = list(manual_table.columns) if manual_table is not None else []
        for k, value in state.get('manual_columns', {}).items():
            if k in self.man_cols:
                if k != 'Pick id':
                    self.man_cols[k]['values'] = cols
                self.man_cols[k].set(value)
        self.man_file_status.set(state.get('manual_file_status', self.man_file_status.get()))
        self.manbook.select(state.get('manual_mode', 0))
        self.max_drift.set(state.get('max_drift', ''))
        self._set_entry(self.ground_elev, state.get('ground_elev', ''))
        self._set_entry(self.stickup, state.get('stickup', '0'))
        self.refresh_fields()
        self.steps.select(state.get('step', 0))

    # --- 1-2. import --- #

    def build_import(self, frame):
        self.filetype, self.file_status = {}, {}
        for row, (kind, label) in enumerate((('well', '1. Well data'), ('baro', '2. Barometric data'))):
            ttk.Label(frame, text=label).grid(row=row * 2, column=0, sticky='w')
            self.filetype[kind] = ttk.Combobox(frame, values=list(FILE_TYPES), state='readonly', width=30)
            self.filetype[kind].current(0)
            self.filetype[kind].grid(row=row * 2, column=1, padx=5)
            ttk.Button(frame, text='Choose file(s)...',
                       command=lambda k=kind: self.choose_file(k)).grid(row=row * 2, column=2)
            self.file_status[kind] = tk.StringVar(frame, value='No file loaded')
            ttk.Label(frame, textvariable=self.file_status[kind], foreground='gray').grid(
                row=row * 2 + 1, column=0, columnspan=3, sticky='w')

    def choose_file(self, kind, filelist=None):
        filetype = FILE_TYPES[self.filetype[kind].get()]
        importer = self.controller.import_well_data if kind == 'well' else self.controller.import_baro_data
        if importer(filelist, filetype=filetype):
            files = self.controller.file_data['file_name'].map(lambda f: Path(f).name)
            self.file_status[kind].set(', '.join(files))
            if 'well' in self.view.data and 'baro' in self.view.data:
                self.goto(self.align_tab)
            return True
        return False

    # --- 3. align --- #

    def build_align(self, frame):
        ttk.Label(frame, text='Well field').grid(row=0, column=0, sticky='w')
        self.well_field = ttk.Combobox(frame, width=12, values=['Level'])
        self.well_field.set('Level')
        self.well_field.grid(row=0, column=1, padx=5)
        ttk.Label(frame, text='Baro field').grid(row=0, column=2, sticky='w')
        self.baro_field = ttk.Combobox(frame, width=12, values=['Level'])
        self.baro_field.set('Level')
        self.baro_field.grid(row=0, column=3, padx=5)

        ttk.Label(frame, text='Pref. data freq. (min)').grid(row=1, column=0, sticky='w')
        self.freq = ttk.Combobox(frame, width=5, values=[60, 15, 30] + list(range(1, 120)))
        self.freq.current(0)
        self.freq.grid(row=1, column=1, padx=5, sticky='w')
        self.vented = tk.BooleanVar(frame, value=False)
        ttk.Checkbutton(frame, text='Vented?', variable=self.vented).grid(row=1, column=2, sticky='w')
        ttk.Button(frame, text='Align Datasets', command=self.align).grid(row=1, column=3, pady=5)

    def refresh_fields(self):
        """Offer the numeric columns of the imported data in the field boxes"""
        for key, box in (('well', self.well_field), ('baro', self.baro_field)):
            if key in self.view.data:
                cols = list(self.view.data[key].select_dtypes(include='number').columns)
                box['values'] = cols
                if box.get() not in cols and cols:
                    box.set('Level' if 'Level' in cols else cols[0])

    def align(self):
        try:
            freq = int(self.freq.get())
        except ValueError:
            messagebox.showwarning("Align", "Data frequency must be a whole number of minutes.")
            return
        if run_step(self.controller.align, self.well_field.get(), self.baro_field.get(),
                    freq, self.vented.get()) is not None:
            self.goto(self.manual_tab)

    # --- 4. manual measurements --- #

    def build_manual(self, frame):
        self.manbook = ttk.Notebook(frame)
        self.manbook.pack(fill='x')
        entry = ttk.Frame(self.manbook, padding=3)
        fileframe = ttk.Frame(self.manbook, padding=3)
        self.manbook.add(entry, text='Manual Entry')
        self.manbook.add(fileframe, text='From File')

        # Two readings typed in, as in llgui
        for col, text in enumerate(('', 'Date of Measure', 'HH', 'MM', 'Depth to water')):
            ttk.Label(entry, text=text).grid(row=0, column=col)
        self.man_date, self.man_hour, self.man_min, self.man_meas = [], [], [], []
        for i in range(2):
            ttk.Label(entry, text=str(i + 1)).grid(row=i + 1, column=0)
            date = DateEntry(entry, width=12, locale='en_US', date_pattern='MM/dd/yyyy')
            date.grid(row=i + 1, column=1, padx=2)
            hour = ttk.Combobox(entry, width=3, values=[f'{h:02}' for h in range(24)], state='readonly')
            hour.current(0)
            hour.grid(row=i + 1, column=2)
            minute = ttk.Combobox(entry, width=3, values=[f'{m:02}' for m in range(60)], state='readonly')
            minute.current(0)
            minute.grid(row=i + 1, column=3)
            meas = ttk.Entry(entry, width=10)
            meas.grid(row=i + 1, column=4, padx=2)
            self.man_date.append(date)
            self.man_hour.append(hour)
            self.man_min.append(minute)
            self.man_meas.append(meas)
        ttk.Label(entry, text='Location id').grid(row=3, column=1, sticky='e')
        self.man_locid = ttk.Entry(entry, width=12)
        self.man_locid.grid(row=3, column=2, columnspan=2, sticky='w')

        # A file of readings with column matching, as in llgui
        ttk.Button(fileframe, text='Choose file...', command=self.load_manual_file).grid(row=0, column=0)
        self.man_file_status = tk.StringVar(fileframe, value='File needs datetime, depth to water and location id')
        ttk.Label(fileframe, textvariable=self.man_file_status, foreground='gray').grid(
            row=0, column=1, columnspan=3, sticky='w')
        self.man_cols = {}
        for col, label in enumerate(('Datetime', 'DTW', 'Location id', 'Pick id')):
            ttk.Label(fileframe, text=label).grid(row=1, column=col)
            box = ttk.Combobox(fileframe, width=14)
            box.grid(row=2, column=col, padx=2)
            self.man_cols[label] = box
        self.man_cols['Pick id'].configure(postcommand=self.fill_pick_ids)

        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', pady=3)
        ttk.Label(bottom, text='Units').pack(side='left')
        self.man_units = ttk.Combobox(bottom, width=4, values=['ft', 'm'], state='readonly')
        self.man_units.current(0)
        self.man_units.pack(side='left', padx=5)
        ttk.Button(bottom, text='Process Manual Data', command=self.process_manual).pack(side='left', padx=5)

    def load_manual_file(self, filename=None):
        if filename is None:
            filename = filedialog.askopenfilename(title='Choose manual measurement file',
                                                  filetypes=[('Tables', '*.csv *.xlsx *.xls'),
                                                             ('All files', '*.*')])
        if not filename:
            return False
        table = run_step(read_table, filename)
        if table is None:
            return False
        self.manual_table = table
        cols = list(table.columns)
        for box, names in ((self.man_cols['Datetime'], DATE_NAMES), (self.man_cols['DTW'], DTW_NAMES),
                           (self.man_cols['Location id'], LOCID_NAMES)):
            box['values'] = cols
            box.set(guess_column(cols, names))
        self.man_cols['Pick id'].set('')
        self.man_file_status.set(f'{Path(filename).name} ({len(table)} rows)')
        if self.controller.on_file_imported:
            self.controller.on_file_imported(filename)
        self.goto(self.manual_tab)
        self.manbook.select(1)
        return True

    def fill_pick_ids(self):
        locid = self.man_cols['Location id'].get()
        if self.manual_table is not None and locid in self.manual_table.columns:
            ids = {normalize_id(x) for x in self.manual_table[locid].dropna()}
            self.man_cols['Pick id']['values'] = sorted(ids, key=lambda x: (not x.isdigit(), x.zfill(12)))

    def process_manual(self):
        units = self.man_units.get()
        if self.manbook.index(self.manbook.select()) == 0:
            try:
                readings = []
                for i in range(2):
                    when = pd.Timestamp(self.man_date[i].get_date()) + pd.Timedelta(
                        hours=int(self.man_hour[i].get()), minutes=int(self.man_min[i].get()))
                    readings.append((when, float(self.man_meas[i].get())))
            except ValueError:
                messagebox.showwarning("Manual Data", "Enter a numeric depth to water for both readings.")
                return
            result = run_step(self.controller.manual_from_entry, readings, units, self.man_locid.get())
        else:
            if self.manual_table is None:
                messagebox.showwarning("Manual Data", "Choose a manual measurement file first.")
                return
            result = run_step(self.controller.manual_from_table, self.manual_table,
                              self.man_cols['Datetime'].get(), self.man_cols['DTW'].get(),
                              self.man_cols['Location id'].get(), self.man_cols['Pick id'].get(), units)
        if result is not None:
            self.goto(self.drift_tab)

    # --- 5. drift --- #

    def build_drift(self, frame):
        ttk.Button(frame, text='Fix Drift', command=self.fix_drift).grid(row=0, column=0, padx=5)
        ttk.Label(frame, text='Max drift =').grid(row=0, column=1)
        self.max_drift = tk.StringVar(frame, value='')
        ttk.Label(frame, textvariable=self.max_drift).grid(row=0, column=2)
        ttk.Label(frame, text='Fits the baro-corrected levels to the manual readings; '
                              'see the drift-info tab for each interval.',
                  foreground='gray', wraplength=450).grid(row=1, column=0, columnspan=3, sticky='w')

    def fix_drift(self):
        drift = run_step(self.controller.fix_drift)
        if drift is not None:
            self.max_drift.set('n/a' if pd.isna(drift) else f'{drift:.3f} ft')
            self.goto(self.elev_tab)

    # --- 6. elevation --- #

    def build_elevation(self, frame):
        for col, text in enumerate(('Ground elev.', 'Units', 'Stickup', 'Units')):
            ttk.Label(frame, text=text).grid(row=0, column=col)
        self.ground_elev = ttk.Entry(frame, width=10)
        self.ground_elev.grid(row=1, column=0, padx=2)
        self.ground_units = ttk.Combobox(frame, width=4, values=['ft', 'm'], state='readonly')
        self.ground_units.current(0)
        self.ground_units.grid(row=1, column=1)
        self.stickup = ttk.Entry(frame, width=8)
        self.stickup.insert(0, '0')
        self.stickup.grid(row=1, column=2, padx=2)
        self.stickup_units = ttk.Combobox(frame, width=4, values=['ft', 'm'], state='readonly')
        self.stickup_units.current(0)
        self.stickup_units.grid(row=1, column=3)
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=4, pady=5)
        ttk.Button(buttons, text='Calculate Elevations', command=self.calc_elevations).pack(side='left', padx=5)
        ttk.Button(buttons, text='Save csv...', command=self.save_one_well).pack(side='left', padx=5)

    def calc_elevations(self):
        try:
            ground, stickup = float(self.ground_elev.get()), float(self.stickup.get() or 0)
        except ValueError:
            messagebox.showwarning("Elevation", "Enter numbers for the ground elevation and stickup.")
            return
        run_step(self.controller.calc_elevations, ground, self.ground_units.get(),
                 stickup, self.stickup_units.get())

    def save_one_well(self, filename=None):
        if 'wl-elev' not in self.view.data:
            messagebox.showwarning("Save", "Calculate elevations first (step 6).")
            return
        if filename is None:
            filename = filedialog.asksaveasfilename(filetypes=[('csv', '*.csv'), ('Excel', '*.xlsx')],
                                                    defaultextension='.csv', confirmoverwrite=True)
        if filename:
            run_step(self.controller.save_one_well, filename)

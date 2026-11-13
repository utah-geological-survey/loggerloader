"""Bulk processing of many wells at once, ported from llgui's 'Bulk Well Process' tab.

The steps follow llgui's bulk tab:
    1. load a well info table (location id, name, ground elevation, stickup, baro id)
    2. match transducer files to locations and import them
    3. remove barometric pressure from every well, using the baro logger named in the well info
    4. import manual depth-to-water readings for all wells
    5. fix drift for each well, calculate water elevations, and export

Tables are indexed by (locationid, date) with location ids as text (see normalize_id),
and are shown in the shared table notebook under 'bulk-' names.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from loggerloader.loader import Drifting, well_baro_merge
from loggerloader.views import FEET_PER_METER, file_summary
from loggerloader.workflow import (DATE_NAMES, DTW_NAMES, FILE_TYPES, LOCID_NAMES, guess_column,
                                   normalize_id, read_table, run_step)


# Standard well info column -> (label, likely names in the user's table)
INFO_COLUMNS = {
    'locationid': ('Location id', ['altlocationid', 'locationid', 'location_id', 'location id', 'well_id',
                                   'wellid', 'locid', 'id']),
    'locationname': ('Name', ['locationname', 'location_name', 'wellname', 'well_name', 'name', 'location']),
    'ground': ('Ground elev.', ['verticalmeasure', 'ground_elevation', 'groundelevation', 'ground_elev',
                                'land_surface_elevation', 'elevation', 'altitude']),
    'stickup': ('Stickup', ['stickup', 'stick_up', 'stickup_height', 'casing_height']),
    'baroid': ('Baro id', ['barologgertype', 'baroid', 'baro_id', 'baro id', 'barometer', 'baro']),
}

LOGGER_EXTENSIONS = ('.xle', '.lev', '.csv', '.htm', '.html', '.xlsx', '.xls')

# step -> (tables, bulk-summary columns) made out of date by re-running it
STALE = {
    'info': (['bulk-well-info', 'bulk-summary', 'bulk-files', 'bulk-well', 'bulk-well-baro',
              'bulk-manual', 'bulk-drift-info', 'bulk-fix-drift'], []),
    'files': (['bulk-files', 'bulk-well', 'bulk-well-baro', 'bulk-drift-info', 'bulk-fix-drift'],
              ['files', 'aligned', 'drift']),
    'align': (['bulk-well-baro', 'bulk-drift-info', 'bulk-fix-drift'], ['aligned', 'drift']),
    'manual': (['bulk-manual', 'bulk-drift-info', 'bulk-fix-drift'], ['manual', 'drift']),
}

MANUAL_BUFFER = pd.DateOffset(days=8)  # manual readings this close to a record are used for its drift


def id_sort_key(locid):
    """Sort numeric ids by value, then text ids"""
    return not locid.isdigit(), locid.zfill(12)


def location_ids(df):
    """Location ids (first index level) of a bulk table, sorted"""
    return sorted(df.index.get_level_values(0).unique(), key=id_sort_key)


def info_value(info, locid, field):
    """A well info value; '' for missing text and NaN for missing numbers"""
    value = info.at[locid, field] if locid in info.index and field in info.columns else np.nan
    if field in ('locationname', 'baroid'):
        return normalize_id(value) if field == 'baroid' else ('' if pd.isna(value) else str(value))
    return pd.to_numeric(value, errors='coerce')


def well_name(info, locid):
    return info_value(info, locid, 'locationname') or locid


def squash(text):
    return re.sub(r'[^a-z0-9]', '', str(text).lower())


def well_info_table(table, columns, units='ft'):
    """Standardize a well info table: indexed by locationid, with locationname, ground, stickup, baroid.

    ``columns`` maps each INFO_COLUMNS key to a column of ``table`` ('' if it has none).
    Ground elevation and stickup are converted to feet.
    """
    id_col = columns.get('locationid', '')
    if id_col not in table.columns:
        raise ValueError("Choose the location id column.")
    df = pd.DataFrame({'locationid': table[id_col].map(normalize_id)})
    for field in ('locationname', 'ground', 'stickup', 'baroid'):
        col = columns.get(field, '')
        if col in table.columns:
            df[field] = table[col]
        else:
            df[field] = 0.0 if field == 'stickup' else np.nan
    df = df[df['locationid'] != ''].drop_duplicates('locationid')
    if df.empty:
        raise ValueError("The well info table has no location ids.")
    df['locationname'] = [normalize_id(n) if pd.notna(n) else i
                          for i, n in zip(df['locationid'], df['locationname'])]
    df['baroid'] = df['baroid'].map(normalize_id)
    for field in ('ground', 'stickup'):
        df[field] = pd.to_numeric(df[field], errors='coerce')
        if units == 'm':
            df[field] = df[field] * FEET_PER_METER
    df['stickup'] = df['stickup'].fillna(0.0)
    df = df.set_index('locationid')
    return df.loc[sorted(df.index, key=id_sort_key)]


def guess_location(filename, info):
    """Location id whose name or id best matches a file name, or ''.

    The file name's first word may be the name or id (e.g. 'pw10baro 20171208.xle'),
    otherwise the longest name found anywhere in it wins (e.g. '1037276_Pw10a_2017.xle').
    """
    stem = Path(filename).stem.strip()
    full = squash(stem)
    token = squash(re.split(r'[_\s]+', stem)[0])
    best, best_len = '', 0
    for locid in info.index:
        name = squash(well_name(info, locid))
        if (token and token in (name, squash(locid))) or full == name:
            return locid
        if len(name) >= 4 and name in full and len(name) > best_len:
            best, best_len = locid, len(name)
    return best


def import_bulk_files(matches, load_file):
    """Read every matched file, combining files from the same location.

    Args:
        matches: {filename: locationid}; files with an empty id are skipped
        load_file: function(filename) -> DataFrame indexed by date, or None if cancelled

    Returns:
        (data indexed by locationid and DateTime, table of file statistics), or None if cancelled
    """
    frames, files = {}, []
    for filename, locid in matches.items():
        if not locid:
            continue
        df = load_file(filename)
        if df is None:
            return None
        if df.empty:
            continue
        frames.setdefault(locid, []).append(df)
        files.append({'locationid': locid, **file_summary(df, filename)})
    if not frames:
        raise ValueError("Match at least one file with data to a location.")

    wells = {}
    for locid, dfs in frames.items():
        data = pd.concat(dfs).sort_index()
        data = data[~data.index.duplicated(keep='first')]
        data.index.name = 'DateTime'
        wells[locid] = data
    data = pd.concat(wells, names=['locationid', 'DateTime'])
    file_info = pd.DataFrame(files)
    file_info['file_name'] = file_info['file_name'].map(lambda f: Path(f).name)
    return data, file_info.set_index(['locationid', 'file_name']).sort_index()


def align_bulk(bulk_well, info, freq=60, vented_without_baro=False, field='Level'):
    """Remove barometric pressure from each well using the baro logger in its info row.

    Locations that are some well's baro logger are not aligned themselves.

    Returns:
        (data indexed by locationid and DateTime, {locationid: note})
    """
    available = set(bulk_well.index.get_level_values(0))
    baro_ids = {info_value(info, i, 'baroid') for i in info.index} - {''}
    merged, notes = {}, {}
    for locid in location_ids(bulk_well):
        if locid in baro_ids:
            notes[locid] = 'barometer'
            continue
        well = bulk_well.xs(locid, level=0)
        baroid = info_value(info, locid, 'baroid')
        try:
            if baroid in available:
                df = well_baro_merge(well, bulk_well.xs(baroid, level=0), wellcolumn=field,
                                     barocolumn=field, sampint=int(freq))
            elif vented_without_baro:
                df = well_baro_merge(well, well, wellcolumn=field, sampint=int(freq), vented=True)
            else:
                notes[locid] = f'no data for baro {baroid}' if baroid else 'no baro id'
                continue
        except (IndexError, KeyError):
            df = pd.DataFrame()
        if df.empty:
            notes[locid] = f'does not overlap baro {baroid}'
            continue
        df.index.name = 'DateTime'
        merged[locid] = df
        notes[locid] = f'{len(df)} rows' + ('' if baroid in available else ' (vented)')
    if not merged:
        raise ValueError("No wells could be aligned:\n" +
                         "\n".join(f"{well_name(info, i)}: {n}" for i, n in notes.items()))
    return pd.concat(merged, names=['locationid', 'DateTime']), notes


def bulk_manual(table, date_col, dtw_col, locid_col, info, units='ft'):
    """Manual depth-to-water readings for every location in the well info table.

    Returns readings indexed by locationid and readingdate, with depth in feet below the
    casing and the water elevation from the well info.
    """
    for label, col in (('datetime', date_col), ('depth to water', dtw_col), ('location id', locid_col)):
        if col not in table.columns:
            raise ValueError(f"Choose the {label} column.")
    df = pd.DataFrame({'locationid': table[locid_col].map(normalize_id),
                       'readingdate': pd.to_datetime(table[date_col], errors='coerce'),
                       'dtwbelowcasing': pd.to_numeric(table[dtw_col], errors='coerce')})
    df = df.dropna(subset=['readingdate', 'dtwbelowcasing'])
    df = df[df['locationid'].isin(info.index)]
    if df.empty:
        raise ValueError("None of the manual readings match a location id in the well info table.")
    if units == 'm':
        df['dtwbelowcasing'] = df['dtwbelowcasing'] * FEET_PER_METER
    df['units'] = units
    ground = df['locationid'].map(lambda i: info_value(info, i, 'ground'))
    stickup = df['locationid'].map(lambda i: info_value(info, i, 'stickup'))
    df['waterelevation'] = ground + stickup.fillna(0) - df['dtwbelowcasing']
    return df.set_index(['locationid', 'readingdate']).sort_index()


def bulk_drift(well_baro, manual, info, max_allowed=None):
    """Fix drift for each aligned well and calculate its water elevations.

    Wells whose max drift is above ``max_allowed`` (ft) are left out of the results.

    Returns:
        (drift-corrected data, drift info, {locationid: note}, {locationid: max drift})
    """
    manual_ids = set(manual.index.get_level_values(0))
    fixed, drift_info, notes, drifts = {}, {}, {}, {}
    for locid in location_ids(well_baro):
        if locid not in manual_ids:
            notes[locid] = 'no manual readings'
            continue
        wellbaro = well_baro.xs(locid, level=0).copy()
        man = manual.xs(locid, level=0).copy()
        start, end = wellbaro.first_valid_index(), wellbaro.last_valid_index()
        man = man[(man.index > start - MANUAL_BUFFER) & (man.index < end + MANUAL_BUFFER)]
        if man.empty:
            notes[locid] = 'no manual readings during the record'
            continue
        # Drifting expects depths as negative numbers (below the casing)
        man['dtwbelowcasing'] = man['dtwbelowcasing'] * -1
        try:
            df, dinfo, max_drift = Drifting(man, wellbaro, drifting_field='corrwl',
                                            man_field='dtwbelowcasing', well_id=locid,
                                            output_field='DTW_WL').process_drift()
        except (KeyError, IndexError, ValueError) as e:
            notes[locid] = f'drift failed ({type(e).__name__}: {e})'
            continue
        drift_info[locid] = dinfo
        drifts[locid] = max_drift
        if max_allowed is not None and pd.notna(max_drift) and abs(max_drift) > max_allowed:
            notes[locid] = f'max drift {max_drift:.3f} ft is over {max_allowed} ft; left out'
            continue
        cols = [c for c in ('barometer', 'corrwl', 'DTW_WL', 'driftcorrection', 'Temperature')
                if c in df.columns]
        df = df[cols].copy()
        df['waterelevation'] = (df['DTW_WL'] + info_value(info, locid, 'stickup') +
                                info_value(info, locid, 'ground'))
        df.index.name = 'DateTime'
        fixed[locid] = df
        notes[locid] = 'max drift ' + ('n/a' if pd.isna(max_drift) else f'{max_drift:.3f} ft')

    if drift_info:
        drift_info = pd.concat(drift_info, names=['locationid', 'interval'])
        drift_info.insert(0, 'locationname', [well_name(info, i)
                                              for i in drift_info.index.get_level_values(0)])
    else:
        drift_info = None
    if not fixed:
        raise ValueError("No wells could be drift corrected:\n" +
                         "\n".join(f"{well_name(info, i)}: {n}" for i, n in notes.items()))
    return pd.concat(fixed, names=['locationid', 'DateTime']), drift_info, notes, drifts


def export_table(fixed):
    """The drift-corrected data in the database's column names (as save_one_well)"""
    df = fixed.reset_index()
    df['measureddtw'] = -1 * df['DTW_WL']
    df = df.rename(columns={'DateTime': 'readingdate', 'Temperature': 'temperature',
                            'corrwl': 'measuredlevel'})
    return df.drop(columns=['DTW_WL'])


def plot_well(ax, title, data, manual=None):
    """Chart one well's drift-corrected record with its manual readings"""
    if 'waterelevation' in data.columns and data['waterelevation'].notna().any():
        field, man_field, sign, label = 'waterelevation', 'waterelevation', 1, 'Water elevation (ft)'
    else:
        field, man_field, sign, label = 'DTW_WL', 'dtwbelowcasing', -1, 'Depth to water (ft, negative down)'
    ax.plot(data.index, data[field], label='Drift-corrected')
    if manual is not None and man_field in manual.columns:
        man = manual[(manual.index > data.index.min() - MANUAL_BUFFER) &
                     (manual.index < data.index.max() + MANUAL_BUFFER)]
        ax.scatter(man.index, sign * man[man_field], color='red', label='Manual', zorder=3)
    ax.ticklabel_format(axis='y', style='plain', useOffset=False)
    ax.set_title(title)
    ax.set_xlabel('Date')
    ax.set_ylabel(label)
    ax.grid(True)
    ax.legend(loc='best')


def write_bulk_pdf(filename, fixed, manual, info):
    """A pdf with one page per drift-corrected well"""
    with PdfPages(filename) as pdf:
        for locid in location_ids(fixed):
            fig = Figure(figsize=(11, 8.5))
            ax = fig.add_subplot(111)
            man = manual.xs(locid, level=0) if manual is not None and locid in manual.index else None
            plot_well(ax, f'{well_name(info, locid)} ({locid})', fixed.xs(locid, level=0), man)
            fig.autofmt_xdate()
            pdf.savefig(fig)
    return filename


class BulkWellView:
    """Numbered bulk steps and a chart of one well; tables go to the single-well table notebook"""

    def __init__(self, master, well_view):
        self.master = master
        self.well_view = well_view
        self.info_table = None    # well info file as read
        self.manual_table = None  # manual readings file as read
        self.matches = {}         # transducer file -> locationid

        self.steps = ttk.Notebook(master)
        self.steps.pack(fill='x', padx=5, pady=5)
        self.info_tab = self.add_step('1 Well Info', self.build_info)
        self.files_tab = self.add_step('2 Files', self.build_files)
        self.align_tab = self.add_step('3 Align', self.build_align)
        self.manual_tab = self.add_step('4 Manual', self.build_manual)
        self.drift_tab = self.add_step('5 Drift & Export', self.build_drift)
        self.build_chart(master)

    @property
    def data(self):
        return self.well_view.data

    @property
    def info(self):
        return self.data.get('bulk-well-info')

    def add_step(self, text, builder):
        frame = ttk.Frame(self.steps, padding=5)
        self.steps.add(frame, text=text)
        builder(frame)
        return frame

    def goto(self, tab):
        self.steps.select(tab)

    def require(self, key, message):
        if key not in self.data:
            messagebox.showwarning("Bulk Well Process", message)
            return False
        return True

    def set_table(self, key, df, select=True):
        if df is None:
            self.well_view.remove_table(key)
        else:
            self.well_view.set_table(key, df, select=select)

    def reset(self, step):
        """Remove the tables and summary columns that re-running `step` makes out of date"""
        tables, columns = STALE[step]
        for key in tables:
            self.well_view.remove_table(key)
        summary = self.data.get('bulk-summary')
        if summary is not None and columns:
            self.set_table('bulk-summary', summary.drop(columns=columns, errors='ignore'), select=False)

    def set_notes(self, column, notes):
        """Record each location's result of a step in the bulk-summary table"""
        summary = self.data.get('bulk-summary')
        if summary is None:
            summary = self.info[['locationname', 'baroid']].copy()
        summary[column] = pd.Series(notes, dtype=object).reindex(summary.index).fillna('')
        self.set_table('bulk-summary', summary, select=False)

    # --- project save/open --- #

    def get_state(self):
        """Everything typed or chosen in the steps, as json-able values"""
        return {
            'step': self.steps.index(self.steps.select()),
            'info_columns': {k: box.get() for k, box in self.info_cols.items()},
            'info_units': self.info_units.get(),
            'info_status': self.info_status.get(),
            'filetype': self.filetype.get(),
            'matches': dict(self.matches),
            'freq': self.freq.get(), 'vented': self.vented.get(),
            'manual_columns': {k: box.get() for k, box in self.man_cols.items()},
            'manual_units': self.man_units.get(),
            'manual_status': self.man_status.get(),
            'max_drift': self.max_drift.get(),
        }

    def set_state(self, state, info_table=None, manual_table=None):
        """Restore get_state() output; missing keys keep their current values"""
        self.info_table, self.manual_table = info_table, manual_table
        for boxes, table, key in ((self.info_cols, info_table, 'info_columns'),
                                  (self.man_cols, manual_table, 'manual_columns')):
            for k, value in state.get(key, {}).items():
                if k in boxes:
                    boxes[k]['values'] = [''] + list(table.columns) if table is not None else []
                    boxes[k].set(value)
        for box, key in ((self.info_units, 'info_units'), (self.filetype, 'filetype'),
                         (self.freq, 'freq'), (self.man_units, 'manual_units')):
            if key in state:
                box.set(state[key])
        self.vented.set(state.get('vented', self.vented.get()))
        self.max_drift.set(state.get('max_drift', self.max_drift.get()))
        self.info_status.set(state.get('info_status', self.info_status.get()))
        self.man_status.set(state.get('manual_status', self.man_status.get()))
        self.matches = {}
        self.file_list.delete(*self.file_list.get_children())
        self.add_files(list(state.get('matches', {})), state.get('matches', {}))
        self.refresh_locations()
        self.refresh_chart_wells()
        self.steps.select(state.get('step', 0))

    # --- 1. well info --- #

    def build_info(self, frame):
        top = ttk.Frame(frame)
        top.grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Button(top, text='Choose file...', command=self.load_info_file).pack(side='left')
        self.info_status = tk.StringVar(frame, value='csv/Excel table with one row per well')
        ttk.Label(top, textvariable=self.info_status, foreground='gray').pack(side='left', padx=5)

        self.info_cols = {}
        for i, (field, (label, _)) in enumerate(INFO_COLUMNS.items()):
            row, col = 1 + i // 3 * 2, i % 3
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky='w', padx=2)
            box = ttk.Combobox(frame, width=16)
            box.grid(row=row + 1, column=col, padx=2)
            self.info_cols[field] = box
        ttk.Label(frame, text='Elev. units').grid(row=3, column=2, sticky='w', padx=2)
        self.info_units = ttk.Combobox(frame, width=4, values=['ft', 'm'], state='readonly')
        self.info_units.current(0)
        self.info_units.grid(row=4, column=2, sticky='w', padx=2)
        ttk.Button(frame, text='Load Well Info', command=self.load_info).grid(
            row=5, column=0, pady=5, sticky='w')
        ttk.Label(frame, text="A well whose id is another well's baro id is treated as a barometer.",
                  foreground='gray', wraplength=450).grid(row=6, column=0, columnspan=3, sticky='w')

    def load_info_file(self, filename=None):
        if filename is None:
            filename = filedialog.askopenfilename(title='Choose well info file',
                                                  filetypes=[('Tables', '*.csv *.xlsx *.xls'),
                                                             ('All files', '*.*')])
        if not filename:
            return False
        table = run_step(read_table, filename)
        if table is None:
            return False
        self.info_table = table
        cols = list(table.columns)
        for field, (_, names) in INFO_COLUMNS.items():
            self.info_cols[field]['values'] = [''] + cols
            self.info_cols[field].set(guess_column(cols, names))
        self.info_status.set(f'{Path(filename).name} ({len(table)} rows)')
        return True

    def load_info(self):
        if self.info_table is None:
            messagebox.showwarning("Well Info", "Choose a well info file first.")
            return None
        columns = {k: box.get() for k, box in self.info_cols.items()}
        info = run_step(well_info_table, self.info_table, columns, self.info_units.get())
        if info is None:
            return None
        self.reset('info')
        self.set_table('bulk-well-info', info)
        self.set_notes('files', {})
        self.refresh_locations()
        for filename in self.matches:
            self.match(filename, self.matches[filename] if self.matches[filename] in info.index
                       else guess_location(filename, info))
        self.goto(self.files_tab)
        return info

    # --- 2. files --- #

    def build_files(self, frame):
        top = ttk.Frame(frame)
        top.pack(fill='x')
        self.filetype = ttk.Combobox(top, values=list(FILE_TYPES), state='readonly', width=28)
        self.filetype.current(0)
        self.filetype.pack(side='left')
        ttk.Button(top, text='Add folder...', command=self.add_folder).pack(side='left', padx=3)
        ttk.Button(top, text='Add files...', command=self.add_files).pack(side='left')
        ttk.Button(top, text='Remove', command=self.remove_files).pack(side='left', padx=3)

        listframe = ttk.Frame(frame)
        listframe.pack(fill='x', pady=3)
        columns = ('file', 'location', 'id')
        self.file_list = ttk.Treeview(listframe, columns=columns, show='headings', height=6)
        for col, width in zip(columns, (220, 180, 60)):
            self.file_list.heading(col, text=col.title())
            self.file_list.column(col, width=width, stretch=col != 'id')
        scroll = ttk.Scrollbar(listframe, orient='vertical', command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scroll.set)
        self.file_list.pack(side='left', fill='x', expand=True)
        scroll.pack(side='right', fill='y')
        self.file_list.bind('<<TreeviewSelect>>', self.file_selected)

        bottom = ttk.Frame(frame)
        bottom.pack(fill='x')
        ttk.Label(bottom, text='Location').pack(side='left')
        self.location = ttk.Combobox(bottom, width=30, state='readonly')
        self.location.pack(side='left', padx=3)
        self.location.bind('<<ComboboxSelected>>', self.assign_location)
        ttk.Button(bottom, text='Import Matched Files', command=self.import_files).pack(side='left', padx=3)
        self.files_status = tk.StringVar(frame, value='Load the well info first, then add files')
        ttk.Label(frame, textvariable=self.files_status, foreground='gray').pack(anchor='w')

    def refresh_locations(self):
        """Offer the well info locations in the location box"""
        self.location_names = {'': ''}
        if self.info is not None:
            for locid in self.info.index:
                self.location_names[f'{well_name(self.info, locid)} ({locid})'] = locid
        self.location['values'] = list(self.location_names)

    def add_folder(self):
        folder = filedialog.askdirectory(parent=self.master, title='Choose folder of transducer files')
        if folder:
            files = sorted(str(p) for p in Path(folder).iterdir()
                           if p.is_file() and p.suffix.lower() in LOGGER_EXTENSIONS)
            self.add_files(files)

    def add_files(self, filelist=None, matches=None):
        """List files with their best-guess location (or the given matches)"""
        if filelist is None:
            filelist = filedialog.askopenfilenames(parent=self.master, title='Choose transducer files')
        for filename in filelist:
            filename = str(filename)
            if filename not in self.matches:
                self.file_list.insert('', 'end', iid=filename, values=(Path(filename).name, '', ''))
            if matches is not None:
                locid = matches.get(filename, '')
            else:
                locid = guess_location(filename, self.info) if self.info is not None else ''
            self.match(filename, locid)
        matched = sum(1 for locid in self.matches.values() if locid)
        self.files_status.set(f'{matched} of {len(self.matches)} file(s) matched to a location')

    def remove_files(self):
        for filename in self.file_list.selection():
            self.file_list.delete(filename)
            self.matches.pop(filename, None)

    def match(self, filename, locid):
        self.matches[filename] = locid
        name = well_name(self.info, locid) if locid and self.info is not None else ''
        self.file_list.item(filename, values=(Path(filename).name, name, locid))

    def file_selected(self, event=None):
        selection = self.file_list.selection()
        if selection:
            locid = self.matches.get(selection[0], '')
            label = next((k for k, v in self.location_names.items() if v == locid), '')
            self.location.set(label)

    def assign_location(self, event=None):
        locid = self.location_names.get(self.location.get(), '')
        for filename in self.file_list.selection():
            self.match(filename, locid)
        matched = sum(1 for locid in self.matches.values() if locid)
        self.files_status.set(f'{matched} of {len(self.matches)} file(s) matched to a location')

    def import_files(self):
        if not self.require('bulk-well-info', "Load the well info first (step 1)."):
            return None
        filetype = FILE_TYPES[self.filetype.get()]
        load = lambda f: self.well_view.controller.load_file(f, filetype)
        result = run_step(import_bulk_files, self.matches, load)
        if result is None:
            return None
        data, file_info = result
        self.reset('files')
        self.set_table('bulk-files', file_info, select=False)
        self.set_table('bulk-well', data)
        counts = file_info.groupby(level=0).size()
        self.set_notes('files', {locid: f'{n} file(s)' for locid, n in counts.items()})
        self.files_status.set(f'Imported {len(file_info)} file(s) for {len(counts)} location(s)')
        self.refresh_chart_wells()
        self.goto(self.align_tab)
        return data

    # --- 3. align --- #

    def build_align(self, frame):
        ttk.Label(frame, text='Pref. data freq. (min)').grid(row=0, column=0, sticky='w')
        self.freq = ttk.Combobox(frame, width=5, values=[60, 15, 30] + list(range(1, 120)))
        self.freq.current(0)
        self.freq.grid(row=0, column=1, padx=5, sticky='w')
        self.vented = tk.BooleanVar(frame, value=False)
        ttk.Checkbutton(frame, text='Wells without baro data are vented',
                        variable=self.vented).grid(row=1, column=0, columnspan=2, sticky='w')
        ttk.Button(frame, text='Align All Wells', command=self.align).grid(row=0, column=2, padx=5)
        self.align_status = tk.StringVar(frame, value='Removes barometric pressure using the baro id in the well info')
        ttk.Label(frame, textvariable=self.align_status, foreground='gray', wraplength=450).grid(
            row=2, column=0, columnspan=3, sticky='w')

    def align(self):
        if not self.require('bulk-well', "Import the matched files first (step 2)."):
            return None
        try:
            freq = int(self.freq.get())
        except ValueError:
            messagebox.showwarning("Align", "Data frequency must be a whole number of minutes.")
            return None
        result = run_step(align_bulk, self.data['bulk-well'], self.info, freq, self.vented.get())
        if result is None:
            return None
        data, notes = result
        self.reset('align')
        self.set_table('bulk-well-baro', data)
        self.set_notes('aligned', notes)
        n = len(data.index.get_level_values(0).unique())
        self.align_status.set(f'Aligned {n} well(s); see bulk-summary for the others')
        self.refresh_chart_wells()
        self.goto(self.manual_tab)
        return data

    # --- 4. manual measurements --- #

    def build_manual(self, frame):
        top = ttk.Frame(frame)
        top.grid(row=0, column=0, columnspan=4, sticky='w')
        ttk.Button(top, text='Choose file...', command=self.load_manual_file).pack(side='left')
        self.man_status = tk.StringVar(frame, value='File needs datetime, depth to water and location id')
        ttk.Label(top, textvariable=self.man_status, foreground='gray').pack(side='left', padx=5)
        self.man_cols = {}
        for col, label in enumerate(('Datetime', 'DTW', 'Location id')):
            ttk.Label(frame, text=label).grid(row=1, column=col)
            box = ttk.Combobox(frame, width=14)
            box.grid(row=2, column=col, padx=2)
            self.man_cols[label] = box
        ttk.Label(frame, text='Units').grid(row=1, column=3)
        self.man_units = ttk.Combobox(frame, width=4, values=['ft', 'm'], state='readonly')
        self.man_units.current(0)
        self.man_units.grid(row=2, column=3)
        ttk.Button(frame, text='Process Manual Data', command=self.process_manual).grid(
            row=3, column=0, columnspan=2, pady=5, sticky='w')

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
        for label, names in (('Datetime', DATE_NAMES), ('DTW', DTW_NAMES), ('Location id', LOCID_NAMES)):
            self.man_cols[label]['values'] = cols
            self.man_cols[label].set(guess_column(cols, names))
        self.man_status.set(f'{Path(filename).name} ({len(table)} rows)')
        return True

    def process_manual(self):
        if not self.require('bulk-well-info', "Load the well info first (step 1)."):
            return None
        if self.manual_table is None:
            messagebox.showwarning("Manual Data", "Choose a manual measurement file first.")
            return None
        result = run_step(bulk_manual, self.manual_table, self.man_cols['Datetime'].get(),
                          self.man_cols['DTW'].get(), self.man_cols['Location id'].get(),
                          self.info, self.man_units.get())
        if result is None:
            return None
        self.reset('manual')
        self.set_table('bulk-manual', result)
        counts = result.groupby(level=0).size()
        self.set_notes('manual', {locid: f'{n} reading(s)' for locid, n in counts.items()})
        self.goto(self.drift_tab)
        return result

    # --- 5. drift and export --- #

    def build_drift(self, frame):
        ttk.Label(frame, text='Max allowed drift (ft)').grid(row=0, column=0, sticky='w')
        self.max_drift = tk.StringVar(frame, value='0.3')
        ttk.Entry(frame, textvariable=self.max_drift, width=8).grid(row=0, column=1, sticky='w', padx=5)
        ttk.Button(frame, text='Fix Drift', command=self.fix_drift).grid(row=0, column=2, padx=5)
        self.drift_status = tk.StringVar(frame, value='Wells over the max drift are left out of the results')
        ttk.Label(frame, textvariable=self.drift_status, foreground='gray', wraplength=450).grid(
            row=1, column=0, columnspan=3, sticky='w')
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, pady=5, sticky='w')
        ttk.Button(buttons, text='Save csv...', command=self.save_csv).pack(side='left')
        ttk.Button(buttons, text='Save drift info...', command=self.save_drift_info).pack(side='left', padx=5)
        ttk.Button(buttons, text='Save pdf charts...', command=self.save_pdf).pack(side='left')

    def fix_drift(self):
        if not self.require('bulk-well-baro', "Align the wells first (step 3)."):
            return None
        if not self.require('bulk-manual', "Process the manual data first (step 4)."):
            return None
        try:
            max_allowed = float(self.max_drift.get()) if self.max_drift.get().strip() else None
        except ValueError:
            messagebox.showwarning("Fix Drift", "Max allowed drift must be a number (or blank for no limit).")
            return None
        result = run_step(bulk_drift, self.data['bulk-well-baro'], self.data['bulk-manual'],
                          self.info, max_allowed)
        if result is None:
            return None
        fixed, drift_info, notes, drifts = result
        self.set_table('bulk-drift-info', drift_info, select=False)
        self.set_table('bulk-fix-drift', fixed)
        self.set_notes('drift', notes)
        n = len(fixed.index.get_level_values(0).unique())
        self.drift_status.set(f'Corrected {n} of {len(notes)} well(s); see bulk-summary for the others')
        self.refresh_chart_wells()
        return fixed

    def save_csv(self, filename=None):
        if not self.require('bulk-fix-drift', "Fix drift first."):
            return None
        if filename is None:
            filename = filedialog.asksaveasfilename(filetypes=[('csv', '*.csv'), ('Excel', '*.xlsx')],
                                                    defaultextension='.csv', confirmoverwrite=True,
                                                    title='Bulk processing output')
        if not filename:
            return None
        df = export_table(self.data['bulk-fix-drift'])
        if Path(filename).suffix.lower() in ('.xlsx', '.xls'):
            return run_step(lambda: df.to_excel(filename, index=False) or filename)
        return run_step(lambda: df.to_csv(filename, index=False) or filename)

    def save_drift_info(self, filename=None):
        if not self.require('bulk-drift-info', "Fix drift first."):
            return None
        if filename is None:
            filename = filedialog.asksaveasfilename(filetypes=[('csv', '*.csv')], defaultextension='.csv',
                                                    confirmoverwrite=True, title='Drift info output')
        if filename:
            return run_step(lambda: self.data['bulk-drift-info'].to_csv(filename) or filename)
        return None

    def save_pdf(self, filename=None):
        if not self.require('bulk-fix-drift', "Fix drift first."):
            return None
        if filename is None:
            filename = filedialog.asksaveasfilename(filetypes=[('PDF', '*.pdf')], defaultextension='.pdf',
                                                    confirmoverwrite=True, title='Charts of each well')
        if filename:
            return run_step(write_bulk_pdf, filename, self.data['bulk-fix-drift'],
                            self.data.get('bulk-manual'), self.info)
        return None

    # --- chart of one well --- #

    def build_chart(self, master):
        top = ttk.Frame(master)
        top.pack(fill='x', padx=5)
        ttk.Label(top, text='Chart well').pack(side='left')
        self.chart_well = ttk.Combobox(top, width=30, state='readonly')
        self.chart_well.pack(side='left', padx=5)
        self.chart_well.bind('<<ComboboxSelected>>', lambda e: self.draw_well())

        frame = ttk.Frame(master)
        frame.pack(fill='both', expand=True)
        self.fig = Figure(figsize=(8, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        NavigationToolbar2Tk(self.canvas, frame).update()
        self.chart_ids = {}

    def refresh_chart_wells(self):
        """Offer the wells with data in the chart box, keeping the current one if it still has data"""
        if 'bulk-well' not in self.data or self.info is None:
            self.chart_ids = {}
        else:
            self.chart_ids = {f'{well_name(self.info, i)} ({i})': i for i in location_ids(self.data['bulk-well'])}
        self.chart_well['values'] = list(self.chart_ids)
        if self.chart_well.get() not in self.chart_ids:
            self.chart_well.set(next(iter(self.chart_ids), ''))
        self.draw_well()

    def draw_well(self):
        """Chart the most processed table that has the chosen well"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        locid = self.chart_ids.get(self.chart_well.get())
        manual = self.data.get('bulk-manual')
        manual = manual.xs(locid, level=0) if manual is not None and locid in manual.index else None
        for key in ('bulk-fix-drift', 'bulk-well-baro', 'bulk-well'):
            df = self.data.get(key)
            if locid is None or df is None or locid not in df.index:
                continue
            df = df.xs(locid, level=0)
            title = f'{self.chart_well.get()} - {key}'
            if key == 'bulk-fix-drift':
                plot_well(ax, title, df, manual)
            else:
                for col, label in (('Level', 'Raw level'), ('corrwl', 'Baro-corrected')):
                    if col in df.columns:
                        ax.plot(df.index, df[col], label=label)
                ax.set_title(title)
                ax.set_ylabel('Level (ft)')
                ax.grid(True)
                ax.legend(loc='best')
            self.fig.autofmt_xdate()
            break
        self.canvas.draw()

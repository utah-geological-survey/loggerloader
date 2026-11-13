"""Save and open Logger Loader projects.

A project is a zip file (``.llproj``) holding:
    manifest.json     format version, app settings, column kinds of every table
    tables/<n>.csv    one csv per table, with its index as the first columns

Tables are csv rather than pickle so a project is safe to open, readable outside the
app, and not tied to one pandas version. The manifest records whether each column
holds numbers, dates, booleans, or text, so values come back with the same types.
"""
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

FORMAT = 'loggerloader-project'
VERSION = 1
EXTENSION = '.llproj'


def column_kind(series):
    """'datetime', 'number', 'bool', or 'text' for a column (object columns are inspected)"""
    if pd.api.types.is_bool_dtype(series):
        return 'bool'
    if pd.api.types.is_datetime64_any_dtype(series):
        return 'datetime'
    if pd.api.types.is_numeric_dtype(series):
        return 'number'
    values = series.dropna()
    if len(values) and values.map(lambda v: isinstance(v, pd.Timestamp)).all():
        return 'datetime'
    if len(values) and values.map(lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)).all():
        return 'number'
    return 'text'


def number_text(value):
    """Exact text for a number (repr round-trips floats; numpy scalars repr differently)"""
    if pd.isna(value):
        return None
    if isinstance(value, float) or pd.api.types.is_float(value):
        return repr(float(value))
    return str(value)


def restore_column(series, kind):
    if kind == 'datetime':
        return pd.to_datetime(series, format='ISO8601')
    if kind == 'number':
        values = series.dropna()
        if values.str.fullmatch(r'-?\d+').all():
            return pd.to_numeric(series)
        # Python's float() parses repr text exactly; pandas' fast parser can be off in the last digit
        return series.map(lambda v: float(v) if isinstance(v, str) else float('nan')).astype('float64')
    if kind == 'bool':
        return series.map({'True': True, 'False': False})
    return series


def table_to_csv(df):
    """Return (csv text, schema) for a DataFrame"""
    index_names = [n if n is not None else f'__index_{i}__' for i, n in enumerate(df.index.names)]
    flat = df.copy()
    flat.index.names = index_names
    flat = flat.reset_index()
    # Columns are stored by position so duplicate or non-text names survive
    flat.columns = range(len(flat.columns))
    schema = {
        'index': [None if n.startswith('__index_') else n for n in index_names],
        'columns': [str(c) for c in df.columns],
        'kinds': [column_kind(flat[i]) for i in flat.columns],
    }
    for i, kind in enumerate(schema['kinds']):
        if kind == 'datetime':
            flat[i] = pd.to_datetime(flat[i]).map(lambda v: v.isoformat() if pd.notna(v) else None)
        elif kind == 'number' and not pd.api.types.is_integer_dtype(flat[i]):
            flat[i] = flat[i].map(number_text).astype(object)
    return flat.to_csv(index=False), schema


def table_from_csv(text, schema):
    flat = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, na_values=[''])
    flat.columns = range(len(flat.columns))
    for i, kind in enumerate(schema['kinds']):
        flat[i] = restore_column(flat[i], kind)
    n_index = len(schema['index'])
    df = flat.set_index(list(range(n_index)))
    df.index.names = schema['index']
    df.columns = schema['columns']
    return df


def save_project(path, tables, settings):
    """Write tables ({group: {name: DataFrame}}) and json-able settings to a project file.

    The file is written to a temporary name first, so a failed save never
    destroys an existing project.
    """
    path = Path(path)
    manifest = {'format': FORMAT, 'version': VERSION, 'settings': settings, 'tables': []}
    tmp = path.with_name(path.name + '.tmp')
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            n = 0
            for group, frames in tables.items():
                for name, df in frames.items():
                    text, schema = table_to_csv(df)
                    member = f'tables/{n}.csv'
                    zf.writestr(member, text)
                    manifest['tables'].append({'group': group, 'name': name, 'file': member, **schema})
                    n += 1
            zf.writestr('manifest.json', json.dumps(manifest, indent=2, default=str))
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def load_project(path):
    """Read a project file; returns (tables {group: {name: DataFrame}}, settings)"""
    with zipfile.ZipFile(path) as zf:
        try:
            manifest = json.loads(zf.read('manifest.json'))
        except KeyError:
            raise ValueError(f"{Path(path).name} is not a Logger Loader project.")
        if manifest.get('format') != FORMAT:
            raise ValueError(f"{Path(path).name} is not a Logger Loader project.")
        if manifest.get('version', 0) > VERSION:
            raise ValueError("This project was saved by a newer version of Logger Loader.")
        tables = {}
        for entry in manifest['tables']:
            text = zf.read(entry['file']).decode('utf-8')
            tables.setdefault(entry['group'], {})[entry['name']] = table_from_csv(text, entry)
    return tables, manifest.get('settings', {})

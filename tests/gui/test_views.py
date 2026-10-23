"""Tests for loggerloader.views: table tabs, charts, and the single-well controller"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from loggerloader import views
from loggerloader.views import (CONVERSION_FACTORS, FEET_PER_METER, default_field, file_summary,
                                numeric_columns, plot_table, resource_path)
from loggerloader.workflow import FILE_TYPES

from .conftest import click, find_widget, time_series

MATCH_COLUMNS = 'Other csv/Excel (match columns)'


def generic_csv(df, path):
    """Write a time series the way ColumnMatchDialog expects (datetime, level, temperature)"""
    out = df.reset_index().rename(columns={'DateTime': 'datetime', 'Level': 'level',
                                           'Temperature': 'temperature'})
    out.to_csv(path, index=False)
    return path


def accept(window):
    click(window, 'OK')


# --- module helpers --- #

class TestHelpers:
    def test_numeric_columns_skips_text(self):
        df = pd.DataFrame({'a': [1.0], 'b': ['x'], 'c': [2]})
        assert numeric_columns(df) == ['a', 'c']

    @pytest.mark.parametrize('key, columns, expected', [
        ('well-baro', ['Level', 'corrwl'], 'corrwl'),
        ('fixed-drift', ['corrwl', 'DTW_WL'], 'DTW_WL'),
        ('wl-elev', ['DTW_WL', 'waterelevation'], 'waterelevation'),
        ('manual', ['units_n', 'dtwbelowcasing'], 'dtwbelowcasing'),
        ('well', ['Temperature', 'Level'], 'Level'),
        ('other', ['Temperature', 'Cond'], 'Temperature'),
    ])
    def test_default_field(self, key, columns, expected):
        df = pd.DataFrame({c: [1.0] for c in columns})
        assert default_field(key, df) == expected

    def test_default_field_without_numbers(self):
        assert default_field('well', pd.DataFrame({'a': ['x']})) is None

    def test_file_summary(self):
        df = time_series(periods=25, wave=0.0, trend=1.0)
        info = file_summary(df, Path('a/b.csv'))
        assert info['file_name'] == str(Path('a/b.csv'))
        assert info['first_date'] == df.index[0]
        assert info['last_date'] == df.index[-1]
        assert info['records'] == 25
        assert info['hours_dur'] == pytest.approx(24.0)
        assert info['file_mean'] == pytest.approx(112.0)
        assert info['file_range'] == pytest.approx(24.0)

    def test_file_summary_without_level(self):
        df = time_series(periods=3).drop(columns='Level')
        info = file_summary(df, 'x')
        assert np.isnan(info['file_mean'])

    def test_resource_path_points_into_package(self):
        assert Path(resource_path('themes/forest-light.tcl')).exists()
        assert Path(resource_path('data_files/icon.ico')).exists()

    def test_conversion_factors_are_consistent(self):
        assert CONVERSION_FACTORS['psi_ft'] * CONVERSION_FACTORS['ft_psi'] == pytest.approx(1.0, rel=1e-3)
        assert CONVERSION_FACTORS['bar_psi'] * CONVERSION_FACTORS['psi_bar'] == pytest.approx(1.0, rel=1e-3)
        assert FEET_PER_METER == pytest.approx(1 / 0.3048, rel=1e-5)


class TestPlotTable:
    @pytest.fixture
    def ax(self):
        return Figure().add_subplot(111)

    def labels(self, ax):
        return ax.get_legend_handles_labels()[1]

    def test_no_chart_for_empty_or_untimed_tables(self, ax):
        assert plot_table(ax, 'x', None) is False
        assert plot_table(Figure().add_subplot(111), 'x', pd.DataFrame()) is False
        assert plot_table(Figure().add_subplot(111), 'drift-info', pd.DataFrame({'a': [1]})) is False
        assert 'No chart for x' in [t.get_text() for t in ax.texts]

    def test_no_numeric_columns(self, ax):
        df = pd.DataFrame({'note': ['a', 'b']}, index=pd.date_range('2023', periods=2))
        assert plot_table(ax, 'well', df) is False
        assert 'No numeric columns in well' in ax.texts[0].get_text()

    def test_well_baro_draws_raw_corrected_and_barometer(self, ax):
        df = time_series().assign(corrwl=1.0, barometer=2.0)
        assert plot_table(ax, 'well-baro', df)
        assert self.labels(ax) == ['Raw Data', 'Corrected Data', 'Barometer']
        assert len(ax.figure.axes) == 2  # barometer on a twin axis

    def test_fixed_drift_with_manual_points(self, ax):
        df = time_series().assign(DTW_WL=-20.0)
        manual = pd.DataFrame({'dtwbelowcasing': [20.0]}, index=df.index[:1])
        assert plot_table(ax, 'fixed-drift', df, manual=manual)
        assert self.labels(ax) == ['Drift-corrected', 'Manual']
        offsets = ax.collections[0].get_offsets()
        assert offsets[0][1] == -20.0  # manual depths are drawn as negative

    def test_wl_elev_with_manual_points(self, ax):
        df = time_series().assign(waterelevation=5000.0)
        manual = pd.DataFrame({'waterelevation': [4999.0]}, index=df.index[:1])
        assert plot_table(ax, 'wl-elev', df, manual=manual)
        assert self.labels(ax) == ['Water elevation', 'Manual']

    def test_manual_table(self, ax):
        df = pd.DataFrame({'dtwbelowcasing': [1.0, 2.0]}, index=pd.date_range('2023', periods=2))
        assert plot_table(ax, 'manual', df)
        assert ax.get_ylabel() == 'Depth to water (ft)'

    def test_other_table_uses_given_field(self, ax):
        assert plot_table(ax, 'well', time_series(), field='Temperature')
        assert ax.get_ylabel() == 'Temperature'

    def test_other_table_falls_back_to_default_field(self, ax):
        assert plot_table(ax, 'well', time_series(), field='missing')
        assert ax.get_ylabel() == 'Level'

    def test_options(self, ax):
        plot_table(ax, 'well', time_series(), flip_y=True, grid=False, legend=False)
        low, high = ax.get_ylim()
        assert low > high
        assert ax.get_legend() is None
        assert not any(line.get_visible() for line in ax.get_xgridlines())
        assert ax.get_title() == 'well'

    def test_defaults_show_grid_and_legend(self, ax):
        plot_table(ax, 'well', time_series())
        assert ax.get_legend() is not None
        assert all(line.get_visible() for line in ax.get_xgridlines())


# --- ViewManager --- #

class TestViewManager:
    def test_builds_the_three_processing_tabs(self, app):
        notebook = app.view_manager.processing_notebook
        texts = [notebook.tab(t, 'text') for t in notebook.tabs()]
        assert texts == ['Single-Well Process', 'Bulk Well Process', 'One Well Many files']

    def test_forest_theme_loaded(self, app):
        assert app.view_manager.style.theme_use() == 'forest-light'

    @pytest.mark.parametrize('mode, ttk_theme, sheet_theme', [
        ('dark', 'forest-dark', 'dark green'),
        ('light', 'forest-light', 'light blue'),
        ('system', 'forest-light', 'light blue'),
    ])
    def test_set_theme(self, loaded, mode, ttk_theme, sheet_theme):
        manager = loaded.view_manager
        manager.set_theme(mode)
        assert manager.style.theme_use() == ttk_theme
        assert manager.sheettheme == sheet_theme
        assert loaded.well_view.sheettheme == sheet_theme

    def test_set_theme_ignores_missing_theme(self, app, monkeypatch):
        manager = app.view_manager

        def fail(name):
            raise views.tk.TclError('no theme')
        monkeypatch.setattr(manager.style, 'theme_use', fail)
        manager.set_theme('dark')
        assert manager.sheettheme == 'light blue'


# --- WellDataView --- #

class TestWellDataView:
    def tab_texts(self, view):
        return [view.notebook.tab(t, 'text') for t in view.notebook.tabs()]

    def test_set_table_adds_tab_sheet_and_chart(self, app, well_df):
        view = app.well_view
        view.set_table('well', well_df)
        assert self.tab_texts(view) == ['well']
        assert view.data['well'] is well_df
        sheet = view.datatable['well']
        assert len(sheet.get_sheet_data()) == len(well_df)
        assert list(sheet.headers()) == ['DateTime', 'Level', 'Temperature']
        assert view.selected_tab == 'well'
        assert view.field == 'Level'
        assert app.chart_manager.last[0] == 'well'

    def test_set_table_replaces_existing_tab(self, app, well_df):
        view = app.well_view
        view.set_table('well', well_df)
        view.set_table('well', well_df.iloc[:5])
        assert self.tab_texts(view) == ['well']
        assert len(view.datatable['well'].get_sheet_data()) == 5

    def test_set_table_without_select_keeps_current(self, app, well_df, baro_df):
        view = app.well_view
        view.set_table('well', well_df)
        view.set_table('baro', baro_df, select=False)
        assert view.selected_tab == 'well'
        assert self.tab_texts(view) == ['well', 'baro']

    def test_set_table_keeps_field_if_still_numeric(self, app, well_df):
        view = app.well_view
        view.field = 'Temperature'
        view.set_table('well', well_df)
        assert view.field == 'Temperature'

    def test_well_table_refreshes_align_fields(self, app, well_df):
        view = app.well_view
        view.set_table('well', well_df.rename(columns={'Level': 'Pressure'}))
        assert list(view.workflow.well_field['values']) == ['Pressure', 'Temperature']
        assert view.workflow.well_field.get() == 'Pressure'

    def test_current_table(self, app, well_df):
        view = app.well_view
        assert view.current_table() == (None, None)
        view.set_table('well', well_df)
        key, df = view.current_table()
        assert key == 'well' and df is well_df

    def test_remove_table(self, loaded):
        view = loaded.well_view
        view.remove_table('baro')
        assert 'baro' not in view.data and 'baro' not in view.datatable and 'baro' not in view.tabs
        assert self.tab_texts(view) == ['well']
        view.remove_table('not-there')  # no error

    def test_remove_selected_table_clears_selection(self, loaded):
        view = loaded.well_view
        view.remove_table('baro')
        assert view.selected_tab is None

    def test_clear_tables(self, loaded):
        view = loaded.well_view
        view.clear_tables()
        assert view.data == {} and view.datatable == {} and view.tabs == {}
        assert view.notebook.tabs() == ()
        assert view.selected_tab is None
        assert loaded.chart_manager.last is None

    def test_nbselect_charts_the_selected_tab(self, loaded):
        view = loaded.well_view
        view.notebook.select(view.tabs['well'])
        view.nbselect(None)
        assert view.selected_tab == 'well'
        assert loaded.chart_manager.last[0] == 'well'

    def test_nbselect_with_no_tabs(self, app):
        app.well_view.nbselect(None)
        assert app.well_view.selected_tab is None

    def test_column_selected_charts_numeric_column(self, loaded):
        view = loaded.well_view
        view.column_selected(SimpleNamespace(selected=SimpleNamespace(column=2)), 'well')
        assert view.field == 'Temperature'
        assert view.selected_tab == 'well'
        assert loaded.chart_manager.last[2] == 'Temperature'

    @pytest.mark.parametrize('event', [
        SimpleNamespace(selected=SimpleNamespace(column=0)),   # the DateTime index
        SimpleNamespace(selected=SimpleNamespace(column=99)),  # out of range
        SimpleNamespace(selected=()),                           # nothing selected
    ])
    def test_column_selected_ignores_other_columns(self, loaded, event):
        view = loaded.well_view
        view.column_selected(event, 'well')
        assert view.field == 'Level'
        assert view.selected_tab == 'baro'

    def test_end_edit_cell_copies_edits_back_with_types(self, loaded, well_df):
        view = loaded.well_view
        sheet = view.datatable['well']
        sheet.set_cell_data(0, 1, '123.5')
        view.end_edit_cell(key='well')
        df = view.data['well']
        assert df['Level'].iloc[0] == 123.5
        assert pd.api.types.is_float_dtype(df['Level'])
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.name == 'DateTime'
        pd.testing.assert_series_equal(df['Temperature'], well_df['Temperature'], check_freq=False)

    def test_end_edit_cell_bad_number_becomes_nan(self, loaded):
        view = loaded.well_view
        view.datatable['well'].set_cell_data(1, 1, 'oops')
        view.end_edit_cell(key='well')
        assert np.isnan(view.data['well']['Level'].iloc[1])

    def test_end_edit_cell_with_unnamed_index(self, app):
        view = app.well_view
        df = pd.DataFrame({'a': [1.0, 2.0]})
        view.set_table('t', df)
        view.datatable['t'].set_cell_data(1, 1, '5')
        view.end_edit_cell(key='t')
        assert view.data['t']['a'].tolist() == [1.0, 5.0]
        assert view.data['t'].index.name is None

    def test_end_edit_cell_redraws_selected_table(self, loaded):
        view = loaded.well_view
        view.datatable['baro'].set_cell_data(0, 1, '50')
        view.end_edit_cell(key='baro')
        assert loaded.chart_manager.last[1]['Level'].iloc[0] == 50.0

    def test_end_edit_cell_unknown_key(self, loaded):
        loaded.well_view.end_edit_cell(key='nope')

    def test_set_sheet_theme(self, loaded):
        view = loaded.well_view
        view.set_sheet_theme('dark green')
        assert view.sheettheme == 'dark green'

    def test_show_error(self, app, dialogs):
        app.well_view.show_error('bad')
        assert dialogs.errors() == ['bad']


# --- WellDataController --- #

class TestImport:
    def test_import_files_through_column_matching(self, app, modal_driver, tmp_path, well_df):
        path = generic_csv(well_df, tmp_path / 'pw01.csv')
        modal_driver.push(accept)
        controller = app.well_view.controller
        assert controller.import_well_data([str(path)], filetype='table')
        df = app.well_view.data['well']
        assert list(df.columns) == ['Level', 'Temperature', 'filename']
        assert df.index.name == 'DateTime'
        assert (df['filename'] == 'pw01').all()
        np.testing.assert_allclose(df['Level'], well_df['Level'])
        assert controller.file_data['records'].tolist() == [len(well_df)]

    def test_import_combines_files_and_drops_duplicate_times(self, app, modal_driver, tmp_path):
        first = time_series(periods=10)
        second = time_series(periods=10, start='2023-01-01 05:00', base=50.0)
        paths = [generic_csv(first, tmp_path / 'a.csv'), generic_csv(second, tmp_path / 'b.csv')]
        modal_driver.push(accept)
        modal_driver.push(accept)
        assert app.well_view.controller.import_baro_data([str(p) for p in paths], filetype='table')
        df = app.well_view.data['baro']
        assert len(df) == 15
        assert df.index.is_monotonic_increasing
        assert df.loc['2023-01-01 05:00', 'filename'] == 'a'  # first file wins
        assert len(app.well_view.controller.file_data) == 2

    def test_import_reports_recent_files(self, app, modal_driver, tmp_path, well_df):
        path = str(generic_csv(well_df, tmp_path / 'pw01.csv'))
        modal_driver.push(accept)
        app.well_view.controller.import_well_data([path], filetype='table')
        assert app.menu.recent_files[0] == path

    def test_cancelled_column_match(self, app, modal_driver, tmp_path, well_df):
        path = generic_csv(well_df, tmp_path / 'pw01.csv')
        modal_driver.push(lambda window: click(window, 'Cancel'))
        assert not app.well_view.controller.import_well_data([str(path)], filetype='table')
        assert 'well' not in app.well_view.data

    def test_cancelled_file_dialog(self, app, dialogs):
        dialogs.answer('askopenfilenames', ())
        assert not app.well_view.controller.import_well_data()
        assert dialogs.called('askopenfilenames')

    def test_unreadable_transducer_file_warns(self, app, dialogs, tmp_path):
        path = tmp_path / 'junk.csv'
        path.write_text('not,a\nlogger,file\n')
        assert not app.well_view.controller.import_well_data([str(path)])
        assert dialogs.warnings() or dialogs.errors()


class TestAlign:
    def test_align(self, loaded):
        df = loaded.well_view.controller.align()
        assert {'Level', 'barometer', 'corrwl'} <= set(df.columns)
        assert loaded.well_view.data['well-baro'] is df
        assert loaded.well_view.selected_tab == 'well-baro'

    def test_vented_needs_no_baro(self, app, well_df):
        app.well_view.set_table('well', well_df)
        df = app.well_view.controller.align(vented=True)
        assert not df.empty

    @pytest.mark.parametrize('tables, kwargs, message', [
        ((), {}, 'Import well data first'),
        (('well',), {}, 'Import barometric data first'),
        (('well', 'baro'), {'well_field': 'nope'}, "no 'nope' column"),
        (('well', 'baro'), {'baro_field': 'nope'}, "no 'nope' column"),
    ])
    def test_align_errors(self, app, well_df, baro_df, tables, kwargs, message):
        for key in tables:
            app.well_view.set_table(key, {'well': well_df, 'baro': baro_df}[key])
        with pytest.raises(ValueError, match=message):
            app.well_view.controller.align(**kwargs)

    def test_align_without_overlap(self, app, well_df):
        app.well_view.set_table('well', well_df)
        app.well_view.set_table('baro', time_series(start='2025-01-01'))
        with pytest.raises(ValueError, match='do not overlap'):
            app.well_view.controller.align()


class TestManual:
    def test_manual_from_entry(self, app, well_df):
        when = well_df.index[[3, 1]]
        df = app.well_view.controller.manual_from_entry([(when[0], '10'), (when[1], 11.5)], 'ft', '42')
        assert df.index.is_monotonic_increasing
        assert df['dtwbelowcasing'].tolist() == [11.5, 10.0]
        assert (df['locationid'] == '42').all() and (df['units'] == 'ft').all()
        assert app.well_view.data['manual'] is df

    def test_manual_from_entry_in_meters(self, app, well_df):
        df = app.well_view.controller.manual_from_entry([(well_df.index[0], 1.0)], 'm')
        assert df['dtwbelowcasing'].iloc[0] == pytest.approx(FEET_PER_METER)

    @pytest.fixture
    def readings(self, well_df):
        index = well_df.index
        return pd.DataFrame({
            'date': [index[1], index[10], index[5], index[0] - pd.Timedelta(days=30), 'bad'],
            'dtw': [10.0, 11.0, 12.0, 13.0, 14.0],
            'site': [71, '71', 71.0, 71, 71],
        })

    def test_manual_from_table(self, loaded, readings):
        df = loaded.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site')
        # sorted; the bad date and the reading a month before the record are dropped
        assert df['dtwbelowcasing'].tolist() == [10.0, 12.0, 11.0]
        assert df.index.name == 'readingdate'
        assert (df['units'] == 'ft').all()

    def test_manual_from_table_picks_one_id(self, loaded, readings):
        readings.loc[0, 'site'] = 99
        df = loaded.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site', pick_id='99')
        assert df['dtwbelowcasing'].tolist() == [10.0]

    def test_manual_from_table_in_meters(self, loaded, readings):
        df = loaded.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site', units='m')
        assert df['dtwbelowcasing'].iloc[0] == pytest.approx(10.0 * FEET_PER_METER)
        assert (df['units'] == 'm').all()

    def test_manual_from_table_without_well_keeps_all_dates(self, app, readings):
        df = app.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site')
        assert len(df) == 4

    @pytest.mark.parametrize('columns, message', [
        (('nope', 'dtw', 'site'), 'datetime'),
        (('date', 'nope', 'site'), 'depth to water'),
        (('date', 'dtw', 'nope'), 'location id'),
    ])
    def test_manual_from_table_missing_columns(self, loaded, readings, columns, message):
        with pytest.raises(ValueError, match=message):
            loaded.well_view.controller.manual_from_table(readings, *columns)

    def test_manual_from_table_several_ids(self, loaded, readings):
        readings.loc[0, 'site'] = 99
        with pytest.raises(ValueError, match='several location ids'):
            loaded.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site')

    def test_manual_from_table_no_match(self, loaded, readings):
        with pytest.raises(ValueError, match='No manual readings'):
            loaded.well_view.controller.manual_from_table(readings, 'date', 'dtw', 'site', pick_id='5')


class TestDriftAndElevation:
    def test_fix_drift(self, loaded, well_df):
        controller = loaded.well_view.controller
        controller.align()
        index = well_df.index
        controller.manual_from_entry([(index[2], 20.0), (index[-3], 20.5)], 'ft', '42')
        max_drift = controller.fix_drift()
        assert np.isfinite(max_drift)
        data = loaded.well_view.data
        assert {'DTW_WL', 'corrwl', 'driftcorrection'} <= set(data['fixed-drift'].columns)
        assert 'drift' in data['drift-info'].columns
        # corrected depths match the manual readings (as negative numbers) where they were taken
        assert data['fixed-drift'].loc[index[2], 'DTW_WL'] == pytest.approx(-20.0, abs=0.01)
        # (Drifting's last segment ends one reading before the last manual measurement)
        last = data['fixed-drift']['DTW_WL'].loc[:index[-3]].dropna().iloc[-1]
        assert last == pytest.approx(-20.5, abs=0.02)
        assert loaded.well_view.selected_tab == 'fixed-drift'

    def test_fix_drift_needs_alignment(self, loaded):
        with pytest.raises(ValueError, match='Align the data first'):
            loaded.well_view.controller.fix_drift()

    def test_fix_drift_needs_manual(self, loaded):
        loaded.well_view.controller.align()
        with pytest.raises(ValueError, match='Process manual data first'):
            loaded.well_view.controller.fix_drift()

    def test_calc_elevations(self, processed):
        data = processed.well_view.data
        wl = data['wl-elev']
        np.testing.assert_allclose(wl['waterelevation'], wl['DTW_WL'] + 2.0 + 5000.0)
        manual = data['manual']
        np.testing.assert_allclose(manual['waterelevation'], 5002.0 - manual['dtwbelowcasing'])
        assert processed.well_view.selected_tab == 'wl-elev'

    def test_calc_elevations_in_meters(self, processed):
        controller = processed.well_view.controller
        wl = controller.calc_elevations(1000.0, 'm', 1.0, 'm')
        np.testing.assert_allclose(wl['waterelevation'], wl['DTW_WL'] + 1001.0 * FEET_PER_METER)

    def test_calc_elevations_needs_drift(self, loaded):
        with pytest.raises(ValueError, match='Fix drift first'):
            loaded.well_view.controller.calc_elevations(100.0)

    @pytest.mark.parametrize('name', ['out.csv', 'out.xlsx'])
    def test_save_one_well(self, processed, tmp_path, name):
        path = processed.well_view.controller.save_one_well(tmp_path / name)
        df = pd.read_csv(path) if name.endswith('.csv') else pd.read_excel(path)
        assert 'DTW_WL' not in df.columns
        assert {'DateTime', 'measureddtw', 'measuredlevel', 'temperature', 'waterelevation'} <= set(df.columns)
        wl = processed.well_view.data['wl-elev']
        np.testing.assert_allclose(df['measureddtw'], -wl['DTW_WL'].values)


class TestConvertUnits:
    @pytest.mark.parametrize('in_units, out_units, expected', [
        ('C', 'F', 50.0),
        ('F', 'C', -12.2222222),
        ('C', 'C', 10.0),
        ('psi', 'ft', 10.0 * CONVERSION_FACTORS['psi_ft']),
        ('kPa', 'bar', 0.1),
    ])
    def test_convert_units(self, app, in_units, out_units, expected):
        df = pd.DataFrame({'Temperature': [10.0]}, index=pd.date_range('2023', periods=1))
        app.well_view.set_table('well', df)
        result = app.well_view.controller.convert_units('well', 'Temperature', in_units, out_units, 'new')
        assert result['new'].iloc[0] == pytest.approx(expected)
        assert app.well_view.data['well'] is result

    def test_unknown_conversion(self, loaded):
        with pytest.raises(ValueError, match="Can't convert"):
            loaded.well_view.controller.convert_units('well', 'Level', 'ft', 'kPa', 'new')


# --- ManyFilesView --- #

class TestManyFiles:
    @pytest.fixture
    def files(self, tmp_path):
        # written out of order, to check they are sorted by date
        later = generic_csv(time_series(periods=24, start='2023-01-02'), tmp_path / 'later.csv')
        early = generic_csv(time_series(periods=24, start='2023-01-01'), tmp_path / 'early.csv')
        return [str(later), str(early)]

    @pytest.fixture
    def many(self, app, files, modal_driver):
        view = app.view_manager.many_files_view
        view.filetype.set(MATCH_COLUMNS)
        modal_driver.push(accept)
        modal_driver.push(accept)
        assert view.select_files(files)
        return view

    def test_select_files_lists_them_by_date(self, many):
        rows = [many.file_list.item(i, 'values') for i in many.file_list.get_children()]
        assert [r[0] for r in rows] == ['early.csv', 'later.csv']
        assert rows[0][1] == '2023-01-01 00:00'
        assert rows[0][3] == '24'
        assert many.status.get() == '2 file(s) loaded'

    def test_select_files_cancelled(self, app, dialogs):
        dialogs.answer('askopenfilenames', '')
        assert not app.view_manager.many_files_view.select_files()

    def test_process_files_sends_combined_data(self, app, many):
        many.target.set('baro')
        data = many.process_files()
        assert len(data) == 48
        assert app.well_view.data['baro'] is data
        assert app.well_view.workflow.file_status['baro'].get() == '2 combined files'
        assert many.status.get() == 'Sent 48 rows to baro'

    def test_process_files_fixes_unit_changes(self, app, tmp_path, modal_driver):
        feet = time_series(periods=96, wave=1.0)
        meters = time_series(periods=96, start='2023-01-05', wave=1.0)
        meters['Level'] = meters['Level'] / FEET_PER_METER
        files = [str(generic_csv(feet, tmp_path / 'ft.csv')), str(generic_csv(meters, tmp_path / 'm.csv'))]
        view = app.view_manager.many_files_view
        view.filetype.set(MATCH_COLUMNS)
        modal_driver.push(accept)
        modal_driver.push(accept)
        view.select_files(files)
        view.fix_units.set(True)
        data = view.process_files()
        np.testing.assert_allclose(data.loc['2023-01-05':, 'Level'], feet['Level'].values, rtol=1e-3)

    def test_process_files_needs_files(self, app, dialogs):
        assert app.view_manager.many_files_view.process_files() is None
        assert dialogs.warnings() == ['Select files first.']

    def test_state_round_trip(self, app):
        view = app.view_manager.many_files_view
        assert view.get_state() == {'fix_units': False, 'target': 'well'}
        view.set_state({'fix_units': True, 'target': 'baro'})
        assert view.get_state() == {'fix_units': True, 'target': 'baro'}
        view.set_state({'target': 'bogus'})
        assert view.get_state() == {'fix_units': False, 'target': 'baro'}

    def test_file_types_offered(self, app):
        assert list(app.view_manager.many_files_view.filetype['values']) == list(FILE_TYPES)


# --- ChartManager --- #

class TestChartManager:
    def test_draw(self, app, well_df):
        charts = app.chart_manager
        charts.draw('well', well_df, 'Level')
        assert charts.last == ('well', well_df, 'Level', None)
        assert charts.ax.get_title() == 'well'
        figure = charts.plotly_widget.current_fig
        assert figure is not None
        np.testing.assert_allclose(figure.data[0].y, well_df['Level'])

    def test_draw_table_without_chart_skips_plotly(self, app):
        charts = app.chart_manager
        charts.draw('drift-info', pd.DataFrame({'drift': [0.1]}))
        assert charts.plotly_widget.current_fig is None
        assert not charts.ax.axison

    @pytest.mark.parametrize('option, check', [
        ('flip_y', lambda ax: ax.get_ylim()[0] > ax.get_ylim()[1]),
        ('legend', lambda ax: ax.get_legend() is None),
        ('grid', lambda ax: not any(l.get_visible() for l in ax.get_xgridlines())),
    ])
    def test_refresh_applies_options(self, app, well_df, option, check):
        charts = app.chart_manager
        charts.draw('well', well_df)
        var = getattr(charts, option)
        var.set(not var.get())
        charts.refresh()
        assert check(charts.ax)

    def test_refresh_without_chart(self, app):
        app.chart_manager.refresh()
        assert app.chart_manager.last is None

    def test_clear(self, app, well_df):
        charts = app.chart_manager
        charts.draw('well', well_df)
        charts.clear()
        assert charts.last is None
        assert len(charts.ax.lines) == 0
        assert len(charts.fig.axes) == 1

    def test_toolbar_and_canvas_are_packed(self, app):
        charts = app.chart_manager
        assert charts.canvas.get_tk_widget().winfo_manager() == 'pack'
        assert find_widget(charts.matplotlib_frame, type(charts.toolbar)) is charts.toolbar

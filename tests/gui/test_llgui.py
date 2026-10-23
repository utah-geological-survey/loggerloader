"""Tests for loggerloader.llgui: the main window and the actions behind its menus"""
import json
import re
import zipfile

import matplotlib
import numpy as np
import pandas as pd
import pytest

from loggerloader.llgui import DataModel, LoggerLoaderApp, PROJECT_TYPES
from loggerloader.project import EXTENSION

from .conftest import click, destroy, start_tk, time_series, toplevels


def pdf_pages(path):
    return len(re.findall(rb'/Type\s*/Page[^s]', path.read_bytes()))


class TestDataModel:
    def test_store_get_clear(self):
        model = DataModel()
        assert model.get_data() is None
        df = pd.DataFrame({'a': [1]})
        model.store_data(df)
        assert model.get_data() is df
        model.clear_data()
        assert model.get_data() is None
        model.clear_data()

    def test_starts_empty(self):
        model = DataModel()
        assert model.well_data is None and model.baro_data is None
        assert model.datatable == {} and model.bcombo == {} and model.beg_end == {}


class TestStartup:
    def test_window(self, app):
        assert app.root.title() == 'Logger Loader'
        assert app.well_view is app.view_manager.single_well_view
        assert app.chart_manager is app.well_view.chart_manager
        assert app.root['menu'] == str(app.menu.menu)
        assert app.project_path is None

    def test_import_callback_feeds_recent_files(self, app):
        app.well_view.controller.on_file_imported('x.csv')
        assert app.menu.recent_files == ['x.csv']

    def test_config_written_to_home(self, app, home):
        assert (home / 'AppData' / 'Local' / 'LoggerLoader' / 'config.json').exists() or \
            any(home.rglob('config.json'))

    def test_saved_theme_is_applied(self, home, dialogs, modal_driver, browser, fast_plotly):
        (home / '.loggerloader').mkdir()
        (home / '.loggerloader' / 'settings.json').write_text(json.dumps({'theme': 'dark'}))
        app = start_tk(LoggerLoaderApp)
        try:
            assert app.view_manager.style.theme_use() == 'forest-dark'
            assert app.menu.theme_var.get() == 'dark'
        finally:
            destroy(app.root)
            matplotlib.style.use('default')

    def test_set_theme_is_saved(self, app, home):
        app.set_theme('dark')
        assert app.view_manager.sheettheme == 'dark green'
        settings = json.loads((home / '.loggerloader' / 'settings.json').read_text())
        assert settings['theme'] == 'dark'

    def test_refresh_chart(self, loaded):
        loaded.chart_manager.grid.set(False)
        loaded.refresh_chart()
        assert not any(l.get_visible() for l in loaded.chart_manager.ax.get_xgridlines())

    def test_update_title(self, app, tmp_path):
        app.update_title()
        assert app.root.title() == 'Logger Loader - untitled'
        app.project_path = tmp_path / 'site.llproj'
        app.update_title()
        assert app.root.title() == 'Logger Loader - site.llproj'

    def test_project_types(self):
        assert PROJECT_TYPES[0] == ('Logger Loader project', f'*{EXTENSION}')


class TestCurrentTable:
    def test_needs_a_table(self, app, dialogs):
        assert app.current_table() == (None, None, None)
        assert dialogs.warnings() == ['Import data or select a table tab first.']

    def test_needs_a_numeric_field(self, loaded, dialogs):
        loaded.well_view.field = 'filename'
        assert loaded.current_table() == (None, None, None)
        assert dialogs.warnings() == ['Click a numeric column header in the table first.']

    def test_needs_a_time_series(self, app, dialogs):
        app.well_view.set_table('t', pd.DataFrame({'a': [1.0, 2.0]}))
        assert app.current_table() == (None, None, None)
        assert dialogs.warnings() == ['t is not a time series.']

    def test_without_field(self, app, dialogs):
        app.well_view.set_table('t', pd.DataFrame({'a': ['x']}))
        key, df, field = app.current_table(need_field=False)
        assert key == 't' and field is None
        dialogs.assert_quiet()

    def test_selected_table(self, loaded):
        key, df, field = loaded.current_table()
        assert (key, field) == ('baro', 'Level')
        assert df is loaded.well_view.data['baro']


class TestImportMenu:
    @pytest.mark.parametrize('kind', ['well', 'baro'])
    def test_well_and_baro(self, app, monkeypatch, kind):
        calls = []
        monkeypatch.setattr(app.well_view.workflow, 'choose_file', lambda k: calls.append(k))
        app.import_data(kind)
        assert calls == [kind]

    def test_manual(self, app, monkeypatch):
        calls = []
        monkeypatch.setattr(app.well_view.workflow, 'load_manual_file', lambda: calls.append('manual'))
        app.import_data('manual')
        assert calls == ['manual']

    def test_unknown_kind(self, app, dialogs):
        app.import_data('other')
        assert dialogs.calls == []


class TestExport:
    def test_nothing_to_export(self, app, dialogs):
        app.export_data()
        assert dialogs.warnings() == ['There is no data to export.']
        assert not dialogs.called('asksaveasfilename')

    def test_cancelled(self, loaded, dialogs, tmp_path):
        loaded.export_data()
        assert dialogs.called('asksaveasfilename')
        assert [p.name for p in tmp_path.iterdir()] == ['home']

    def test_every_table_to_excel(self, loaded, dialogs, tmp_path):
        long_name = 'a-table-with-a-very-long-name-indeed'
        loaded.well_view.set_table(long_name, time_series(periods=3), select=False)
        path = tmp_path / 'out.xlsx'
        dialogs.answer('asksaveasfilename', str(path))
        loaded.export_data()
        sheets = pd.read_excel(path, sheet_name=None, index_col=0)
        assert list(sheets) == ['well', 'baro', long_name[:31]]
        np.testing.assert_allclose(sheets['well']['Level'], loaded.well_view.data['well']['Level'])

    def test_selected_table_to_csv(self, loaded, dialogs, tmp_path):
        path = tmp_path / 'out.csv'
        dialogs.answer('asksaveasfilename', str(path))
        loaded.export_data()
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        np.testing.assert_allclose(df['Level'], loaded.well_view.data['baro']['Level'])

    def test_csv_needs_selected_table(self, loaded, dialogs, tmp_path):
        loaded.well_view.selected_tab = None
        dialogs.answer('asksaveasfilename', str(tmp_path / 'out.csv'))
        loaded.export_data()
        assert dialogs.warnings() == ['Select a table tab to export as csv.']
        assert not (tmp_path / 'out.csv').exists()

    def test_write_error_is_shown(self, loaded, dialogs, tmp_path):
        dialogs.answer('asksaveasfilename', str(tmp_path / 'no-such-dir' / 'out.csv'))
        loaded.export_data()
        assert dialogs.errors()

    def test_no_chart_to_export(self, app, dialogs):
        app.export_charts()
        assert dialogs.warnings() == ['There is no chart to export.']

    @pytest.mark.parametrize('name, magic', [('chart.png', b'\x89PNG'), ('chart.pdf', b'%PDF'),
                                             ('chart.svg', b'<?xml')])
    def test_export_chart(self, loaded, dialogs, tmp_path, name, magic):
        path = tmp_path / name
        dialogs.answer('asksaveasfilename', str(path))
        loaded.export_charts()
        assert path.read_bytes().startswith(magic)

    def test_export_chart_cancelled(self, loaded, dialogs, tmp_path):
        loaded.export_charts()
        assert list(tmp_path.glob('chart.*')) == []


class TestReport:
    def test_nothing_to_report(self, app, dialogs):
        app.generate_report()
        assert dialogs.warnings() == ['There is no data to report.']

    def test_report_has_summary_and_a_page_per_table(self, processed, dialogs, tmp_path):
        path = tmp_path / 'report.pdf'
        dialogs.answer('asksaveasfilename', str(path))
        processed.generate_report()
        dialogs.assert_quiet()
        # summary + well, baro, well-baro, manual, drift-info, fixed-drift, wl-elev
        assert pdf_pages(path) == 1 + 7

    def test_tables_without_charts_are_skipped(self, loaded, tmp_path):
        loaded.well_view.set_table('notes', pd.DataFrame({'a': ['x']}), select=False)
        path = loaded.write_report(tmp_path / 'r.pdf')
        assert pdf_pages(path) == 1 + 2

    def test_report_cancelled(self, loaded, dialogs, tmp_path):
        loaded.generate_report()
        assert list(tmp_path.glob('*.pdf')) == []


class TestProjects:
    def test_save_as_and_open_round_trip(self, processed, dialogs, tmp_path):
        app = processed
        view = app.well_view
        view.workflow._set_entry(view.workflow.ground_elev, '5000')
        view.field = 'DTW_WL'
        view.set_table('fixed-drift', view.data['fixed-drift'])
        app.chart_manager.flip_y.set(True)
        app.view_manager.many_files_view.target.set('baro')
        saved = {k: df.copy() for k, df in view.data.items()}

        path = tmp_path / 'site.llproj'
        dialogs.answer('asksaveasfilename', str(path))
        assert app.save_project_as() == str(path)
        assert zipfile.is_zipfile(path)
        assert app.project_path == str(path)
        assert app.root.title() == 'Logger Loader - site.llproj'
        assert app.menu.recent_files[0] == str(path)

        # change everything, then open the project again
        view.clear_tables()
        view.workflow._set_entry(view.workflow.ground_elev, '')
        app.chart_manager.flip_y.set(False)
        app.view_manager.many_files_view.target.set('well')
        assert app.open_project(str(path))

        dialogs.assert_quiet()
        assert list(view.data) == list(saved)
        for key, df in saved.items():
            # drift-info holds Timestamps in object columns; the project restores them as datetimes
            pd.testing.assert_frame_equal(view.data[key], df, check_freq=False,
                                          check_dtype=key != 'drift-info')
        assert view.selected_tab == 'fixed-drift' and view.field == 'DTW_WL'
        assert view.workflow.ground_elev.get() == '5000'
        assert app.chart_manager.flip_y.get() is True
        assert app.view_manager.many_files_view.target.get() == 'baro'
        assert app.chart_manager.last[0] == 'fixed-drift'

    def test_manual_input_table_is_saved(self, loaded, dialogs, tmp_path):
        manual = tmp_path / 'm.csv'
        pd.DataFrame({'date': ['2023-01-01'], 'dtw': [1.0], 'locationid': ['a']}).to_csv(manual, index=False)
        loaded.well_view.workflow.load_manual_file(str(manual))
        path = tmp_path / 'p.llproj'
        loaded.write_project(path)
        loaded.well_view.workflow.manual_table = None
        loaded.open_project(str(path))
        table = loaded.well_view.workflow.manual_table
        assert list(table.columns) == ['date', 'dtw', 'locationid']
        assert loaded.well_view.workflow.man_cols['DTW'].get() == 'dtw'

    def test_save_uses_existing_path(self, loaded, dialogs, tmp_path):
        path = tmp_path / 'p.llproj'
        loaded.project_path = str(path)
        assert loaded.save_project() == str(path)
        assert path.exists()
        assert not dialogs.called('asksaveasfilename')

    def test_save_without_path_asks(self, loaded, dialogs):
        assert loaded.save_project() is None
        assert dialogs.called('asksaveasfilename')
        assert loaded.project_path is None

    def test_failed_save_keeps_old_path(self, loaded, dialogs, tmp_path):
        assert loaded.write_project(tmp_path / 'missing-dir' / 'p.llproj') is None
        assert dialogs.errors()
        assert loaded.project_path is None

    def test_open_cancelled(self, loaded, dialogs):
        assert loaded.open_project() is False
        assert dialogs.called('askopenfilename')
        assert 'well' in loaded.well_view.data

    def test_open_bad_file(self, loaded, dialogs, tmp_path):
        path = tmp_path / 'bad.llproj'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('other.txt', 'x')
        assert loaded.open_project(str(path)) is False
        assert dialogs.warnings() == ['bad.llproj is not a Logger Loader project.']
        assert 'well' in loaded.well_view.data  # nothing was cleared

    def test_open_selects_first_table_if_saved_tab_is_gone(self, loaded, tmp_path, monkeypatch):
        path = tmp_path / 'p.llproj'
        loaded.well_view.selected_tab = 'gone'
        loaded.write_project(path)
        loaded.open_project(str(path))
        assert loaded.well_view.selected_tab == 'well'

    def test_open_empty_project(self, app, tmp_path):
        path = tmp_path / 'empty.llproj'
        app.write_project(path)
        assert app.open_project(str(path))
        assert app.well_view.data == {}


class TestOpenRecent:
    def test_missing_file_is_removed(self, app, dialogs, tmp_path):
        missing = str(tmp_path / 'gone.csv')
        app.menu.add_recent_file(missing)
        assert app.open_recent(missing) is False
        assert dialogs.warnings() == [f'{missing} no longer exists.']
        assert app.menu.recent_files == []

    def test_project(self, loaded, tmp_path):
        path = tmp_path / 'p.llproj'
        loaded.write_project(path)
        loaded.well_view.clear_tables()
        assert loaded.open_recent(str(path))
        assert 'well' in loaded.well_view.data

    @pytest.mark.parametrize('button, kind', [('Well data', 'well'), ('Barometric data', 'baro')])
    def test_data_file_asks_its_kind(self, app, modal_driver, monkeypatch, tmp_path, button, kind):
        path = tmp_path / 'f.csv'
        path.write_text('x')
        calls = []
        monkeypatch.setattr(app.well_view.workflow, 'choose_file',
                            lambda k, files: calls.append((k, files)) or True)
        modal_driver.push(lambda window: click(window, button))
        assert app.open_recent(str(path))
        assert calls == [(kind, [str(path)])]

    def test_manual_file(self, app, modal_driver, tmp_path):
        path = tmp_path / 'm.csv'
        pd.DataFrame({'date': ['2023-01-01'], 'dtw': [1.0], 'locationid': [7]}).to_csv(path, index=False)
        modal_driver.push(lambda window: click(window, 'Manual measurements'))
        assert app.open_recent(str(path))
        assert app.well_view.workflow.manual_table is not None

    def test_cancel(self, app, modal_driver, tmp_path):
        path = tmp_path / 'f.csv'
        path.write_text('x')
        modal_driver.push(lambda window: click(window, 'Cancel'))
        assert app.open_recent(str(path)) is False

    def test_closing_the_question_is_cancel(self, app, modal_driver, tmp_path):
        path = tmp_path / 'f.csv'
        path.write_text('x')
        titles = []
        modal_driver.push(lambda window: titles.append(window.title()))
        assert app.ask_import_kind(str(path)) is None
        assert titles == ['Open Recent File']


class TestCleanData:
    @pytest.fixture
    def spiky(self, app):
        df = time_series(periods=48, wave=0.0, trend=0.01)
        df.iloc[20, 0] += 5.0
        app.well_view.set_table('well', df)
        return df

    def test_needs_a_table(self, app, dialogs):
        app.clean_data('smooth')
        assert dialogs.warnings() == ['Import data or select a table tab first.']

    def test_remove_outliers(self, app, spiky, dialogs):
        dialogs.answer('askfloat', 1.0)
        app.clean_data('outliers')
        df = app.well_view.data['well']
        assert len(df) == len(spiky) - 1
        assert spiky.index[20] not in df.index
        assert dialogs.messages('showinfo') == [f'Removed 1 of {len(spiky)} rows.']

    @pytest.mark.parametrize('field, expected', [('Level', 0.5), ('Temperature', 1.0)])
    def test_outlier_default_threshold(self, app, spiky, dialogs, field, expected):
        app.well_view.field = field
        app.clean_data('outliers')
        (args, kwargs), = dialogs.called('askfloat')
        assert kwargs['initialvalue'] == expected

    def test_outlier_default_threshold_from_settings(self, app, dialogs):
        df = time_series(periods=48).rename(columns={'Level': 'Pressure'})
        app.well_view.set_table('well', df)
        app.clean_data('outliers')
        (args, kwargs), = dialogs.called('askfloat')
        expected = round(app.config.processing.outlier_threshold * df['Pressure'].diff().std(), 4)
        assert kwargs['initialvalue'] == expected

    def test_remove_outliers_cancelled(self, app, spiky, dialogs):
        app.clean_data('outliers')
        assert len(app.well_view.data['well']) == len(spiky)

    def test_fix_gaps(self, app, dialogs):
        full = time_series(periods=12)
        df = full.drop(full.index[[3, 8]])
        app.well_view.set_table('well', df)
        dialogs.answer('askyesno', True)
        app.clean_data('gaps')
        filled = app.well_view.data['well']
        assert list(filled.index) == list(full.index)
        assert filled['Level'].iloc[3] == pytest.approx((df['Level'].iloc[2] + df['Level'].iloc[3]) / 2)
        assert dialogs.messages('showinfo') == ['well now has 12 rows (was 10).']
        assert 'every 60 minutes' in dialogs.messages('askyesno')[0]

    def test_fix_gaps_declined(self, app, spiky, dialogs):
        dialogs.answer('askyesno', False)
        app.clean_data('gaps')
        assert app.well_view.data['well'] is spiky

    def test_smooth(self, app, spiky):
        app.clean_data('smooth')
        df = app.well_view.data['well']
        assert 'Level_smooth' in df.columns
        assert abs(df['Level_smooth'].iloc[20] - spiky['Level'].iloc[20]) > 4  # the spike is gone
        pd.testing.assert_series_equal(df['Level'], spiky['Level'])

    def test_trim(self, app, spiky, dialogs):
        dialogs.answer('askfloat', 100.0, 101.0)
        app.clean_data('trim')
        df = app.well_view.data['well']
        assert df['Level'].between(100.0, 101.0).all()
        assert len(df) == len(spiky) - 1

    @pytest.mark.parametrize('answers', [(), (100.0,)])
    def test_trim_cancelled(self, app, spiky, dialogs, answers):
        dialogs.answer('askfloat', *answers)
        app.clean_data('trim')
        assert app.well_view.data['well'] is spiky

    def test_units_opens_converter(self, app, spiky):
        app.clean_data('units')
        assert [w.title() for w in toplevels(app.root)] == ['Convert Units']


class TestFillGaps:
    def test_interpolates_short_gaps(self):
        index = pd.to_datetime(['2023-01-01 00:00', '2023-01-01 02:00', '2023-01-01 03:00'])
        df = pd.DataFrame({'Level': [0.0, 2.0, 3.0], 'name': ['a', 'b', 'c']}, index=index)
        filled = LoggerLoaderApp.fill_gaps(df, 60, 90)
        assert filled['Level'].tolist() == [0.0, 1.0, 2.0, 3.0]
        assert list(filled.columns) == ['Level', 'name']
        assert filled['name'].tolist() == ['a', 'a', 'b', 'c']

    @pytest.mark.xfail(strict=True, reason="fill_gaps uses interpolate(limit=...), which fills the "
                                           "first readings of a gap longer than the limit instead "
                                           "of leaving the whole gap empty")
    def test_leaves_long_gaps_empty(self):
        index = pd.to_datetime(['2023-01-01 00:00', '2023-01-01 02:00', '2023-01-01 06:00'])
        df = pd.DataFrame({'Level': [0.0, 2.0, 6.0]}, index=index)
        filled = LoggerLoaderApp.fill_gaps(df, 60, 90)
        # the 4-hour gap is longer than the 90 minute limit, so nothing in it is invented
        assert filled['Level'].tolist() == [0.0, 1.0, 2.0, 6.0]

    def test_resamples_to_interval(self):
        df = time_series(periods=8, freq='15min')
        filled = LoggerLoaderApp.fill_gaps(df, 30, 60)
        assert len(filled) == 4
        assert filled['Level'].iloc[0] == pytest.approx(df['Level'].iloc[:2].mean())


class TestAnalyze:
    def test_jump_fix(self, app, dialogs):
        df = time_series(periods=20, wave=0.0)
        df.iloc[10:, 0] += 5.0
        app.well_view.set_table('well', df)
        dialogs.answer('askfloat', 1.0)
        app.analyze('jump')
        fixed = app.well_view.data['well']
        assert fixed['Level'].max() - fixed['Level'].min() < 1.0
        assert 'delta' not in fixed.columns
        (args, kwargs), = dialogs.called('askfloat')
        assert kwargs['initialvalue'] == round(df['Level'].diff().abs().std() * 5, 4)

    def test_jump_fix_cancelled(self, loaded, dialogs):
        before = loaded.well_view.data['baro']
        loaded.analyze('jump')
        assert loaded.well_view.data['baro'] is before

    def test_basic_statistics(self, loaded):
        loaded.analyze('basic')
        window, = toplevels(loaded.root)
        assert window.title() == 'Statistics - baro'

    def test_statistics_need_numbers(self, app, dialogs):
        app.show_statistics('t', pd.DataFrame({'a': ['x']}))
        assert dialogs.warnings() == ['t has no numeric columns.']
        assert toplevels(app.root) == []

    def test_statistics_of_untimed_table(self, app):
        app.show_statistics('t', pd.DataFrame({'a': [1.0, 2.0]}))
        assert len(toplevels(app.root)) == 1

    def test_trend(self, app, dialogs):
        app.well_view.set_table('well', time_series(periods=49, wave=0.0, trend=0.005))
        app.analyze('trend')
        message, = dialogs.messages('showinfo')
        assert 'Linear trend: 0.12000 per day (43.830 per year)' in message
        assert 'R squared: 1.000' in message
        assert 'Net change: 0.240' in message
        assert '2023-01-01 to 2023-01-03 (2.0 days)' in message

    def test_trend_needs_two_values(self, app, dialogs):
        df = time_series(periods=3)
        df['Level'] = [np.nan, 1.0, np.nan]
        app.well_view.set_table('well', df)
        app.analyze('trend')
        assert dialogs.warnings() == ['Level needs at least two values.']

    def test_trend_of_flat_line(self, app, dialogs):
        app.well_view.set_table('well', time_series(periods=5, wave=0.0))
        app.analyze('trend')
        assert 'R squared: nan' in dialogs.messages('showinfo')[0]

    def test_custom_column(self, loaded, dialogs):
        dialogs.answer('askstring', 'Level_m = Level * 0.3048')
        loaded.analyze('custom')
        df = loaded.well_view.data['baro']
        np.testing.assert_allclose(df['Level_m'], df['Level'] * 0.3048)

    def test_custom_scalar(self, loaded, dialogs):
        dialogs.answer('askstring', 'Level.max() - Level.min()')
        loaded.analyze('custom')
        baro = loaded.well_view.data['baro']['Level']
        assert dialogs.messages('showinfo') == [f'Level.max() - Level.min()\n= {baro.max() - baro.min()}']

    def test_custom_works_on_any_table(self, app, dialogs):
        app.well_view.set_table('t', pd.DataFrame({'a': [1.0, 2.0]}))
        dialogs.answer('askstring', 'b = a * 2')
        app.analyze('custom')
        assert app.well_view.data['t']['b'].tolist() == [2.0, 4.0]

    def test_custom_bad_expression(self, loaded, dialogs):
        dialogs.answer('askstring', 'nope +')
        loaded.analyze('custom')
        assert dialogs.errors() or dialogs.warnings()
        assert list(loaded.well_view.data['baro'].columns) == ['Level', 'Temperature']

    def test_custom_cancelled(self, loaded, dialogs):
        loaded.analyze('custom')
        assert dialogs.messages('showinfo') == []

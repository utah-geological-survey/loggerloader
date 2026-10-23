"""Tests for loggerloader.workflow: the numbered single-well steps and their dialogs"""
import datetime
from tkinter import ttk

import numpy as np
import pandas as pd
import pytest

from loggerloader.workflow import (ColumnMatchDialog, FILE_TYPES, SingleWellWorkflow, guess_column,
                                   normalize_id, read_table, run_step, unit_converter_popup)

from .conftest import click, descendants, time_series, toplevels
from .test_views import MATCH_COLUMNS, accept, generic_csv


# --- helpers --- #

class TestReadTable:
    def test_csv(self, tmp_path):
        path = tmp_path / 't.csv'
        pd.DataFrame({'a': [1, 2]}).to_csv(path, index=False)
        assert read_table(path)['a'].tolist() == [1, 2]

    def test_excel_sheets(self, tmp_path):
        path = tmp_path / 't.xlsx'
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame({'a': [1]}).to_excel(writer, sheet_name='first', index=False)
            pd.DataFrame({'b': [2]}).to_excel(writer, sheet_name='second', index=False)
        assert list(read_table(path).columns) == ['a']
        assert list(read_table(path, 'second').columns) == ['b']


@pytest.mark.parametrize('value, expected', [
    (71, '71'), (71.0, '71'), ('71', '71'), (' 71 ', '71'), (71.5, '71.5'),
    ('PW-01 ', 'PW-01'), (np.nan, ''), (None, ''),
])
def test_normalize_id(value, expected):
    assert normalize_id(value) == expected


@pytest.mark.parametrize('columns, expected', [
    (['Foo', ' DateTime '], ' DateTime '),
    (['a', 'b'], ''),
    (['Date', 'datetime'], 'Date'),  # the first match wins
])
def test_guess_column(columns, expected):
    assert guess_column(columns, ['datetime', 'date']) == expected


class TestRunStep:
    def test_returns_result(self, dialogs):
        assert run_step(lambda a, b=0: a + b, 1, b=2) == 3
        dialogs.assert_quiet()

    def test_value_error_is_a_warning(self, dialogs):
        def step():
            raise ValueError('choose a column')
        assert run_step(step) is None
        assert dialogs.warnings() == ['choose a column']

    def test_other_errors_are_errors(self, dialogs):
        def step():
            raise KeyError('x')
        assert run_step(step) is None
        assert dialogs.errors() == ["KeyError: 'x'"]


# --- ColumnMatchDialog --- #

class TestColumnMatch:
    @pytest.fixture
    def table(self):
        return pd.DataFrame({
            'when': ['2023-01-02', '2023-01-01', 'bad', '2023-01-03'],
            'value': ['1.5', '2.5', '3', None],
            'temp': [10, 11, 12, 13],
            'ec': [100, 200, 300, 400],
        })

    def test_match(self, table):
        df = ColumnMatchDialog.match(table, 'when', 'value', 'temp', 'ec')
        assert list(df.columns) == ['Level', 'Temperature', 'Cond']
        assert df.index.name == 'DateTime'
        assert df['Level'].tolist() == [2.5, 1.5]  # sorted; bad date and missing value dropped

    def test_match_without_optional_columns(self, table):
        df = ColumnMatchDialog.match(table, 'when', 'value')
        assert list(df.columns) == ['Level']

    @pytest.mark.parametrize('date, value', [('', 'value'), ('when', ''), ('nope', 'value')])
    def test_match_needs_date_and_value(self, table, date, value):
        with pytest.raises(ValueError, match='Choose the datetime and value'):
            ColumnMatchDialog.match(table, date, value)

    def test_match_with_no_valid_rows(self, table):
        table['value'] = 'x'
        with pytest.raises(ValueError, match='No rows'):
            ColumnMatchDialog.match(table, 'when', 'value')

    def combos(self, window):
        return [w for w in descendants(window) if isinstance(w, ttk.Combobox)]

    def test_dialog_guesses_columns(self, root, modal_driver, tmp_path, well_df):
        path = generic_csv(well_df, tmp_path / 'w.csv')
        seen = {}
        def check(window):
            seen['values'] = [c.get() for c in self.combos(window)]
            accept(window)
        modal_driver.push(check)
        dialog = ColumnMatchDialog(root, path)
        assert seen['values'] == ['datetime', 'level', 'temperature', '']
        assert list(dialog.result.columns) == ['Level', 'Temperature']
        assert len(dialog.result) == len(well_df)

    def test_dialog_cancel(self, root, modal_driver, tmp_path, well_df):
        modal_driver.push(lambda window: click(window, 'Cancel'))
        assert ColumnMatchDialog(root, generic_csv(well_df, tmp_path / 'w.csv')).result is None

    def test_dialog_warns_and_stays_open_on_bad_columns(self, root, modal_driver, dialogs, tmp_path, well_df):
        path = tmp_path / 'w.csv'
        well_df.reset_index().rename(columns={'DateTime': 'stamp'}).to_csv(path, index=False)
        state = {}
        def check(window):
            accept(window)  # no datetime column guessed
            state['open'] = window.winfo_exists()
        modal_driver.push(check)
        assert ColumnMatchDialog(root, path).result is None
        assert state['open']
        assert dialogs.warnings() == ['Choose the datetime and value columns.']

    def test_dialog_excel_sheet_choice(self, root, modal_driver, tmp_path, well_df):
        path = tmp_path / 'w.xlsx'
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame({'x': [1]}).to_excel(writer, sheet_name='notes', index=False)
            well_df.reset_index().to_excel(writer, sheet_name='data', index=False)
        def pick_second_sheet(window):
            sheet, date, value = self.combos(window)[:3]
            assert list(sheet['values']) == ['notes', 'data']
            assert date.get() == ''
            sheet.set('data')
            sheet.event_generate('<<ComboboxSelected>>')
            assert date.get() == 'DateTime' and value.get() == 'Level'
            accept(window)
        modal_driver.push(pick_second_sheet)
        dialog = ColumnMatchDialog(root, path)
        assert len(dialog.result) == len(well_df)


# --- unit converter --- #

class TestUnitConverter:
    @pytest.fixture
    def popup(self, loaded):
        return unit_converter_popup(loaded.well_view, 'well', 'Temperature')

    def boxes(self, popup):
        return [w for w in descendants(popup) if isinstance(w, ttk.Combobox)]

    def test_temperature_conversion(self, loaded, popup):
        in_units, out_units, out_field = self.boxes(popup)
        in_units.set('C')
        in_units.event_generate('<<ComboboxSelected>>')
        assert list(out_units['values']) == ['C', 'F']
        assert out_units.get() == 'F'
        assert out_field.get() == 'Temperature_F'
        click(popup, 'Convert')
        df = loaded.well_view.data['well']
        np.testing.assert_allclose(df['Temperature_F'], df['Temperature'] * 1.8 + 32)
        assert not popup.winfo_exists()

    def test_pressure_conversion(self, loaded, popup):
        in_units, out_units, out_field = self.boxes(popup)
        in_units.set('C')
        in_units.event_generate('<<ComboboxSelected>>')
        in_units.set('psi')
        in_units.event_generate('<<ComboboxSelected>>')
        assert list(out_units['values']) == ['psi', 'mmHg', 'ft', 'bar']
        assert out_units.get() == 'ft'
        click(popup, 'Convert')
        assert 'Temperature_ft' in loaded.well_view.data['well']

    def test_needs_units(self, loaded, popup, dialogs):
        click(popup, 'Convert')
        assert dialogs.warnings() == ['Choose the units and a column name.']
        assert popup.winfo_exists()

    def test_unsupported_conversion_keeps_popup(self, loaded, popup, dialogs):
        in_units, out_units, out_field = self.boxes(popup)
        in_units.set('ft')
        out_units.set('ft')
        out_field.set('x')
        out_units['values'] = ['kPa']
        out_units.set('kPa')
        click(popup, 'Convert')
        assert dialogs.warnings() == ["Can't convert ft to kPa."]
        assert popup.winfo_exists()


# --- SingleWellWorkflow --- #

def tab_text(notebook):
    return notebook.tab(notebook.select(), 'text')


class TestWorkflowState:
    def test_default_state(self, app):
        state = app.well_view.workflow.get_state()
        assert state['step'] == 0
        assert state['filetype'] == {'well': list(FILE_TYPES)[0], 'baro': list(FILE_TYPES)[0]}
        assert state['file_status'] == {'well': 'No file loaded', 'baro': 'No file loaded'}
        assert (state['well_field'], state['baro_field'], state['freq']) == ('Level', 'Level', '60')
        assert state['vented'] is False
        assert state['manual_units'] == 'ft' and state['stickup'] == '0'
        assert len(state['manual_entry']) == 2

    def test_round_trip(self, app):
        workflow = app.well_view.workflow
        table = pd.DataFrame({'when': [], 'dtw': [], 'site': []})
        state = {
            'step': 3,
            'filetype': {'well': 'Troll csv', 'baro': MATCH_COLUMNS},
            'file_status': {'well': 'a.xle', 'baro': 'b.xle'},
            'well_field': 'Level', 'baro_field': 'Level', 'freq': '15', 'vented': True,
            'manual_mode': 1,
            'manual_entry': [{'date': '2023-04-05', 'hour': '07', 'minute': '30', 'measure': '12.5'},
                             {'date': '2023-05-06', 'hour': '23', 'minute': '59', 'measure': '13'}],
            'manual_locid': '42',
            'manual_columns': {'Datetime': 'when', 'DTW': 'dtw', 'Location id': 'site', 'Pick id': '7'},
            'manual_file_status': 'm.csv (0 rows)',
            'manual_units': 'm',
            'max_drift': '0.100 ft',
            'ground_elev': '5000', 'ground_units': 'm',
            'stickup': '1.5', 'stickup_units': 'm',
        }
        workflow.set_state(state, manual_table=table)
        assert workflow.get_state() == state
        assert workflow.manual_table is table
        assert list(workflow.man_cols['DTW']['values']) == ['when', 'dtw', 'site']
        assert tab_text(workflow.steps) == '5 Drift'

    def test_missing_keys_keep_current_values(self, app):
        workflow = app.well_view.workflow
        before = workflow.get_state()
        workflow.set_state({})
        assert workflow.get_state() == before

    def test_bad_values_are_ignored(self, app):
        workflow = app.well_view.workflow
        workflow.set_state({'filetype': {'well': 'bogus', 'nope': 'Troll csv'},
                            'manual_entry': [{'date': 'not a date'}]})
        state = workflow.get_state()
        assert state['filetype']['well'] == list(FILE_TYPES)[0]
        assert state['manual_entry'][0]['date'] == datetime.date.today().isoformat()


class TestImportStep:
    def test_choose_file(self, app, modal_driver, tmp_path, well_df, baro_df):
        workflow = app.well_view.workflow
        workflow.filetype['well'].set(MATCH_COLUMNS)
        workflow.filetype['baro'].set(MATCH_COLUMNS)
        modal_driver.push(accept)
        assert workflow.choose_file('well', [str(generic_csv(well_df, tmp_path / 'w1.csv'))])
        assert workflow.file_status['well'].get() == 'w1.csv'
        assert tab_text(workflow.steps) == '1-2 Import'
        modal_driver.push(accept)
        assert workflow.choose_file('baro', [str(generic_csv(baro_df, tmp_path / 'b1.csv'))])
        assert workflow.file_status['baro'].get() == 'b1.csv'
        assert tab_text(workflow.steps) == '3 Align'

    def test_choose_file_cancelled(self, app, dialogs):
        dialogs.answer('askopenfilenames', ())
        assert not app.well_view.workflow.choose_file('well')
        assert app.well_view.workflow.file_status['well'].get() == 'No file loaded'

    def test_refresh_fields(self, app, well_df):
        workflow = app.well_view.workflow
        app.well_view.data['baro'] = well_df.rename(columns={'Level': 'Pressure'})
        workflow.refresh_fields()
        assert list(workflow.baro_field['values']) == ['Pressure', 'Temperature']
        assert workflow.baro_field.get() == 'Pressure'
        assert workflow.well_field.get() == 'Level'  # no well data yet


class TestAlignStep:
    def test_align(self, loaded, dialogs):
        workflow = loaded.well_view.workflow
        workflow.freq.set('30')
        workflow.align()
        dialogs.assert_quiet()
        assert 'well-baro' in loaded.well_view.data
        assert tab_text(workflow.steps) == '4 Manual'

    def test_freq_must_be_whole_minutes(self, loaded, dialogs):
        workflow = loaded.well_view.workflow
        workflow.freq.set('1.5')
        workflow.align()
        assert dialogs.warnings() == ['Data frequency must be a whole number of minutes.']
        assert 'well-baro' not in loaded.well_view.data

    def test_align_errors_are_shown(self, app, dialogs):
        app.well_view.workflow.align()
        assert dialogs.warnings() == ['Import well data first (step 1).']
        assert tab_text(app.well_view.workflow.steps) == '1-2 Import'


class TestManualStep:
    def enter(self, workflow, readings):
        for i, (date, hour, minute, measure) in enumerate(readings):
            workflow.man_date[i].set_date(date)
            workflow.man_hour[i].set(hour)
            workflow.man_min[i].set(minute)
            workflow._set_entry(workflow.man_meas[i], measure)

    def test_manual_entry(self, loaded):
        workflow = loaded.well_view.workflow
        self.enter(workflow, [(datetime.date(2023, 1, 1), '05', '30', '10.5'),
                              (datetime.date(2023, 1, 3), '12', '00', '11')])
        workflow._set_entry(workflow.man_locid, '42')
        workflow.process_manual()
        manual = loaded.well_view.data['manual']
        assert list(manual.index) == [pd.Timestamp('2023-01-01 05:30'), pd.Timestamp('2023-01-03 12:00')]
        assert manual['dtwbelowcasing'].tolist() == [10.5, 11.0]
        assert (manual['locationid'] == '42').all()
        assert tab_text(workflow.steps) == '5 Drift'

    def test_manual_entry_in_meters(self, loaded):
        workflow = loaded.well_view.workflow
        self.enter(workflow, [(datetime.date(2023, 1, 1), '00', '00', '1'),
                              (datetime.date(2023, 1, 2), '00', '00', '2')])
        workflow.man_units.set('m')
        workflow.process_manual()
        assert loaded.well_view.data['manual']['dtwbelowcasing'].iloc[0] == pytest.approx(3.28084)

    def test_manual_entry_needs_numbers(self, loaded, dialogs):
        workflow = loaded.well_view.workflow
        workflow.process_manual()
        assert dialogs.warnings() == ['Enter a numeric depth to water for both readings.']
        assert 'manual' not in loaded.well_view.data

    @pytest.fixture
    def manual_csv(self, tmp_path, well_df):
        path = tmp_path / 'manual.csv'
        pd.DataFrame({
            'readingdate': [well_df.index[1], well_df.index[30], well_df.index[40]],
            'dtw': [10.0, 10.5, 99.0],
            'locationid': [71, 71, 1003],
            'notes': ['a', 'b', 'c'],
        }).to_csv(path, index=False)
        return path

    def test_load_manual_file(self, loaded, manual_csv):
        workflow = loaded.well_view.workflow
        assert workflow.load_manual_file(str(manual_csv))
        cols = workflow.man_cols
        assert (cols['Datetime'].get(), cols['DTW'].get(), cols['Location id'].get()) == \
            ('readingdate', 'dtw', 'locationid')
        assert list(cols['DTW']['values']) == ['readingdate', 'dtw', 'locationid', 'notes']
        assert workflow.man_file_status.get() == 'manual.csv (3 rows)'
        assert tab_text(workflow.steps) == '4 Manual'
        assert tab_text(workflow.manbook) == 'From File'
        assert loaded.menu.recent_files[0] == str(manual_csv)

    def test_load_manual_file_cancelled(self, app, dialogs):
        dialogs.answer('askopenfilename', '')
        assert not app.well_view.workflow.load_manual_file()

    def test_load_manual_file_unreadable(self, app, dialogs, tmp_path):
        assert not app.well_view.workflow.load_manual_file(str(tmp_path / 'missing.csv'))
        assert dialogs.errors()

    def test_fill_pick_ids(self, loaded, manual_csv):
        workflow = loaded.well_view.workflow
        workflow.load_manual_file(str(manual_csv))
        workflow.fill_pick_ids()
        assert list(workflow.man_cols['Pick id']['values']) == ['71', '1003']

    def test_process_manual_file(self, loaded, manual_csv, dialogs):
        workflow = loaded.well_view.workflow
        workflow.load_manual_file(str(manual_csv))
        workflow.man_cols['Pick id'].set('71')
        workflow.process_manual()
        dialogs.assert_quiet()
        assert loaded.well_view.data['manual']['dtwbelowcasing'].tolist() == [10.0, 10.5]
        assert tab_text(workflow.steps) == '5 Drift'

    def test_process_manual_file_needs_pick_id(self, loaded, manual_csv, dialogs):
        workflow = loaded.well_view.workflow
        workflow.load_manual_file(str(manual_csv))
        workflow.process_manual()
        assert "several location ids" in dialogs.warnings()[0]

    def test_process_manual_file_needs_file(self, loaded, dialogs):
        workflow = loaded.well_view.workflow
        workflow.manbook.select(1)
        workflow.process_manual()
        assert dialogs.warnings() == ['Choose a manual measurement file first.']


class TestDriftAndElevationSteps:
    @pytest.fixture
    def manual(self, loaded, well_df):
        controller = loaded.well_view.controller
        controller.align()
        controller.manual_from_entry([(well_df.index[2], 20.0), (well_df.index[-3], 20.5)], 'ft', '42')
        return loaded

    def test_fix_drift(self, manual):
        workflow = manual.well_view.workflow
        workflow.fix_drift()
        assert workflow.max_drift.get().endswith(' ft')
        float(workflow.max_drift.get().split()[0])
        assert tab_text(workflow.steps) == '6 Elevation'

    def test_fix_drift_error(self, loaded, dialogs):
        loaded.well_view.workflow.fix_drift()
        assert dialogs.warnings() == ['Align the data first (step 3).']
        assert loaded.well_view.workflow.max_drift.get() == ''

    def test_calc_elevations(self, processed):
        workflow = processed.well_view.workflow
        workflow._set_entry(workflow.ground_elev, '4000')
        workflow._set_entry(workflow.stickup, '')
        workflow.calc_elevations()
        wl = processed.well_view.data['wl-elev']
        np.testing.assert_allclose(wl['waterelevation'], wl['DTW_WL'] + 4000.0)

    def test_calc_elevations_needs_numbers(self, processed, dialogs):
        workflow = processed.well_view.workflow
        workflow._set_entry(workflow.ground_elev, 'high')
        workflow.calc_elevations()
        assert dialogs.warnings() == ['Enter numbers for the ground elevation and stickup.']

    def test_save_one_well(self, processed, tmp_path, dialogs):
        path = tmp_path / 'one.csv'
        dialogs.answer('asksaveasfilename', str(path))
        processed.well_view.workflow.save_one_well()
        assert len(pd.read_csv(path)) == len(processed.well_view.data['wl-elev'])

    def test_save_one_well_cancelled(self, processed, dialogs, tmp_path):
        processed.well_view.workflow.save_one_well()
        assert dialogs.called('asksaveasfilename')
        assert list(tmp_path.glob('*.csv')) == []

    def test_save_one_well_needs_elevations(self, loaded, dialogs):
        loaded.well_view.workflow.save_one_well('x.csv')
        assert dialogs.warnings() == ['Calculate elevations first (step 6).']


def test_full_single_well_workflow_through_the_steps(app, modal_driver, dialogs, tmp_path, well_df, baro_df):
    """Run every step the way a user would, through the widgets"""
    workflow = app.well_view.workflow
    for kind, df in (('well', well_df), ('baro', baro_df)):
        workflow.filetype[kind].set(MATCH_COLUMNS)
        modal_driver.push(accept)
        workflow.choose_file(kind, [str(generic_csv(df, tmp_path / f'{kind}.csv'))])
    workflow.align()
    TestManualStep().enter(workflow, [(datetime.date(2023, 1, 1), '02', '00', '20'),
                                      (datetime.date(2023, 1, 3), '21', '00', '20.5')])
    workflow.process_manual()
    workflow.fix_drift()
    workflow._set_entry(workflow.ground_elev, '5000')
    workflow.calc_elevations()
    out = tmp_path / 'out.csv'
    workflow.save_one_well(str(out))
    dialogs.assert_quiet()
    assert list(app.well_view.data) == ['well', 'baro', 'well-baro', 'manual', 'drift-info',
                                        'fixed-drift', 'wl-elev']
    assert out.exists()
    assert toplevels(app.root) == []

"""Tests for loggerloader.bulk: the Bulk Well Process tab and the functions behind its steps"""
import re

import numpy as np
import pandas as pd
import pytest

from loggerloader.bulk import (INFO_COLUMNS, align_bulk, bulk_drift, bulk_manual, export_table,
                               guess_location, id_sort_key, import_bulk_files, info_value,
                               location_ids, well_info_table, well_name, write_bulk_pdf)
from loggerloader.views import FEET_PER_METER

from .conftest import time_series


def tab_text(notebook):
    return notebook.tab(notebook.select(), 'text')


def pdf_pages(path):
    return len(re.findall(rb'/Type\s*/Page[^s]', path.read_bytes()))


# --- data --- #

@pytest.fixture
def info_table():
    """A well info table in the database's column names"""
    return pd.DataFrame({
        'altlocationid': [1001, 1002.0, '9000', 1003, None],
        'locationname': ['PW01', 'PW02', 'Baro1', 'PW03', 'blank'],
        'verticalmeasure': [5000.0, 5100.0, 5050.0, 5200.0, 1.0],
        'stickup': [2.0, None, 0.0, 1.0, 0.0],
        'barologgertype': [9000, 9000, None, 9999, None],
    })


@pytest.fixture
def info(info_table):
    columns = {k: c for k, c in zip(INFO_COLUMNS, info_table.columns)}
    return well_info_table(info_table, columns)


@pytest.fixture
def records():
    """Transducer records by location id; PW01's water rises 0.36 ft, PW02's is steady"""
    return {
        '1001': time_series(base=100.0, trend=0.005),
        '1002': time_series(base=90.0),
        '9000': time_series(base=33.0, temperature=20.0),
        '1003': time_series(base=80.0),
    }


@pytest.fixture
def bulk_well(records):
    return pd.concat(records, names=['locationid', 'DateTime'])


@pytest.fixture
def manual_table(records):
    index = records['1001'].index
    return pd.DataFrame({
        'readingdate': [index[2], index[-3], index[2], index[-3], index[5]],
        'dtw': [20.0, 19.66, 30.0, 35.0, 1.0],
        'locationid': ['1001', '1001', '1002', '1002', '5555'],
    })


@pytest.fixture
def files(tmp_path, records, info_table, manual_table):
    """Files on disk for the bulk tab; transducer files are named the ways field staff name them"""
    names = {'PW01_2023.csv': '1001', '2023_pw02a.csv': '1002', 'Baro1 jan.csv': '9000',
             '1003 2023.csv': '1003'}
    paths = {}
    for name, locid in names.items():
        paths[name] = tmp_path / name
        records[locid].to_csv(paths[name])
    (tmp_path / 'unknown.csv').write_text(records['1001'].to_csv())
    info_table.to_csv(tmp_path / 'info.csv', index=False)
    manual_table.to_csv(tmp_path / 'manual.csv', index=False)
    return tmp_path, [str(p) for p in paths.values()] + [str(tmp_path / 'unknown.csv')]


def read_record(filename, filetype='auto'):
    return pd.read_csv(filename, index_col=0, parse_dates=True)


# --- functions --- #

class TestWellInfo:
    def test_id_sort_key(self):
        assert sorted(['10', 'abc', '9', '2', 'ABD'], key=id_sort_key) == ['2', '9', '10', 'ABD', 'abc']

    def test_well_info_table(self, info):
        assert list(info.index) == ['1001', '1002', '1003', '9000']
        assert list(info.columns) == ['locationname', 'ground', 'stickup', 'baroid']
        assert info.loc['1002', 'stickup'] == 0.0  # missing stickup is zero
        assert info.loc['1001', 'baroid'] == '9000'
        assert info.loc['9000', 'baroid'] == ''

    def test_well_info_in_meters(self, info_table):
        info = well_info_table(info_table, {'locationid': 'altlocationid', 'ground': 'verticalmeasure',
                                            'stickup': 'stickup'}, units='m')
        assert info.loc['1001', 'ground'] == pytest.approx(5000 * FEET_PER_METER)
        assert info.loc['1001', 'stickup'] == pytest.approx(2 * FEET_PER_METER)
        assert info.loc['1001', 'locationname'] == '1001'  # names default to the id
        assert np.isnan(info.loc['1001', 'baroid'] if info.loc['1001', 'baroid'] != '' else np.nan)

    def test_duplicate_ids_keep_the_first(self, info_table):
        info_table.loc[1, 'altlocationid'] = 1001
        info = well_info_table(info_table, {'locationid': 'altlocationid', 'locationname': 'locationname'})
        assert info.loc['1001', 'locationname'] == 'PW01'
        assert '1002' not in info.index

    def test_needs_id_column(self, info_table):
        with pytest.raises(ValueError, match='location id column'):
            well_info_table(info_table, {'locationid': ''})

    def test_needs_ids(self):
        with pytest.raises(ValueError, match='no location ids'):
            well_info_table(pd.DataFrame({'id': [None, '']}), {'locationid': 'id'})

    def test_info_value(self, info):
        assert info_value(info, '1001', 'ground') == 5000.0
        assert info_value(info, '1001', 'baroid') == '9000'
        assert info_value(info, '1001', 'locationname') == 'PW01'
        assert np.isnan(info_value(info, 'nope', 'ground'))
        assert info_value(info, 'nope', 'locationname') == ''
        assert well_name(info, '1001') == 'PW01'
        assert well_name(info, 'nope') == 'nope'

    @pytest.mark.parametrize('filename, expected', [
        ('PW01_2023.csv', '1001'),         # first word is the name
        ('pw01 20171208.xle', '1001'),
        ('1002 2023.csv', '1002'),         # first word is the id
        ('2023_pw02a.csv', '1002'),        # name found inside the file name
        ('Baro1.xle', '9000'),
        ('unknown.csv', ''),
    ])
    def test_guess_location(self, info, filename, expected):
        assert guess_location(filename, info) == expected


class TestImportBulkFiles:
    def test_combines_files_by_location(self, tmp_path, records):
        first, second = records['1001'].iloc[:40], records['1001'].iloc[30:]
        loaded = {'a.csv': first, 'b.csv': second, 'c.csv': records['9000'], 'skip.csv': None}
        data, file_info = import_bulk_files({'a.csv': '1001', 'b.csv': '1001', 'c.csv': '9000',
                                             'skip.csv': ''}, loaded.get)
        assert data.index.names == ['locationid', 'DateTime']
        assert location_ids(data) == ['1001', '9000']
        assert len(data.xs('1001', level=0)) == len(records['1001'])  # overlap dropped
        assert list(file_info.index) == [('1001', 'a.csv'), ('1001', 'b.csv'), ('9000', 'c.csv')]
        assert file_info.loc[('1001', 'a.csv'), 'records'] == 40

    def test_cancelled(self):
        assert import_bulk_files({'a.csv': '1001'}, lambda f: None) is None

    def test_needs_a_matched_file(self, records):
        with pytest.raises(ValueError, match='Match at least one file'):
            import_bulk_files({'a.csv': '', 'b.csv': '1001'}, lambda f: records['1001'].iloc[:0])


class TestAlignBulk:
    def test_align(self, bulk_well, info):
        data, notes = align_bulk(bulk_well, info)
        assert location_ids(data) == ['1001', '1002']
        assert notes['9000'] == 'barometer'
        assert notes['1001'] == f"{len(data.xs('1001', level=0))} rows"
        assert notes['1003'] == 'no data for baro 9999'
        assert 'corrwl' in data.columns

    def test_vented_wells_without_baro(self, bulk_well, info):
        data, notes = align_bulk(bulk_well, info, vented_without_baro=True)
        assert '1003' in location_ids(data)
        assert notes['1003'].endswith('(vented)')

    def test_no_baro_id(self, bulk_well, info):
        info.loc['1003', 'baroid'] = ''
        data, notes = align_bulk(bulk_well, info)
        assert notes['1003'] == 'no baro id'

    def test_no_overlap(self, info, records):
        records['9000'] = time_series(start='2025-01-01', base=33.0)
        data, notes = align_bulk(pd.concat(records, names=['locationid', 'DateTime']), info,
                                 vented_without_baro=True)
        assert notes['1001'] == 'does not overlap baro 9000'
        assert location_ids(data) == ['1003']

    def test_nothing_aligned(self, records, info):
        only_wells = pd.concat({'1003': records['1003']}, names=['locationid', 'DateTime'])
        with pytest.raises(ValueError, match='No wells could be aligned:\nPW03: no data for baro 9999'):
            align_bulk(only_wells, info)


class TestBulkManual:
    def test_bulk_manual(self, manual_table, info):
        df = bulk_manual(manual_table, 'readingdate', 'dtw', 'locationid', info)
        assert location_ids(df) == ['1001', '1002']  # 5555 is not in the well info
        assert df.index.names == ['locationid', 'readingdate']
        first = df.xs('1001', level=0).iloc[0]
        assert first['waterelevation'] == pytest.approx(5000 + 2 - 20.0)
        assert first['units'] == 'ft'

    def test_in_meters(self, manual_table, info):
        df = bulk_manual(manual_table, 'readingdate', 'dtw', 'locationid', info, units='m')
        assert df['dtwbelowcasing'].iloc[0] == pytest.approx(20.0 * FEET_PER_METER)

    def test_missing_column(self, manual_table, info):
        with pytest.raises(ValueError, match='depth to water'):
            bulk_manual(manual_table, 'readingdate', '', 'locationid', info)

    def test_no_matching_ids(self, manual_table, info):
        manual_table['locationid'] = 'zzz'
        with pytest.raises(ValueError, match='None of the manual readings'):
            bulk_manual(manual_table, 'readingdate', 'dtw', 'locationid', info)


class TestBulkDrift:
    @pytest.fixture
    def aligned(self, bulk_well, info):
        return align_bulk(bulk_well, info, vented_without_baro=True)[0]

    @pytest.fixture
    def manual(self, manual_table, info):
        return bulk_manual(manual_table, 'readingdate', 'dtw', 'locationid', info)

    def test_bulk_drift(self, aligned, manual, info):
        fixed, drift_info, notes, drifts = bulk_drift(aligned, manual, info)
        assert location_ids(fixed) == ['1001', '1002']
        assert notes['1003'] == 'no manual readings'
        assert notes['1001'].startswith('max drift ')
        assert abs(drifts['1001']) < 0.05 < abs(drifts['1002'])
        assert drift_info.index.names == ['locationid', 'interval']
        assert drift_info['locationname'].iloc[0] == 'PW01'
        pw01 = fixed.xs('1001', level=0)
        np.testing.assert_allclose(pw01['waterelevation'], pw01['DTW_WL'] + 2.0 + 5000.0)

    def test_wells_over_max_drift_are_left_out(self, aligned, manual, info):
        fixed, drift_info, notes, drifts = bulk_drift(aligned, manual, info, max_allowed=1.0)
        assert location_ids(fixed) == ['1001']
        assert notes['1002'].endswith('is over 1.0 ft; left out')
        assert '1002' in drift_info.index  # its drift is still reported

    def test_manual_readings_outside_the_record(self, aligned, manual, info):
        shifted = manual.rename(index=lambda t: t + pd.DateOffset(years=1) if isinstance(t, pd.Timestamp) else t)
        with pytest.raises(ValueError, match='no manual readings during the record'):
            bulk_drift(aligned, shifted, info)

    def test_export_table(self, aligned, manual, info):
        fixed = bulk_drift(aligned, manual, info)[0]
        df = export_table(fixed)
        assert {'locationid', 'readingdate', 'measureddtw', 'measuredlevel', 'waterelevation'} <= set(df.columns)
        assert 'DTW_WL' not in df.columns
        np.testing.assert_allclose(df['measureddtw'], -fixed['DTW_WL'].values)

    def test_write_bulk_pdf(self, aligned, manual, info, tmp_path):
        fixed = bulk_drift(aligned, manual, info)[0]
        path = write_bulk_pdf(tmp_path / 'wells.pdf', fixed, manual, info)
        assert pdf_pages(path) == 2


# --- the tab --- #

@pytest.fixture
def bulk(app, monkeypatch):
    """The Bulk Well Process view, reading transducer files as plain csv"""
    monkeypatch.setattr(app.well_view.controller, 'load_file', read_record)
    return app.view_manager.bulk_well_view


@pytest.fixture
def with_info(bulk, files):
    folder, _ = files
    assert bulk.load_info_file(str(folder / 'info.csv'))
    bulk.load_info()
    return bulk


@pytest.fixture
def imported(with_info, files):
    with_info.add_files(files[1])
    with_info.import_files()
    return with_info


@pytest.fixture
def drift_fixed(imported, files):
    imported.vented.set(True)
    imported.align()
    imported.load_manual_file(str(files[0] / 'manual.csv'))
    imported.process_manual()
    imported.max_drift.set('')
    imported.fix_drift()
    return imported


class TestInfoStep:
    def test_load_info_file_guesses_columns(self, bulk, files):
        assert bulk.load_info_file(str(files[0] / 'info.csv'))
        assert {k: box.get() for k, box in bulk.info_cols.items()} == {
            'locationid': 'altlocationid', 'locationname': 'locationname', 'ground': 'verticalmeasure',
            'stickup': 'stickup', 'baroid': 'barologgertype'}
        assert bulk.info_status.get() == 'info.csv (5 rows)'
        assert list(bulk.info_cols['ground']['values'])[0] == ''

    def test_load_info_file_cancelled(self, bulk, dialogs):
        dialogs.answer('askopenfilename', '')
        assert not bulk.load_info_file()

    def test_load_info(self, with_info, app):
        data = app.well_view.data
        assert list(data['bulk-well-info'].index) == ['1001', '1002', '1003', '9000']
        assert list(data['bulk-summary'].columns) == ['locationname', 'baroid', 'files']
        assert list(with_info.location['values']) == ['', 'PW01 (1001)', 'PW02 (1002)', 'PW03 (1003)',
                                                      'Baro1 (9000)']
        assert tab_text(with_info.steps) == '2 Files'

    def test_load_info_needs_file(self, bulk, dialogs):
        assert bulk.load_info() is None
        assert dialogs.warnings() == ['Choose a well info file first.']

    def test_load_info_bad_columns(self, bulk, files, dialogs):
        bulk.load_info_file(str(files[0] / 'info.csv'))
        bulk.info_cols['locationid'].set('')
        assert bulk.load_info() is None
        assert dialogs.warnings() == ['Choose the location id column.']

    def test_reloading_info_rematches_files(self, with_info, files):
        with_info.add_files(files[1])
        with_info.match(files[1][0], '1003')
        with_info.load_info()
        assert with_info.matches[files[1][0]] == '1003'  # still a known location, so kept


class TestFilesStep:
    def test_add_files_guesses_locations(self, with_info, files):
        with_info.add_files(files[1])
        assert list(with_info.matches.values()) == ['1001', '1002', '9000', '1003', '']
        rows = [with_info.file_list.item(i, 'values') for i in with_info.file_list.get_children()]
        assert tuple(rows[0]) == ('PW01_2023.csv', 'PW01', '1001')
        assert with_info.files_status.get() == '4 of 5 file(s) matched to a location'

    def test_add_files_before_info(self, bulk, files):
        bulk.add_files(files[1][:1])
        assert bulk.matches == {files[1][0]: ''}

    def test_add_folder(self, with_info, files, dialogs):
        dialogs.answer('askdirectory', str(files[0]))
        with_info.add_folder()
        # every csv in the folder, including the info and manual tables
        assert len(with_info.matches) == 7

    def test_adding_a_file_twice_lists_it_once(self, with_info, files):
        with_info.add_files(files[1][:1])
        with_info.add_files(files[1][:1])
        assert len(with_info.file_list.get_children()) == 1

    def test_assign_location(self, with_info, files):
        with_info.add_files(files[1])
        unknown = files[1][-1]
        with_info.file_list.selection_set(unknown)
        with_info.location.set('PW03 (1003)')
        with_info.assign_location()
        assert with_info.matches[unknown] == '1003'
        assert with_info.files_status.get() == '5 of 5 file(s) matched to a location'

    def test_file_selected_shows_its_location(self, with_info, files):
        with_info.add_files(files[1])
        with_info.file_list.selection_set(files[1][0])
        with_info.file_selected()
        assert with_info.location.get() == 'PW01 (1001)'

    def test_remove_files(self, with_info, files):
        with_info.add_files(files[1])
        with_info.file_list.selection_set(files[1][0])
        with_info.remove_files()
        assert files[1][0] not in with_info.matches
        assert len(with_info.file_list.get_children()) == 4

    def test_import_files(self, imported, app):
        data = app.well_view.data
        assert location_ids(data['bulk-well']) == ['1001', '1002', '1003', '9000']
        assert len(data['bulk-files']) == 4
        assert data['bulk-summary'].loc['1001', 'files'] == '1 file(s)'
        assert imported.files_status.get() == 'Imported 4 file(s) for 4 location(s)'
        assert tab_text(imported.steps) == '3 Align'
        assert list(imported.chart_well['values'])[0] == 'PW01 (1001)'

    def test_import_needs_info(self, bulk, dialogs):
        assert bulk.import_files() is None
        assert dialogs.warnings() == ['Load the well info first (step 1).']

    def test_import_needs_matches(self, with_info, dialogs):
        assert with_info.import_files() is None
        assert dialogs.warnings() == ['Match at least one file with data to a location.']


class TestAlignStep:
    def test_align(self, imported, app):
        data = imported.align()
        assert location_ids(data) == ['1001', '1002']
        summary = app.well_view.data['bulk-summary']
        assert summary.loc['9000', 'aligned'] == 'barometer'
        assert summary.loc['1003', 'aligned'] == 'no data for baro 9999'
        assert imported.align_status.get() == 'Aligned 2 well(s); see bulk-summary for the others'
        assert tab_text(imported.steps) == '4 Manual'

    def test_align_needs_files(self, with_info, dialogs):
        assert with_info.align() is None
        assert dialogs.warnings() == ['Import the matched files first (step 2).']

    def test_align_needs_whole_minutes(self, imported, dialogs):
        imported.freq.set('ten')
        assert imported.align() is None
        assert dialogs.warnings() == ['Data frequency must be a whole number of minutes.']


class TestManualStep:
    def test_load_and_process(self, imported, files, app):
        assert imported.load_manual_file(str(files[0] / 'manual.csv'))
        assert [imported.man_cols[k].get() for k in ('Datetime', 'DTW', 'Location id')] == \
            ['readingdate', 'dtw', 'locationid']
        assert imported.man_status.get() == 'manual.csv (5 rows)'
        result = imported.process_manual()
        assert location_ids(result) == ['1001', '1002']
        assert app.well_view.data['bulk-summary'].loc['1001', 'manual'] == '2 reading(s)'
        assert tab_text(imported.steps) == '5 Drift & Export'

    def test_needs_info(self, bulk, dialogs):
        assert bulk.process_manual() is None
        assert dialogs.warnings() == ['Load the well info first (step 1).']

    def test_needs_file(self, with_info, dialogs):
        assert with_info.process_manual() is None
        assert dialogs.warnings() == ['Choose a manual measurement file first.']


class TestDriftStep:
    def test_fix_drift(self, drift_fixed, app):
        data = app.well_view.data
        assert location_ids(data['bulk-fix-drift']) == ['1001', '1002']
        assert 'bulk-drift-info' in data
        assert data['bulk-summary'].loc['1003', 'drift'] == 'no manual readings'
        assert drift_fixed.drift_status.get() == 'Corrected 2 of 3 well(s); see bulk-summary for the others'

    def test_max_drift_limit(self, drift_fixed, app):
        drift_fixed.max_drift.set('1.0')
        drift_fixed.fix_drift()
        assert location_ids(app.well_view.data['bulk-fix-drift']) == ['1001']

    def test_max_drift_must_be_a_number(self, drift_fixed, dialogs):
        drift_fixed.max_drift.set('lots')
        assert drift_fixed.fix_drift() is None
        assert 'must be a number' in dialogs.warnings()[0]

    @pytest.mark.parametrize('fixture, message', [
        ('imported', 'Align the wells first (step 3).'),
    ])
    def test_needs_alignment(self, request, dialogs, fixture, message):
        view = request.getfixturevalue(fixture)
        assert view.fix_drift() is None
        assert dialogs.warnings() == [message]

    def test_needs_manual(self, imported, dialogs):
        imported.align()
        assert imported.fix_drift() is None
        assert dialogs.warnings() == ['Process the manual data first (step 4).']

    @pytest.mark.parametrize('name', ['out.csv', 'out.xlsx'])
    def test_save_csv(self, drift_fixed, tmp_path, name):
        path = tmp_path / name
        assert drift_fixed.save_csv(str(path)) == str(path)
        df = pd.read_csv(path) if name.endswith('csv') else pd.read_excel(path)
        assert set(df['locationid'].astype(str)) == {'1001', '1002'}

    def test_save_drift_info(self, drift_fixed, tmp_path):
        path = tmp_path / 'drift.csv'
        assert drift_fixed.save_drift_info(str(path)) == str(path)
        assert 'locationname' in pd.read_csv(path).columns

    def test_save_pdf(self, drift_fixed, tmp_path, dialogs):
        path = tmp_path / 'wells.pdf'
        dialogs.answer('asksaveasfilename', str(path))
        assert drift_fixed.save_pdf() == str(path)
        assert pdf_pages(path) == 2

    @pytest.mark.parametrize('method', ['save_csv', 'save_drift_info', 'save_pdf'])
    def test_saving_needs_drift(self, with_info, dialogs, method):
        assert getattr(with_info, method)('x') is None
        assert dialogs.warnings() == ['Fix drift first.']

    @pytest.mark.parametrize('method', ['save_csv', 'save_drift_info', 'save_pdf'])
    def test_saving_cancelled(self, drift_fixed, dialogs, method):
        assert getattr(drift_fixed, method)() is None
        assert dialogs.called('asksaveasfilename')


class TestResetAndState:
    def test_reimporting_files_clears_later_steps(self, drift_fixed, app):
        drift_fixed.import_files()
        data = app.well_view.data
        assert {'bulk-well-baro', 'bulk-fix-drift', 'bulk-drift-info'}.isdisjoint(data)
        assert 'bulk-manual' in data  # manual readings do not depend on the files
        assert 'aligned' not in data['bulk-summary'].columns
        assert 'manual' in data['bulk-summary'].columns

    def test_reloading_info_clears_everything(self, drift_fixed, app):
        drift_fixed.load_info()
        assert sorted(k for k in app.well_view.data if k.startswith('bulk-')) == \
            ['bulk-summary', 'bulk-well-info']

    def test_state_round_trip(self, drift_fixed, files):
        drift_fixed.max_drift.set('0.5')
        drift_fixed.freq.set('30')
        state = drift_fixed.get_state()
        assert state['matches'][files[1][0]] == '1001'
        info_table, manual_table = drift_fixed.info_table, drift_fixed.manual_table

        drift_fixed.set_state({})
        drift_fixed.set_state(state, info_table=info_table, manual_table=manual_table)
        assert drift_fixed.get_state() == state
        assert len(drift_fixed.file_list.get_children()) == 5
        assert list(drift_fixed.info_cols['ground']['values'])[1:] == list(info_table.columns)

    def test_state_through_a_project(self, drift_fixed, app, tmp_path):
        state = drift_fixed.get_state()
        path = tmp_path / 'bulk.llproj'
        app.write_project(path)
        drift_fixed.info_table = drift_fixed.manual_table = None
        assert app.open_project(str(path))
        assert drift_fixed.get_state() == state
        pd.testing.assert_frame_equal(drift_fixed.info_table, pd.read_csv(tmp_path / 'info.csv'),
                                      check_dtype=False)
        assert location_ids(app.well_view.data['bulk-fix-drift']) == ['1001', '1002']


class TestChart:
    def test_charts_most_processed_table(self, drift_fixed):
        assert drift_fixed.chart_well.get() == 'PW01 (1001)'
        ax = drift_fixed.fig.axes[0]
        assert ax.get_title() == 'PW01 (1001) - bulk-fix-drift'
        assert ax.get_legend_handles_labels()[1] == ['Drift-corrected', 'Manual']

    def test_choose_well(self, drift_fixed):
        drift_fixed.chart_well.set('Baro1 (9000)')
        drift_fixed.draw_well()
        ax = drift_fixed.fig.axes[0]
        assert ax.get_title() == 'Baro1 (9000) - bulk-well'
        assert ax.get_legend_handles_labels()[1] == ['Raw level']

    def test_aligned_well(self, imported):
        imported.align()
        assert imported.fig.axes[0].get_legend_handles_labels()[1] == ['Raw level', 'Baro-corrected']

    def test_no_data(self, with_info):
        with_info.refresh_chart_wells()
        assert list(with_info.chart_well['values']) == []
        assert with_info.chart_well.get() == ''
        ax, = with_info.fig.axes
        assert len(ax.lines) == 0

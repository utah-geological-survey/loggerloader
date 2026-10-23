"""Tests for loggerloader.menu: the menu bar, recent files, settings, and the dialogs it opens"""
import json
import tkinter as tk
from dataclasses import asdict
from tkinter import ttk

import pytest

from loggerloader import __version__
from loggerloader.config import ProcessingSettings
from loggerloader.menu import ApplicationMenu

from .conftest import click, descendants, toplevels


def entries(menu):
    """(type, label) of each entry of a tk Menu; separators and tear-off lines have no label"""
    end = menu.index('end')
    if end is None:
        return []
    return [(menu.type(i), '' if menu.type(i) in ('separator', 'tearoff') else menu.entrycget(i, 'label'))
            for i in range(end + 1)]


def labels(menu):
    return [label for kind, label in entries(menu) if kind not in ('separator', 'tearoff')]


def submenu(menu, label):
    index = labels_index(menu, label)
    return menu.nametowidget(menu.entrycget(index, 'menu'))


def labels_index(menu, label):
    for i, (kind, text) in enumerate(entries(menu)):
        if text == label:
            return i
    raise LookupError(label)


def invoke(menu, *path):
    """Invoke File > Import > Well Data... as invoke(menu.menu, 'File', 'Import', 'Well Data...')"""
    for label in path[:-1]:
        menu = submenu(menu, label)
    menu.invoke(labels_index(menu, path[-1]))


def settings_file(home):
    return home / '.loggerloader' / 'settings.json'


class TestStructure:
    def test_top_level_menus(self, app):
        assert labels(app.menu.menu) == ['File', 'Edit', 'View', 'Tools', 'Help']

    def test_file_menu(self, app):
        assert labels(app.menu.file_menu) == ['Open Project...', 'Import', 'Export', 'Recent Files',
                                              'Save Project', 'Save Project As...', 'Exit']
        file_menu = app.menu.file_menu
        assert labels(submenu(file_menu, 'Import')) == ['Well Data...', 'Barometric Data...',
                                                         'Manual Measurements...']
        assert labels(submenu(file_menu, 'Export')) == ['Processed Data...', 'Charts...', 'Report...']

    def test_edit_menu(self, app):
        assert labels(app.menu.edit_menu) == ['Clean Data', 'Preferences...']
        assert labels(submenu(app.menu.edit_menu, 'Clean Data')) == [
            'Remove Outliers', 'Fix Gaps', 'Smooth Data', 'Trim Extrema...', 'Convert Units...']

    def test_view_menu(self, app):
        view = app.menu.view_menu
        assert labels(view) == ['Theme', 'Chart Options', 'Status Bar', 'Toolbar']
        assert entries(submenu(view, 'Theme')) == [('radiobutton', 'Light'), ('radiobutton', 'Dark'),
                                                   ('radiobutton', 'System')]
        assert entries(submenu(view, 'Chart Options')) == [
            ('checkbutton', 'Show Grid'), ('checkbutton', 'Show Legend'), ('checkbutton', 'Flip Y Axis')]

    def test_tools_menu(self, app):
        assert labels(app.menu.tools_menu) == ['Analysis', 'Options...']
        assert labels(submenu(app.menu.tools_menu, 'Analysis')) == [
            'Jump Fix', 'Basic Statistics', 'Trend Analysis', 'Custom Analysis...']

    def test_help_menu(self, app):
        assert labels(app.menu.help_menu) == ['Documentation', 'Quick Start Guide',
                                              'Check for Updates', 'About']

    def test_menus_do_not_tear_off(self, app):
        for menu in (app.menu.file_menu, app.menu.edit_menu, app.menu.view_menu,
                     app.menu.tools_menu, app.menu.help_menu):
            assert not int(menu.cget('tearoff'))


class TestCommands:
    """Each menu item calls the matching app action"""

    @pytest.mark.parametrize('path, method, args', [
        (('File', 'Import', 'Well Data...'), 'import_data', ('well',)),
        (('File', 'Import', 'Barometric Data...'), 'import_data', ('baro',)),
        (('File', 'Import', 'Manual Measurements...'), 'import_data', ('manual',)),
        (('File', 'Export', 'Processed Data...'), 'export_data', ('processed',)),
        (('File', 'Export', 'Charts...'), 'export_charts', ()),
        (('File', 'Export', 'Report...'), 'generate_report', ()),
        (('Edit', 'Clean Data', 'Remove Outliers'), 'clean_data', ('outliers',)),
        (('Edit', 'Clean Data', 'Fix Gaps'), 'clean_data', ('gaps',)),
        (('Edit', 'Clean Data', 'Smooth Data'), 'clean_data', ('smooth',)),
        (('Edit', 'Clean Data', 'Trim Extrema...'), 'clean_data', ('trim',)),
        (('Edit', 'Clean Data', 'Convert Units...'), 'clean_data', ('units',)),
        (('View', 'Theme', 'Dark'), 'set_theme', ('dark',)),
        (('View', 'Theme', 'System'), 'set_theme', ('system',)),
        (('Tools', 'Analysis', 'Jump Fix'), 'analyze', ('jump',)),
        (('Tools', 'Analysis', 'Basic Statistics'), 'analyze', ('basic',)),
        (('Tools', 'Analysis', 'Trend Analysis'), 'analyze', ('trend',)),
        (('Tools', 'Analysis', 'Custom Analysis...'), 'analyze', ('custom',)),
    ])
    def test_menu_item_calls_app(self, app, monkeypatch, path, method, args):
        calls = []
        monkeypatch.setattr(app, method, lambda *a: calls.append(a))
        invoke(app.menu.menu, *path)
        assert calls == [args]

    def test_open_project(self, app, dialogs):
        invoke(app.menu.menu, 'File', 'Open Project...')
        assert dialogs.called('askopenfilename')[0][1]['title'] == 'Open project'

    @pytest.mark.parametrize('label', ['Save Project', 'Save Project As...'])
    def test_save_project(self, app, dialogs, label):
        invoke(app.menu.menu, 'File', label)
        assert dialogs.called('asksaveasfilename')[0][1]['title'] == 'Save project'

    @pytest.mark.parametrize('label, option', [('Show Grid', 'grid'), ('Show Legend', 'legend'),
                                               ('Flip Y Axis', 'flip_y')])
    def test_chart_options_toggle_and_redraw(self, loaded, label, option):
        var = getattr(loaded.chart_manager, option)
        before = var.get()
        loaded.chart_manager.last = None
        loaded.well_view.redraw()
        drawn = []
        loaded.chart_manager.draw = lambda *a: drawn.append(a)
        invoke(loaded.menu.menu, 'View', 'Chart Options', label)
        assert var.get() is (not before)
        assert drawn

    def test_theme_choice_is_saved(self, app, home):
        invoke(app.menu.menu, 'View', 'Theme', 'Dark')
        assert app.menu.theme_var.get() == 'dark'
        assert json.loads(settings_file(home).read_text())['theme'] == 'dark'
        assert app.view_manager.style.theme_use() == 'forest-dark'

    def test_help_documentation(self, app, browser):
        invoke(app.menu.menu, 'Help', 'Documentation')
        assert browser == ['https://github.com/utah-geological-survey/loggerloader/wiki']

    @pytest.mark.parametrize('label, title', [('Quick Start Guide', 'Quick Start Guide'),
                                              ('Check for Updates', 'Updates')])
    def test_help_messages(self, app, dialogs, label, title):
        invoke(app.menu.menu, 'Help', label)
        (args, kwargs), = dialogs.called('showinfo')
        assert args[0] == title


class TestRecentFiles:
    def test_empty(self, app):
        assert entries(app.menu.recent_menu) == [('command', '(No recent files)')]
        assert app.menu.recent_menu.entrycget(0, 'state') == 'disabled'

    def test_add_lists_newest_first(self, app, tmp_path):
        for name in ('a.csv', 'b.csv'):
            app.menu.add_recent_file(str(tmp_path / name))
        assert labels(app.menu.recent_menu) == ['b.csv', 'a.csv', 'Clear Recent Files']

    def test_add_moves_existing_to_front(self, app):
        for name in ('a', 'b', 'a'):
            app.menu.add_recent_file(name)
        assert app.menu.recent_files == ['a', 'b']

    def test_keeps_five(self, app):
        for i in range(7):
            app.menu.add_recent_file(f'f{i}')
        assert app.menu.recent_files == ['f6', 'f5', 'f4', 'f3', 'f2']

    def test_saved_and_reloaded(self, app, home):
        app.menu.add_recent_file('x.csv')
        saved = json.loads(settings_file(home).read_text())
        assert saved['recent_files'] == ['x.csv']
        assert saved['theme'] == 'light'
        menu = ApplicationMenu(app.root, app)
        assert menu.recent_files == ['x.csv']
        assert labels(menu.recent_menu) == ['x.csv', 'Clear Recent Files']

    def test_clear(self, app, home):
        app.menu.add_recent_file('x.csv')
        invoke(app.menu.recent_menu, 'Clear Recent Files')
        assert app.menu.recent_files == []
        assert labels(app.menu.recent_menu) == ['(No recent files)']
        assert json.loads(settings_file(home).read_text())['recent_files'] == []

    def test_choosing_one_opens_it(self, app, monkeypatch):
        opened = []
        monkeypatch.setattr(app, 'open_recent', opened.append)
        app.menu.add_recent_file('a.csv')
        app.menu.add_recent_file('b.csv')
        invoke(app.menu.recent_menu, 'a.csv')
        assert opened == ['a.csv']

    def test_corrupt_settings_are_ignored(self, app, home):
        settings_file(home).parent.mkdir(exist_ok=True)
        settings_file(home).write_text('{not json')
        assert app.menu.load_settings() == {}

    def test_no_settings_file(self, app):
        assert app.menu.load_settings() == {}

    def test_settings_keep_other_options(self, app, home):
        app.menu.settings['show_toolbar'] = False
        app.menu.save_settings()
        saved = json.loads(settings_file(home).read_text())
        assert saved['show_toolbar'] is False and saved['show_statusbar'] is True


class TestOptionsDialog:
    @pytest.fixture
    def options(self, app):
        app.menu.show_options()
        window, = toplevels(app.root)
        return window

    def fields(self, window):
        return [w for w in descendants(window) if isinstance(w, ttk.Entry)]

    def test_shows_current_settings(self, app, options):
        assert options.title() == 'Options'
        values = [e.get() for e in self.fields(options)]
        current = asdict(app.config.processing)
        assert values == [str(current[k]) for k in ('sampling_interval', 'max_gap', 'outlier_threshold',
                                                     'smoothing_window', 'drift_tolerance',
                                                     'interpolation_limit')]

    def test_ok_saves(self, app, options):
        interval, gap, outlier, *_ = self.fields(options)
        for entry, value in ((interval, '15'), (gap, '30'), (outlier, '2.5')):
            entry.delete(0, 'end')
            entry.insert(0, value)
        click(options, 'OK')
        assert not options.winfo_exists()
        settings = app.config.processing
        assert (settings.sampling_interval, settings.max_gap, settings.outlier_threshold) == (15, 30, 2.5)
        assert isinstance(settings.sampling_interval, int)
        saved = json.loads(app.config.config_file.read_text())
        assert saved['processing']['sampling_interval'] == 15

    def test_whole_number_settings_accept_decimals(self, app, options):
        self.fields(options)[3].delete(0, 'end')
        self.fields(options)[3].insert(0, '5.0')
        click(options, 'OK')
        assert app.config.processing.smoothing_window == 5

    def test_out_of_range(self, app, options, dialogs):
        gap = self.fields(options)[1]
        gap.delete(0, 'end')
        gap.insert(0, '10')  # less than the 60 minute sampling interval
        click(options, 'OK')
        assert 'out of range' in dialogs.warnings()[0]
        assert options.winfo_exists()
        assert app.config.processing == ProcessingSettings()

    def test_not_a_number(self, app, options, dialogs):
        self.fields(options)[0].insert(0, 'x')
        click(options, 'OK')
        assert dialogs.warnings() == ['Enter numbers for every setting.']
        assert options.winfo_exists()

    def test_cancel(self, app, options):
        self.fields(options)[0].insert(0, '9')
        click(options, 'Cancel')
        assert not options.winfo_exists()
        assert app.config.processing == ProcessingSettings()

    def test_opened_from_tools_menu(self, app):
        invoke(app.menu.menu, 'Tools', 'Options...')
        assert [w.title() for w in toplevels(app.root)] == ['Options']


class TestOtherDialogs:
    def test_preferences(self, app):
        invoke(app.menu.menu, 'Edit', 'Preferences...')
        window, = toplevels(app.root)
        assert window.title() == 'Preferences'
        notebook = next(w for w in descendants(window) if isinstance(w, ttk.Notebook))
        assert [notebook.tab(t, 'text') for t in notebook.tabs()] == ['General', 'Display']
        click(window, 'OK')
        assert not window.winfo_exists()

    def test_about(self, app):
        invoke(app.menu.menu, 'Help', 'About')
        window, = toplevels(app.root)
        assert window.title() == 'About'
        texts = [str(w.cget('text')) for w in descendants(window) if isinstance(w, tk.Label)]
        assert f'Logger Loader v.{__version__}' in texts
        assert any(t.startswith('pandas v') for t in texts)
        assert any(t.startswith('Using Python v') for t in texts)

    def test_about_links(self, app, browser):
        app.menu.show_about()
        window, = toplevels(app.root)
        links = [w for w in descendants(window) if isinstance(w, tk.Label) and w.bind('<Button-1>')]
        assert len(links) == 6
        app.menu.callback('https://geology.utah.gov')
        assert browser == ['https://geology.utah.gov']

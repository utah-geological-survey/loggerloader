"""Shared fixtures for the GUI tests.

Every test gets:
    * a temporary home directory, so config.json and settings.json never touch the real ones
    * stubbed tkinter dialogs (messagebox, filedialog, simpledialog) that record each call
      and return canned answers
    * a ``modal`` driver for windows that block in ``wait_window`` (ColumnMatchDialog,
      Open Recent's import-kind question)
    * a plotly widget that keeps the figure but skips writing the 3 MB html file

The tests need a display; they are skipped where Tk cannot start (e.g. headless CI).
"""
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import matplotlib
import numpy as np
import pandas as pd
import pytest


def _tk_available():
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


if not _tk_available():
    pytest.skip("Tk needs a display", allow_module_level=True)


GUI_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    """Mark every test in this folder 'gui', so `pytest -m "not gui"` skips them"""
    for item in items:
        if GUI_DIR in Path(item.fspath).parents:
            item.add_marker(pytest.mark.gui)


DIALOG_FUNCTIONS = {
    messagebox: ['showinfo', 'showwarning', 'showerror', 'askyesno', 'askokcancel',
                 'askquestion', 'askyesnocancel', 'askretrycancel'],
    filedialog: ['askopenfilename', 'askopenfilenames', 'asksaveasfilename', 'askdirectory'],
    simpledialog: ['askfloat', 'askstring', 'askinteger'],
}


class Dialogs:
    """Records dialog calls and returns queued answers.

    ``dialogs.answer('askfloat', 1.5, 2.5)`` queues answers returned in order; when the
    queue is empty a dialog returns None (i.e. the user cancelled).
    """

    def __init__(self, monkeypatch):
        self.calls = []
        self.answers = {}
        for module, names in DIALOG_FUNCTIONS.items():
            for name in names:
                monkeypatch.setattr(module, name, self._stub(name))

    def _stub(self, name):
        def stub(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            queue = self.answers.get(name)
            if queue:
                return queue.pop(0)
            return 'ok' if name.startswith('show') else None
        return stub

    def answer(self, name, *values):
        self.answers.setdefault(name, []).extend(values)

    def called(self, name):
        return [(args, kwargs) for n, args, kwargs in self.calls if n == name]

    def messages(self, name):
        """The message text of each call to a messagebox function"""
        return [args[1] if len(args) > 1 else kwargs.get('message', '')
                for args, kwargs in self.called(name)]

    def warnings(self):
        return self.messages('showwarning')

    def errors(self):
        return self.messages('showerror')

    def assert_quiet(self):
        """No warnings or errors were shown"""
        assert self.warnings() == [] and self.errors() == []


class Modal:
    """Drives windows that block in wait_window.

    Push handlers with ``modal.push(func)``; each blocking window is passed to the next
    handler. A window with no handler is closed, as if the user cancelled.
    """

    def __init__(self, monkeypatch):
        self.handlers = []
        self.windows = []

        def wait_window(widget, window=None):
            window = window if window is not None else widget
            self.windows.append(window)
            if self.handlers:
                self.handlers.pop(0)(window)
            if window.winfo_exists():
                window.destroy()

        monkeypatch.setattr(tk.Misc, 'wait_window', wait_window)
        monkeypatch.setattr(tk.Misc, 'grab_set', lambda widget: None)

    def push(self, handler):
        self.handlers.append(handler)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def find_widget(window, cls, text=None):
    """First descendant of type cls (with the given text, if any)"""
    for child in descendants(window):
        if isinstance(child, cls) and (text is None or str(child.cget('text')) == text):
            return child
    raise LookupError(f"No {cls.__name__} {text!r} in {window}")


def click(window, text):
    """Invoke the button labelled text"""
    find_widget(window, (ttk.Button, tk.Button), text).invoke()


def toplevels(root):
    """Open dialog windows anywhere under root (not the hidden calendar and tooltip popups)"""
    return [w for w in descendants(root) if type(w) is tk.Toplevel and w.winfo_exists()
            and w.wm_state() != 'withdrawn']


def start_tk(factory):
    """Call factory (which creates a Tk root), retrying once if Tk fails to read its library.

    On Windows, Tk's startup scripts are occasionally unreadable for a moment (e.g. while
    a virus scanner has them open), which fails with "Can't find a usable tk.tcl".
    """
    try:
        return factory()
    except tk.TclError as e:
        if 'usable tk.tcl' not in str(e) and 'usable init.tcl' not in str(e):
            raise
        return factory()


def destroy(window):
    """Process pending events, then destroy the window.

    A root that is not destroyed leaks its Tk interpreter, and enough of them crash Tk,
    so errors here are raised rather than ignored (unless the window is already gone).
    """
    try:
        window.update()
    except tk.TclError:
        pass
    try:
        window.destroy()
    except tk.TclError as e:
        if 'application has been destroyed' not in str(e):
            raise


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A temporary home directory for config and settings files"""
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    return home


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def modal_driver(monkeypatch):
    return Modal(monkeypatch)


@pytest.fixture
def browser(monkeypatch):
    """Records urls opened with webbrowser instead of opening them"""
    import webbrowser
    opened = []
    monkeypatch.setattr(webbrowser, 'open', lambda url, *a, **k: opened.append(url))
    monkeypatch.setattr(webbrowser, 'open_new', lambda url, *a, **k: opened.append(url))
    return opened


@pytest.fixture
def fast_plotly(monkeypatch):
    """Keep the plotly figure in memory instead of writing it to html"""
    from loggerloader.plotly_tk_vis import PlotlyTkinterWidget

    def update_plot(self, fig):
        self.current_fig = fig
        self.plot_label.config(text="Plot updated - click 'Show Plot' to view")

    monkeypatch.setattr(PlotlyTkinterWidget, 'update_plot', update_plot)


@pytest.fixture
def app(home, dialogs, modal_driver, browser, fast_plotly):
    """A LoggerLoaderApp with its window hidden"""
    from loggerloader.llgui import LoggerLoaderApp

    application = start_tk(LoggerLoaderApp)
    application.root.withdraw()
    yield application
    destroy(application.root)
    matplotlib.style.use('default')


@pytest.fixture
def root(dialogs, modal_driver):
    """A bare hidden Tk root for widgets tested on their own"""
    window = start_tk(tk.Tk)
    window.withdraw()
    yield window
    destroy(window)


# --- data --- #

def time_series(periods=72, freq='h', start='2023-01-01', base=100.0, trend=0.0, wave=0.2,
                temperature=10.0, name='DateTime'):
    index = pd.date_range(start, periods=periods, freq=freq, name=name)
    steps = np.arange(periods)
    return pd.DataFrame({
        'Level': base + trend * steps + wave * np.sin(steps / 4),
        'Temperature': temperature + 0.01 * steps,
    }, index=index)


@pytest.fixture
def well_df():
    return time_series(base=100.0, trend=0.005)


@pytest.fixture
def baro_df():
    return time_series(base=33.0, temperature=20.0)


@pytest.fixture
def loaded(app, well_df, baro_df):
    """An app with well and baro tables, like after steps 1-2"""
    app.well_view.set_table('well', well_df)
    app.well_view.set_table('baro', baro_df)
    return app


@pytest.fixture
def processed(loaded, well_df):
    """An app that has run every single-well step through elevations"""
    controller = loaded.well_view.controller
    controller.align()
    index = well_df.index
    controller.manual_from_entry([(index[2], 20.0), (index[-3], 20.5)], 'ft', '42')
    controller.fix_drift()
    controller.calc_elevations(5000.0, 'ft', 2.0, 'ft')
    return loaded


@pytest.fixture
def csv_file(tmp_path):
    """Write a DataFrame to csv and return its path"""
    def write(df, name='data.csv', index=False):
        path = tmp_path / name
        df.to_csv(path, index=index)
        return path
    return write

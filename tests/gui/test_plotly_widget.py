"""Tests for loggerloader.plotly_tk_vis: the 'Interactive View' chart tab"""
import os
from pathlib import Path

import pytest

from loggerloader.plotly_tk_vis import PlotlyTkinterWidget

from .conftest import time_series


@pytest.fixture
def widget(root):
    """A widget that really writes its html (no fast_plotly stub)"""
    plot = PlotlyTkinterWidget(root, height=300)
    yield plot
    if plot.frame.winfo_exists():
        plot.destroy()


@pytest.fixture
def plotted(widget):
    widget.plot_water_levels(time_series(periods=10), well_field='Level')
    return widget


def test_starts_empty(widget):
    assert widget.current_fig is None and widget.current_html is None
    assert widget.plot_label.cget('text') == "Click 'Show Plot' to view visualization"
    assert widget.plot_type.get() == 'line'


def test_plot_water_levels_writes_html(plotted):
    path = Path(plotted.current_html)
    assert path.exists() and path.parent == Path(plotted.temp_dir)
    assert '<html' in path.read_text(encoding='utf-8')[:500].lower()
    trace, = plotted.current_fig.data
    assert trace.name == 'Well Level' and len(trace.y) == 10
    assert plotted.current_fig.layout.height == 300
    assert plotted.plot_label.cget('text') == "Plot updated - click 'Show Plot' to view"


def test_new_plot_replaces_old_file(plotted):
    plotted.plot_water_levels(time_series(periods=5), well_field='Temperature')
    assert os.listdir(plotted.temp_dir) == [Path(plotted.current_html).name]
    assert list(plotted.current_fig.data[0].y) == list(time_series(periods=5)['Temperature'])


def test_show_plot_opens_browser(plotted, browser):
    plotted.show_plot()
    assert browser == [f'file://{plotted.current_html}']


def test_show_plot_without_plot(widget, browser):
    widget.show_plot()
    assert browser == []


def test_export_html(plotted, dialogs, tmp_path):
    path = tmp_path / 'chart.html'
    dialogs.answer('asksaveasfilename', str(path))
    plotted.export_plot()
    assert path.exists()


def test_export_cancelled(plotted, dialogs, tmp_path):
    plotted.export_plot()
    assert dialogs.called('asksaveasfilename')
    assert list(tmp_path.glob('*.html')) == []


def test_export_without_plot(widget, dialogs):
    widget.export_plot()
    assert dialogs.calls == []


@pytest.mark.parametrize('kind, mode', [('scatter', 'markers'), ('line', 'lines')])
def test_plot_type_change(plotted, kind, mode):
    plotted.plot_type.set(kind)
    plotted.on_plot_type_change()
    assert plotted.current_fig.data[0].mode == mode


def test_plot_type_change_without_plot(widget):
    widget.plot_type.set('scatter')
    widget.on_plot_type_change()
    assert widget.current_fig is None


def test_destroy_removes_temp_files(plotted):
    html, folder = plotted.current_html, plotted.temp_dir
    plotted.destroy()
    assert not os.path.exists(html) and not os.path.exists(folder)
    assert not plotted.frame.winfo_exists()

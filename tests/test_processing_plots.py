import matplotlib
matplotlib.use("Agg")  # Prevent GUI windows during headless test runs

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import pytest

from loggerloader.processing_plots import (
    manual_vs_transducer,
    manual_vs_transducer_plotly,
    plotlystuff,
    processed_vs_manual,
    scatterplot_by_data_status,
    stickup_plot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def suppress_plot_display(monkeypatch):
    """Captures Plotly fig.show() calls instead of launching a browser window,
    and closes all Matplotlib figures after each test.
    """
    shown_figs = []
    monkeypatch.setattr(go.Figure, "show", lambda self, *args, **kwargs: shown_figs.append(self))
    yield shown_figs
    plt.close("all")


@pytest.fixture
def time_index():
    return pd.date_range("2025-01-01 00:00", periods=3, freq="1D", name="readingdate")


# ---------------------------------------------------------------------------
# Tests for `scatterplot_by_data_status`
# ---------------------------------------------------------------------------

def test_scatterplot_by_data_status_combines_sources_and_statuses(time_index):
    old_df = pd.DataFrame(
        {
            "waterelevation": [100.0, 101.0, 102.0],
            "datastatus": ["approved", "approved", "provisional"],
        },
        index=time_index,
    )
    new_df = pd.DataFrame(
        {
            "waterelevation": [102.5, 103.0, 103.5],
            "datastatus": ["provisional", "raw", "raw"],
        },
        index=time_index,
    )

    fig = scatterplot_by_data_status(
        old_data=old_df,
        new_data=new_df,
        field_name="waterelevation",
        title_text="Well W-1 Comparison",
        plot_height=450,
    )

    assert isinstance(fig, go.Figure)
    assert fig.layout.title.text == "Well W-1 Comparison"
    assert fig.layout.height == 450
    assert fig.layout.yaxis.title.text == "Waterelevation"

    # Total plotted points across all traces should equal len(old_df) + len(new_df) = 6
    total_points = sum(len(trace.x) for trace in fig.data)
    assert total_points == 6
    # Input DataFrames should not be mutated with 'source'
    assert "source" not in old_df.columns
    assert "source" not in new_df.columns


# ---------------------------------------------------------------------------
# Tests for `manual_vs_transducer` (Matplotlib)
# ---------------------------------------------------------------------------

def test_manual_vs_transducer_creates_dual_axis_matplotlib_figure(time_index):
    manual_df = pd.DataFrame({"dtwbelowcasing": [15.0, 15.5, 16.0]}, index=time_index)
    corr_df = pd.DataFrame({"corrwl": [25.0, 24.5, 24.0]}, index=time_index)

    manual_vs_transducer(manual_df, corr_df, siteid="SITE-42")

    fig = plt.gcf()
    # twinx() creates 2 Axes on the active figure
    assert len(fig.axes) == 2
    ax1, ax2 = fig.axes
    assert ax1.get_ylabel() == "Depth to water below casing"
    assert ax2.get_ylabel() == "Feet of water above transducer"
    assert ax2.get_title() == "SITE-42"
    assert len(ax1.lines) == 1
    assert len(ax2.lines) == 1


# ---------------------------------------------------------------------------
# Tests for `manual_vs_transducer_plotly`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "corrected_flag,expected_col",
    [
        (True, "corrwl"),
        (False, "Level"),
    ],
)
def test_manual_vs_transducer_plotly_selects_corrected_or_raw(
    time_index, suppress_plot_display, corrected_flag, expected_col
):
    manual_df = pd.DataFrame({"dtwbelowcasing": [10.0, 11.0, 12.0]}, index=time_index)
    well_df = pd.DataFrame(
        {
            "corrwl": [30.0, 29.0, 28.0],
            "Level": [50.0, 49.0, 48.0],
        },
        index=time_index,
    )

    manual_vs_transducer_plotly(
        manual_data=manual_df,
        well_data=well_df,
        siteid="WELL-99",
        corrected=corrected_flag,
    )

    assert len(suppress_plot_display) == 1
    fig = suppress_plot_display[0]
    assert fig.layout.title.text == "WELL-99"
    assert len(fig.data) == 2
    assert list(fig.data[0].y) == [10.0, 11.0, 12.0]
    assert list(fig.data[1].y) == list(well_df[expected_col])
    assert fig.data[1].yaxis == "y2"


# ---------------------------------------------------------------------------
# Tests for `stickup_plot` (Matplotlib)
# ---------------------------------------------------------------------------

def test_stickup_plot_renders_scatter_and_line(time_index):
    plot_df = pd.DataFrame({"current_stickup_height": [2.1, 2.15, 2.2]}, index=time_index)

    stickup_plot(plot_df, locationid="LOC-7")

    fig = plt.gcf()
    ax = fig.axes[0]
    assert ax.get_title() == "LOC-7"
    assert ax.get_ylabel() == "Current Stickup Height"
    assert len(ax.collections) == 1  # scatter PathCollection
    assert len(ax.lines) == 1        # dashed connecting line


# ---------------------------------------------------------------------------
# Tests for `processed_vs_manual` (Plotly)
# ---------------------------------------------------------------------------

def test_processed_vs_manual_plots_common_field(time_index, suppress_plot_display):
    proc_df = pd.DataFrame({"waterelevation": [4500.1, 4500.2, 4500.3]}, index=time_index)
    man_df = pd.DataFrame({"waterelevation": [4500.15, 4500.25]}, index=time_index[:2])

    processed_vs_manual(
        siteid="PW-03",
        processed_data=proc_df,
        manual_data=man_df,
        plot_field="waterelevation",
    )

    assert len(suppress_plot_display) == 1
    fig = suppress_plot_display[0]
    assert fig.layout.title.text == "PW-03"
    assert fig.layout.yaxis.title.text == "waterelevation (ft)"
    assert fig.data[0].mode == "lines"
    assert fig.data[1].mode == "markers"
    assert list(fig.data[1].y) == [4500.15, 4500.25]


# ---------------------------------------------------------------------------
# Tests for `plotlystuff`
# ---------------------------------------------------------------------------

def test_plotlystuff_dual_yaxis_and_reverse_y(time_index, suppress_plot_display):
    df1 = pd.DataFrame({"Level": [12.0, 12.5, 13.0]}, index=time_index)
    df2 = pd.DataFrame({"Baro": [30.1, 30.2, 30.0]}, index=time_index)

    plotlystuff(
        datasets=[df1, df2],
        colnames=["Level", "Baro"],
        datatitles=["Water Level", "Barometer"],
        chrttitle="Level vs Baro",
        two_yaxes=True,
        reverse_y=[True, False],
        plot_height=400,
    )

    assert len(suppress_plot_display) == 1
    fig = suppress_plot_display[0]

    assert fig.layout.title.text == "Level vs Baro"
    assert fig.layout.height == 400
    assert fig.layout.margin.r == 140  # Expanded margin for y2 axis
    assert fig.data[0].yaxis == "y"
    assert fig.data[1].yaxis == "y2"
    assert fig.layout.yaxis.autorange == "reversed"
    assert fig.layout.yaxis2.autorange is None


def test_plotlystuff_more_than_five_datasets_generates_fallback_colors(
    time_index, suppress_plot_display
):
    datasets = [pd.DataFrame({"val": [i, i + 1, i + 2]}, index=time_index) for i in range(6)]
    colnames = ["val"] * 6

    plotlystuff(datasets=datasets, colnames=colnames, two_yaxes=False)

    fig = suppress_plot_display[0]
    assert len(fig.data) == 6
    assert fig.layout.margin.r == 60
    assert all(trace.yaxis == "y" for trace in fig.data)
    assert fig.data[5].line.color.startswith("#")
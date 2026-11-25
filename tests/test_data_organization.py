import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from loggerloader.data_organization import (
    NewTransImp,
    barodistance,
    check_file_completeness,
    compilation,
    compilefiles,
    copy_recent_files,
    dataendclean,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures for Synthetic Transducer Files
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_new_xle(tmp_path):
    """Creates a synthetic new-format Solinst .xle file (kpa + Deg F)."""
    xle_content = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Body_xle>
    <File_info><Company>Solinst</Company></File_info>
    <Instrument_info><Serial_number>123456</Serial_number></Instrument_info>
    <Ch1_data_header>
        <Identification>LEVEL</Identification>
        <Unit>kpa</Unit>
    </Ch1_data_header>
    <Ch2_data_header>
        <Identification>TEMPERATURE</Identification>
        <Unit>Deg F</Unit>
    </Ch2_data_header>
    <Data>
        <Log id="1"><Date>2025/01/01</Date><Time>00:00:00</Time><ms>0</ms><ch1>10.0</ch1><ch2>68.0</ch2></Log>
        <Log id="2"><Date>2025/01/01</Date><Time>01:00:00</Time><ms>0</ms><ch1>20.0</ch1><ch2>77.0</ch2></Log>
    </Data>
</Body_xle>
"""
    filepath = tmp_path / "well_a_2025.xle"
    filepath.write_text(xle_content, encoding="ISO-8859-1")
    return filepath


@pytest.fixture
def sample_old_xle(tmp_path):
    """Creates a synthetic old-format .xle file (indexed XML tree without <Log> tags)."""
    xle_content = """<?xml version="1.0" encoding="ISO-8859-1"?>
<Body_xle>
    <File_info><Company>Solinst</Company></File_info>
    <Instrument_info><Serial_number>123456</Serial_number></Instrument_info>
    <Instrument_info_from_data_header><Location>WellB</Location></Instrument_info_from_data_header>
    <Ch1_data_header>
        <Identification>Level</Identification>
        <Unit>ft</Unit>
    </Ch1_data_header>
    <Ch2_data_header>
        <Identification>Temperature</Identification>
        <Unit>Deg C</Unit>
    </Ch2_data_header>
    <Data>
        <row><Date>2025/01/01</Date><Time>00:00:00</Time><ch1>15.0</ch1><ch2>12.5</ch2></row>
        <row><Date>2025/01/01</Date><Time>01:00:00</Time><ch1>15.5</ch1><ch2>13.0</ch2></row>
    </Data>
</Body_xle>
"""
    filepath = tmp_path / "well_b_old.xle"
    filepath.write_text(xle_content, encoding="ISO-8859-1")
    return filepath


@pytest.fixture
def sample_lev(tmp_path):
    """Creates a synthetic Solinst .lev file."""
    lev_content = (
        "Data file for DataLogger.\n"
        "[CHANNEL 1 from data header]\n"
        "Identification=LEVEL\n"
        "Unit=ft\n"
        "[CHANNEL 2 from data header]\n"
        "Identification=TEMPERATURE\n"
        "Unit=Deg C\n"
        "[Data]\n"
        "Date Time Level Temperature\n"
        "2025/01/01 00:00:00 12.0 14.0\n"
        "2025/01/01 01:00:00 12.5 14.5\n"
        "END OF DATA FILE OF DATALOGGER FOR WINDOWS\n"
    )
    filepath = tmp_path / "well_c.lev"
    filepath.write_text(lev_content, encoding="utf-8")
    return filepath


@pytest.fixture
def sample_solinst_csv(tmp_path):
    """Creates a synthetic Solinst-exported .csv file (13 header lines)."""
    lines = [
        "Serial_number: 999999",
        "Project ID: Test",
        "Location: WellD",
        "Latitude: 40.0",
        "Longitude: -111.0",
        "Channel 1: LEVEL",
        "Offset: 0.0",
        "UNIT: ft",
        "Channel 2: TEMP",
        "Offset: 0.0",
        "Range: 0-50",
        "Linearity: 0.1",
        "UNIT: Deg C",
        "Date,Time,ms,LEVEL,TEMP",
        "2025/01/01,00:00:00,0,25.0,15.0",
        "2025/01/01,01:00:00,0,25.5,15.2",
    ]
    filepath = tmp_path / "well_d_solinst.csv"
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


@pytest.fixture
def sample_global_csv(tmp_path):
    """Creates a synthetic Global Water .csv file."""
    lines = [
        "Global Water Logger",
        "Date,Time, Feet, Temp C, Volts",
        "2025-01-01,00:00:00,30.0,11.0,12.1",
        "2025-01-01,01:00:00,30.2,11.2,12.1",
        "2025-01-01,02:00:00,30.4,11.4,12.0",
    ]
    filepath = tmp_path / "well_e_global.csv"
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


@pytest.fixture
def sample_troll_htm(tmp_path):
    """Creates a synthetic In-Situ Troll .htm file (psi -> ft conversion)."""
    html_content = """<html><body><table>
        <tr class="dataHeader">
            <td>Date and Time</td>
            <td>Pressure (psi)</td>
            <td>Temperature (C)</td>
        </tr>
        <tr class="data">
            <td>2025-01-01 00:00:00</td>
            <td>10.0</td>
            <td>12.0</td>
        </tr>
        <tr class="data">
            <td>2025-01-01 01:00:00</td>
            <td>10.5</td>
            <td>12.5</td>
        </tr>
    </table></body></html>
    """
    filepath = tmp_path / "well_f_troll.htm"
    filepath.write_text(html_content, encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Tests for File Management Functions
# ---------------------------------------------------------------------------

def test_copy_recent_files_purges_old_and_copies_matching(tmp_path):
    (tmp_path / "2024_well1.xle").write_text("data24")
    (tmp_path / "2025_well1.xle").write_text("data25")
    (tmp_path / "2020_old.xle").write_text("data20")

    recent_dir = tmp_path / "recent"
    recent_dir.mkdir()
    stale_file = recent_dir / "stale_file.xle"
    stale_file.write_text("stale")

    copy_recent_files(tmp_path, ["2024", "2025"])

    copied_names = {f.name for f in recent_dir.iterdir()}
    assert copied_names == {"2024_well1.xle", "2025_well1.xle"}
    assert not stale_file.exists()


def test_compilefiles_prepends_mtime_and_skips_duplicates(tmp_path):
    search_dir = tmp_path / "raw"
    nested_dir = search_dir / "subdir"
    nested_dir.mkdir(parents=True)
    copy_dir = tmp_path / "compiled"

    f1 = nested_dir / "PW03_logger.xle"
    f2 = nested_dir / "PW10_logger.xle"
    f3 = nested_dir / "PW03_notes.txt"  # Wrong extension
    for f in (f1, f2, f3):
        f.write_text("dummy")

    expected_date = datetime.datetime.fromtimestamp(f1.stat().st_mtime).strftime("%Y-%m-%d")

    compilefiles(search_dir, copy_dir, filecontains=["pw03"], filetype=".xle")

    copied_files = list(copy_dir.iterdir())
    assert len(copied_files) == 1
    assert copied_files[0].name == f"{expected_date}_PW03_logger.xle"

    # Running a second time should skip without error
    compilefiles(search_dir, copy_dir, filecontains=["pw03"], filetype=".xle")
    assert len(list(copy_dir.iterdir())) == 1


def test_check_file_completeness_reports_unmatched(tmp_path, capsys):
    (tmp_path / "PW03_2025.xle").write_text("a")
    (tmp_path / "mystery_file.xle").write_text("b")

    well_dict = {
        "Well_PW03": ["PW03"],
        "Well_PW10": ["PW10"],
    }

    check_file_completeness(tmp_path, well_dict)
    captured = capsys.readouterr().out

    assert "mystery_file.xle" in captured
    assert "Well_PW10" in captured
    assert "Well_PW03" not in captured


# ---------------------------------------------------------------------------
# Tests for `NewTransImp` File Readers
# ---------------------------------------------------------------------------

def test_new_trans_imp_new_xle_unit_conversions(sample_new_xle):
    imp = NewTransImp(sample_new_xle, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    # 10.0 kpa * 0.33456 = 3.3456 ft
    assert np.isclose(df["Level"].iloc[0], 3.3456)
    # 68.0 F -> 20.0 C
    assert np.isclose(df["Temperature"].iloc[0], 20.0)
    assert df["filename"].iloc[0] == "well_a_2025"


def test_new_trans_imp_old_xle_fallback(sample_old_xle):
    imp = NewTransImp(sample_old_xle, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df["Level"]) == [15.0, 15.5]
    assert list(df["Temperature"]) == [12.5, 13.0]


def test_new_trans_imp_lev(sample_lev):
    imp = NewTransImp(sample_lev, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df["Level"]) == [12.0, 12.5]
    assert list(df["Temperature"]) == [14.0, 14.5]


def test_new_trans_imp_solinst_csv(sample_solinst_csv):
    imp = NewTransImp(sample_solinst_csv, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    assert list(df["Level"]) == [25.0, 25.5]
    assert list(df["Temp"]) == [15.0, 15.2]


def test_new_trans_imp_global_csv(sample_global_csv):
    imp = NewTransImp(sample_global_csv, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    # First row is dropped by datediff > 0 filter in Global CSV branch
    assert list(df["Level"]) == [30.2, 30.4]
    assert list(df["Temp"]) == [11.2, 11.4]


def test_new_trans_imp_troll_htm(sample_troll_htm):
    imp = NewTransImp(sample_troll_htm, trim_end=False)
    df = imp.well

    assert isinstance(df.index, pd.DatetimeIndex)
    # 10.0 psi * 2.3067 = 23.067 ft
    assert np.isclose(df["Level"].iloc[0], 23.067)
    assert df["filename"].iloc[0] == "well_f_troll"


def test_new_trans_imp_unrecognized_extension(tmp_path, capsys):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("hello")

    imp = NewTransImp(bad_file)
    assert imp.well is None
    assert "filetype not recognized" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Tests for `compilation`, `dataendclean`, and `barodistance`
# ---------------------------------------------------------------------------

def test_compilation_combines_and_deduplicates(tmp_path):
    # Create two .lev files with one overlapping timestamp
    lev1 = tmp_path / "part1.lev"
    lev1.write_text(
        "Header\n[CHANNEL 1 from data header]\nIdentification=LEVEL\nUnit=ft\n"
        "[CHANNEL 2 from data header]\nIdentification=TEMPERATURE\nUnit=Deg C\n"
        "[Data]\nDate Time Level Temperature\n"
        "2025/01/01 00:00:00 10.0 12.0\n"
        "2025/01/01 01:00:00 10.5 12.0\n"
        "END\n"
    )
    lev2 = tmp_path / "part2.lev"
    lev2.write_text(
        "Header\n[CHANNEL 1 from data header]\nIdentification=LEVEL\nUnit=ft\n"
        "[CHANNEL 2 from data header]\nIdentification=TEMPERATURE\nUnit=Deg C\n"
        "[Data]\nDate Time Level Temperature\n"
        "2025/01/01 01:00:00 10.5 12.0\n"
        "2025/01/01 02:00:00 11.0 12.0\n"
        "END\n"
    )

    compiled = compilation(tmp_path, trm=False, wildcard="*.lev")

    assert len(compiled) == 3
    assert compiled.index.is_monotonic_increasing
    assert list(compiled["Level"]) == [10.0, 10.5, 11.0]


def test_dataendclean_trims_beginning_and_end_jumps():
    # Needs >50 rows because dataendclean checks df.index[50] and df.index[-50]
    idx = pd.date_range("2025-01-01 00:00", periods=120, freq="1h")
    levels = np.full(120, 20.0)
    # Out-of-water jump at index 3 (beginning) and index 116 (end)
    levels[:3] = 0.0
    levels[116:] = 0.0

    df = pd.DataFrame({"Level": levels}, index=idx)
    cleaned = dataendclean(df, "Level", inplace=False, jumptol=1.0)

    # Original df should not be mutated when inplace=False
    assert len(df) == 120
    # Trimmed df should drop the 0.0 sections at both ends
    assert (cleaned["Level"] == 20.0).all()
    assert cleaned.index.min() == idx[4]
    assert cleaned.index.max() == idx[115]


def test_barodistance_identifies_closest_barometer():
    wellinfo = pd.DataFrame(
        {
            "WellID": ["Near_PW03", "Near_PW10", "Near_PW19"],
            "UTMEasting": [240330.0, 271130.0, 305090.0],
            "UTMNorthing": [4314995.0, 4356070.0, 4389630.0],
            "G_Elev_m": [1623.0, 1605.0, 1413.0],
        }
    )

    result = barodistance(wellinfo.copy())

    assert list(result["closest_baro"]) == ["pw03", "pw10", "pw19"]
    for col in ("pw03", "pw10", "pw19"):
        assert col in result.columns
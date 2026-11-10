import pandas as pd
from pathlib import Path


def get_line_num(filename, lookup="Date and Time,Seconds"):

    """This function will find the first instance of the string `lookup` and give the line number of that string.
    I chose 'Date and Time,Seconds' as the default value for the `lookup` variable because that looks like the
    first part of the header.  If the function can't find that string, it uses 70 by default.

    Stolen from https://stackoverflow.com/questions/3961265/get-line-number-of-certain-phrase-in-file-python
    """
    linenum = 70
    with open(filename) as myFile:
        for num, line in enumerate(myFile, 1):
            if lookup in line:
                linenum = num - 1

    return linenum

def getfilename(path):
    """This function extracts the file name without file path or extension

    Args:
        path (file):
            full path and file (including extension of file)

    Returns:
        name of file as string
    """
    return path.name.split(".")[0]


def read_troll_csv(filename):
    """Read an In-Situ (Aqua TROLL / Level TROLL) csv export into a DataFrame indexed by DateTime.

    Pressure columns are converted to feet of water in a new ``Level`` column, and
    specific conductivity is renamed ``specific_conductivity``.
    """
    df = pd.read_csv(
        filename,
        skiprows=get_line_num(filename),
        encoding="unicode_escape",
    )
    df.columns = (
        df.columns.str.replace(" ", "").str.replace("(", "_").str.replace(")", "")
    )
    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    if date_col is None:
        raise ValueError(f"No date column found in {Path(filename).name}")
    df["DateTime"] = pd.to_datetime(df[date_col])
    df = df.drop(columns=date_col).drop_duplicates("DateTime")
    df = df.set_index("DateTime").sort_index()

    for col in list(df.columns):
        if "Press" in col:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if "psi" in col:
                df["Level"] = df[col] * 2.3067
            elif "Hg" in col:
                df["Level"] = df[col] * 0.044603
            elif "kPa" in col:
                df["Level"] = df[col] * 0.33455
        elif "specificcond" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.rename(columns={col: "specific_conductivity"})
        elif any(k in col for k in ("Depth", "Cond", "Total", "Salin", "Dens", "Temp")):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["filename"] = Path(filename).stem
    return df

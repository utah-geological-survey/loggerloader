import pandas as pd
import numpy as np
import shutil
from pathlib import Path

import datetime
import os
import xml.etree.ElementTree as eletree
from shutil import copyfile
from xml.etree.ElementTree import ParseError

from bs4 import BeautifulSoup

#
def copy_recent_files(copydir, recent_years):
    """Copies matching recent files into a dedicated subdirectory.

    Creates a subfolder named 'recent' inside `copydir`, purges any existing
    files inside it, and copies over files from `copydir` whose filenames
    start with any of the prefixes defined in `recent_years`.

    Args:
        copydir (str or pathlib.Path): Directory containing the source files
            to evaluate and where the 'recent' destination folder will be created.
        recent_years (iterable of str): Collection of year strings (e.g.,
            ['2024', '2025', '2026']) to match against the start of filenames.

    Returns:
        None

    Raises:
        FileNotFoundError: If `copydir` does not exist.
        NotADirectoryError: If `copydir` is not a directory.
    """
    # Use Path objects for paths
    recent_dir = Path(copydir) / 'recent'
    if not recent_dir.exists():
        recent_dir.mkdir(parents=True, exist_ok=True)  

    for filename in recent_dir.iterdir():
        if filename.is_file():
            filename.unlink()  # Delete the file

    # Copy the relevant files from the source directory
    for filename in Path(copydir).iterdir():
        if filename.name.startswith(tuple(recent_years)): 
            destination_file = recent_dir / filename.name
            shutil.copy(filename, destination_file)  # Copy the file to the 'recent' directory
            print(f'Copied: {filename.name}')

def compilefiles(searchdir, copydir, filecontains, filetype=".xle"):
    """
    Copies files matching specified criteria from a source directory to a target directory.

    Parameters:
    - searchdir (str or Path): The root directory to search for files.
    - copydir (str or Path): The directory where matching files will be copied.
    - filecontains (list): A list of substrings to match in file names.
    - filetype (str, optional): A string of file extension to filter files (default: "xle").

    Behavior:
    - Recursively searches for files in the `searchdir` that contain any of the substrings in `filecontains`.
    - Filters files by the specified extensions in `filetypes`.
    - Prepends the file's last modified date (in YYYY-MM-DD format) to its name before copying.
    - Ensures the target directory exists before copying files.
    - Skips files if they already exist in the target directory.

    Returns:
    None
    """
    # Ensure searchdir and copydir are Path objects
    if not isinstance(searchdir, Path):
        searchdir = Path(searchdir)
    if not isinstance(copydir, Path):
        copydir = Path(copydir)

    if not isinstance(filecontains, list):
        filecontains = list(filecontains)
    # filetypes = set(filetypes)  # Use a set for faster lookups

    for name in filecontains:
        for file in searchdir.rglob(f"*{name}*{filetype}", case_sensitive=False):

            # Find matching files
            dater = file.stat().st_mtime
            dater_str = datetime.datetime.fromtimestamp(dater).strftime("%Y-%m-%d")
            rightfile = f"{dater_str}_{file.name}"

            # Ensure the copy directory exists
            if not copydir.exists():
                print(f"Creating {copydir}")
                copydir.mkdir(parents=True)

            target_path = copydir / rightfile

            if not target_path.is_file():
                print(f"Copying to {target_path}")
                try:
                    copyfile(file, target_path)
                except Exception as e:
                    print(f"Error copying {file} to {target_path}: {e}")

    print("Copy Complete!")
    return

# compile transducer files into a single dastaframe

class NewTransImp(object):
    """This class uses an imports and cleans the ends of transducer file.

    Args:
        infile (file):
            complete file path to input file
        xle (bool):
            if true, then the file type should be xle; else it should be csv

    Returns:
        A Pandas DataFrame containing the transducer data
    """

    def __init__(self, infile, trim_end=True, jumptol=1.0):
        """

        :param infile: complete file path to input file
        :param trim_end: turns on the dataendclean function
        :param jumptol: minimum amount of jump to search for that was caused by an out-of-water experience
        """

        self.well = None
        self.infile = infile
        if type(self.infile) is str:
            self.infile = Path(self.infile)
        file_ext = self.infile.name.split(".")[-1]
        try:
            if file_ext == "xle":
                try:
                    self.well = self.new_xle_imp()
                except (ParseError, KeyError):
                    self.well = self.old_xle_imp()
            elif file_ext == "lev":
                self.well = self.new_lev_imp()
            elif file_ext == "csv":
                self.well = self.new_csv_imp()
            elif file_ext in ['htm', 'html']:
                self.well = self.read_troll_htm()
            else:
                print("filetype not recognized")
                self.well = None

            if self.well is None:
                pass
            elif trim_end:
                self.well = dataendclean(self.well, "Level", jumptol=jumptol)
            else:
                pass
            return

        except AttributeError as e:
            print("Bad File", e)
            print(e)
            return

    def read_troll_htm(self):
        """given a path to the .htm (html) file, function will read in the data and produce pandas dataframe
        Args:
            filepath (str):
                path to data file

        Return:
            df:
                dataframe
        """
        with self.infile.open("r") as f:
            html_string = f.read()

        # use BeautifulSoup to parse the HTML content of the page
        soup = BeautifulSoup(html_string, "html.parser")
        table_rows = soup.find_all('tr', {'class': 'data'})
        header = soup.find_all('tr', {'class': 'dataHeader'})
        heads = header[0].find_all('td')
        colnames = [head.text.strip() for head in heads]
        data = []
        for row in table_rows:
            cols = row.find_all("td")
            cols = [col.text.strip() for col in cols]
            data.append(cols)

                # convert the list of data into a pandas dataframe
        df = pd.DataFrame(data)
        df.columns = colnames

        for col in df.columns:
            if "Date" in col or "date" in col:
                df[col] = pd.to_datetime(df[col])
                df = df.rename(columns={col: "DateTime"})  # Renaming the column to match name from xle files
                df = df.set_index("DateTime")
            elif "Press" in col:
                df[col] = pd.to_numeric(df[col])
                if "psi" in col:
                    df["Level"] = df[col] * 2.3067
                elif "Hg" in col:
                    df['Level'] = df[col] * 0.044603
                df = df.drop(columns=[col])
            elif 'Temp' in col:
                df[col] = pd.to_numeric(df[col])
                df = df.rename(columns={col: "Temperature"})
                if 'F)' in col:
                    df[col] = (df[col] - 32.0) * 5 / 9
                    print(f"CH. 2 units in F, converting to deg C...")
            elif 'Specific Cond' in col or "specific cond" in col:
                df[col] = pd.to_numeric(df[col])
                df = df.rename(columns={col: "specific_conductivity"})
            elif "Depth" in col or "Cond" in col or "Total" in col or "Salin" in col or "Dens" in col:
                df[col] = pd.to_numeric(df[col])
        df['filename'] = self.infile.stem

        return df

    def new_csv_imp(self):
        """This function uses an exact file path to upload a csv transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        nm = self.infile.name
        with self.infile.open("r") as fd:
            txt = fd.readlines()
            if len(txt) > 1:
                if "Serial" in txt[0]:
                    print("{:} is Solinst".format(nm))
                    if "UNIT: " in txt[7]:
                        level_units = str(txt[7])[5:].strip().lower()
                    if "UNIT: " in txt[12]:
                        temp_units = str(txt[12])[5:].strip().lower()
                    f = pd.read_csv(
                        self.infile,
                        skiprows=13,
                        parse_dates=[[0, 1]],
                        usecols=[0, 1, 3, 4],
                    )
                    print(f.columns)
                    f["DateTime"] = pd.to_datetime(f["Date_Time"], errors="coerce")
                    f.set_index("DateTime", inplace=True)
                    f.drop("Date_Time", axis=1, inplace=True)
                    f.rename(
                        columns={"LEVEL": "Level", "TEMP": "Temp", "COND": "Cond"},
                        inplace=True,
                    )
                    level = "Level"
                    temp = "Temp"
                    cond = "Cond"

                    if level_units == "feet" or level_units == "ft":
                        f[level] = pd.to_numeric(f[level])
                    elif level_units == "kpa":
                        f[level] = pd.to_numeric(f[level]) * 0.33456
                        print("Units in kpa, converting {:} to ft...".format(nm))
                    elif level_units == "mbar":
                        f[level] = pd.to_numeric(f[level]) * 0.0334552565551
                    elif level_units == "psi":
                        f[level] = pd.to_numeric(f[level]) * 2.306726
                        print("Units in psi, converting {:} to ft...".format(nm))
                    elif level_units == "m" or level_units == "meters":
                        f[level] = pd.to_numeric(f[level]) * 3.28084
                        print("Units in psi, converting {:} to ft...".format(nm))
                    elif level_units == "???":
                        f[level] = pd.to_numeric(f[level])
                        print("Units in ???, {:} is messed up...".format(nm))
                    else:
                        f[level] = pd.to_numeric(f[level])
                        print("Unknown units, no conversion")

                    if temp_units == "Deg C" or temp_units == "\N{DEGREE SIGN}" + "C":
                        f[temp] = f[temp]
                    elif temp_units == "Deg F" or temp_units == "\N{DEGREE SIGN}" + "F":
                        print("Temp in F, converting {:} to C...".format(nm))
                        f[temp] = (f[temp] - 32.0) * 5.0 / 9.0
                    return f

                elif "Date" in txt[1]:
                    print("{:} is Global".format(self.infile))
                    f = pd.read_csv(
                        self.infile, skiprows=1, parse_dates={"DateTime": [0, 1]}
                    )
                    # f = f.reset_index()
                    # f['DateTime'] = pd.to_datetime(f.columns[0], errors='coerce')
                    f = f[f.DateTime.notnull()]
                    if " Feet" in list(f.columns.values):
                        f["Level"] = f[" Feet"]
                        f.drop([" Feet"], inplace=True, axis=1)
                    elif "Feet" in list(f.columns.values):
                        f["Level"] = f["Feet"]
                        f.drop(["Feet"], inplace=True, axis=1)
                    else:
                        f["Level"] = f.iloc[:, 1]
                    # Remove first and/or last measurements if the transducer was out of the water
                    # f = dataendclean(f, 'Level')
                    flist = f.columns.tolist()
                    if " Temp C" in flist:
                        f["Temperature"] = f[" Temp C"]
                        f["Temp"] = f["Temperature"]
                        f.drop([" Temp C", "Temperature"], inplace=True, axis=1)
                    elif " Temp F" in flist:
                        f["Temperature"] = (f[" Temp F"] - 32) * 5 / 9
                        f["Temp"] = f["Temperature"]
                        f.drop([" Temp F", "Temperature"], inplace=True, axis=1)
                    else:
                        f["Temp"] = np.nan
                    f.set_index(["DateTime"], inplace=True)
                    f["date"] = f.index.to_julian_date().values
                    f["datediff"] = f["date"].diff()
                    f = f[f["datediff"] > 0]
                    f = f[f["datediff"] < 1]
                    # bse = int(pd.to_datetime(f.index).minute[0])
                    # f = hourly_resample(f, bse)
                    f.rename(columns={" Volts": "Volts"}, inplace=True)
                    for col in ["date", "datediff", "Date_ Time", "Date_Time"]:
                        if col in f.columns:
                            f = f.drop(col, axis=1)
                    return f
            else:
                print("{:} is unrecognized".format(self.infile))

    def new_lev_imp(self):
        nm = self.infile.name.split(".")[0]
        with self.infile.open("r") as fd:
            txt = fd.readlines()

        try:
            data_ind = txt.index("[Data]\n")
            # inst_info_ind = txt.index('[Instrument info from data header]\n')
            ch1_ind = txt.index("[CHANNEL 1 from data header]\n")
            ch2_ind = txt.index("[CHANNEL 2 from data header]\n")
            level = txt[ch1_ind + 1].split("=")[-1].strip().title()
            level_units = txt[ch1_ind + 2].split("=")[-1].strip().lower()
            temp = txt[ch2_ind + 1].split("=")[-1].strip().title()
            temp_units = txt[ch2_ind + 2].split("=")[-1].strip().lower()
            # serial_num = txt[inst_info_ind+1].split('=')[-1].strip().strip(".")
            # inst_num = txt[inst_info_ind+2].split('=')[-1].strip()
            # location = txt[inst_info_ind+3].split('=')[-1].strip()
            # start_time = txt[inst_info_ind+6].split('=')[-1].strip()
            # stop_time = txt[inst_info_ind+7].split('=')[-1].strip()

            df = pd.read_table(
                self.infile,
                parse_dates=[[0, 1]],
                sep=r"\s+",
                skiprows=data_ind + 2,
                names=["Date", "Time", level, temp],
                skipfooter=1,
                engine="python",
            )
            df.rename(columns={"Date_Time": "DateTime"}, inplace=True)
            df.set_index("DateTime", inplace=True)

            if level_units == "feet" or level_units == "ft":
                df[level] = pd.to_numeric(df[level])
            elif level_units == "kpa":
                df[level] = pd.to_numeric(df[level]) * 0.33456
                print("Units in kpa, converting {:} to ft...".format(nm))
            elif level_units == "mbar":
                df[level] = pd.to_numeric(df[level]) * 0.0334552565551
            elif level_units == "psi":
                df[level] = pd.to_numeric(df[level]) * 2.306726
                print("Units in psi, converting {:} to ft...".format(nm))
            elif level_units == "m" or level_units == "meters":
                df[level] = pd.to_numeric(df[level]) * 3.28084
                print("Units in psi, converting {:} to ft...".format(nm))
            else:
                df[level] = pd.to_numeric(df[level])
                print("Unknown units, no conversion")

            if temp_units == "Deg C" or temp_units == "\N{DEGREE SIGN}" + "C":
                df[temp] = df[temp]
            elif temp_units == "Deg F" or temp_units == "\N{DEGREE SIGN}" + "F":
                print("Temp in F, converting {:} to C...".format(nm))
                df[temp] = (df[temp] - 32.0) * 5.0 / 9.0
            df["filename"] = self.infile
            return df
        except ValueError:
            print("File {:} has formatting issues".format(nm))

    def old_xle_imp(self):
        """This function uses an exact file path to upload a xle transducer file.

        Returns:
            A Pandas DataFrame containing the transducer data
        """
        with self.infile.open("r", encoding="ISO-8859-1") as f:
            contents = f.read()
            tree = eletree.fromstring(contents)

        dfdata = []
        for child in tree[5]:
            dfdata.append([child[i].text for i in range(len(child))])
        f = pd.DataFrame(
            dfdata, columns=[tree[5][0][i].tag for i in range(len(tree[5][0]))]
        )

        try:
            ch1ID = tree[3][0].text.title()  # Level
        except AttributeError:
            ch1ID = "Level"

        ch1Unit = tree[3][1].text.lower()

        if ch1Unit == "feet" or ch1Unit == "ft":
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"])
        elif ch1Unit == "kpa":
            print(
                "CH. 1 units in {:}, converting {:} to ft...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"]) * 0.33456
        elif ch1Unit == "mbar":
            print(
                "CH. 1 units in {:}, converting {:} to ft...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"]) * 0.0334552565551
        elif ch1Unit == "psi":
            print(
                "CH. 1 units in {:}, converting {:} to ft...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"]) * 2.306726
        elif ch1Unit == "m" or ch1Unit == "meters":
            print(
                "CH. 1 units in {:}, converting {:} to ft...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"]) * 3.28084
        elif ch1Unit == "???":
            print(
                "CH. 1 units in {:}, {:} messed up...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"])
        else:
            f[str(ch1ID).title()] = pd.to_numeric(f["ch1"])
            print(
                "Unknown units {:}, no conversion for {:}...".format(
                    ch1Unit, os.path.basename(self.infile)
                )
            )

        if "ch2" in f.columns:
            try:
                ch2ID = tree[4][0].text.title()  # Level
            except AttributeError:
                ch2ID = "Temperature"

            ch2Unit = tree[4][1].text
            numCh2 = pd.to_numeric(f["ch2"])

            if (
                ch2Unit == "Deg C"
                or ch2Unit == "Deg_C"
                or ch2Unit == "\N{DEGREE SIGN}" + "C"
            ):
                f[str(ch2ID).title()] = numCh2
            elif ch2Unit == "Deg F" or ch2Unit == "\N{DEGREE SIGN}" + "F":
                print(
                    "CH. 2 units in {:}, converting {:} to C...".format(
                        ch2Unit, os.path.basename(self.infile)
                    )
                )
                f[str(ch2ID).title()] = (numCh2 - 32) * 5 / 9
            else:
                print(
                    "Unknown temp units {:}, no conversion for {:}...".format(
                        ch2Unit, os.path.basename(self.infile)
                    )
                )
                f[str(ch2ID).title()] = numCh2
        else:
            print("No channel 2 for {:}".format(self.infile))

        if "ch3" in f.columns:
            # Usually Conductivity
            ch3ID = tree[5][0].text.title()  # Level
            ch3Unit = tree[5][1].text
            f[str(ch3ID).title()] = pd.to_numeric(f["ch3"])

        # add extension-free file name to dataframe
        f["filename"] = self.infile.name.split(".")[0]
        # combine Date and Time fields into one field
        f["DateTime"] = pd.to_datetime(
            f.apply(lambda x: x["Date"] + " " + x["Time"], 1)
        )
        f[str(ch1ID).title()] = pd.to_numeric(f[str(ch1ID).title()])

        f = f.reset_index()
        f = f.set_index("DateTime")
        f["Level"] = f[str(ch1ID).title()]

        droplist = ["Date", "Time", "ch1", "ch2", "index", "ms"]
        for item in droplist:
            if item in f.columns:
                f = f.drop(item, axis=1)

        return f

    def new_xle_imp(self):
        tree = eletree.parse(
            self.infile, parser=eletree.XMLParser(encoding="ISO-8859-1")
        )
        root = tree.getroot()

        # ch1id = root.find('./Identification')
        dfdata = {}
        for item in root.findall("./Data/Log"):
            dfdata[item.attrib["id"]] = {}
            for child in item:
                dfdata[item.attrib["id"]][child.tag] = child.text
                # print([child[i].text for i in range(len(child))])
        ch = {}
        for child in root:
            if "Ch" in child.tag:
                ch[child.tag[:3].lower()] = {}
                for item in child:
                    if item.text is not None:
                        ch[child.tag[:3].lower()][item.tag] = item.text

        f = pd.DataFrame.from_dict(dfdata, orient="index")
        f["DateTime"] = f.apply(
            lambda x: pd.to_datetime(x["Date"] + " " + x["Time"]), 1
        )

        f = f.reset_index()
        f = f.set_index("DateTime")

        levelconv = {
            "feet": 1,
            "ft": 1,
            "kpa": 0.33456,
            "mbar": 0.033455256555148,
            "m": 3.28084,
            "meters": 3.28084,
            "psi": 2.306726,
        }
        for col in f:
            if col in ch.keys():
                if col == "ch1":
                    chname = "Level"
                elif col == "ch2":
                    chname = "Temperature"
                elif "Identification" in ch[col].keys():
                    chname = ch[col]["Identification"].title()

                chunit = ch[col]["Unit"]
                f = f.rename(columns={col: chname})
                f[chname] = pd.to_numeric(f[chname])
                if chname == "Level":
                    f[chname] = f[chname] * levelconv.get(chunit.lower(), 1)
                    print(f"CH. 1 units in {chunit}, converting to ft...")
                elif chname == "Temperature" or chname == "Temp":
                    if (
                        chunit[-1] == "F"
                        or chunit.title() == "Fahrenheit"
                        or chunit.title() == "Deg F"
                        or chunit.title() == "Deg_F"
                    ):
                        f[chname] = (f[chname] - 32.0) * 5 / 9
                        print(f"CH. 2 units in {chunit}, converting to deg C...")
            elif col in ["ms", "Date", "Time", "index"]:
                f = f.drop(col, axis=1)
        f["filename"] = self.infile.name.split(".")[0]
        return f

def compilation(inputfile, trm=True, wildcard="*"):
    """This function reads multiple xle transducer files in a directory and generates a compiled Pandas DataFrame.
    Args:
        inputfile (file):
            complete file path to input files; use * for wildcard in file name
        trm (bool):
            whether or not to trim the end
    Returns:
        outfile (object):
            Pandas DataFrame of compiled data
    Example::
        >>> compilation('O:/Snake Valley Water/Transducer Data/Raw_data_archive/all/LEV/*baro*')
        picks any file containing 'baro'
    """

    # create empty dictionary to hold DataFrames
    f = {}

    if not isinstance(inputfile, Path):
        inputfile = Path(inputfile)

    # generate list of relevant files
    filelist = inputfile.glob(wildcard)

    # iterate through list of relevant files
    for infile in filelist:
        # run computations using lev files
        filename, file_extension = os.path.splitext(infile)
        if file_extension in ['.csv', '.lev', '.xle', '.htm', '.html']:
            print(infile)
            nti = NewTransImp(infile, trim_end=trm).well
            file_name = Path(infile).stem # change instead of function to avoid issue with strings!
            f[file_name] = nti
    # concatenate all of the DataFrames in dictionary f to one DataFrame: g
    g = pd.concat(f)
    # remove multiindex and replace with index=Datetime
    g = g.reset_index()
    g['DateTime'] = pd.to_datetime(g['DateTime'], errors='coerce') ### change to address deprecation!
    g = g.set_index(['DateTime'])
    # drop old indexes
    g = g.drop(["level_0"], axis=1)
    # remove duplicates based on index then sort by index
    g["ind"] = g.index
    g = g.drop_duplicates(subset="ind")
    g = g.drop("ind", axis=1)
    g = g.sort_index()
    return g

def dataendclean(df, x, inplace=False, jumptol=1.0):
    """Trims off ends and beginnings of datasets that exceed 2.0 standard deviations of the first and last 50 values

    Args:
        df (pandas.core.frame.DataFrame): Pandas DataFrame
        x (str): Column name of data to be trimmed contained in df
        inplace (bool): if DataFrame should be duplicated
        jumptol (float): acceptable amount of offset in feet caused by the transducer being out of water at time of measurement; default is 1

    Returns:
        (pandas.core.frame.DataFrame) df trimmed data


    This function printmess a message if data are trimmed.
    """
    # Examine Mean Values
    if inplace:
        df = df
    else:
        df = df.copy()

    jump = df[abs(df.loc[:, x].diff()) > jumptol]
    try:
        for i in range(len(jump)):
            if jump.index[i] < df.index[50]:
                df = df[df.index > jump.index[i]]
                print("Dropped from beginning to " + str(jump.index[i]))
            if jump.index[i] > df.index[-50]:
                df = df[df.index < jump.index[i]]
                print("Dropped from end to " + str(jump.index[i]))
    except IndexError:
        print("No Jumps")
    return df
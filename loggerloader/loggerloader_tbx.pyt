from __future__ import absolute_import, division, print_function, unicode_literals
try:
    from loggerloader.loggerloader import *
except:
    from loggerloader import *

from pylab import rcParams
import os
import pandas as pd

rcParams['figure.figsize'] = 15, 10

pd.options.mode.chained_assignment = None

try:
    import arcpy
    arcpy.env.overwriteOutput = True
except ImportError:
    pass


# ---------------ArcGIS Python Toolbox Classes and Functions-------------------------------------------------------------

def parameter(displayName, name, datatype, parameterType='Required', direction='Input', defaultValue=None):
    """The parameter implementation makes it a little difficult to quickly create parameters with defaults. This method
    prepopulates some of these values to make life easier while also allowing setting a default value."""
    # create parameter with a few default properties
    param = arcpy.Parameter(
        displayName=displayName,
        name=name,
        datatype=datatype,
        parameterType=parameterType,
        direction=direction)

    # set new parameter to a default value
    param.value = defaultValue

    # return complete parameter object
    return param


class Toolbox(object):
    def __init__(self):
        self.label = "Loggerloader"
        self.alias = "loggerloader"

        # List of tool classes associated with this toolbox
        self.tools = [SingleTransducerImport, MultBarometerImport, MultTransducerImport, SimpleBaroFix,
                      SimpleBaroDriftFix, XLERead, GapData]


class SingleTransducerImport(object):
    def __init__(self):
        self.label = "Single Transducer Import to SDE"
        self.description = """Imports XLE or CSV file into UGS SDE based on well information, 
        barometric pressure and manual data """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input SDE Connection", "in_conn_file", "DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.5/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter("Well XLE or CSV", "well_file", "DEFile"),
            parameter("Barometer XLE or CSV", "baro_file", "DEFile"),
            parameter("Date of Initial Manual Measurement", "startdate", "Date", parameterType="Optional"),
            parameter("Initial Manual Measurement", "startlevel", "GPDouble"),
            parameter("Date of Final Manual Measurement", "enddate", "Date"),
            parameter("Final Manual Measurement", "endlevel", "GPDouble"),
            parameter("Well Name", "wellname", "GPString"),
            parameter("Transducer Drift Tolerance (ft)", "tol", "GPDouble", defaultValue=0.3),
            parameter("Overide Date Filter?", "ovrd", "GPBoolean", parameterType="Optional"),
            parameter("Create a Chart?", "should_plot", "GPBoolean", parameterType="Optional"),
            parameter("Chart output location", "chart_out", "DEFile", parameterType="Optional", direction="Output")
        ]
        self.parameters[1].filter.list = ['csv', 'xle']
        self.parameters[2].filter.list = ['csv', 'xle']

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal validation is performed.
        This method is called whenever a parameter has been changed."""
        if parameters[0].value and arcpy.Exists(parameters[0].value):
            arcpy.env.workspace = parameters[0].value
            loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

            # use a search cursor to iterate rows
            loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName') if
                         str(row[0]) != 'None' and str(row[0]) != '']

            parameters[7].filter.list = sorted(loc_names)

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.sde_conn = parameters[0].valueAsText
        wellimp.well_file = parameters[1].valueAsText
        wellimp.baro_file = parameters[2].valueAsText
        wellimp.man_startdate = parameters[3].valueAsText
        wellimp.man_start_level = parameters[4].value
        wellimp.man_enddate = parameters[5].valueAsText
        wellimp.man_end_level = parameters[6].value
        wellimp.wellid = parameters[7].valueAsText
        wellimp.tol = parameters[8].value
        wellimp.ovrd = parameters[9].value
        wellimp.should_plot = parameters[10].value
        wellimp.chart_out = parameters[11].valueAsText

        wellimp.one_well()
        printmes(arcpy.GetMessages())
        return


class MultBarometerImport(object):
    def __init__(self):
        self.label = 'Multiple Barometer Transducer Import to SDE'
        self.description = """Imports XLE or CSV file based on well information and barometric pressure """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input SDE Connection", "in_conn_file", "DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.6/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter('Directory Containing Files', 'xledir', 'DEFolder'),
            parameter("Barometer File Matches", "well_files", 'GPValueTable'),
            parameter("Import data into SDE?", "to_import", "GPBoolean",
                      parameterType="Optional", defaultValue=0),
            #parameter("Barometer Compilation csv location", "baro_comp_file", "DEFile",
            #          direction="Output"),
            parameter("Override date filter? (warning: can cause duplicate data.", "ovrd", "GPBoolean",
                      parameterType="Optional", defaultValue=0),
            parameter("Create a Chart?", "should_plot", "GPBoolean", parameterType="Optional"),
            parameter("Chart output location (end with .pdf)", "chart_out", "DEFile", parameterType="Optional",
                      direction="Output"),
            parameter("Create Compiled Excel File with import?", "toexcel", "GPBoolean", defaultValue=0,
                      parameterType="Optional")
        ]
        # self.parameters[2].parameterDependencies = [self.parameters[1].value]
        self.parameters[2].columns = [['GPString', 'xle file'], ['GPString', 'Matching Barometer Name'],
                                      ['GPString', 'Matching Barometer ID']]

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[1].value and parameters[0].value and arcpy.Exists(parameters[1].value):
            if not parameters[2].altered:
                arcpy.env.workspace = parameters[0].value
                loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

                # use a search cursor to iterate rows
                loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName', where_clause='AltLocationID is not Null') if
                             str(row[0]) != 'None' and str(row[0]) != '']
                well_ident = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID', where_clause='AltLocationID is not Null') if
                              str(row[0]) != 'None' and str(row[0]) != '']
                loc_names_simp = [i.upper().replace(" ", "").replace("-", "") for i in loc_names]
                loc_dict = dict(zip(loc_names_simp, loc_names))
                id_dict = dict(zip(well_ident, loc_names))
                getid = dict(zip(loc_names, well_ident))
                serialdict = {'1044546': 'P1001', '1044532': 'P1002', '1044519': 'P1003',
                              '1044531': 'P1004', '1044524': 'P1005', '1044506': 'P1006', '1044545': 'P1007',
                              '1044547': 'P1008', '1044530': 'P1009', '1044508': 'P1010', '1044536': 'P1011',
                              '1044543': 'P1012', '1044544': 'P1013', '1044538': 'P1014', '1044504': 'P1015',
                              '1044535': 'P1016', '1044516': 'P1018', '1044526': 'P1019', '1044517': 'P1020',
                              '1044539': 'P1021', '1044520': 'P1022', '1044529': 'P1023', '1044502': 'P1024',
                              '1044507': 'P1025', '1044528': 'P1026',
                              '1044779': 'SG25 Barometer', '1044788':'Twin Springs Baro',
                              '1046310': 'P1028', '1046323': 'P1029',
                              '1046314': 'P1030', '1046393': 'P1031', '1046394': 'P1033', '1046388': 'P1035',
                              '1046396': 'P1036', '1046382': 'P1037', '1046399': 'P1038', '1046315': 'P1039',
                              '1046392': 'P1040', '1046319': 'P1041', '1046309': 'P1042', '1046398': 'P1043',
                              '1046381': 'P1044', '1046387': 'P1045', '1046390': 'P1046', '1046400': 'P1047',
                              '1044534': 'P1097', '1044548': 'P1049', '1044537': 'P1051', '1046311': 'P1052',
                              '1046377': 'P1053', '1046318': 'P1054', '1046326': 'P1055', '1046395': 'P1056',
                              '1046391': 'P1057', '1046306': 'P1060', '2011070': 'P1061', '2011072': 'P1063',
                              '2011762': 'P1065', '2012196': 'P1070', '2022358': 'P1076', '2006774': 'P1069',
                              '2022498': 'P1071', '2022489': 'P1072', '2010753': 'P1090', '2022490': 'P1073',
                              '2022401': 'P1075', '2022348': 'P2001', '2022496': 'P2002', '2022499': 'P1079',
                              '2022501': 'P1080', '2022167': 'P1081', '1046308': 'P1091', '2011557': 'P1092',
                              '1046384': 'P1093', '1046307': 'P1094', '1046317': 'P1095', '1044541': 'P1096',
                              '1046312': 'P1098', '2037596': 'P2003', '2037610': 'P3001', '2037607': 'P3002',
                              '2006781': 'P3003', '2064855':'Mills Mona Baro', '1038964': 'PW03 Baro',
                              }
                vtab = []
                for file in os.listdir(parameters[1].valueAsText):
                    filetype = os.path.splitext(parameters[1].valueAsText + file)[1]
                    if filetype == '.xle' or filetype == '.csv':
                        nameparts = str(file).split(' ')
                        namepartA = nameparts[0].upper().replace("-", "")
                        namepartB = str(' '.join(nameparts[:-1])).upper().replace(" ", "").replace("-", "")
                        nameparts_alt = str(file).split('_')
                        nameparts_alt2 = str(file).split('.')
                        if len(nameparts_alt) > 3:
                            namepartC = str(' '.join(nameparts_alt[1:-3])).upper().replace(" ", "")
                            namepartD = str(nameparts_alt[-4])

                        # populates default based on matches
                        if namepartA in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartA), getid.get(loc_dict.get(namepartA))])
                        elif namepartB in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartB), getid.get(loc_dict.get(namepartB))])
                        elif len(nameparts_alt) > 3 and namepartC in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartC), getid.get(loc_dict.get(namepartC))])
                        elif len(nameparts_alt) > 3 and namepartD in well_ident:
                            vtab.append([file, id_dict.get(namepartD), namepartD])
                        elif nameparts_alt2[0] in serialdict.keys():
                            vtab.append([file, serialdict.get(nameparts_alt2[0]), getid.get(serialdict.get(nameparts_alt2[0]))])
                        elif nameparts_alt[0] in serialdict.keys():
                            vtab.append([file, serialdict.get(nameparts_alt[0]), getid.get(serialdict.get(nameparts_alt[0]))])
                        else:
                            vtab.append([file, None, None])

                parameters[2].values = vtab

                parameters[2].filters[1].list = sorted(loc_names)

                parameters[2].filters[2].list = sorted(well_ident)

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        printmes("Initiating")
        wellimp = baroimport()
        printmes("Parametizing")

        wellimp.sde_conn = parameters[0].valueAsText
        wellimp.xledir = parameters[1].valueAsText

        if parameters[2].altered:
            wellimp.well_files = [str(f[0]) for f in parameters[2].value]
            wellimp.wellname = [str(f[1]) for f in parameters[2].value]
            wellimp.wellid = [str(f[2]) for f in parameters[2].value]
            wellimp.welldict = dict(zip(wellimp.wellname, wellimp.well_files))
            wellimp.filedict = dict(zip(wellimp.well_files, wellimp.wellname))
            wellimp.idget = dict(zip(wellimp.wellname, wellimp.wellid))
        wellimp.to_import = parameters[3]
        #wellimp.baro_comp_file = parameters[4].value
        wellimp.ovrd = parameters[4].value
        wellimp.should_plot = parameters[5].value
        wellimp.chart_out = parameters[6].valueAsText
        wellimp.toexcel = parameters[7].value
        printmes("Processing")
        wellimp.many_baros()
        printmes(arcpy.GetMessages())
        return


class MultTransducerImport(object):
    def __init__(self):
        self.label = 'Multiple Transducer Import to SDE'
        self.description = """Imports XLE or CSV file based on well information, barometric pressure and manual data """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input SDE Connection", "in_conn_file", "DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.6/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter('Directory Containing Files', 'xledir', 'DEFolder'),
            parameter("Well File Matches", "well_files", 'GPValueTable'),
            parameter("Manual File Location", "man_file", "DEFile"),
            parameter("Constant Stickup?", "isstbl", "GPBoolean", defaultValue=1),
            parameter("Transducer Drift Tolerance (ft)", "tol", "GPDouble", defaultValue=0.3),
            parameter("Beginning Jump Tolerance (ft)", "jumptol", "GPDouble", defaultValue=1.0),
            parameter("Override date filter? (warning: can cause duplicate data.", "ovrd", "GPBoolean",
                      parameterType="Optional", defaultValue=0),
            parameter("Create a Chart?", "should_plot", "GPBoolean", parameterType="Optional"),
            parameter("Chart output location", "chart_out", "DEFile", parameterType="Optional", direction="Output"),
            parameter("Create Compiled Excel File with import?", "toexcel", "GPBoolean", defaultValue=0,
                      parameterType="Optional"),
            parameter("Barometer data API key", "api_token", "GPString",parameterType="Optional")
        ]
        # self.parameters[2].parameterDependencies = [self.parameters[1].value]
        self.parameters[2].columns = [['GPString', 'xle file'], ['GPString', 'Matching Well Name']]

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[1].value and parameters[0].value and arcpy.Exists(parameters[1].value):
            if not parameters[2].altered:
                arcpy.env.workspace = parameters[0].value
                loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

                # use a search cursor to iterate rows
                loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName', where_clause='AltLocationID is not Null') if
                             str(row[0]) != 'None' and str(row[0]) != '']
                well_ident = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID', where_clause='AltLocationID is not Null') if
                              str(row[0]) != 'None' and str(row[0]) != '']
                loc_names_simp = [i.upper().replace(" ", "").replace("-", "") for i in loc_names]
                loc_dict = dict(zip(loc_names_simp, loc_names))
                id_dict = dict(zip(well_ident, loc_names))
                serialdict = {'1044546': 'P1001', '1044532': 'P1002', '1044519': 'P1003',
                              '1044531': 'P1004', '1044524': 'P1005', '1044506': 'P1006', '1044545': 'P1007',
                              '1044547': 'P1008', '1044530': 'P1009', '1044508': 'P1010', '1044536': 'P1011',
                              '1044543': 'P1012', '1044544': 'P1013', '1044538': 'P1014', '1044504': 'P1015',
                              '1044535': 'P1016', '1044516': 'P1018', '1044526': 'P1019', '1044517': 'P1020',
                              '1044539': 'P1021', '1044520': 'P1022', '1044529': 'P1023', '1044502': 'P1024',
                              '1044507': 'P1025', '1044528': 'P1026',
                              '1044779': 'SG25 Barometer', '1044788':'Twin Springs Baro',
                              '1046310': 'P1028', '1046323': 'P1029',
                              '1046314': 'P1030', '1046393': 'P1031', '1046394': 'P1033', '1046388': 'P1035',
                              '1046396': 'P1036', '1046382': 'P1037', '1046399': 'P1038', '1046315': 'P1039',
                              '1046392': 'P1040', '1046319': 'P1041', '1046309': 'P1042', '1046398': 'P1043',
                              '1046381': 'P1044', '1046387': 'P1045', '1046390': 'P1046', '1046400': 'P1047',
                              '1044534': 'P1097', '1044548': 'P1049', '1044537': 'P1051', '1046311': 'P1052',
                              '1046377': 'P1053', '1046318': 'P1054', '1046326': 'P1055', '1046395': 'P1056',
                              '1046391': 'P1057', '1046306': 'P1060', '2011070': 'P1061', '2011072': 'P1063',
                              '2011762': 'P1065', '2012196': 'P1070', '2022358': 'P1076', '2006774': 'P1069',
                              '2022498': 'P1071', '2022489': 'P1072', '2010753': 'P1090', '2022490': 'P1073',
                              '2022401': 'P1075', '2022348': 'P2001', '2022496': 'P2002', '2022499': 'P1079',
                              '2022501': 'P1080', '2022167': 'P1081', '1046308': 'P1091', '2011557': 'P1092',
                              '1046384': 'P1093', '1046307': 'P1094', '1046317': 'P1095', '1044541': 'P1096',
                              '1046312': 'P1098', '2037596': 'P2003', '2037610': 'P3001', '2037607': 'P3002',
                              '2006781': 'P3003', '2064855':'Mills Mona Baro', '1038964': 'PW03 Baro',
                              }
                vtab = []
                for file in os.listdir(parameters[1].valueAsText):
                    filetype = os.path.splitext(parameters[1].valueAsText + file)[1]
                    if filetype == '.xle' or filetype == '.csv':
                        nameparts = str(file).split(' ')
                        namepartA = nameparts[0].upper().replace("-", "")
                        namepartB = str(' '.join(nameparts[:-1])).upper().replace(" ", "").replace("-", "")
                        nameparts_alt = str(file).split('_')
                        nameparts_alt2 = str(file).split('.')
                        if len(nameparts_alt) > 3:
                            namepartC = str(' '.join(nameparts_alt[1:-3])).upper().replace(" ", "")
                            namepartD = str(nameparts_alt[-4])

                        # populates default based on matches
                        if namepartA in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartA)])
                        elif namepartB in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartB)])
                        elif len(nameparts_alt) > 3 and namepartC in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartC)])
                        elif len(nameparts_alt) > 3 and namepartD in well_ident:
                            vtab.append([file, id_dict.get(namepartD)])
                        elif nameparts_alt2[0] in serialdict.keys():
                            vtab.append([file, serialdict.get(nameparts_alt2[0])])
                        else:
                            vtab.append([file, None])

                parameters[2].values = vtab

                parameters[2].filters[1].list = sorted(loc_names)

                if not parameters[11].altered:
                    try:
                        import sys
                        connection_filepath = "G:/My Drive/Python/Pycharm/loggerloader/loggerloader/"
                        sys.path.append(connection_filepath)
                        try:
                            import config
                        except:
                            import loggerloader.config

                        parameters[11].values = config.token
                    except:
                        parameters[11].values = None

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.sde_conn = parameters[0].valueAsText
        wellimp.xledir = parameters[1].valueAsText

        if parameters[2].altered:
            wellimp.well_files = [str(f[0]) for f in parameters[2].value]
            wellimp.wellname = [str(f[1]) for f in parameters[2].value]
            wellimp.welldict = dict(zip(wellimp.wellname, wellimp.well_files))
            wellimp.filedict = dict(zip(wellimp.well_files, wellimp.wellname))
        wellimp.man_file = parameters[3].valueAsText
        wellimp.stbl = parameters[4].value
        wellimp.tol = parameters[5].value
        wellimp.jumptol = parameters[6].value
        wellimp.ovrd = parameters[7].value
        wellimp.should_plot = parameters[8].value
        wellimp.chart_out = parameters[9].valueAsText
        wellimp.toexcel = parameters[10].value
        wellimp.api_token = parameters[11].valueAsText
        wellimp.many_wells()
        printmes(arcpy.GetMessages())
        return


class SimpleBaroFix(object):
    def __init__(self):
        self.label = "Simple Barometer Pressure Removal"
        self.description = """Cleans nonvented transducer data of barometric pressure based on transducer data and barometric pressure. """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Well XLE or CSV", "well_file", "DEFile"),
            parameter("Barometer XLE or CSV", "baro_file", "DEFile"),
            parameter("Output Folder", "save_location", "DEFile", direction="Output")]
        self.parameters[0].filter.list = ['csv', 'xle']
        self.parameters[1].filter.list = ['csv', 'xle']
        self.parameters[2].filter.list = ['csv']

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter"""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.well_file = parameters[0].valueAsText
        wellimp.baro_file = parameters[1].valueAsText
        wellimp.save_location = parameters[2].valueAsText
        wellimp.remove_bp()
        printmes(arcpy.GetMessages())


class SimpleBaroDriftFix(object):
    def __init__(self):
        self.label = "Simple Barometer Pressure and Drift Removal (separate files)"
        self.description = """Cleans nonvented transducer data of barometric pressure based on transducer data and barometric pressure. """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Well XLE or CSV", "well_file", "DEFile"),
            parameter("Barometer XLE or CSV", "baro_file", "DEFile"),
            parameter("Date of Initial Manual Measurement", "startdate", "Date"),
            parameter("Date of Final Manual Measurement", "enddate", "Date"),
            parameter("Initial Manual Measurement", "startlevel", "GPDouble"),
            parameter("Final Manual Measurement", "endlevel", "GPDouble"),
            parameter("Measurement Frequency (minutes)","sampint","GPDouble"),
            parameter("Output File", "save_location", "DEFile", direction="Output"),
            parameter("Create a Chart?", "should_plot", "GPBoolean", parameterType="Optional"),
            parameter("Chart output location (end with .pdf)", "chart_out", "DEFile", parameterType="Optional",
                      direction="Output")
        ]
        self.parameters[0].filter.list = ['csv', 'xle']
        self.parameters[1].filter.list = ['csv', 'xle']
        self.parameters[6].value = 60
        self.parameters[7].filter.list = ['csv']
        # self.parameters[8].filter.list = ['pdf']

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter"""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.well_file = parameters[0].valueAsText
        wellimp.baro_file = parameters[1].valueAsText
        wellimp.man_startdate = parameters[2].valueAsText
        wellimp.man_enddate = parameters[3].valueAsText
        wellimp.man_start_level = parameters[4].value
        wellimp.man_end_level = parameters[5].value
        wellimp.sampint = parameters[6].value
        wellimp.save_location = parameters[7].valueAsText
        wellimp.should_plot = parameters[8].value
        wellimp.chart_out = parameters[9].valueAsText
        wellimp.remove_bp_drift()
        printmes(arcpy.GetMessages())


class XLERead(object):
    def __init__(self):
        self.label = "Read and convert XLE files into .csv files, which can be read by excel"
        self.description = """Reads raw transducer data files and converts them into a standard csv format. """
        self.canRunInBackground = False
        self.parameters = [
            parameter("XLE File", "well_file", "DEFile"),
            parameter("Output location", "save_location", "DEFile", direction="Output"),
        ]
        self.parameters[0].filter.list = ['xle']
        self.parameters[1].filter.list = ['csv']

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter"""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()

        wellimp.well_file = parameters[0].valueAsText
        wellimp.save_location = parameters[1].valueAsText
        wellimp.read_xle()
        printmes(arcpy.GetMessages())

class GapData(object):
    def __init__(self):
        self.label = "Find gaps in time series in an SDE database"
        self.description = """Reads SDE time series data and returns csv with information on gaps. """
        self.canRunInBackground = False
        self.parameters = [
            parameter("Input SDE Connection", "sde_conn", "DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.5/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter("Station Search","searchtype","GPString"),
            parameter("Begin Date", "man_startdate", "Date", parameterType = "Optional"),
            parameter("End Date", "man_enddate", "Date", parameterType="Optional"),
            parameter("Output File", "save_location", "DEFile", direction="Output")
        ]

        self.parameters[1].filter.list = ['all stations','wetland piezometers','snake valley wells','hazards']

    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter"""

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.sde_conn = parameters[0].valueAsText
        wellimp.quer = parameters[1].valueAsText
        wellimp.man_startdate= parameters[2].valueAsText
        wellimp.man_enddate= parameters[3].valueAsText
        wellimp.save_location= parameters[4].valueAsText
        wellimp.find_gaps()
        printmes(arcpy.GetMessages())


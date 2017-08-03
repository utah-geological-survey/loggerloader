from __future__ import absolute_import, division, print_function, unicode_literals
import arcpy
arcpy.env.overwriteOutput = True

import loggerloader # add import
import importlib
try:
    importlib.reload(loggerloader)  # add a forced reload
except:
    reload(loggerloader)
import loggerloader as ll

import os

class Toolbox(object):
    def __init__(self):
        self.label =  "Loggerloader"
        self.alias  = "loggerloader"
        # List of tool classes associated with this toolbox
        self.tools = [SingleTransducerImport]


class SingleTransducerImport(object):
    def __init__(self):
        self.label       = "Single Transducer Import"
        self.description = """Imports XLE or CSV file based on well information, barometric pressure and manual data """
        self.canRunInBackground = False

    def getParameterInfo(self):
        #Define parameter definitions

        # Input Features parameter
        param0 = arcpy.Parameter(
            displayName="Input Sde Connection",
            name="in_conn_file",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        param0.value = "C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.5/ArcCatalog/UGS_SDE.sde".format(os.environ.get('USERNAME'))
        #param0.filter.list = ["Remote Database"]

        # Sinuosity Field parameter
        param1 = arcpy.Parameter(
            displayName="Well XLE or CSV",
            name="well_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="Barometer XLE or CSV",
            name="baro_file",
            datatype="DEFile",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Date of Initial Manual Measurement",
            name="startdate",
            datatype="Date",
            parameterType="Optional",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Date of Final Manual Measurement",
            name="enddate",
            datatype="Date",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Initial Manual Measurement",
            name="startlevel",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Final Manual Measurement",
            name="endlevel",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param7 = arcpy.Parameter(
            displayName="Well ID",
            name="wellname",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        params = [param0, param1, param2, param3, param4, param5, param6, param7]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
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
        sde_conn = parameters[0].valueAsText
        well_file = parameters[1].valueAsText
        baro_file = parameters[2].valueAsText
        man_startdate = parameters[3].valueAsText
        man_enddate = parameters[4].valueAsText
        man_start_level = parameters[5].value
        man_end_level = parameters[6].value
        wellid = parameters[7].valueAsText

        arcpy.env.workspace = sde_conn
        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

        loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName')]
        loc_ids = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID')]

        iddict = dict(zip(loc_names,loc_ids))

        if man_startdate  in ["#", "", None]:
            man_startdate, man_start_level, wlelev = ll.find_extreme(wellid)

        ll.imp_one_well(well_file, baro_file, man_startdate, man_enddate, man_start_level, man_end_level, sde_conn, iddict.get(wellid))

        arcpy.AddMessage('Well Imported!')

        return
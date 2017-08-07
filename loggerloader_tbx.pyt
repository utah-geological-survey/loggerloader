from __future__ import absolute_import, division, print_function, unicode_literals
import arcpy
arcpy.env.overwriteOutput = True
import pandas as pd
import loggerloader as ll

import os

class wellimport(object):

    def __init__(self):
        self.sde_conn = None
        self.well_file = None
        self.baro_file = None
        self.man_startdate = None
        self.man_enddate = None
        self.man_start_level = None
        self.man_end_level = None
        self.wellid = None
        self.xledir = None
        self.well_files = None
        self.wellname = None
        self.welldict = None
        self.man_file = None

    def one_well(self):

        arcpy.env.workspace = self.sde_conn
        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

        loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName')]
        loc_ids = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'AltLocationID')]

        iddict = dict(zip(loc_names,loc_ids))

        if self.man_startdate  in ["#", "", None]:
            self.man_startdate, self.man_start_level, wlelev = ll.find_extreme(self.wellid)

        ll.imp_one_well(self.well_file, self.baro_file, self.man_startdate, self.man_enddate, self.man_start_level,
                        self.man_end_level, self.sde_conn, iddict.get(self.wellid))

        arcpy.AddMessage('Well Imported!')

        return

    def many_wells(self):

        arcpy.env.workspace = self.sde_conn
        loc_table = "UGGP.UGGPADMIN.UGS_NGWMN_Monitoring_Locations"

        field_names = ['LocationID', 'LocationName', 'LocationType', 'LocationDesc', 'AltLocationID', 'Altitude',
                       'AltitudeUnits', 'WellDepth', 'SiteID', 'Offset', 'LoggerType', 'BaroEfficiency',
                       'BaroEfficiencyStart', 'BaroLoggerType']
        df = pd.DataFrame(columns=field_names)

        # use a search cursor to iterate rows
        search_cursor = arcpy.da.SearchCursor(loc_table, field_names)

        # iterate the rows
        for row in search_cursor:
            # combine the field names and row items together, and append them
            df = df.append(dict(zip(field_names, row)), ignore_index=True)

        iddict = dict(zip(df['LocationName'].values,df['AltLocationID'].values))
        wellidlist = [iddict.get(well) for well in self.wellname]
        well_table = df.set_index(['AltLocationID'])
        namedict = dict(zip(df['AltLocationID'].values,df['LocationName'].values))
        # import barometric data
        barolist = well_table[well_table['LocationType']=='Barometer'].index

        bardf = {}
        for bar in barolist:
            if bar in wellidlist:
                barfile = self.welldict.get(namedict.get(bar))

                bardf[bar] = ll.new_trans_imp(self.xledir+"/"+barfile)
                ll.upload_bp_data(bardf[bar],bar)
        arcpy.AddMessage('Barometers Imported')

        man = pd.read_csv(self.man_file)

        for i in range(len(wellidlist)):

            if well_table.loc[wellidlist[i],'LocationType'] == 'Well':
                ll.simp_imp_well(well_table, self.xledir+"/"+self.welldict.get(namedict.get(str(wellidlist[i]))),bardf,wellidlist[i], man)
                arcpy.AddMessage("Well {:} imported".format(well_table.loc[wellidlist[i], 'LocationName']))
        return

def parameter(displayName, name, datatype, parameterType='Required', direction='Input', defaultValue=None):
    '''
    The parameter implementation makes it a little difficult to
    quickly create parameters with defaults. This method
    prepopulates some of these values to make life easier while
    also allowing setting a default value.
    '''
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
        self.label =  "Loggerloader"
        self.alias  = "loggerloader"
        # List of tool classes associated with this toolbox
        self.tools = [SingleTransducerImport, MultTransducerImport]


class SingleTransducerImport(object):
    def __init__(self):
        self.label = "Single Transducer Import"
        self.description = """Imports XLE or CSV file based on well information, barometric pressure and manual data """
        self.canRunInBackground = False
        self.parameters=[
            parameter("Input SDE Connection","in_conn_file","DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.5/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter("Well XLE or CSV","well_file","DEFile"),
            parameter("Barometer XLE or CSV","baro_file","DEFile"),
            parameter("Date of Initial Manual Measurement","startdate","Date",parameterType="Optional"),
            parameter("Date of Final Manual Measurement","enddate","Date"),
            parameter("Initial Manual Measurement","startlevel","GPDouble"),
            parameter("Final Manual Measurement","endlevel","GPDouble"),
            parameter("Well Name","wellname","GPString")]
        self.parameters[1].filter.list = ['csv','xle']
        self.parameters[2].filter.list = ['csv', 'xle']

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
        wellimp.man_enddate = parameters[4].valueAsText
        wellimp.man_start_level = parameters[5].value
        wellimp.man_end_level = parameters[6].value
        wellimp.wellid = parameters[7].valueAsText


        wellimp.one_well()

        return

class MultTransducerImport(object):

    def __init__(self):
        self.label = 'Multiple Transducer Import'
        self.description = """Imports XLE or CSV file based on well information, barometric pressure and manual data """
        self.canRunInBackground = False
        self.parameters=[
            parameter("Input SDE Connection","in_conn_file","DEWorkspace",
                      defaultValue="C:/Users/{:}/AppData/Roaming/ESRI/Desktop10.5/ArcCatalog/UGS_SDE.sde".format(
                          os.environ.get('USERNAME'))),
            parameter('Directory Containing Files', 'xledir', 'DEFolder'),
            parameter("Well File Matches","well_files",'GPValueTable'),
            parameter("Manual File Location","man_file","DEFile")]
        #self.parameters[2].parameterDependencies = [self.parameters[1].value]
        self.parameters[2].columns = [['GPString','xle file'],['GPString','Matching Well Name']]

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
                loc_names = [str(row[0]) for row in arcpy.da.SearchCursor(loc_table, 'LocationName') if
                             str(row[0]) != 'None' and str(row[0]) != '']

                vtab = []
                for file in os.listdir(parameters[1].valueAsText):
                    filetype = os.path.splitext(parameters[1].valueAsText + file)[1]
                    if filetype == '.xle' or filetype == '.csv':
                        loc_names_simp = [i.upper().replace(" ", "").replace("-", "") for i in loc_names]
                        loc_dict = dict(zip(loc_names_simp,loc_names))
                        nameparts = str(file).split(' ')
                        namepartA = nameparts[0].upper().replace("-", "")
                        namepartB = str(' '.join(nameparts[:-1])).upper().replace(" ", "").replace("-","")

                        # populates default based on matches
                        if namepartA in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartA)])
                        elif namepartB in loc_names_simp:
                            vtab.append([file, loc_dict.get(namepartB)])
                        else:
                            vtab.append([file,None])

                parameters[2].values = vtab

                parameters[2].filters[1].list = sorted(loc_names)

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        wellimp = wellimport()
        wellimp.sde_conn = parameters[0].valueAsText
        wellimp.xledir = parameters[1].valueAsText

        if  parameters[2].altered:
               wellimp.well_files = [str(f[0]) for f in parameters[2].value]
               wellimp.wellname = [str(f[1]) for f in parameters[2].value]
               wellimp.welldict = dict(zip(wellimp.wellname, wellimp.well_files))

        wellimp.man_file = parameters[3].valueAsText

        wellimp.many_wells()
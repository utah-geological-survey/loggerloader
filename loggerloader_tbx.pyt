from __future__ import absolute_import, division, print_function, unicode_literals
import arcpy
arcpy.env.overwriteOutput = True
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.ticker as tick
import loggerloader as ll
import datetime
import os
from pylab import rcParams
rcParams['figure.figsize'] = 15, 10

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
        self.filedict = None
        self.man_file = None
        self.save_location = None
        self.should_plot = None
        self.chart_out = None

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

    def remove_bp(self):

        well = ll.new_trans_imp(self.well_file)
        baro = ll.new_trans_imp(self.baro_file)

        df = ll.well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl', vented=False,
                        sampint=60)

        df.to_csv(self.save_location)

    def remove_bp_drift(self):

        well = ll.new_trans_imp(self.well_file)
        baro = ll.new_trans_imp(self.baro_file)

        man = pd.DataFrame(
            {'DateTime': [self.man_startdate, self.man_enddate],
             'MeasuredDTW': [self.man_start_level*-1, self.man_end_level*-1]}).set_index('DateTime')

        corrwl = ll.well_baro_merge(well, baro, barocolumn='Level', wellcolumn='Level', outcolumn='corrwl', vented=False,
                        sampint=60)

        dft = ll.fix_drift(corrwl, man, meas='corrwl', manmeas='MeasuredDTW')
        drift = round(float(dft[1]['drift'].values[0]), 3)

        arcpy.AddMessage("Drift is {:} feet".format(drift))
        dft[0].to_csv(self.save_location)

        if self.should_plot:
            pdf_pages = PdfPages(self.chart_out)
            plt.figure()
            # plot data
            df = dft[0]
            y1 = df['DTW_WL'].values
            y2 = df['barometer'].values
            x1 = df.index.values
            x2 = df.index.values

            x4 = man.index
            y4 = man['MeasuredDTW']
            fig, ax1 = plt.subplots()
            plt.xticks(rotation=70)
            ax1.scatter(x4, y4, color='purple')
            ax1.plot(x1, y1, color='blue', label='Water Level')
            ax1.set_ylabel('Water Level Elevation', color='blue')
            ax1.set_ylim(min(y1), max(y1))
            y_formatter = tick.ScalarFormatter(useOffset=False)
            ax1.yaxis.set_major_formatter(y_formatter)
            ax2 = ax1.twinx()
            ax2.set_ylabel('Barometric Pressure (ft)', color='red')
            ax2.plot(x2, y2, color='red', label='Barometric pressure (ft)')
            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1 + h2, l1 + l2, loc=3)
            plt.xlim(df.first_valid_index() - datetime.timedelta(days=3),
                     df.last_valid_index() + datetime.timedelta(days=3))

            pdf_pages.savefig(fig)
            plt.close()
            pdf_pages.close()

    def get_ftype(self,x):
        if x[1] == 'Solinst':
            ft = '.xle'
        else:
            ft = '.csv'
        return self.filedict.get(x[0]+ft)

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
        welltable = df.set_index(['AltLocationID'])
        namedict = dict(zip(df['AltLocationID'].values,df['LocationName'].values))
        # import barometric data
        barolist = welltable[welltable['LocationType']=='Barometer'].index
        arcpy.AddMessage('Barometers in this file: {:}'.format(barolist))

        xles = ll.xle_head_table(self.xledir + '/')
        arcpy.AddMessage('xles examined')
        csvs = ll.csv_info_table(self.xledir + '/')
        arcpy.AddMessage('csvs examined')
        file_info_table = pd.concat([xles, csvs[0]])
        arcpy.AddMessage(file_info_table.columns)
        file_info_table['WellID'] = file_info_table[['fileroot','trans type']].apply(lambda x: self.get_ftype(x),1)
        well_table = pd.merge(welltable, file_info_table, left_index=True, right_on = 'WellID', how='left')
        well_table.to_csv(self.xledir + '/file_info_table.csv')
        arcpy.AddMessage("Header Table with well information created at {:}/file_info_table.csv".format(self.xledir))
        maxtime = max(pd.to_datetime(file_info_table['Stop_time']))
        mintime = min(pd.to_datetime(file_info_table['Start_time']))
        arcpy.AddMessage("Data span from {:} to {:}.".format(mintime,maxtime))

        baro_out = {}
        for bar in barolist:
            if bar in wellidlist:
                barfile = self.welldict.get(namedict.get(bar))

                df = ll.new_trans_imp(self.xledir+"/"+barfile)
                ll.upload_bp_data(df,bar)
                baro_out[bar] = ll.get_location_data(bar, mintime, maxtime + datetime.timedelta(days=1))
                arcpy.AddMessage('Barometer {:} Imported'.format(namedict.get(bar)))

        man = pd.read_csv(self.man_file)

        for i in range(len(wellidlist)):

            if well_table.loc[wellidlist[i],'LocationType'] == 'Well':
                ll.simp_imp_well(well_table, self.xledir+"/"+self.welldict.get(namedict.get(str(wellidlist[i]))),
                                 baro_out, wellidlist[i], man)
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
        self.tools = [SingleTransducerImport, MultTransducerImport, SimpleBaroFix, SimpleBaroDriftFix]


class SingleTransducerImport(object):
    def __init__(self):
        self.label = "Single Transducer Import to SDE"
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
        self.label = 'Multiple Transducer Import to SDE'
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
               wellimp.filedict = dict(zip(wellimp.well_files, wellimp.wellname))
        wellimp.man_file = parameters[3].valueAsText

        wellimp.many_wells()

class SimpleBaroFix(object):
    def __init__(self):
        self.label = "Simple Barometer Pressure Removal"
        self.description = """Cleans nonvented transducer data of barometric pressure based on transducer data and barometric pressure. """
        self.canRunInBackground = False
        self.parameters=[
            parameter("Well XLE or CSV","well_file","DEFile"),
            parameter("Barometer XLE or CSV","baro_file","DEFile"),
            parameter("Output Folder","save_location","DEFile",direction="Output")]
        self.parameters[0].filter.list = ['csv','xle']
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

class SimpleBaroDriftFix(object):
    def __init__(self):
        self.label = "Simple Barometer Pressure and Drift Removal"
        self.description = """Cleans nonvented transducer data of barometric pressure based on transducer data and barometric pressure. """
        self.canRunInBackground = False
        self.parameters=[
            parameter("Well XLE or CSV","well_file","DEFile"),
            parameter("Barometer XLE or CSV","baro_file","DEFile"),
            parameter("Date of Initial Manual Measurement","startdate","Date"),
            parameter("Date of Final Manual Measurement","enddate","Date"),
            parameter("Initial Manual Measurement","startlevel","GPDouble"),
            parameter("Final Manual Measurement","endlevel","GPDouble"),
            parameter("Output Folder","save_location","DEFile",direction="Output"),
            parameter("Create a Chart?","should_plot","GPBoolean",parameterType="Optional"),
            parameter("Chart output location","chart_out","DEFile",parameterType="Optional",direction="Output")
        ]
        self.parameters[0].filter.list = ['csv','xle']
        self.parameters[1].filter.list = ['csv', 'xle']
        self.parameters[6].filter.list = ['csv']


    def getParameterInfo(self):
        """Define parameter definitions; http://joelmccune.com/lessons-learned-and-ideas-for-python-toolbox-coding/"""
        return self.parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter"""
        if parameters[7].value and parameters[0].value and arcpy.Exists(parameters[7].value):

            self.parameters[8].filter.list = ['pdf']
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
        wellimp.save_location = parameters[6].valueAsText
        wellimp.should_plot = parameters[7].value
        wellimp.chart_out = parameters[8].valueAsText
        wellimp.remove_bp_drift()
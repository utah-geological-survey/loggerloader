import arcpy

class Toolbox(object):
    def __init__(self):
        self.label =  "Loggerloader"
        self.alias  = "loggerloader"

        # List of tool classes associated with this toolbox
        self.tools = [SingleTransducerImport]

class SingleTransducerImport(object):
    def __init__(self):
        self.label       = "Single Transducer Import"
        self.description = "Imports XLE or CSV file " + \
                           "based on well information, barometric pressure and manual data "

    def getParameterInfo(self):
        #Define parameter definitions

        # Input Features parameter
        sde_conn = arcpy.Parameter(
            displayName="Input Sde Connection",
            name="in_conn_file",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        in_features.filter.list = ["Polyline"]

        # Sinuosity Field parameter
        sinuosity_field = arcpy.Parameter(
            displayName="Sinuosity Field",
            name="sinuosity_field",
            datatype="Field",
            parameterType="Optional",
            direction="Input")

        sinuosity_field.value = "sinuosity"

        # Derived Output Features parameter
        out_features = arcpy.Parameter(
            displayName="Output Features",
            name="out_features",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output")

        out_features.parameterDependencies = [in_features.name]
        out_features.schema.clone = True

        parameters = [in_features, sinuosity_field, out_features]

        return parameters

    def isLicensed(self): #optional
        return True

    def updateParameters(self, parameters): #optional
        if parameters[0].altered:
            parameters[1].value = arcpy.ValidateFieldName(parameters[1].value,
                                                          parameters[0].value)
        return

    def updateMessages(self, parameters): #optional
        return

    def execute(self, parameters, messages):
        inFeatures  = parameters[0].valueAsText
        fieldName   = parameters[1].valueAsText

        if fieldName in ["#", "", None]:
            fieldName = "sinuosity"

        arcpy.AddField_management(inFeatures, fieldName, 'DOUBLE')

        expression = '''
import math
def getSinuosity(shape):
    length = shape.length
    d = math.sqrt((shape.firstPoint.X - shape.lastPoint.X) ** 2 +
                  (shape.firstPoint.Y - shape.lastPoint.Y) ** 2)
    return d/length
'''

        arcpy.CalculateField_management(inFeatures,
                                        fieldName,
                                        'getSinuosity(!shape!)',
                                        'PYTHON_9.3',
                                        expression)
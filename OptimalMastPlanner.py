# -*- coding: utf-8 -*-
"""
OptimalMastPlanner QGIS Plugin

This plugin provides tools for the optimal placement and analysis of
meteorological masts and wind turbines.

It processes TRIX files, generates spatial outputs (CSV, shapefiles, rasters),
and supports visualization and reporting in QGIS.

Main Features:
- Reads and processes TRIX files containing uncertainty and site data.
- Assigns unique IDs to turbines and met masts for easy reference.
- Generates CSV outputs for full data, grouped/averaged mast points, unique turbines, and unique masts.
- Creates shapefiles for met mast points and turbine locations.
- Produces IDW (Inverse Distance Weighted) raster heatmaps for uncertainty visualization.
- Provides a user interface for selecting input files, output directories, and project settings.
- Integrates with QGIS to add layers, style them, and manage visibility.
- Offers tools to highlight the best single or pair of met masts based on uncertainty metrics.

Workflow:
1. User selects a TRIX file and output directory via the plugin dialog.
2. The plugin processes the TRIX file, aggregates and analyzes the data, and generates all outputs.
3. Outputs are saved in a timestamped results folder within the chosen directory.
4. Layers are added to the QGIS project for visualization.
5. Additional tools allow highlighting of optimal met mast locations.

This script contains the main plugin class, UI integration, and all processing logic.
"""
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .OptimalMastPlanner_dialog import OptimalMastPlannerDialog
import os.path
import warnings

import math
import pandas as pd
import csv
import processing
from datetime import datetime, UTC
import numpy as np
from itertools import combinations
import io
# Suppress deprecation warnings from QGIS
warnings.filterwarnings("ignore", category=DeprecationWarning)

class OptimalMastPlanner:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'OptimalMastPlanner_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&OptimalMastPlanner')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.cities_by_country = None
        self.output_direcory = None
        self.df_data = None
        
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('OptimalMastPlanner', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def save_as_shp(self, vl, outpath, crs):
    
        params = {
            'INPUT': vl,
            'OUTPUT': outpath,
            'ENCODING': 'UTF-8'
        }
        
        result = processing.run("native:savefeatures", params)
        return result['OUTPUT']  # Returns the saved file path
            
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/OptimalMastPlanner/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&OptimalMastPlanner'),
                action)
            self.iface.removeToolBarIcon(action)

    def display_info(self, message: str):
        """
        Display info message in message bar
        :param message: String
        :return:
        """
        messageBar = self.iface.messageBar().createMessage(message)
        self.iface.messageBar().pushWidget(messageBar, level=Qgis.Info, duration=3)

    def display_warning(self, message: str):
        """
        Display warning message in message bar
        :param message: String
        :return:
        """
        messageBar = self.iface.messageBar().createMessage(message)
        self.iface.messageBar().pushWidget(messageBar, level=Qgis.Warning, duration=3)

    def display_success(self, message: str):
        """
        Display success message in message bar
        :param message: String
        :return:
        """
        messageBar = self.iface.messageBar().createMessage(message)
        self.iface.messageBar().pushWidget(messageBar, level=Qgis.Success, duration=3)

    def style_point_layer(self, layer, style, color, size) :
            
        # Apply basic styling
        symbol = QgsMarkerSymbol.createSimple({
                'name': style,
                'color': color,
                'size': size
        })
        layer.renderer().setSymbol(symbol)   
            
        return layer
        
    def selectOutputDir(self): 
    
        folder = str(QFileDialog.getExistingDirectory(
            self.dlg, 
            "Select Output Directory"
        ))
        
        self.dlg.out_dir.setText(folder)  
        
    def selectOutputFile(self):
        filename,_filter=QFileDialog.getOpenFileName(self.dlg,"select output file","",'TXT(*.txt)')
        self.dlg.trix_file.setText(filename)
        win=self.iface.mainWindow()
                
        if not filename or filename=='':
            return

    def set_layer_visibility(self, layer, visible=True):
        """
        Sets the visibility of a layer in the QGIS canvas.
        
        Args:
            layer (QgsVectorLayer): The layer to modify.
            visible (bool): Whether the layer should be visible (default: True).
        """
        if not layer:
            print("Error: Invalid layer provided.")
            return
        
        root = QgsProject.instance().layerTreeRoot()
        layer_node = root.findLayer(layer.id())
        
        if layer_node:
            layer_node.setItemVisibilityChecked(visible)
            print(f"Visibility for '{layer.name()}' set to {'ON' if visible else 'OFF'}.")
        else:
            print("Layer not found in the project.")
       
    def layer_exists(self, layer_name):
        """Check if OSM basemap layer already exists in the project."""
        for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == layer_name:
                    return True
        return False

    def add_osm_basemap(self):
        """Add OpenStreetMap XYZ tile layer to the project."""
        
        if not self.layer_exists('OpenStreetMap') :
        
            # Create proper XYZ tile connection parameters
            osm_uri = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
            
            # Create the raster layer
            osm_layer = QgsRasterLayer(osm_uri, "OpenStreetMap", "wms")
            
            if osm_layer.isValid():
                # Set some display properties
                osm_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))  # Web Mercator
                QgsProject.instance().addMapLayer(osm_layer)
                
                # Optionally move to bottom of layer stack
                root = QgsProject.instance().layerTreeRoot()
                layer_node = root.findLayer(osm_layer.id())
                if layer_node:
                    layer_clone = layer_node.clone()
                    root.insertChildNode(0, layer_clone)
                    root.removeChildNode(layer_node)
                
                print("OSM basemap added successfully!")
                return True
            else:
                print("Failed to load OSM basemap. Error:", osm_layer.error().message())
                return False
            
    def create_completer(self, list_items):
        
        completer = QCompleter(list_items)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        return completer
        
    def fill_countries(self):

        country_list = self.cities_by_country['country'].dropna().unique()
        self.dlg.country_input.setCompleter(self.create_completer(country_list))

    def update_cities(self):
        
        country = self.dlg.country_input.currentText()
        self.dlg.city_input.clear()
        countries = self.cities_by_country
        cities = countries[countries['country'] == country]['city']
        self.dlg.city_input.addItems(cities)
        self.dlg.city_input.setCompleter(self.create_completer(cities))
        
    def get_coordinates(self, country_name, city_name):
        
        df = self.cities_by_country
        result = df[(df['country'] == country_name) & (df['city'] == city_name)]
        
        if not result.empty:
            x = result['lng'].values[0]
            y = result['lat'].values[0]
            return [x, y]
        else:
            return None

    def get_utm_crs_from_lonlat(self, lon, lat, precision=5):

        zone_number = math.floor((lon + 180) / 6) + 1

        if lat >= 0:
            hemisphere = 'N'  
            crs_code = f"EPSG:326{zone_number:02d}"  # UTM CRS for Northern Hemisphere (326)
        else:
            hemisphere = 'S'  # Southern Hemisphere
            crs_code = f"EPSG:327{zone_number:02d}"  # UTM CRS for Southern Hemisphere (327)

        # Handle precision and adjust if closer to a boundary (zone edge cases)
        if precision > 5:  # Check if we want a more precise CRS based on decimals

            longitude_decimal_part = lon - math.floor(lon)
            if longitude_decimal_part >= 5:  # Close to the edge of a zone
                zone_number = zone_number + 1 if lon > 0 else zone_number - 1
                crs_code = f"EPSG:326{zone_number:02d}" if lat >= 0 else f"EPSG:327{zone_number:02d}"

        if lat > 84 or lat < -80:
            return None  

        return crs_code                  
            
    def get_crs(self):
        coords = self.get_coordinates(self.dlg.country_input.currentText(),self.dlg.city_input.currentText())
        return self.get_utm_crs_from_lonlat(coords[0], coords[1])
            
    def create_turbine_shapefile(self, csv_path, outpath, crs_epsg):
        """
        Creates a turbine shapefile directly from CSV data.
        
        :param csv_path: Path to CSV file containing turbine data
        :param outpath: Output path for the shapefile
        :param crs_epsg: EPSG code for the CRS
        """
        # Read CSV data
        turbines = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                turbines.append({
                    'x': float(row['WTG X [m]']),
                    'y': float(row['WTG Y [m]']),
                    'z': float(row['WTG Z [m]']),
                    'rix': float(row['WTG RIX [%]'])
                })
        
        # Create vector layer
        vl = QgsVectorLayer(f"Point?crs={crs_epsg}", "wind_turbines", "memory")
        pr = vl.dataProvider()
        
        # Add fields
        pr.addAttributes([
            QgsField("id", QMetaType.Int, "integer"),  # Integer field (32-bit)
            QgsField("x_coord", QMetaType.Double, "double", 20, 6),  # 20 digits, 6 decimal places
            QgsField("y_coord", QMetaType.Double, "double", 20, 6),
            QgsField("elevation", QMetaType.Double, "double", 10, 2),  # 10 digits, 2 decimal places
            QgsField("rix", QMetaType.Double, "double", 10, 4),  # 10 digits, 4 decimal places
            QgsField("turbine_id", QMetaType.QString, "text", 50)  # Text field with max 50 chars
        ])
        vl.updateFields()
        
        # Add features
        for idx, turbine in enumerate(turbines, start=1):
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(turbine['x'], turbine['y'])
            ))
            feat.setAttributes([
                idx,
                turbine['x'],
                turbine['y'],
                turbine['z'],
                turbine['rix'],
                f"WTG_{idx:02d}"
            ])
            pr.addFeature(feat)
        
        # Save to shapefile
        noerror = self.save_as_shp(vl, outpath, crs_epsg)
        
        if noerror :
            layer = QgsVectorLayer(outpath, "Wind Turbines", "ogr")
            layer = self.style_point_layer(layer, 'star','red', '4')   
            QgsProject.instance().addMapLayer(layer)
            return layer
  
  
    def create_met_mast_layer(self, text_file_path, crs, outpath):
        
        # Create the point layer (shapefile or memory layer)
        fields = [
            QgsField('Reference_Point_X_m', QMetaType.Double, 'double', 20, 6),
            QgsField('Reference_Point_Y_m', QMetaType.Double, 'double', 20, 6),
            QgsField('Reference_Point_Z_m', QMetaType.Double, 'double', 20, 6),
            QgsField('Reference_RIX_percent', QMetaType.Double, 'double', 10, 2),
            QgsField('RSS_uncertainty_increases_percent', QMetaType.Double, 'double', 10, 2)
        ]
        
        # Create memory layer (type=QGIS.Point)
        vector_mast_layer = QgsVectorLayer("Point?crs="+crs, "Met Mast Points", "memory")
        
        # Set fields (attributes)
        vector_mast_layer.dataProvider().addAttributes(fields)
        vector_mast_layer.updateFields()

        # Open the CSV file and read it
        with open(text_file_path, 'r') as file:
            reader = csv.DictReader(file)
            features = []
            for row in reader:
                x = float(row['Reference Point X [m]'])
                y = float(row['Reference Point Y [m]'])
                z = float(row['Reference Point Z [m]'])
                rix = float(row['Reference RIX [%]'])
                # Only use new RSS uncertainty
                uncertainty = float(row['adj_RSS_uncertainty'])
                point = QgsPointXY(x, y)
                point_geometry = QgsGeometry.fromPointXY(point)
                feature = QgsFeature()
                feature.setGeometry(point_geometry)
                feature.setAttributes([x, y, z, rix, uncertainty])
                features.append(feature)
            vector_mast_layer.dataProvider().addFeatures(features)
            vector_mast_layer.updateExtents()
        noerror = self.save_as_shp(vector_mast_layer, outpath, crs)
        if noerror:
            layer = QgsVectorLayer(outpath, "Met Mass Points", "ogr")
            layer = self.style_point_layer(layer, 'circle','magenta', '1.8')   
            return layer

    def generate_idw_raster(self, vector_mast_layer, vector_mast_path, output_idw_raster):

        
        param = {
            'INTERPOLATION_DATA':'{}::~::0::~::4::~::0'.format(vector_mast_path),
            'DISTANCE_COEFFICIENT':2,
            'EXTENT':vector_mast_layer.extent(),
            'PIXEL_SIZE':5,
            'OUTPUT': output_idw_raster
        }
        raster_layer = processing.run("qgis:idwinterpolation",  param)['OUTPUT']
    

    def apply_color_ramp(self, raster_layer):

        provider = raster_layer.dataProvider()
        stats = provider.bandStatistics(1)
        min_value = stats.minimumValue
        max_value = stats.maximumValue
        num_classes =5
        class_interval = (max_value - min_value) / (num_classes - 1)

        shader = QgsRasterShader()
        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)
        color_ramp_name = 'RdYlGn'

        color_ramp = QgsStyle().defaultStyle().colorRamp(color_ramp_name)
        color_ramp_items = []
        
        for i in range(num_classes):
        
            value = min_value + i * class_interval
            # Check if the color ramp is 'RdYIGn' to invert it
            if color_ramp_name == 'RdYlGn':
            
                position = 1.0 - (float(i) / (num_classes - 1))
                #position = float(i) / (num_classes - 1)
                color = color_ramp.color(position)
                color_ramp_items.append(QgsColorRampShader.ColorRampItem(value, color, f"{value:.2f}"))
                color_ramp_shader.setColorRampItemList(color_ramp_items)
         
        color_ramp_shader.setColorRampItemList(color_ramp_items)
         
        shader.setRasterShaderFunction(color_ramp_shader)
         
        # Apply the shader to the raster layer with the correct min and max values
        renderer = QgsSingleBandPseudoColorRenderer(raster_layer.dataProvider(), 1, shader)
        renderer.setClassificationMin(min_value)
        renderer.setClassificationMax(max_value)
        raster_layer.setRenderer(renderer)
        raster_layer.triggerRepaint()

        return raster_layer
        
        
    def save_rendred_raster0(self, raster_layer, out_colorized_raster_path):
    
    
        extent = raster_layer.extent()
        width, height = raster_layer.width(), raster_layer.height()
        renderer = raster_layer.renderer()
        provider=raster_layer.dataProvider()
        
        crs = raster_layer.crs()
        
        pipe = QgsRasterPipe()
        pipe.set(provider.clone())
        pipe.set(renderer.clone())
        
        file_writer = QgsRasterFileWriter(out_colorized_raster_path)
        
        file_writer.writeRaster(pipe,
                                width,
                                height,
                                extent,
                                crs)

    def save_rendred_raster(self, raster_layer, out_colorized_raster_path):
        """
        Save a raster layer with its current renderer (colormap/style) applied.
        Uses QGIS Processing (GDAL) instead of deprecated QgsRasterFileWriter.
        
        Args:
            raster_layer: QgsRasterLayer to export
            out_colorized_raster_path: Output file path (e.g., .tif, .png)
        
        Returns:
            Path to the saved raster if successful
        """
        params = {
            'INPUT': raster_layer,
            'TARGET_CRS': raster_layer.crs(),
            'OUTPUT': out_colorized_raster_path
        }
        
        try:
            # Use GDAL Translate for maximum control
            result = processing.run("gdal:translate", params)
            return result['OUTPUT']
        
        except Exception as e:
            raise Exception(f"Failed to export raster: {str(e)}")
            
            
    def highlight_best_met(self) :
    
        output_best_pair_shp_path = os.path.join(self.output_direcory,'Optimal_pair_mest_mast.shp')
        output_best_single_shp_path = os.path.join(self.output_direcory,'Optimal_single_mest_mast.shp')
        output_mast_points_file = os.path.join(self.output_direcory,'mast_points_data.csv')
        
        input_trix_file = self.dlg.trix_file.text()
        crs = self.dlg.crs.crs().authid()

        if str(crs) == '' :
            if self.dlg.country_input.currentText()=='' or self.dlg.city_input.currentText()=='' :
                self.display_warning('Specify Project Country/City OR CRS')
            else:
                crs = self.get_crs()
            
            if str(crs) != '' :   
                choice = self.dlg.comboBox.currentText()
                if choice == 'Single' :
                    if not self.layer_exists('Optimal_single_mest_mast') :
                        #self.display_info('Generating Optimal_single_mest_mast')
                        self.process_best_single_met_mast(output_mast_points_file, output_best_single_shp_path, crs)
                        self.display_success('Optimal_single_mest_mast Successfully Generated')
                    else :
                        self.display_warning('Optimal_single_mest_mast Already Generated')     
                        
                elif choice == 'Pair'  :
                    if not self.layer_exists('Optimal_pair_mest_mast') :
                        #self.display_info('Generating Optimal_pair_mest_mast')
                        self.process_best_two_met_mast(input_trix_file, output_best_pair_shp_path, crs)
                        self.display_success('Optimal_pair_mest_mast Successfully Generated')
                    else :
                        self.display_warning('Optimal_pair_mest_mast Already Generated')
                else:
                    self.display_warning('Select an option for optimal Mest Mast')
                    
    def process_best_single_met_mast(self, file_path, output_shapefile_path, crs):

        
        # Step 1: Load the data into a DataFrame
        data = pd.read_csv(file_path, delimiter=',')  # Assuming the delimiter is a comma, change if needed

        # Step 2: Find the row with the lowest RSS of uncertainty increases [%]
        if 'adj_RSS_uncertainty' in data.columns:
            lowest_rss_row = data.loc[data['adj_RSS_uncertainty'].idxmin()]
            rss_col = 'adj_RSS_uncertainty'
        else:
            lowest_rss_row = data.loc[data['RSS of uncertainty increases [%]'].idxmin()]
            rss_col = 'RSS of uncertainty increases [%]'

        # Step 3: Create a point feature with the coordinates
        point = QgsPointXY(lowest_rss_row['Reference Point X [m]'], lowest_rss_row['Reference Point Y [m]'])

        # Create a QgsFeature and set its geometry to the point
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))

        # Step 4: Create a new memory layer to hold this point
        fields = QgsFields()
        fields.append(QgsField("ref_x", QMetaType.Double, "double", 20, 6, "Reference Point X [m]"))
        fields.append(QgsField("ref_y", QMetaType.Double, "double", 20, 6, "Reference Point Y [m]"))
        fields.append(QgsField("ref_z", QMetaType.Double, "double", 20, 6, "Reference Point Z [m]"))
        fields.append(QgsField("rix_pct", QMetaType.Double, "double", 10, 2, "Reference RIX [%]"))
        fields.append(QgsField("rss_uncert_pct", QMetaType.Double, "double", 10, 2, rss_col))
        # Create a memory vector layer
        layer = QgsVectorLayer('Point?crs='+crs, 'Optimal_single_mest_mast', 'memory')
        pr = layer.dataProvider()

        # Add fields to the layer
        pr.addAttributes(fields)
        layer.updateFields()
        
        # Set the feature attributes
        feature.setAttributes([
            lowest_rss_row['Reference Point X [m]'],
            lowest_rss_row['Reference Point Y [m]'],
            lowest_rss_row['Reference Point Z [m]'],
            lowest_rss_row['Reference RIX [%]'],
            lowest_rss_row[rss_col]
        ])
        
        # Add the feature to the layer
        pr.addFeature(feature)

        # Step 5: Save the layer as a shapefile          

        noerror = self.save_as_shp(layer, output_shapefile_path, crs)
        
        if noerror :
            print("Shapefile created successfully!")
        
        # Step 6: Styling the layer
        

        layer = QgsVectorLayer(output_shapefile_path, "Optimal_single_mest_mast", "ogr")
        layer = self.style_point_layer(layer, 'circle','#4bff4b', '3.5')
        
        # Step 7: Add the layer to the QGIS project
        QgsProject.instance().addMapLayer(layer)
                           
    def process_best_two_met_mast(self, input_trix_file, outpath, crs_epsg):
    
        # Extract unique turbines and met masts using their coordinates
        turbines = self.df_data[['WTG X [m]', 'WTG Y [m]', 'WTG Z [m]']].drop_duplicates().reset_index(drop=True)
        masts = self.df_data[['Reference Point X [m]', 'Reference Point Y [m]', 'Reference Point Z [m]']].drop_duplicates().reset_index(drop=True)

        # Also get mast IDs for name field
        ref_cols = ['Reference Point X [m]', 'Reference Point Y [m]', 'Reference Point Z [m]', 'Reference RIX [%]', 'mast_id']
        unique_masts = self.df_data[ref_cols].drop_duplicates().reset_index(drop=True)

        # Create a matrix where rows represent turbines and columns represent met masts
        rss_matrix = pd.DataFrame(
            index=pd.MultiIndex.from_arrays([turbines['WTG X [m]'], turbines['WTG Y [m]'], turbines['WTG Z [m]']]),
            columns=pd.MultiIndex.from_arrays([masts['Reference Point X [m]'], masts['Reference Point Y [m]'], masts['Reference Point Z [m]']])
        )

        # Instead of using loc, use `at` for efficient assignment
        for _, row in self.df_data.iterrows():
            turbine = (row['WTG X [m]'], row['WTG Y [m]'], row['WTG Z [m]'])
            mast = (row['Reference Point X [m]'], row['Reference Point Y [m]'], row['Reference Point Z [m]'])
            rss_matrix.at[turbine, mast] = row['adj_RSS_uncertainty']

        # Convert to numpy array for efficient computation
        rss_values = rss_matrix.to_numpy()

        # Find the best pair of met masts
        best_pair = None
        best_total = float('inf')
        best_min_rss = None

        # Try all combinations of two met masts
        for (i, j) in combinations(range(len(masts)), 2):
            # For each turbine, select the minimum RSS between the two masts
            min_rss = np.minimum(rss_values[:, i], rss_values[:, j])
            total_rss = np.sum(min_rss)
            # Track the best combination
            if total_rss < best_total:
                best_total = total_rss
                best_pair = (i, j)
                best_min_rss = min_rss

        # Prepare results
        mast_coords = masts.to_numpy()
        mast1_coords = mast_coords[best_pair[0]]
        mast2_coords = mast_coords[best_pair[1]]
        # Find mast_id for each mast by matching coordinates
        def get_mast_id(coords):
            match = unique_masts[(unique_masts['Reference Point X [m]'] == coords[0]) &
                                 (unique_masts['Reference Point Y [m]'] == coords[1]) &
                                 (unique_masts['Reference Point Z [m]'] == coords[2])]
            if not match.empty:
                return match.iloc[0]['mast_id']
            else:
                return ""
        mast_ids = [get_mast_id(mast1_coords), get_mast_id(mast2_coords)]
        pair_total_rss = best_total / len(turbines) if len(turbines) > 0 else float('nan')

        vl = QgsVectorLayer("Point?crs={}".format(crs_epsg), "Optimal_pair_mest_mast", "memory")
        pr = vl.dataProvider()

        # Add attributes (no individual_rss)
        pr.addAttributes([
            QgsField("name", QMetaType.QString, "text", 255),  # String field with max 255 characters
            QgsField("x", QMetaType.Double, "double", 20, 6),  # 20 digits total, 6 decimal places
            QgsField("y", QMetaType.Double, "double", 20, 6),
            QgsField("z", QMetaType.Double, "double", 10, 2),   # 10 digits total, 2 decimal places
            QgsField("pair_total_rss", QMetaType.Double, "double", 20, 6)
        ])
        vl.updateFields()

        # Create features
        for name, coords in zip(mast_ids, [mast1_coords, mast2_coords]):
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1])))
            feat.setAttributes([
                name,
                coords[0],
                coords[1],
                coords[2],
                float(pair_total_rss)
            ])
            pr.addFeature(feat)

        noerror = self.save_as_shp(vl, outpath, crs_epsg)

        if noerror:
            print("Successfully created shapefile at:", outpath)
            # Add layer to QGIS project
            layer = QgsVectorLayer(outpath, "Optimal_pair_mest_mast", "ogr")
            layer = self.style_point_layer(layer, 'square', '#4bff4b', '3.5')
            QgsProject.instance().addMapLayer(layer)
            
            # Output all pairs and their uncertainties to CSV
            all_pairs_csv = outpath.replace('.shp', '_all_pairs.csv')
            num_turbines = len(turbines)
            with open(all_pairs_csv, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['mast_id_1', 'mast_id_2', 'total_rss', 'avg_rss', 'is_best'])
                for (i, j) in combinations(range(len(masts)), 2):
                    min_rss = np.minimum(rss_values[:, i], rss_values[:, j])
                    total_rss = np.sum(min_rss)
                    avg_rss = total_rss / num_turbines if num_turbines > 0 else float('nan')
                    mast1_coords = masts.iloc[i].values
                    mast2_coords = masts.iloc[j].values
                    mast_ids_pair = [get_mast_id(mast1_coords), get_mast_id(mast2_coords)]
                    is_best = (i, j) == best_pair
                    writer.writerow([mast_ids_pair[0], mast_ids_pair[1], total_rss, avg_rss, is_best])
            
            
    def process_best_two_met_mast0(self, input_trix_file, outpath, crs_epsg):
                            
            # Extract unique turbines and met masts using their coordinates
            turbines = self.df_data[['WTG X [m]', 'WTG Y [m]', 'WTG Z [m]']].drop_duplicates().reset_index(drop=True)
            masts = self.df_data[['Reference Point X [m]', 'Reference Point Y [m]', 'Reference Point Z [m]']].drop_duplicates().reset_index(drop=True)

            # Create a matrix where rows represent turbines and columns represent met masts
            rss_matrix = pd.DataFrame(
                index=pd.MultiIndex.from_arrays([turbines['WTG X [m]'], turbines['WTG Y [m]'], turbines['WTG Z [m]']]),
                columns=pd.MultiIndex.from_arrays([masts['Reference Point X [m]'], masts['Reference Point Y [m]'], masts['Reference Point Z [m]']])
            )

            # Fill the matrix with RSS values
            for _, row in self.df_data.iterrows():
                turbine = (row['WTG X [m]'], row['WTG Y [m]'], row['WTG Z [m]'])
                mast = (row['Reference Point X [m]'], row['Reference Point Y [m]'], row['Reference Point Z [m]'])
                rss_matrix.loc[turbine, mast] = row['RSS of uncertainty increases [%]']

            # Convert to numpy array for efficient computation
            rss_values = rss_matrix.to_numpy()

            # Find the best pair of met masts
            best_pair = None
            best_total = float('inf')
            best_min_rss = None

            # Try all combinations of two met masts
            for (i, j) in combinations(range(len(masts)), 2):
                # For each turbine, select the minimum RSS between the two masts
                min_rss = np.minimum(rss_values[:, i], rss_values[:, j])
                total_rss = np.sum(min_rss)
                
                # Track the best combination
                if total_rss < best_total:
                    best_total = total_rss
                    best_pair = (i, j)
                    best_min_rss = min_rss

            # Prepare results
            mast_coords = masts.to_numpy()
            mast1_coords = mast_coords[best_pair[0]]
            mast2_coords = mast_coords[best_pair[1]]

            vl = QgsVectorLayer("Point?crs={}".format(crs_epsg), "Optimal_pair_mest_mast", "memory")
            pr = vl.dataProvider()
            
            # Add attributes
            pr.addAttributes([
                QgsField("name", QMetaType.QString, "text", 255),  # String field with max 255 characters
                QgsField("x", QMetaType.Double, "double", 20, 6),  # 20 digits total, 6 decimal places
                QgsField("y", QMetaType.Double, "double", 20, 6),
                QgsField("z", QMetaType.Double, "double", 10, 2)   # 10 digits total, 2 decimal places
            ])
            vl.updateFields()
            
            # Create features
            for i, (name, coords) in enumerate(zip(["Mast 1", "Mast 2"], [mast1_coords, mast2_coords])):
                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(coords[0], coords[1])))
                feat.setAttributes([name, coords[0], coords[1], coords[2]])
                pr.addFeature(feat)
            
            
            
            noerror = self.save_as_shp(vl, outpath, crs_epsg)
                        
            if noerror :
                print("Successfully created shapefile at:", outpath)
                # Add layer to QGIS project
                layer = QgsVectorLayer(outpath, "Optimal_pair_mest_mast", "ogr")
                layer = self.style_point_layer(layer, 'square','#4bff4b', '3.5')
                QgsProject.instance().addMapLayer(layer)
     
    def aggregate_process_trix_file(self, input_trix_file, output_turbine_file, output_mast_points_file):
        # Optimized file reading: read until stop marker is found
        with open(input_trix_file, 'r') as f:
            data_lines = []
            while True:
                line = f.readline()
                # Stop when we hit EOF or our markers
                if not line or line.startswith(('Assumptions:', '*')):
                    break
                data_lines.append(line)
        
        # Create DataFrame and clean columns
        self.df_data = pd.read_csv(io.StringIO(''.join(data_lines)), sep='\t', engine='c')
        self.df_data.columns = self.df_data.columns.str.strip()

        # Assign unique turbine_id
        turbine_cols = ['WTG X [m]', 'WTG Y [m]', 'WTG Z [m]', 'WTG RIX [%]']
        unique_turbines = self.df_data[turbine_cols].drop_duplicates().reset_index(drop=True)
        unique_turbines['turbine_id'] = ['WTG_{:02d}'.format(i+1) for i in range(len(unique_turbines))]
        self.df_data = pd.merge(self.df_data, unique_turbines, on=turbine_cols, how='left')

        # Assign unique mast_id
        ref_cols = ['Reference Point X [m]', 'Reference Point Y [m]', 'Reference Point Z [m]', 'Reference RIX [%]']
        unique_masts = self.df_data[ref_cols].drop_duplicates().reset_index(drop=True)
        unique_masts['mast_id'] = ['Mast_{:02d}'.format(i+1) for i in range(len(unique_masts))]
        self.df_data = pd.merge(self.df_data, unique_masts, on=ref_cols, how='left')

        # Ensure all relevant columns are numeric to avoid TypeError
        cols_to_numeric = [
            'Horiz. Uc increase due to horiz. distance [%]',
            'Horizontal Distance [m]',
            'Horiz. Uc increase due to vert. distance [%]',
            'Vertical uncertainty increase [%]'
        ]
        for col in cols_to_numeric:
            self.df_data[col] = pd.to_numeric(self.df_data[col], errors='coerce')

        # If any of these columns is null, set it to 100 before arithmetic
        self.df_data['Horiz. Uc increase due to horiz. distance [%]'] = self.df_data['Horiz. Uc increase due to horiz. distance [%]'].fillna(100)
        self.df_data['Horiz. Uc increase due to vert. distance [%]'] = self.df_data['Horiz. Uc increase due to vert. distance [%]'].fillna(100)

        # --- Begin corrected RSS uncertainty logic ---
        # 1. Add (Horizontal Distance [m] / 1000) to Horiz. Uc increase due to horiz. distance [%]
        self.df_data['adj_horiz_uc_horiz_dist'] = (
            self.df_data['Horiz. Uc increase due to horiz. distance [%]'] +
            (self.df_data['Horizontal Distance [m]'] / 1000)
        )

        # 2. Sum with Horiz. Uc increase due to vert. distance [%]
        self.df_data['adj_sum_horiz_uc'] = (
            self.df_data['adj_horiz_uc_horiz_dist'] +
            self.df_data['Horiz. Uc increase due to vert. distance [%]']
        )

        # 3. New RSS uncertainty
        self.df_data['adj_RSS_uncertainty'] = np.sqrt(
            self.df_data['adj_sum_horiz_uc']**2 +
            self.df_data['Vertical uncertainty increase [%]']**2
        )

        # 4. Save the full DataFrame before grouping/averaging
        pre_avg_csv = output_mast_points_file.replace('.csv', '_full.csv')
        self.df_data.to_csv(pre_avg_csv, index=False)

        # Save unique met masts with mast_id
        met_masts_csv = output_mast_points_file.replace('mast_points_data.csv', 'met_masts_locations.csv')
        unique_masts.to_csv(met_masts_csv, index=False)

        # Group reference points and calculate mean of new RSS uncertainty, keeping mast_id
        grouped_ref = self.df_data.groupby(ref_cols + ['mast_id'], as_index=False, observed=True).agg({
            'adj_RSS_uncertainty': 'mean'
        })
        grouped_ref.to_csv(output_mast_points_file, index=False)

        # Save unique turbines with turbine_id
        unique_turbines.to_csv(output_turbine_file, index=False)
    
  
    def init_ui(self):
    
    
        icon = QIcon(":/plugins/OptimalMastPlanner/folder.png")
        self.dlg.trix_file_dir.setIcon(icon)
        self.dlg.out_dir_sele.setIcon(icon)
        self.dlg.out_dir_sele.setIcon(icon)

        self.dlg.setFixedSize(402, 473)
        
        self.dlg.comboBox.addItems(['Single', 'Pair'])
        list_countries = self.cities_by_country['country'].drop_duplicates()
        self.dlg.country_input.addItems(list_countries)

    def define_actions(self):
    
        self.dlg.country_input.currentIndexChanged.connect(self.update_cities)
        self.dlg.trix_file_dir.clicked.connect(self.selectOutputFile)
        self.dlg.out_dir_sele.clicked.connect(self.selectOutputDir)
        self.dlg.start_process.clicked.connect(self.main_process)
        self.dlg.pushButton.clicked.connect(self.highlight_best_met)
        
    def main_process(self):
           
          
        input_trix_file = self.dlg.trix_file.text()
        
        out_dir = self.dlg.out_dir.text()
        if input_trix_file != '':
            if out_dir != '':
                

                current_datetime = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M")
                warnings.filterwarnings(action="ignore", message=r"datetime.datetime.utcnow")
                self.output_direcory = os.path.join(out_dir, 'met_mast_process_results_'+current_datetime) 
                output_mast_points_file = os.path.join(self.output_direcory,'mast_points_data.csv')
                output_turbine_file = os.path.join(self.output_direcory,'turbines_locations.csv')
                output_met_mast_points_shp_path = os.path.join(self.output_direcory,'met_mast_points.shp')
                output_turbins_shp_path = os.path.join(self.output_direcory,'wind_turbins.shp')
                output_idw_raster = os.path.join(self.output_direcory,'idw_met_mast.tif')
                out_colorized_raster_path = os.path.join(self.output_direcory,'idw_met_mast_heatmap.tif')
                
                crs = self.dlg.crs.crs().authid()

                if str(crs) == '' :
                    if self.dlg.country_input.currentText()=='' or self.dlg.city_input.currentText()=='' :
                        self.display_warning('Specify Project City OR CRS')
                    else:
                        crs = self.get_crs()
                
                if str(crs) != '' :   
                    if not os.path.exists(self.output_direcory):
                        os.makedirs(self.output_direcory)
                        
                        #self.display_info('Processing Heatmap')
                      
                        self.dlg.process.setStyleSheet("""
                                                QLabel {
                                                    font-weight: bold;
                                                    color: #3498db;  /* Nice blue color */
                                                }
                                            """)

                        self.aggregate_process_trix_file(input_trix_file, output_turbine_file, output_mast_points_file)               
                        met_mast_layer = self.create_met_mast_layer(output_mast_points_file, crs, output_met_mast_points_shp_path)
                        
                        self.add_osm_basemap()
                        self.generate_idw_raster(met_mast_layer, output_met_mast_points_shp_path, output_idw_raster)
                        
                        raster_layer = QgsRasterLayer(output_idw_raster, "idw_met_mast_heatmap")
                        raster_layer = self.apply_color_ramp(raster_layer)
                        
                        self.save_rendred_raster(raster_layer, out_colorized_raster_path)
                        
                        QgsProject.instance().addMapLayer(raster_layer)
                        QgsProject.instance().addMapLayer(met_mast_layer)
                        self.set_layer_visibility(met_mast_layer, visible=False)
                        self.create_turbine_shapefile(output_turbine_file, output_turbins_shp_path, crs)
                        self.display_success("Process Successfully Done !")
                        self.dlg.tabWidget.setTabEnabled(1, True)
                        
            else: 
                self.display_warning('Please Choose Output Directory')  
        else: 
            self.display_warning('Please Choose a TRIX File')       
        
    def run(self):
        """Run method that performs all the real work"""

        cities_by_country_file = os.path.join(self.plugin_dir, 'cities_by_country', 'cities_by_country.xlsx')
        self.cities_by_country = pd.read_excel(cities_by_country_file)
        self.dlg = OptimalMastPlannerDialog()
        
        self.fill_countries()
        self.define_actions()
        self.init_ui()
        self.dlg.tabWidget.setTabEnabled(1, False)
        
        self.dlg.show()
        result = self.dlg.exec_()
        
        if result:
            pass

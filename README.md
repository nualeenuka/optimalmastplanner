# OptimalMeasurementPlanner QGIS Plugin

## Overview

**OptimalMeasurementPlanner** is a QGIS plugin designed to support the optimal placement and analysis of meteorological masts (met masts) and wind turbines. It processes TRIX files and generates spatial outputs—CSV, shapefiles, and raster heatmaps—while offering visualization and reporting tools directly within QGIS.

---

## Features

- **TRIX File Processing**  
  Reads and processes TRIX files containing site uncertainty and turbine data.

- **Unique ID Assignment**  
  Automatically assigns unique IDs to turbines and met masts.

- **Output Generation**  
  - CSV outputs for:
    - Full TRIX data
    - Grouped/averaged met mast points
    - Unique turbine and mast locations  
  - Shapefiles for met mast and turbine locations  
  - IDW (Inverse Distance Weighted) raster heatmaps for visualizing uncertainty  

- **QGIS Integration**  
  - Adds styled vector/raster layers to your QGIS project  
  - Manages layer visibility and styles  
  - Adds an OpenStreetMap basemap for context  

- **User Interface**  
  - Intuitive dialog to select input files and output directories  
  - Country/city selection with autocomplete for CRS auto-detection  
  - Manual CRS input option  

- **Analysis Tools**  
  - Automatically highlights the optimal single or pair of met masts based on uncertainty metrics  

---

## Workflow

1. **Input Selection**  
   Select a TRIX file and output directory via the plugin dialog.

2. **Processing**  
   The plugin processes and aggregates TRIX data and prepares spatial outputs.

3. **Output Generation**  
   Results are saved in a timestamped folder within the selected output directory.

4. **Visualization**  
   CSV, shapefile, and raster layers are added to the QGIS project for visualization.

5. **Analysis**  
   Use built-in tools to highlight the best single or pair of met mast locations.

---

## Installation

1. **Copy the Plugin**  
   Copy the `OptimalMeasurementPlanner` directory into your QGIS plugins folder:
   ```
   C:\Users\<YourUser>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins
   ```

2. **Dependencies**  
   - QGIS 3.x  
   - Python 3.x  
   - Required Python packages:
     - `pandas`
     - `numpy`
     - `openpyxl`
     - QGIS Python libraries (built-in)

3. **Activate the Plugin**  
   - Open QGIS  
   - Go to **Plugins > Manage and Install Plugins**  
   - Enable **OptimalMeasurementPlanner**

---

## Usage

1. **Open the Plugin**  
   Click the *OptimalMeasurementPlanner* icon in the QGIS toolbar.

2. **Configure Inputs**  
   - Select a TRIX file  
   - Choose an output directory  
   - Select a country and city (for automatic CRS detection) or input CRS manually

3. **Run Processing**  
   Click the *Process* button to generate all outputs:
   - CSVs
   - Shapefiles
   - Raster heatmaps

4. **Analyze Results**  
   Use the built-in analysis tool to highlight the best single or pair of met mast locations.

---

## File Structure

```
OptimalMeasurementPlanner/
├── OptimalMeasurementPlanner.py            # Main plugin logic
├── OptimalMeasurementPlanner_dialog.py     # UI logic
├── resources.py                     # Compiled Qt resources (icons, etc.)
├── cities_by_country/
│   └── cities_by_country.xlsx       # Country/city CRS lookup
├── icon.png                         # Plugin icon
├── README.html                      # Optional: Setup guide
└── ... (additional UI/resource files)
```

---

## Key Classes & Methods

- **OptimalMeasurementPlanner**
  - `initGui()` – Adds toolbar and menu actions  
  - `main_process()` – Full workflow: processing, output generation, and visualization  
  - `aggregate_process_trix_file()` – Aggregates TRIX data  
  - `create_met_mast_layer()` – Generates met mast shapefile  
  - `create_turbine_shapefile()` – Generates turbine shapefile  
  - `generate_idw_raster()` – Creates IDW raster heatmap  
  - `apply_color_ramp()` – Styles the raster with a color gradient  
  - `highlight_best_met()` – Highlights optimal met mast(s)  
  - `add_osm_basemap()` – Adds OpenStreetMap background layer  

---

## Inputs & Outputs

### Inputs:
- TRIX file (tab-delimited `.txt`)
- Output directory
- Country/city (for CRS) or manual CRS input

### Outputs:
- `mast_points_data.csv` – Aggregated/grouped met mast data  
- `turbines_locations.csv` – Unique turbine coordinates  
- `met_mast_points.shp` – Shapefile of met masts  
- `wind_turbines.shp` – Shapefile of turbines  
- `idw_met_mast.tif` – Raw IDW raster  
- `idw_met_mast_heatmap.tif` – Styled raster heatmap  
- `Optimal_single_met_mast.shp` – Best single mast location  
- `Optimal_pair_met_mast.shp` – Best mast pair

---

## Contact

For questions or contributions, please contact:  
**[nalni@vestas.com](mailto:nalni@vestas.com)**

# MOHID HDF5 Viewer

**Version 2.0**

A comprehensive, interactive utility to inspect and export data from MOHID HDF5 files into various formats, including animations (MP4, GIF, AVI), frame-by-frame images (JPG), geospatial data (GeoTIFF), and raw text (CSV).

---

## Table of Contents

- [Features](#-features)
- [Authors](#-authors)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Guide](#-usage-guide)
- [Supported Models](#-supported-models)
- [Export Formats](#-export-formats)
- [Vertical Sections](#-vertical-sections)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Citation](#-citation)

---

## Features

### Core Capabilities
- **Fast JPG/PNG Export**: Single figure with efficient pcolormesh updates
- **Multiple Basemap Options**: Google Satellite, Google Terrain, OpenStreetMap, or none
- **Customizable Tile Zoom**: Control basemap detail level with fast tile construction
- **Labeled Visualizations**: Automatic colorbar on images and animations
- **Robust NoData Handling**: Configurable masking (e.g., -9.9e15 → NaN)
- **3D Variable Support**: Surface, bottom, mean, or specific k-layer selection
- **Vertical Cross-Sections**: Interactive longitudinal and latitudinal section viewer
- **Layer Information**: Display all available k layers with mean depth when geometry file is provided

### Advanced Features
- **Vertical Exaggeration**: Adjust vertical scale for MOHID Land models
- **Multiple Export Formats**: Images, animations, GeoTIFF, CSV, and shapefiles
- **QGIS Integration**: Export to GeoTIFF with projection information
- **Time Series Viewer**: Efficient disk-based JPG viewer with timestamp navigation
- **Batch Processing**: Process multiple variables at once
- **User Preferences**: Persistent settings between sessions

### Visualization Options
- **40+ Colormaps**: Including scientific (viridis, plasma) and classic (rainbow, jet)
- **Color Scale Control**: Global or per-frame color scaling
- **Coastline Overlay**: Optional coastline rendering
- **Grid Controls**: Toggle grid lines and customize appearance
- **Statistics Display**: Min, max, mean, std dev for selected data

---

## Authors

- **Giulliano de Lima Lopes de Oliveira Simeão Bigão**
- **Nikolas Gomes Silveira de Souza**
- **Rogério Atem de Carvalho**
- **Jader Lugon Junior**
- **Antônio José Silva Neto**

Created: October 11, 2025

---

## Requirements

### Core Dependencies (Required)
```
python >= 3.7
h5py
numpy
matplotlib
cartopy
pillow
FreeSimpleGUI
```

### Optional Dependencies
```
ffmpeg          # For MP4/AVI animation export
rasterio        # For GeoTIFF export
```

### Installation via Conda (Recommended)
```bash
# Create environment with all dependencies
conda create -n mohid python=3.9
conda activate mohid

# Install required packages from conda-forge
conda install -c conda-forge h5py numpy matplotlib cartopy pillow ffmpeg

# Install FreeSimpleGUI via pip
pip install FreeSimpleGUI

# Optional: Install rasterio for GeoTIFF support
conda install -c conda-forge rasterio
```

### Installation via pip
```bash
pip install h5py numpy matplotlib cartopy pillow FreeSimpleGUI

# Optional dependencies
pip install imageio imageio-ffmpeg  # For animations
pip install rasterio  # For GeoTIFF
```

---

## Installation

### Clone or Download
```bash
# Clone repository (if available)
git clone https://github.com/yourusername/mohid-hdf5-viewer.git
cd mohid-hdf5-viewer

# Or download ZIP and extract
```

### Verify Installation
```bash
python -c "import h5py, numpy, matplotlib, cartopy; print('All dependencies OK!')"
```

---

## ⚡ Quick Start

### Basic Usage
```bash
# Run the application (recommended with unbuffered output)
python -u MOHID_HDF5_Viewer.py

# Or simply
python MOHID_HDF5_Viewer.py
```

### First Steps
1. **Welcome Screen**: Review features and click "Continue"
2. **Load HDF5 File**: Browse and select your MOHID HDF5 file
3. **Select Model Type**: Choose "MOHID Water" or "MOHID Land"
4. **Load Variables**: Click "Load Variables" to scan available data
5. **Select Variable**: Choose from dropdown list
6. **Configure Settings**: Click "Configuration" to adjust parameters
7. **Export**: Choose export format (Images, Animations, Shapefiles, etc.)

---

## Usage Guide

### 1. Configuration Window

#### Vertical Selection (3D Variables)
- **Surface**: Extract top layer (default)
- **Bottom**: Extract bottom layer
- **Mean**: Average across all vertical layers
- **Choose k**: Select specific layer index

Click "Refresh k list" to update available layers after loading a variable.

#### NoData Handling
- **Sentinel Values**: Comma-separated list (e.g., `-99, -999, -9.9e15`)
- **Auto Threshold**: Automatically treat values < -1e12 as NoData
- Common values: -99, -999, -9.9e15

#### Basemap Settings
- **Use Basemap Tiles**: Enable/disable background map
- **Basemap Type**: Google Satellite, Google Terrain, OpenStreetMap, None
- **Tile Zoom**: 1-21 (higher = more detail but slower)
- **Fast Tiles**: Reuse tiles across frames (recommended)
- **Show Coastlines**: Overlay coastline data

#### Color Scale
- **Colormap**: Choose from 40+ options
- **Original/Reversed**: Flip color scale
- **Min/Max Limits**: Set explicit values (0 = auto)
- **Global Scale**: Use same scale for all frames (faster, recommended)
- **Per-Frame Scale**: Optimize scale for each frame (slower)

### 2. Image Export

#### Format Options
- **JPG**: Fast, small files, good for web
- **PNG**: Lossless, supports transparency

#### Quality Settings
- **DPI**: 90-200 (higher = better quality but larger files)
- **JPG Quality**: 1-100 (95 recommended)

#### Output
- **Folder Name**: Destination directory
- **Overwrite**: Replace existing files
- **Open After**: Automatically open folder when complete

### 3. Animation Export

#### Format Options
- **MP4**: Best compression, requires FFmpeg
- **GIF**: Universal compatibility, larger files
- **AVI**: High quality, very large files

#### Settings
- **FPS**: Frames per second (1-30)
- **DPI**: Resolution (90-200)
- **Loop**: Enable looping (GIF only)
- **Bitrate**: Video quality in kbps (MP4/AVI)
- **Codec**: libx264 (recommended), mpeg4, libx265

### 4. Shapefile Export (QGIS)

#### Formats
- **GeoTIFF**: Raster format with georeferencing
- **Shapefile**: Vector point format
- **GeoJSON**: Modern vector format
- **CSV with Coordinates**: Simple text format

#### GeoTIFF Settings
- **NoData Value**: Value for masked areas
- **Compression**: LZW (recommended), DEFLATE, PACKBITS
- **Tiled**: Create tiled GeoTIFF for better performance

#### Coordinate System
- **EPSG:4326**: WGS84 (default, lat/lon)
- **EPSG:3857**: Web Mercator
- **Custom EPSG**: Enter custom code

### 5. Vertical Sections

#### Prerequisites
- Load 3D variable (with vertical layers)
- Specify geometry file (`Geometry_1.dat`) in main window
  - Auto-detected if in same folder as HDF5 file
  - Required for accurate depth calculation

#### Section Configuration
- **Longitudinal**: Vertical slice along longitude (at fixed latitude)
- **Latitudinal**: Vertical slice along latitude (at fixed longitude)

Use sliders or text input to select section position.

#### Visualization Options
- **Colormap**: Choose color scheme
- **Show Bathymetry**: Overlay bottom topography
- **Show Grid**: Display layer interfaces
- **Color Limits**: Min/Max (auto or manual)
- **Point Size**: Size of data points
- **Vertical Exaggeration**: Enhance vertical scale (MOHID Land only)

#### Statistics
View min, max, mean, std dev, median, and valid point count for selected section.

#### Export Options
- **CSV**: Tabular data (coordinate, depth, value)
- **Image**: PNG or JPG of section plot

### 6. Time Series Viewer

Open exported JPG sequences:
- **Navigation**: Slider, Previous/Next buttons, timestamp dropdown
- **Maximize**: Toggle fullscreen mode
- **Memory Efficient**: Loads images on-demand from disk

---

## Supported Models

### MOHID Water
- Hydrodynamic simulations
- 3D water column variables
- Sigma + Cartesian vertical coordinate system
- Variables: temperature, salinity, velocity, water level, etc.

### MOHID Land
- Land surface and subsurface hydrology
- Soil moisture, infiltration, runoff
- Cartesian TOP vertical layers
- Variables: soil moisture, water table depth, etc.

---

## Export Formats

| Format | Use Case | Pros | Cons |
|--------|----------|------|------|
| **JPG** | Quick preview, web sharing | Fast, small files | Lossy compression |
| **PNG** | High-quality images | Lossless, transparency | Larger files |
| **MP4** | Presentations, sharing | Best compression, universal | Requires FFmpeg |
| **GIF** | Web animations | No dependencies, loops | Limited colors, large |
| **AVI** | Video editing | High quality | Very large files |
| **GeoTIFF** | GIS analysis | Georeferenced, standard | Requires rasterio |
| **Shapefile** | QGIS integration | Vector format, attributes | Multiple files |
| **CSV** | Custom processing | Universal, readable | Very slow, huge files |

---

## Vertical Sections

### Geometry File Format
The viewer requires a MOHID `Geometry_1.dat` file for accurate vertical section rendering.

#### Structure
```
<begindomain>
ID           : 2
TYPE         : SIGMA
LAYERS       : 10
LAYERTHICKNESS: 0.05 0.05 0.10 0.10 0.10 0.15 0.15 0.15 0.10 0.10
DOMAINDEPTH  : 25
<enddomain>

<begindomain>
ID           : 1
TYPE         : CARTESIAN
LAYERS       : 15
LAYERTHICKNESS: 5 5 5 5 10 10 10 10 20 20 20 20 20 20 20
<enddomain>
```

#### Domain Types
- **SIGMA**: Surface-following layers (0m to DOMAINDEPTH)
- **CARTESIAN**: Fixed-thickness layers (DOMAINDEPTH to bottom)
- **CARTESIANTOP**: Top-down layers for MOHID Land (surface to depth)

### Vertical Exaggeration
For MOHID Land models, you can apply vertical exaggeration to enhance visualization of thin layers:
- Recommended range: 1.0x (no exaggeration) to 10.0x
- Rebuilds 3D depth grid with scaled layer thicknesses
- Not applicable to MOHID Water models

### Section Location Map
Displays a 2D map showing where the vertical section cuts through the domain.

---

## Project Structure

```
mohid-hdf5-viewer/
│
├── MOHID_HDF5_Viewer.py    # Main application entry point
├── config.py               # Configuration and constants
├── gui_components.py       # GUI window layouts
├── hdf5_utils.py          # HDF5 file reading utilities
├── processing.py          # Data processing and masking
├── vertical_section.py    # Vertical cross-section tools
├── viewer.py              # JPG time series viewer
├── exporters.py           # Export functions (not shown in provided files)
│
└── README.md              # This file
```

### Module Overview

#### `MOHID_HDF5_Viewer.py`
- Application entry point
- Main event loop
- Window coordination
- State management

#### `config.py`
- Application metadata
- UI constants
- Configuration classes
- Dependency checking
- User preferences management

#### `gui_components.py`
- Modular window components
- Configuration dialogs
- Export wizards
- Progress dialogs

#### `hdf5_utils.py`
- HDF5 file parsing
- Variable loading
- Timestamp extraction
- Grid data reading
- Structure validation

#### `processing.py`
- ND to 2D reduction
- NoData masking
- Grid alignment
- Color scale computation
- Statistics calculation

#### `vertical_section.py`
- Geometry file parsing
- 3D depth grid construction
- Section extraction (longitudinal/latitudinal)
- Bathymetry/altimetry overlay
- Section visualization

#### `viewer.py`
- Disk-based JPG viewer
- On-demand image loading
- Timestamp navigation
- Memory-efficient playback

---

## Troubleshooting

### Common Issues

#### "No variables found in Results/"
- **Cause**: Invalid HDF5 file structure
- **Solution**: Verify file is MOHID-compatible HDF5. Check for `Results/`, `Grid/`, and `Time/` groups.

#### "FFmpeg not available"
- **Cause**: FFmpeg not installed
- **Solution**: 
  ```bash
  conda install -c conda-forge ffmpeg
  ```
  Or use GIF format instead.

#### "Rasterio not available - GeoTIFF export disabled"
- **Cause**: Rasterio not installed
- **Solution**:
  ```bash
  conda install -c conda-forge rasterio
  ```

#### "Could not find horizontal axes"
- **Cause**: Unexpected array dimensions
- **Solution**: Check variable dimensions match grid. Try different k-layer selection.

#### Geometry file not found
- **Cause**: `Geometry_1.dat` not in expected location
- **Solution**: Manually specify path in main window. File should be in same directory as HDF5 file.

#### "Memory Error" during export
- **Cause**: Dataset too large
- **Solution**: 
  - Export smaller time ranges
  - Reduce DPI
  - Use JPG instead of PNG
  - Close other applications

#### Slow tile rendering
- **Cause**: High zoom level or slow internet
- **Solution**:
  - Enable "Fast Tiles" option
  - Reduce tile zoom level
  - Use "None" basemap for fastest performance

### Performance Tips

1. **Use Global Color Scale**: Faster than per-frame
2. **Enable Fast Tiles**: Reuse basemap across frames
3. **Lower DPI**: For draft exports (90-120)
4. **JPG Format**: Faster than PNG
5. **Batch Similar Variables**: Reuse settings
6. **Close Viewer**: When not needed to free memory

---

## Example Workflow

### Exporting Temperature Time Series

1. **Launch Application**
   ```bash
   python -u MOHID_HDF5_Viewer.py
   ```

2. **Load Data**
   - Select HDF5 file
   - Choose "MOHID Water"
   - Click "Load Variables"
   - Select "temperature" from dropdown

3. **Configure**
   - Open "Configuration"
   - Select "Surface" for vertical mode
   - Choose "viridis" colormap
   - Enable "Google Satellite" basemap
   - Set tile zoom to 12
   - Click "Save Settings"

4. **Export Animation**
   - Click "Animations"
   - Select "MP4"
   - Set FPS to 10
   - Set DPI to 150
   - Name file "temperature_surface.mp4"
   - Click "Start Export"

5. **View Results**
   - Animation opens automatically
   - Or use "Open Viewer" for frame-by-frame inspection

### Creating Vertical Section

1. **Prepare**
   - Load 3D variable (e.g., "salinity")
   - Ensure `Geometry_1.dat` is specified

2. **Open Section Viewer**
   - Click "Vertical Sections"

3. **Configure Section**
   - Select "Longitudinal" section type
   - Adjust latitude slider to desired position
   - Set timestep (0 = first frame)

4. **Customize Visualization**
   - Choose colormap (e.g., "plasma")
   - Enable "Show bathymetry"
   - Adjust color limits if needed

5. **Update and Export**
   - Click "Update Section"
   - Review statistics
   - Export as CSV or Image

---

## Citation

If you use this tool in your research, please cite:

```
MOHID HDF5 Viewer v2.0
Authors: Bigão, G.L.L.O.S., Souza, N.G.S., Carvalho, R.A., Lugon Jr., J.
Year: 2025
```

---

## License

This project is open source. Please check with the authors for specific license terms.

---

## Contributing

Contributions are welcome! Please contact the authors for guidelines.

---

## Contact

For questions, bug reports, or feature requests, please contact the authors.

---

## Version History

### Version 2.0 (Current)
- Refactored modular architecture
- Added vertical section viewer
- Enhanced geometry file parsing
- Improved MOHID Land support
- Added vertical exaggeration
- Persistent user preferences
- Better error handling

### Version 1.0
- Initial release
- Basic export functionality
- JPG viewer
- Multiple format support

---

## Acknowledgments

- FAPERJ, CNPq and CAPES
- MOHID Development Team
- Cartopy Contributors
- Matplotlib Community
- HDF5 Group

---

**Tested with**: MOHID Land HDF files and MOHID Water Hydrodynamic HDF files

**Last Updated**: November 2025</parameter>

"""
MOHID HDF5 Viewer - GUI Components (Refactored)
Modular window layouts with separate configuration, export, and viewer windows
"""
import sys
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Optional, Tuple

import FreeSimpleGUI as sg

from .config import (
    UIConfig, BASEMAP_OPTIONS, COLOR_SCALE_OPTIONS,
    APP_TITLE, APP_AUTHORS, APP_DESCRIPTION,
    logger #DS_18/11
)


# ===================== WELCOME DIALOG =====================

WELCOME_TEXT = f"""\
Created on Sat Oct 11 01:00:00 2025
@authors:
  - {APP_AUTHORS[0]}
  - {APP_AUTHORS[1]}
  - {APP_AUTHORS[2]}
  - {APP_AUTHORS[3]}

Title:
  {APP_TITLE}

Description:
{APP_DESCRIPTION}

What you get:
  • Very fast JPG/PNG export (single figure + pcolormesh update)
  • Basemap tiles: Google Satellite, Google Terrain, OSM, or None
  • Tile zoom control + Fast tile construction
  • Labeled colorbar on images and animations
  • Robust NoData masking (e.g., -9.9e15 → NaN). Configurable values.
  • 3D variables: Surface / Bottom / Mean / explicit k index
  • Shows all available k (with mean layer depth if available)
  • Shapefile export for QGIS integration
  • Separate windows for different export types
  • Viewer: slider, Prev/Next, timestamp jump, maximize
  
Run (recommended):
  python -u main.py

Dependencies (conda-forge recommended):
  conda install -c conda-forge h5py numpy matplotlib cartopy pillow ffmpeg
  # Optional for GeoTIFF:
  conda install -c conda-forge rasterio

If there is no ffmpeg, it will automatically convert to .gif.
Refactored version with modular window architecture.
"""


def show_welcome_dialog():
    """Display welcome/about dialog on startup"""
    from config import UserPreferences  # Import aqui para evitar circular import
    
    sg.theme('Dark Blue 3')
    
    layout = [
        [sg.Text(
            "MOHID HDF5 Viewer: Maps and Sections",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        [sg.Frame("About", [
            [sg.Multiline(
                WELCOME_TEXT,
                size=(90, 24),
                font=UIConfig.CONSOLE_FONT,
                disabled=True,
                key="-ABOUT-"
            )]
        ], expand_x=True, expand_y=True)],
        [sg.Push(), sg.Button("Continue", bind_return_key=True), sg.Button("Don't show"), sg.Button("Quit")]
    ]
    
    window = sg.Window(
        "About",
        layout,
        modal=True,
        finalize=True,
        keep_on_top=True,
        resizable=True
    )
    
    while True:
        event, _ = window.read()
        
        if event in (sg.WINDOW_CLOSED, "Quit"):
            window.close()
            sys.exit(0)

        if event == "Don't show":
            # Save preference to not show welcome screen
            UserPreferences.set_show_welcome(False)
            break
            
        if event == "Continue":
            break
    
    window.close()


# ===================== MAIN WINDOW (HUB) =====================

def make_main_window() -> sg.Window:
    """
    Create main hub window for navigation to specialized windows.
    
    Returns:
        PySimpleGUI Window
    """
    layout = [
#        [sg.Text(
#            APP_TITLE,
#            font=UIConfig.TITLE_FONT,
#            justification="center",
#            expand_x=True
#        )],
        
        # File selection
        [sg.Frame('File Selection', [
            [
                sg.Text("Path to HDF5 file:"),
                sg.Input(key='-FILE-', size=(50, 1)),
                sg.FileBrowse(file_types=(("HDF5 Files", "*.hdf5"), ("All files", "*.*")))
            ],
            [
                sg.Radio('MOHID Water', 'MOHID', key='-M_WATER-', 
                        default='MOHID Water'),
                sg.Radio('MOHID Land', 'MOHID', key='-M_LAND-')
            ],
            [
                sg.Button("Load Variables", size=(15, 1)),
                sg.Text("Variable (Results/*):"),
                sg.Combo(
                    [],
                    key='-VAR-',
                    readonly=True,
                    size=(40, 1),
                    enable_events=True
                )
            ],
            [
                sg.Text("Geometry file (layer information):"),
                sg.Input(key='-STATS_GEOMETRY-', size=(40, 1), enable_events=True),
                sg.FileBrowse(file_types=((".dat Files", "*.dat"),))
            ]
        ], expand_x=True)],
        
        # Export options
        [sg.Frame('Export Options', [
            [
                sg.Button("Configuration", key='-OPEN_CONFIG-', size=(20, 2)),
                sg.Text("Configure data processing settings", pad=(10, 0))
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button("Images (PNG/JPG)", key='-OPEN_IMAGE-', size=(20, 2)),
                sg.Text("Export individual frames as images", pad=(10, 0))
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button("Animations", key='-OPEN_ANIM-', size=(20, 2)),
                sg.Text("Create MP4, GIF, or AVI animations", pad=(10, 0))
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button("Shapefiles (QGIS)", key='-OPEN_SHAPE-', size=(20, 2)),
                sg.Text("Export to QGIS-compatible formats", pad=(10, 0))
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button("Vertical Sections", key='-OPEN_VSECTION-', size=(20, 2)),
                sg.Text("View vertical cross-sections", pad=(10, 0))
            ]
        ], expand_x=True)],
        
        # Viewer
        [sg.Frame('Viewer', [
            [
                sg.Text("Last export folder:"),
                sg.Input(key='-LAST_DIR-', size=(50, 1), disabled=True),
                sg.Button('Browse', key='-BROWSE_LAST-')
            ],
            [
                sg.Button("Open Viewer", key='-OPEN_VIEWER-', size=(20, 1)),
                sg.Button("Open from Folder...", key='-OPEN_VIEWER_DIR-', size=(20, 1))
            ]
        ], expand_x=True)],
        
        # Status and quit
        [
            sg.Text("Ready", key='-STATUS-', size=(60, 1), relief=sg.RELIEF_SUNKEN),
            sg.Push(),
            sg.Button('About', size=(10, 1), key='Show welcome window'),
            sg.Button('Quit', size=(10, 1))
        ]
    ]
    
    return sg.Window(
        APP_TITLE,
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        location=UIConfig.MAIN_WINDOW_LOCATION,
        resizable=True
    )


# ===================== CONFIGURATION WINDOW =====================

def make_config_window(current_settings: dict = None) -> sg.Window:
    """
    Create configuration window for data processing settings.
    
    Args:
        current_settings: Current settings dictionary (optional)
        
    Returns:
        PySimpleGUI Window
    """
    if current_settings is None:
        current_settings = {}
    
    layout = [
#        [sg.Text(
#            "Configuration Settings",
#            font=UIConfig.TITLE_FONT,
#            justification="center",
#            expand_x=True
#        )],
        
        # Vertical selection (3D variables)
        [sg.Frame("Vertical Selection (for 3-D variables)", [
            [
                sg.Radio('Surface', 'VERT', key='-SURF-', 
                        default=current_settings.get('reduce_mode', 'top') == 'top'),
                sg.Radio('Bottom', 'VERT', key='-BOTT-',
                        default=current_settings.get('reduce_mode', '') == 'bottom'),
                sg.Radio('Mean', 'VERT', key='-VMN-',
                        default=current_settings.get('reduce_mode', '') == 'mean'),
                sg.Radio('Choose k:', 'VERT', key='-VK-', enable_events=True,
                        default=current_settings.get('reduce_mode', '') == 'index')
            ],
            [
                sg.Text("k index:"),
                sg.Combo([], key='-K_COMBO-', size=(28, 1), disabled=True)
            ],
            [
                sg.Button('Refresh k list', key='-K_REFRESH-', size=(15, 1)),
                sg.Button('Show all k', key='-K_SHOW-', size=(15, 1)),
            ],
            [
                sg.Text('Detected: ', key='-K_INFO-', size=(70, 1))
            ]
        ], expand_x=True)],
        
        # NoData handling
        [sg.Frame("NoData Handling", [
            [
                sg.Text('NoData sentinel value(s):'),
                sg.Input(
                    current_settings.get('nodata_values_text', '-99'),
                    key='-NODATA-',
                    size=(25, 1)
                ),
                sg.Text("(comma or semicolon separated)")
            ],
            [
                sg.Checkbox(
                    'Also treat values -1e12 as NoData',
                    key='-AUTO_ND-',
                    default=current_settings.get('auto_land_threshold', True)
                )
            ],
            [
                sg.Text("Note: Common NoData values are -99, -999, -9.9e15", 
                       font=("Helvetica", 9, "italic"))
            ]
        ], expand_x=True)],
        
        # Basemap settings
        [sg.Frame("Basemap and Coastline", [
            [
                sg.Checkbox('Use basemap tiles', key='-USE_TILES-',
                           default=current_settings.get('use_tiles', True)),
                sg.Combo(
                    BASEMAP_OPTIONS,
                    key='-BASEMAP-',
                    readonly=True,
                    default_value=current_settings.get('basemap', "Google Satellite (imagery)")
                )
            ],
            [
                sg.Text('Tile zoom level [1-21]:'),
                sg.Spin(
                    [i for i in range(1, 22)],
                    initial_value=current_settings.get('tile_zoom', 12),
                    size=(4, 1),
                    key='-TILE_ZOOM-'
                ),
                sg.Checkbox(
                    'Fast tiles (draw once)',
                    key='-FAST_TILES-',
                    default=current_settings.get('fast_tiles', True),
                    tooltip="Add tiles once and reuse across frames for faster export"
                )
            ],
            [
                sg.Checkbox('Show coastlines', key='-USE_COASTLINE-',
                           default=current_settings.get('use_coastline', True))
            ]
        ], expand_x=True)],
        
        # Color scale settings
        [sg.Frame("Color Scale", [
            [
                sg.Text("Colormap:"),
                sg.Combo(
                    COLOR_SCALE_OPTIONS,
                    key='-COLOR_SCALE-',
                    readonly=True,
                    enable_events=True,
                    default_value=current_settings.get('colormap', 'rainbow'),
                    size=(20, 1)
                ),
                sg.Radio('Original', 'ORIG_REV', key='-ORIGINAL-',
                        default=current_settings.get('original', True)),
                sg.Radio('Reversed', 'ORIG_REV', key='-REVERSED-',
                        default=not current_settings.get('original', True))
            ],
            [sg.Canvas(
                size=UIConfig.COLORBAR_PREVIEW_SIZE,
                background_color='white',
                key='-COLORBAR_CANVAS-'
            )],
            [sg.Text("Color scale limits (0 = auto):")],
            [
                sg.Text('Minimum:'),
                sg.Input(str(current_settings.get('vmin', 0)), key='-MINIMO-', size=(15, 1)),
                sg.Text('Maximum:'),
                sg.Input(str(current_settings.get('vmax', 0)), key='-MAXIMO-', size=(15, 1))
            ],
            [
                sg.Checkbox(
                    'Global color scale (faster, recommended)',
                    key='-GLOBAL_SCALE-',
                    default=current_settings.get('global_scale', True)
                ),
                sg.Checkbox(
                    'Per-frame color scale (slower)',
                    key='-PERFRAME-',
                    default=current_settings.get('per_frame', False)
                )
            ]
        ], expand_x=True)],
        
        # Action buttons
        [
            sg.Push(),
            sg.Button('Save Settings', size=(15, 1)),
            sg.Button('Cancel', size=(15, 1))
        ]
    ]
    
    return sg.Window(
        "Configuration",
        layout,
        modal=True,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True
    )


# ===================== IMAGE EXPORT WINDOW =====================

def make_image_export_window(current_settings: dict = None) -> sg.Window:
    """
    Create window for PNG/JPG image export.
    
    Args:
        current_settings: Current settings dictionary (optional)
        
    Returns:
        PySimpleGUI Window
    """
    if current_settings is None:
        current_settings = {}
    
    layout = [
        [sg.Text(
            "Image Export (PNG/JPG)",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Format selection
        [sg.Frame("Image Format", [
            [
                sg.Radio('JPG (faster, smaller)', 'IMG_FMT', key='-JPG-', default=True),
                sg.Radio('PNG (lossless, larger)', 'IMG_FMT', key='-PNG-')
            ]
        ], expand_x=True)],
        
        # Quality settings
        [sg.Frame("Quality Settings", [
            [
                sg.Text('DPI (resolution) [90-200]:'),
                sg.Spin(
                    [90, 100, 120, 150, 180, 200],
                    initial_value=current_settings.get('jpg_dpi', 120),
                    key='-IMG_DPI-',
                    size=(6, 1)
                ),
                sg.Text("Higher = better quality but slower")
            ],
            [
                sg.Text('JPG Quality [1-100]:'),
                sg.Slider(
                    range=(1, 100),
                    default_value=current_settings.get('jpg_quality', 95),
                    orientation='h',
                    size=(30, 15),
                    key='-JPG_QUALITY-'
                )
            ]
        ], expand_x=True)],
        
        # Output settings
        [sg.Frame("Output Settings", [
            [
                sg.Text("Output folder name:"),
                sg.Input(
                    current_settings.get('output_folder', 'image_export'),
                    key='-OUT_FOLDER-',
                    size=(40, 1)
                ),
                sg.FolderBrowse()
            ],
            [
                sg.Checkbox(
                    'Overwrite existing files',
                    key='-OVERWRITE-',
                    default=current_settings.get('overwrite', False)
                )
            ],
            [
                sg.Checkbox(
                    'Open folder after export',
                    key='-OPEN_AFTER-',
                    default=current_settings.get('open_after', True)
                )
            ]
        ], expand_x=True)],
        
        # Progress
        [sg.Frame("Export Progress", [
            [sg.ProgressBar(100, orientation='h', size=(50, 20), key='-PROG-')],
            [sg.Text('Ready to export', key='-PROG_TEXT-', size=(60, 1))]
        ], expand_x=True)],
        
        # Action buttons
        [
            sg.Button('Start Export', size=(15, 1)),
            sg.Push(),
            sg.Button('Close', size=(15, 1))
        ]
    ]
    
    return sg.Window(
        "Image Export",
        layout,
        modal=True,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True
    )


# ===================== ANIMATION EXPORT WINDOW =====================

def make_animation_export_window(current_settings: dict = None) -> sg.Window:
    """
    Create window for animation export (MP4, GIF, AVI).
    
    Args:
        current_settings: Current settings dictionary (optional)
        
    Returns:
        PySimpleGUI Window
    """
    if current_settings is None:
        current_settings = {}
    
    layout = [
        [sg.Text(
            "Animation Export",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Format selection
        [sg.Frame("Animation Format", [
            [
                sg.Radio('MP4 (recommended, requires ffmpeg)', 'ANIM_FMT', 
                        key='-MP4-', default=True),
                sg.Radio('GIF (universal, larger files)', 'ANIM_FMT', key='-GIF-'),
                sg.Radio('AVI (requires ffmpeg)', 'ANIM_FMT', key='-AVI-')
            ]
        ], expand_x=True)],
        
        # Animation settings
        [sg.Frame("Animation Settings", [
            [
                sg.Text('Frames per second (FPS):'),
                sg.Spin(
                    [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 24, 30],
                    initial_value=current_settings.get('fps', 6),
                    key='-FPS-',
                    size=(5, 1)
                ),
                sg.Text("Higher = smoother but faster playback")
            ],
            [
                sg.Text('DPI (resolution) [90-200]:'),
                sg.Spin(
                    [90, 100, 120, 150, 180, 200],
                    initial_value=current_settings.get('anim_dpi', 150),
                    key='-ANIM_DPI-',
                    size=(6, 1)
                )
            ],
            [
                sg.Checkbox(
                    'Loop animation',
                    key='-LOOP-',
                    default=current_settings.get('loop', True)
                ),
                sg.Text('(GIF only)')
            ]
        ], expand_x=True)],
        
        # Video codec settings (MP4/AVI)
        [sg.Frame("Video Codec Settings", [
            [
                sg.Text('Bitrate (kbps):'),
                sg.Spin(
                    [500, 1000, 2000, 3000, 5000, 8000, 10000],
                    initial_value=current_settings.get('bitrate', 5000),
                    key='-BITRATE-',
                    size=(7, 1)
                ),
                sg.Text("Higher = better quality but larger file")
            ],
            [
                sg.Text('Codec:'),
                sg.Combo(
                    ['libx264', 'mpeg4', 'libx265'],
                    key='-CODEC-',
                    readonly=True,
                    default_value=current_settings.get('codec', 'libx264'),
                    size=(15, 1)
                )
            ]
        ], expand_x=True)],
        
        # Output settings
        [sg.Frame("Output Settings", [
            [
                sg.Text("Output filename:"),
                sg.Input(
                    current_settings.get('output_file', 'animation'),
                    key='-OUT_FILE-',
                    size=(40, 1)
                ),
                sg.FileSaveAs(file_types=(
                    ("MP4 Video", "*.mp4"),
                    ("GIF Animation", "*.gif"),
                    ("AVI Video", "*.avi")
                ))
            ],
            [
                sg.Checkbox(
                    'Overwrite existing file',
                    key='-OVERWRITE_ANIM-',
                    default=current_settings.get('overwrite', False)
                )
            ],
            [
                sg.Checkbox(
                    'Open file after export',
                    key='-OPEN_AFTER_ANIM-',
                    default=current_settings.get('open_after', True)
                )
            ]
        ], expand_x=True)],
        
        # Progress
        [sg.Frame("Export Progress", [
            [sg.ProgressBar(100, orientation='h', size=(50, 20), key='-PROG_ANIM-')],
            [sg.Text('Ready to export', key='-PROG_TEXT_ANIM-', size=(60, 1))]
        ], expand_x=True)],
        
        # Action buttons
        [
            sg.Button('Start Export', size=(15, 1)),
            sg.Push(),
            sg.Button('Close', size=(15, 1))
        ]
    ]
    
    return sg.Window(
        "Animation Export",
        layout,
        modal=True,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True
    )


# ===================== SHAPEFILE EXPORT WINDOW =====================

def make_shapefile_export_window(current_settings: dict = None) -> sg.Window:
    """
    Create window for shapefile export (QGIS integration).
    
    Args:
        current_settings: Current settings dictionary (optional)
        
    Returns:
        PySimpleGUI Window
    """
    if current_settings is None:
        current_settings = {}
    
    layout = [
        [sg.Text(
            "Shapefile Export for QGIS",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Format selection
        [sg.Frame("Export Format", [
            [
                sg.Radio('GeoTIFF (raster)', 'SHAPE_FMT', key='-GEOTIFF-', default=True),
                sg.Radio('Shapefile (vector points)', 'SHAPE_FMT', key='-SHAPEFILE-'),
                sg.Radio('GeoJSON (vector)', 'SHAPE_FMT', key='-GEOJSON-')
            ],
            [
                sg.Radio('CSV with coordinates', 'SHAPE_FMT', key='-CSV_GEO-'),
                sg.Radio('NetCDF', 'SHAPE_FMT', key='-NETCDF-')
            ]
        ], expand_x=True)],
        
        # GeoTIFF settings
        [sg.Frame("GeoTIFF Settings", [
            [
                sg.Text('NoData value:'),
                sg.Input(
                    str(current_settings.get('tiff_nodata', -9999)),
                    key='-TIFF_NODATA-',
                    size=(15, 1)
                )
            ],
            [
                sg.Text('Compression:'),
                sg.Combo(
                    ['LZW', 'DEFLATE', 'PACKBITS', 'None'],
                    key='-TIFF_COMPRESS-',
                    readonly=True,
                    default_value=current_settings.get('tiff_compress', 'LZW'),
                    size=(15, 1)
                )
            ],
            [
                sg.Checkbox(
                    'Create tiled GeoTIFF',
                    key='-TIFF_TILED-',
                    default=current_settings.get('tiff_tiled', True)
                ),
                sg.Text('Block size:'),
                sg.Spin([128, 256, 512], initial_value=256, key='-TIFF_BLOCKSIZE-', size=(5, 1))
            ]
        ], expand_x=True)],
        
        # Vector settings
        [sg.Frame("Vector Settings (Shapefile/GeoJSON)", [
            [
                sg.Text('Point type:'),
                sg.Combo(
                    ['Grid centers', 'Grid corners'],
                    key='-VECTOR_TYPE-',
                    readonly=True,
                    default_value='Grid centers',
                    size=(20, 1)
                )
            ],
            [
                sg.Checkbox(
                    'Include NoData points',
                    key='-INCLUDE_NODATA-',
                    default=False
                )
            ],
            [
                sg.Checkbox(
                    'Add timestamp attribute',
                    key='-ADD_TIMESTAMP-',
                    default=True
                )
            ]
        ], expand_x=True)],
        
        # Coordinate system
        [sg.Frame("Coordinate Reference System", [
            [
                sg.Text('CRS:'),
                sg.Combo(
                    ['EPSG:4326 (WGS84)', 'EPSG:3857 (Web Mercator)', 'Custom EPSG...'],
                    key='-CRS-',
                    readonly=True,
                    default_value='EPSG:4326 (WGS84)',
                    size=(30, 1)
                )
            ],
            [
                sg.Text('Custom EPSG code:'),
                sg.Input('', key='-CUSTOM_EPSG-', size=(15, 1), disabled=True)
            ]
        ], expand_x=True)],
        
        # Output settings
        [sg.Frame("Output Settings", [
            [
                sg.Text("Output folder:"),
                sg.Input(
                    current_settings.get('output_folder', 'shapefile_export'),
                    key='-OUT_FOLDER_SHAPE-',
                    size=(40, 1)
                ),
                sg.FolderBrowse()
            ],
            [
                sg.Checkbox(
                    'Create QGIS project file (.qgs)',
                    key='-CREATE_QGS-',
                    default=current_settings.get('create_qgs', True)
                )
            ],
            [
                sg.Checkbox(
                    'Open in QGIS after export',
                    key='-OPEN_QGIS-',
                    default=False
                )
            ]
        ], expand_x=True)],
        
        # Progress
        [sg.Frame("Export Progress", [
            [sg.ProgressBar(100, orientation='h', size=(50, 20), key='-PROG_SHAPE-')],
            [sg.Text('Ready to export', key='-PROG_TEXT_SHAPE-', size=(60, 1))]
        ], expand_x=True)],
        
        # Action buttons
        [
            sg.Button('Start Export', size=(15, 1)),
            sg.Push(),
            sg.Button('Close', size=(15, 1))
        ]
    ]
    
    return sg.Window(
        "Shapefile Export",
        layout,
        modal=True,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True
    )


# ===================== COLORBAR PREVIEW =====================

class ColorbarPreview:
    """
    Manages colorbar preview canvas in configuration window.
    """
    
    def __init__(self, tk_canvas):
        """
        Initialize colorbar preview.
        
        Args:
            tk_canvas: Tkinter canvas widget
        """
        self.canvas = tk_canvas
        self.figure_canvas_agg = None
        self.gradient = np.linspace(0, 1, 256)
        self.gradient = np.vstack((self.gradient, self.gradient))
    
    def update(self, colormap_name: str) -> None:
        """
        Update preview with new colormap.
        
        Args:
            colormap_name: Matplotlib colormap name
        """
        # Clean up previous figure
        if self.figure_canvas_agg:
            try:
                self.figure_canvas_agg.get_tk_widget().forget()
            except Exception:
                pass
        
        # Create new figure
        fig, ax = plt.subplots(1, figsize=(6, 0.2))
        ax.imshow(
            self.gradient,
            aspect='auto',
            cmap=mpl.colormaps[colormap_name]
        )
        ax.set_axis_off()
        
        # Draw to canvas
        self.figure_canvas_agg = FigureCanvasTkAgg(fig, self.canvas)
        self.figure_canvas_agg.draw()
        self.figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
        
        # Close figure immediately
        plt.close(fig)


# ===================== BUSY MODAL =====================

def open_busy_modal(message: str = "Processingâ€¦ Please wait") -> sg.Window:
    """
    Open blocking modal window to indicate busy state.
    
    Args:
        message: Message to display
        
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(
            message,
            key='-TXT-',
            size=(60, 3),
            justification='center'
        )]
    ]
    
    window = sg.Window(
        'Exportingâ€¦',
        layout,
        modal=True,
        keep_on_top=True,
        finalize=True,
        no_titlebar=False
    )
    
    window.refresh()
    return window


def close_busy_modal(window: sg.Window) -> None:
    """
    Close busy modal window.
    
    Args:
        window: Window to close
    """
    try:
        window.close()
    except Exception:
        pass


# ===================== HELPER DIALOGS =====================

def show_info_popup(title: str, message: str, size: tuple = (60, 10)) -> None:
    """
    Show scrollable information popup.
    
    Args:
        title: Popup title
        message: Message text
        size: Window size (width, height)
    """
    sg.popup_scrolled(message, title=title, size=size)


def show_error_popup(message: str) -> None:
    """
    Show error popup.
    
    Args:
        message: Error message
    """
    sg.popup_error(message)


def show_success_popup(message: str) -> None:
    """
    Show success popup.
    
    Args:
        message: Success message
    """
    sg.popup(message)


# ===================== PROGRESS DIALOG =====================

def make_progress_dialog(title: str = "Processing") -> sg.Window:
    """
    Create a progress dialog window.
    
    Args:
        title: Dialog title
        
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(title, font=("Helvetica", 12, "bold"))],
        [sg.ProgressBar(100, orientation='h', size=(40, 20), key='-PROGRESS-')],
        [sg.Text('Initializing...', key='-STATUS-', size=(50, 1))],
        [sg.Text('0 / 0 frames', key='-COUNTER-', size=(50, 1))],
        [sg.Push(), sg.Button('Cancel', size=(10, 1))]
    ]
    
    return sg.Window(
        title,
        layout,
        modal=True,
        finalize=True,
        keep_on_top=True,
        disable_close=False
    )


def update_progress_dialog(
    window: sg.Window,
    current: int,
    total: int,
    status: str = ""
) -> None:
    """
    Update progress dialog with current status.
    
    Args:
        window: Progress dialog window
        current: Current item number
        total: Total number of items
        status: Status message
    """
    try:
        if total > 0:
            progress = int((current / total) * 100)
            window['-PROGRESS-'].update(progress)
        
        if status:
            window['-STATUS-'].update(status)
        
        window['-COUNTER-'].update(f'{current} / {total} frames')
        window.refresh()
    except Exception:
        pass


# ===================== SETTINGS SUMMARY DIALOG =====================

def show_settings_summary(settings: dict) -> None:
    """
    Display a summary of current settings.
    
    Args:
        settings: Settings dictionary
    """
    summary_lines = [
        "Current Configuration Summary",
        "=" * 50,
        "",
        f"Variable: {settings.get('name', 'N/A')}",
        f"Vertical mode: {settings.get('reduce_mode', 'top')}",
        f"Reduce index: {settings.get('reduce_index', 0)}",
        "",
        "NoData Handling:",
        f"  Sentinel values: {settings.get('nodata_values', [])}",
        f"  Auto threshold: {settings.get('auto_land_threshold', True)}",
        "",
        "Basemap:",
        f"  Type: {settings.get('basemap', 'None')}",
        f"  Coastline: {settings.get('use_coastline', True)}",
        f"  Tile zoom: {settings.get('tile_zoom', 12)}",
        f"  Fast tiles: {settings.get('fast_tiles', True)}",
        "",
        "Color Scale:",
        f"  Colormap: {settings.get('colormap', 'rainbow')}",
        f"  Original: {settings.get('original', True)}",
        f"  Min value: {settings.get('vmin', 'auto')}",
        f"  Max value: {settings.get('vmax', 'auto')}",
        f"  Global scale: {settings.get('global_scale', True)}",
    ]
    
    summary = "\n".join(summary_lines)
    show_info_popup("Settings Summary", summary, size=(60, 25))


# ===================== EXPORT FORMAT INFO =====================

EXPORT_FORMAT_INFO = {
    'jpg': {
        'name': 'JPEG Image',
        'pros': [
            'Fast export',
            'Small file size',
            'Universal compatibility',
            'Good for web sharing'
        ],
        'cons': [
            'Lossy compression',
            'No transparency support',
            'Quality loss with repeated saves'
        ],
        'recommended': 'Quick previews and web sharing'
    },
    'png': {
        'name': 'PNG Image',
        'pros': [
            'Lossless compression',
            'Transparency support',
            'Better for scientific visualization',
            'No quality loss'
        ],
        'cons': [
            'Larger file size',
            'Slower export than JPG'
        ],
        'recommended': 'High-quality visualization and publishing'
    },
    'mp4': {
        'name': 'MP4 Video',
        'pros': [
            'Excellent compression',
            'Universal playback support',
            'Smooth playback',
            'Professional quality'
        ],
        'cons': [
            'Requires ffmpeg',
            'Longer export time',
            'Cannot edit individual frames'
        ],
        'recommended': 'Presentations and final animations'
    },
    'gif': {
        'name': 'GIF Animation',
        'pros': [
            'No external dependencies',
            'Loops automatically',
            'Universal compatibility',
            'Easy to share'
        ],
        'cons': [
            'Limited to 256 colors',
            'Larger file size',
            'Lower quality than video'
        ],
        'recommended': 'Quick animations and web sharing'
    },
    'avi': {
        'name': 'AVI Video',
        'pros': [
            'High quality',
            'Wide software support',
            'Good for editing'
        ],
        'cons': [
            'Very large file size',
            'Requires ffmpeg',
            'Not web-friendly'
        ],
        'recommended': 'Video editing and archival'
    },
    'geotiff': {
        'name': 'GeoTIFF',
        'pros': [
            'Georeferenced',
            'QGIS compatible',
            'Industry standard',
            'Preserves spatial information'
        ],
        'cons': [
            'Requires rasterio',
            'Large file size',
            'Raster format only'
        ],
        'recommended': 'GIS analysis and spatial processing'
    },
    'shapefile': {
        'name': 'Shapefile',
        'pros': [
            'Vector format',
            'QGIS compatible',
            'Attribute tables',
            'Precise coordinates'
        ],
        'cons': [
            'Multiple files (.shp, .shx, .dbf)',
            'Slower export',
            'Large for dense grids'
        ],
        'recommended': 'Point-based GIS analysis'
    },
    'geojson': {
        'name': 'GeoJSON',
        'pros': [
            'Human-readable',
            'Web-friendly',
            'Single file',
            'Modern GIS standard'
        ],
        'cons': [
            'Large file size',
            'Slower parsing',
            'Not ideal for huge datasets'
        ],
        'recommended': 'Web mapping and modern GIS workflows'
    },
    'csv': {
        'name': 'CSV with coordinates',
        'pros': [
            'Universal compatibility',
            'Easy to process',
            'Human-readable',
            'No dependencies'
        ],
        'cons': [
            'Very large files',
            'Very slow export',
            'No spatial indexing',
            'Memory intensive'
        ],
        'recommended': 'Custom processing and statistics'
    }
}


def show_format_info(format_key: str) -> None:
    """
    Show information about a specific export format.
    
    Args:
        format_key: Format key (e.g., 'jpg', 'mp4', 'geotiff')
    """
    info = EXPORT_FORMAT_INFO.get(format_key.lower())
    
    if not info:
        show_error_popup(f"No information available for format: {format_key}")
        return
    
    lines = [
        f"{info['name']}",
        "=" * 60,
        "",
        "Advantages:",
    ]
    
    for pro in info['pros']:
        lines.append(f"  âœ“ {pro}")
    
    lines.extend(["", "Disadvantages:"])
    
    for con in info['cons']:
        lines.append(f"  âœ— {con}")
    
    lines.extend([
        "",
        f"Recommended for: {info['recommended']}"
    ])
    
    show_info_popup(f"Format Info: {info['name']}", "\n".join(lines), size=(70, 20))


# ===================== BATCH EXPORT WINDOW =====================

def make_batch_export_window() -> sg.Window:
    """
    Create window for batch exporting multiple variables.
    
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(
            "Batch Export Multiple Variables",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Variable selection
        [sg.Frame("Variable Selection", [
            [
                sg.Listbox(
                    [],
                    key='-VAR_LIST-',
                    size=(40, 10),
                    select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                    enable_events=True
                )
            ],
            [
                sg.Button('Select All', size=(12, 1)),
                sg.Button('Deselect All', size=(12, 1)),
                sg.Text('', key='-SELECTED_COUNT-', size=(30, 1))
            ]
        ], expand_x=True)],
        
        # Export settings
        [sg.Frame("Batch Export Settings", [
            [
                sg.Text("Export format:"),
                sg.Combo(
                    ['JPG', 'PNG', 'MP4', 'GIF', 'GeoTIFF'],
                    key='-BATCH_FORMAT-',
                    readonly=True,
                    default_value='JPG',
                    size=(15, 1)
                )
            ],
            [
                sg.Text("Output base folder:"),
                sg.Input('batch_export', key='-BATCH_FOLDER-', size=(35, 1)),
                sg.FolderBrowse()
            ],
            [
                sg.Checkbox(
                    'Create subfolder for each variable',
                    key='-BATCH_SUBFOLDERS-',
                    default=True
                )
            ],
            [
                sg.Checkbox(
                    'Use same settings for all variables',
                    key='-BATCH_SAME_SETTINGS-',
                    default=True
                )
            ],
            [
                sg.Checkbox(
                    'Stop on error',
                    key='-BATCH_STOP_ERROR-',
                    default=False
                )
            ]
        ], expand_x=True)],
        
        # Progress
        [sg.Frame("Batch Progress", [
            [sg.Text("Overall progress:")],
            [sg.ProgressBar(100, orientation='h', size=(50, 20), key='-BATCH_PROG-')],
            [sg.Text('0 / 0 variables completed', key='-BATCH_STATUS-', size=(60, 1))],
            [sg.Multiline(
                '',
                key='-BATCH_LOG-',
                size=(70, 10),
                autoscroll=True,
                disabled=True,
                font=UIConfig.CONSOLE_FONT
            )]
        ], expand_x=True)],
        
        # Action buttons
        [
            sg.Button('Start Batch Export', size=(15, 1)),
            sg.Button('Pause', size=(10, 1), disabled=True),
            sg.Push(),
            sg.Button('Close', size=(10, 1))
        ]
    ]
    
    return sg.Window(
        "Batch Export",
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True,
        size=(800, 700)
    )


# ===================== COMPARISON VIEWER WINDOW =====================

def make_comparison_viewer_window() -> sg.Window:
    """
    Create window for side-by-side comparison of two time series.
    
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(
            "Time Series Comparison Viewer",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Left series
        [sg.Frame("Left Series", [
            [
                sg.Text("Folder:"),
                sg.Input(key='-LEFT_FOLDER-', size=(40, 1)),
                sg.FolderBrowse()
            ],
            [
                sg.Text("Variable:"),
                sg.Input(key='-LEFT_VAR-', size=(40, 1), disabled=True)
            ]
        ], expand_x=True)],
        
        # Right series
        [sg.Frame("Right Series", [
            [
                sg.Text("Folder:"),
                sg.Input(key='-RIGHT_FOLDER-', size=(40, 1)),
                sg.FolderBrowse()
            ],
            [
                sg.Text("Variable:"),
                sg.Input(key='-RIGHT_VAR-', size=(40, 1), disabled=True)
            ]
        ], expand_x=True)],
        
        # Sync settings
        [sg.Frame("Synchronization", [
            [
                sg.Checkbox(
                    'Synchronize time sliders',
                    key='-SYNC_TIME-',
                    default=True
                ),
                sg.Checkbox(
                    'Synchronize color scales',
                    key='-SYNC_COLOR-',
                    default=False
                )
            ]
        ], expand_x=True)],
        
        # Canvas for side-by-side display
        [
            sg.Column([[sg.Canvas(key='-LEFT_CANVAS-', size=(400, 400))]], 
                     vertical_alignment='top'),
            sg.VerticalSeparator(),
            sg.Column([[sg.Canvas(key='-RIGHT_CANVAS-', size=(400, 400))]], 
                     vertical_alignment='top')
        ],
        
        # Controls
        [sg.Frame("Playback Controls", [
            [
                sg.Button('<<', key='-COMP_PREV-', size=(4, 1)),
                sg.Button('>>', key='-COMP_NEXT-', size=(4, 1)),
                sg.Button('>', key='-COMP_PLAY-', size=(4, 1)),
                sg.Slider(
                    range=(0, 100),
                    default_value=0,
                    orientation='h',
                    size=(40, 15),
                    key='-COMP_SLIDER-',
                    enable_events=True
                ),
                sg.Text('0 / 0', key='-COMP_INDEX-', size=(10, 1))
            ]
        ], expand_x=True)],
        
        # Close button
        [sg.Push(), sg.Button('Close', size=(10, 1))]
    ]
    
    return sg.Window(
        "Comparison Viewer",
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True,
        size=(900, 700)
    )


# ===================== STATISTICS WINDOW =====================

def make_statistics_window() -> sg.Window:
    """
    Create window for displaying time series statistics.
    
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(
            "Time Series Statistics",
            font=UIConfig.TITLE_FONT,
            justification="center",
            expand_x=True
        )],
        
        # Input
        [sg.Frame("Data Source", [
            [
                sg.Text("HDF5 file:"),
                sg.Input(key='-STATS_FILE-', size=(40, 1)),
                sg.FileBrowse(file_types=(("HDF5 Files", "*.hdf5"),))
            ],
            [
                sg.Text("Variable:"),
                sg.Combo([], key='-STATS_VAR-', size=(40, 1), readonly=True)
            ],
            [sg.Button('Compute Statistics', size=(20, 1))]
        ], expand_x=True)],
        
        # Global statistics
        [sg.Frame("Global Statistics", [
            [
                sg.Column([
                    [sg.Text("Minimum:", size=(15, 1))],
                    [sg.Text("Maximum:", size=(15, 1))],
                    [sg.Text("Mean:", size=(15, 1))],
                    [sg.Text("Std. Deviation:", size=(15, 1))],
                    [sg.Text("Median:", size=(15, 1))]
                ]),
                sg.Column([
                    [sg.Text('---', key='-STATS_MIN-', size=(20, 1))],
                    [sg.Text('---', key='-STATS_MAX-', size=(20, 1))],
                    [sg.Text('---', key='-STATS_MEAN-', size=(20, 1))],
                    [sg.Text('---', key='-STATS_STD-', size=(20, 1))],
                    [sg.Text('---', key='-STATS_MEDIAN-', size=(20, 1))]
                ])
            ]
        ], expand_x=True)],
        
        # Temporal statistics
        [sg.Frame("Temporal Statistics", [
            [
                sg.Column([
                    [sg.Text("Number of timesteps:", size=(20, 1))],
                    [sg.Text("Time range:", size=(20, 1))],
                    [sg.Text("Temporal mean:", size=(20, 1))],
                    [sg.Text("Temporal std:", size=(20, 1))]
                ]),
                sg.Column([
                    [sg.Text('---', key='-STATS_NTIMES-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_TIMERANGE-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_TMEAN-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_TSTD-', size=(30, 1))]
                ])
            ]
        ], expand_x=True)],
        
        # Spatial statistics
        [sg.Frame("Spatial Statistics", [
            [
                sg.Column([
                    [sg.Text("Grid dimensions:", size=(20, 1))],
                    [sg.Text("Valid data points:", size=(20, 1))],
                    [sg.Text("NoData points:", size=(20, 1))],
                    [sg.Text("Data coverage:", size=(20, 1))]
                ]),
                sg.Column([
                    [sg.Text('---', key='-STATS_DIMS-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_VALID-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_NODATA-', size=(30, 1))],
                    [sg.Text('---', key='-STATS_COVERAGE-', size=(30, 1))]
                ])
            ]
        ], expand_x=True)],
        
        # Export statistics
        [sg.Frame("Export", [
            [
                sg.Button('Export to CSV', size=(15, 1)),
                sg.Button('Export to TXT', size=(15, 1)),
                sg.Button('Copy to Clipboard', size=(15, 1))
            ]
        ], expand_x=True)],
        
        # Close button
        [sg.Push(), sg.Button('Close', size=(10, 1))]
    ]
    
    return sg.Window(
        "Statistics",
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True
    )


# ===================== QUICK EXPORT DIALOG =====================

# ===================== VERTICAL SECTION WINDOW =====================

def make_vertical_section_window(
    lat_range: Tuple[float, float] = None,
    lon_range: Tuple[float, float] = None
) -> sg.Window:
    """
    Create window for vertical section visualization.
    
    Args:
        lat_range: Tuple of (min_lat, max_lat)
        lon_range: Tuple of (min_lon, max_lon)
        
    Returns:
        PySimpleGUI Window
    """
    if lat_range is None:
        lat_range = (-90.0, 90.0)
    if lon_range is None:
        lon_range = (-180.0, 180.0)
    
    layout = [
#        [sg.Text(
#            "Vertical Section Viewer",
#            font=UIConfig.TITLE_FONT,
#            justification="center",
#            expand_x=True
#        )],
        
        # Section configuration
        [sg.Frame("Section Configuration", [
            [
                sg.Radio('Longitudinal (Line at given latitude)', 'SECTION', 
                        key='-SECTION_LON-', default=True, enable_events=True),
                sg.Radio('Latitudinal (Line at given longitude)', 'SECTION', 
                        key='-SECTION_LAT-', enable_events=True)
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Text("Select section position:", font=("Helvetica", 10, "bold"))
            ],
            [
                sg.Text("Latitude:", size=(12, 1)),
                sg.Slider(
                    range=lat_range,
                    default_value=(lat_range[0] + lat_range[1]) / 2,
                    resolution=0.001,
                    orientation='h',
                    size=(20, 15),
                    key='-SECTION_LAT_VAL-',
                    enable_events=True,
                    disabled=False
                ),
                sg.Input(
                    f'{(lat_range[0] + lat_range[1]) / 2:.4f}',
                    key='-SECTION_LAT_INPUT-',
                    size=(12, 1),
                    enable_events=True,
                    disabled=False
                ),
                sg.Text("        Longitude:", size=(12, 1)),
                sg.Slider(
                    range=lon_range,
                    default_value=(lon_range[0] + lon_range[1]) / 2,
                    resolution=0.001,
                    orientation='h',
                    size=(20, 15),
                    key='-SECTION_LON_VAL-',
                    enable_events=True,
                    disabled=True
                ),
                sg.Input(
                    f'{(lon_range[0] + lon_range[1]) / 2:.4f}',
                    key='-SECTION_LON_INPUT-',
                    size=(12, 1),
                    enable_events=True,
                    disabled=True
                )
            ]
        ], expand_x=True)],
        
        # Data source
        [sg.Frame("Data Source", [
            [
                sg.Text("Variable:"),
                sg.Input(key='-VS_VAR-', size=(30, 1), disabled=True),
                
                sg.Text("Timestep:"),
                sg.Slider(
                    range=(0, 100),
                    default_value=0,
                    orientation='h',
                    size=(25, 15),
                    key='-VS_TIMESTEP-',
                    enable_events=True
                ),
                sg.Text('0 / 0', key='-VS_TIME_INFO-', size=(15, 1)),

                sg.Text("Timestamp:"),
                sg.Input(key='-VS_TIMESTAMP-', size=(25, 1), disabled=True)
            ]
        ], expand_x=True)],
        
        # Visualization options
        [sg.Frame("Visualization Options", [
             [
                 sg.Text("Colormap:"),
                 sg.Combo(
                     COLOR_SCALE_OPTIONS,
                     key='-VS_CMAP-',
                     readonly=True,
                     default_value='viridis',
                     size=(20, 1),
                     enable_events=True
                 ),
                 sg.Checkbox('Show altimetry/bathymetry', key='-VS_BATHY-', default=True),
                 sg.Checkbox('Show grid', key='-VS_GRID-', default=True),
                 sg.Text("Color limits:"),
                 sg.Text("Min:"),
                 sg.Input('auto', key='-VS_VMIN-', size=(10, 1)),
                 sg.Text("Max:"),
                 sg.Input('auto', key='-VS_VMAX-', size=(10, 1)),
                 sg.Button('Reset', key='-VS_RESET_COLORS-', size=(10, 1))
             ],
             [
                 sg.Text("Point Size:"),
                 sg.Input('10', key='-P_SIZE-', size=(10, 1)),
                 sg.Text("Layer Vertical Exaggeration:"),
                 sg.Input('1.0', key='-VS_VE-', size=(10, 1)),
                 sg.Button('Apply VE', key='-VS_APPLY_VE-', size=(10, 1)),
                 sg.Text("(MOHID Land only - Rebuilds depth grid)", font=("Helvetica", 9, "italic"), 
                 key='-VS_VE_NOTE-'),
             ]
             ], expand_x=True)],

        # Canvas for section plot
        [sg.Column([
        [sg.Frame("Vertical Section", [
            [sg.Canvas(key='-VS_CANVAS-', size=(700, 300))]
        ], expand_x=False, expand_y=False)]]),
        
        # Canvas for location map
        sg.Column([
        [sg.Frame("Section Location Map", [
            [sg.Canvas(key='-VS_MAP_CANVAS-', size=(400, 300))]
        ], expand_x=False)]])
        ],
        
        # Statistics
        [sg.Frame("Section Statistics", [
            [
                sg.Column([
                    [sg.Text("Min:", size=(12, 1))],
                    [sg.Text("Max:", size=(12, 1))]
                ]),
                sg.Column([
                    [sg.Text('---', key='-VS_STAT_MIN-', size=(15, 1))],
                    [sg.Text('---', key='-VS_STAT_MAX-', size=(15, 1))]
                ]),
                sg.Column([
                    [sg.Text("Mean:", size=(12, 1))],
                    [sg.Text("Std Dev:", size=(12, 1))]
                ]),
                sg.Column([                   
                    [sg.Text('---', key='-VS_STAT_MEAN-', size=(15, 1))],
                    [sg.Text('---', key='-VS_STAT_STD-', size=(15, 1))]
                ]),
                sg.Column([
                    [sg.Text("Median:", size=(12, 1))],
                    [sg.Text("Valid points:", size=(12, 1))]
                ]),
                sg.Column([
                    [sg.Text('---', key='-VS_STAT_MEDIAN-', size=(15, 1))],
                    [sg.Text('---', key='-VS_STAT_VALID-', size=(15, 1))]
                ])
            ]
        ], expand_x=True)],
        
        # Status bar
        [
            sg.Text("Ready", key='-STATUS-', size=(100, 1), 
                   relief=sg.RELIEF_SUNKEN, font=("Helvetica", 9),
                   text_color='white', background_color='#2b5b84')
        ],
        
        # Action buttons
        [
            sg.Button('Update Section', size=(15, 1)),
            sg.Button('Export to CSV', key='-VS_EXPORT_CSV-', size=(15, 1)),
            sg.Button('Export Image', key='-VS_EXPORT_IMG-', size=(15, 1)),
            sg.Push(),
            sg.Button('Close', size=(10, 1))
        ]
    ]
    
    return sg.Window(
        "Vertical Section Viewer",
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        resizable=True,
        size=(1200, 800),
        location=(100, 50)
    )


def quick_export_dialog(var_name: str) -> Optional[Tuple[str, dict]]:
    """
    Show quick export dialog with minimal options.
    
    Args:
        var_name: Variable name
        
    Returns:
        Tuple of (format, settings) or None if cancelled
    """
    layout = [
        [sg.Text(f"Quick Export: {var_name}", font=("Helvetica", 12, "bold"))],
        [sg.Text("Choose export format:")],
        [
            sg.Radio('JPG Images', 'QUICK', key='-Q_JPG-', default=True),
            sg.Radio('MP4 Video', 'QUICK', key='-Q_MP4-'),
            sg.Radio('GIF', 'QUICK', key='-Q_GIF-')
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Quick settings:")],
        [
            sg.Text("Quality:"),
            sg.Combo(['Draft', 'Standard', 'High', 'Publication'], 
                    default_value='Standard', key='-Q_QUALITY-', readonly=True)
        ],
        [
            sg.Checkbox('Use basemap', key='-Q_BASEMAP-', default=True),
            sg.Checkbox('Show coastlines', key='-Q_COAST-', default=True)
        ],
        [sg.Push(), sg.Button('Export', size=(10, 1)), sg.Button('Cancel', size=(10, 1))]
    ]
    
    window = sg.Window(
        "Quick Export",
        layout,
        modal=True,
        finalize=True,
        keep_on_top=True
    )
    
    result = None
    
    while True:
        event, values = window.read()
        
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        
        if event == 'Export':
            # Determine format
            if values['-Q_JPG-']:
                fmt = 'jpg'
            elif values['-Q_MP4-']:
                fmt = 'mp4'
            else:
                fmt = 'gif'
            
            # Quality presets
            quality_map = {
                'Draft': {'dpi': 90, 'fps': 4},
                'Standard': {'dpi': 120, 'fps': 6},
                'High': {'dpi': 150, 'fps': 10},
                'Publication': {'dpi': 200, 'fps': 15}
            }
            
            quality = quality_map[values['-Q_QUALITY-']]
            
            settings = {
                'use_basemap': values['-Q_BASEMAP-'],
                'use_coastline': values['-Q_COAST-'],
                'dpi': quality['dpi'],
                'fps': quality['fps']
            }
            
            result = (fmt, settings)
            break
    
    window.close()
    return result
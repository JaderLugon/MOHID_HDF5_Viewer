"""
MOHID HDF5 Viewer - Main Application (Refactored)
Entry point and GUI management with modular window architecture
"""
import sys
import os
from typing import Optional, Dict, Any

import numpy as np

# Matplotlib configuration
import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.pyplot as plt
plt.ioff()  # Turn off interactive mode

import FreeSimpleGUI as sg

from .config import (
    logger, UIConfig, BASEMAP_OPTIONS, COLOR_SCALE_OPTIONS,
    EXPORT_FORMATS, get_message, APP_TITLE, APP_DESCRIPTION,
    APP_AUTHORS, Dependencies, UserPreferences,
    setup_logging, #DS_18/11
    finalize_log, #DS_18/11
    logger #DS_18/11
)
from .hdf5_utils import (
    get_available_variables, load_variable_data,
    probe_k_axis_and_count, compute_k_depths_mean
)
from .exporters import (
    export_animation, export_as_jpgs,
    export_as_geotiffs, export_as_csvs
)
from .viewer import JpgSeriesViewer, open_viewer_window
from .gui_components import (
    make_main_window, make_config_window, make_image_export_window,
    make_animation_export_window, make_shapefile_export_window,
    make_vertical_section_window,
    show_welcome_dialog, ColorbarPreview, 
    open_busy_modal, close_busy_modal, show_error_popup, show_success_popup,
    update_progress_dialog, make_progress_dialog
)
from .vertical_section import (
    parse_geometry_file, build_3d_depth_grid_water, build_3d_depth_grid_land,
    load_3d_variable_timestep, extract_longitudinal_section,
    extract_latitudinal_section, plot_vertical_section,
    plot_section_with_bathymetry, plot_section_location_on_map,
    compute_section_statistics, export_section_to_csv,
)

logger, log_file_handler = setup_logging()

class AppState:
    """Application state manager"""
    
    def __init__(self):
        self.last_jpg_dir: Optional[str] = None
        self.viewer_dir: Optional[str] = None
        self.hdf_path: Optional[str] = None
        self.current_var: Optional[str] = None
        self.variables_list: list = []
        self.geometry_path: Optional[str] = None
        self.model_type: str = 'MOHID Water'  # 'MOHID Water' ou 'MOHID Land'        

        # K-layer metadata
        self.k_metadata = {
            "has_k": False,
            "k_count": 0,
            "k_depths": None
        }
        
        # Current settings
        self.settings = self._default_settings()
        
        # Window references
        self.config_window: Optional[sg.Window] = None
        self.image_window: Optional[sg.Window] = None
        self.anim_window: Optional[sg.Window] = None
        self.shape_window: Optional[sg.Window] = None
        self.vsection_window: Optional[sg.Window] = None
        self.colorbar_preview: Optional[ColorbarPreview] = None
        
        # Vertical section data
        self.geometry_info: Optional[Dict] = None
        self.depth_grid_3d: Optional[np.NDArray] = None
        self.vs_canvas_agg = None
        self.vs_map_canvas_agg = None
    
    def _default_settings(self) -> Dict[str, Any]:
        """Return default settings"""
        return {
            'reduce_mode': 'top',
            'reduce_index': 0,
            'nodata_values': [-99.0],
            'nodata_values_text': '-99',
            'auto_land_threshold': True,
            'basemap': 'Google Satellite (imagery)',
            'use_tiles': True,
            'use_coastline': True,
            'tile_zoom': 12,
            'fast_tiles': True,
            'colormap': 'rainbow',
            'original': True,
            'vmin': 0.0,
            'vmax': 0.0,
            'p_size': 10,
            'global_scale': True,
            'per_frame': False,
            'jpg_dpi': 120,
            'jpg_quality': 95,
            'fps': 6,
            'output_folder': 'image_export',
            'overwrite': False,
            'open_after': True,
            'tiff_nodata': -9999.0,
            'tiff_compress': 'LZW',
            'tiff_tiled': True
        }
    
    def reset_k_metadata(self):
        """Reset k-layer metadata"""
        self.k_metadata = {
            "has_k": False,
            "k_count": 0,
            "k_depths": None
        }

    def reset_geometry_data(self):
        """Reset geometry and vertical section data"""
        logger.info("Resetting geometry data...")
        self.geometry_info = None
        self.depth_grid_3d = None
        
        # Cleanup canvas references
        if self.vs_canvas_agg:
            try:
                self.vs_canvas_agg.get_tk_widget().destroy()
            except:
                pass
            self.vs_canvas_agg = None
        
        if self.vs_map_canvas_agg:
            try:
                self.vs_map_canvas_agg.get_tk_widget().destroy()
            except:
                pass
            self.vs_map_canvas_agg = None
        
        logger.info("Geometry data reset complete")
        
    def update_settings(self, new_settings: dict):
        """Update current settings"""
        self.settings.update(new_settings)


def parse_nodata_values(text: str) -> list:
    """
    Parse comma/semicolon separated NoData values.
    
    Args:
        text: Input text with values
        
    Returns:
        List of float values
    """
    values = []
    if not text:
        return values
    
    for token in text.replace(';', ',').split(','):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError:
            logger.warning(f"Could not parse NoData value: {token}")
    
    return values


def refresh_k_metadata(window: sg.Window, state: AppState):
    """
    Refresh k-layer metadata for current variable.
    
    Args:
        window: Configuration window
        state: Application state
    """
    if not state.hdf_path or not state.current_var:
        return
    
    try:
        import h5py
        with h5py.File(state.hdf_path, "r") as f:
            lat_full = f["Grid/Latitude"][:]
            var_path = f"Results/{state.current_var}"
            
            k_axis, k_count = probe_k_axis_and_count(
                f, var_path, state.current_var, lat_full.shape
            )
            
            if not k_axis and not k_count:
                # 2D variable
                state.reset_k_metadata()
                window['-K_INFO-'].update("Detected: 2-D variable (no vertical k)")
                window['-K_COMBO-'].update(values=[], value='')
                window['-VK-'].update(disabled=True)
                window['-K_COMBO-'].update(disabled=True)
                window['-SURF-'].update(True)
                return
            
            # 3D variable
            depths = compute_k_depths_mean(f, lat_full.shape, k_count)
            state.k_metadata = {
                "has_k": True,
                "k_count": k_count,
                "k_depths": depths
            }
            
            # Build combo list
            if depths is not None:
                items = [f"k={k} (~ {depths[k]:.2f} m)" for k in range(k_count)]
                info = f"Detected: 3-D variable with k=0..{k_count-1} (mean depth per layer)"
            else:
                items = [f"k={k}" for k in range(k_count)]
                info = f"Detected: 3-D variable with k=0..{k_count-1}"
            
            window['-K_INFO-'].update(info)
            window['-K_COMBO-'].update(values=items, value=items[0] if items else '')
            window['-VK-'].update(disabled=False)
            window['-K_COMBO-'].update(disabled=not window['-VK-'].get())
            
    except Exception as e:
        logger.error(f"Error reading k metadata: {e}")
        show_error_popup(f"Error reading k layer metadata: {e}")


def show_all_k_layers(state: AppState):
    """Show popup with all k layers and depths"""
    if not state.k_metadata.get("has_k"):
        sg.popup(get_message('no_k_list'))
        return
    
    k_count = state.k_metadata.get("k_count", 0)
    depths = state.k_metadata.get("k_depths")
    
    lines = []
    for k in range(k_count):
        if depths is not None:
            lines.append(f"k={k:3d}  ~{depths[k]:.3f} m")
        else:
            lines.append(f"k={k:3d}")
    
    sg.popup_scrolled(
        "\n".join(lines),
        title="Available k layers",
        size=(40, 20)
    )


def handle_config_window(state: AppState) -> Optional[dict]:
    """
    Handle configuration window.
    
    Args:
        state: Application state
        
    Returns:
        Updated settings dictionary or None if cancelled
    """
    config_win = make_config_window(state.settings)
    state.config_window = config_win
    
    # Setup colorbar preview
    colorbar_preview = ColorbarPreview(config_win['-COLORBAR_CANVAS-'].TKCanvas)
    colorbar_preview.update(state.settings['colormap'])
    
    # Refresh k metadata if variable is loaded
    if state.hdf_path and state.current_var:
        refresh_k_metadata(config_win, state)
    
    result = None
    
    while True:
        event, values = config_win.read()
        
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        
        # Enable/disable k combo
        if event == '-VK-':
            config_win['-K_COMBO-'].update(disabled=not values['-VK-'])
        
        # Refresh k metadata
        if event == '-K_REFRESH-':
            if state.hdf_path and state.current_var:
                refresh_k_metadata(config_win, state)
            else:
                show_error_popup(get_message('no_k_refresh'))
        
        # Show all k layers
        if event == '-K_SHOW-':
            show_all_k_layers(state)
        
        # Colormap changed
        if event == '-COLOR_SCALE-':
            colormap = values['-COLOR_SCALE-']
            colorbar_preview.update(colormap)
        
        # Save settings
        if event == 'Save Settings':
            # Parse vertical choice
            if values.get('-SURF-'):
                reduce_mode, reduce_index = 'top', 0
            elif values.get('-BOTT-'):
                reduce_mode, reduce_index = 'bottom', 0
            elif values.get('-VMN-'):
                reduce_mode, reduce_index = 'mean', 0
            elif values.get('-VK-'):
                selected = values.get('-K_COMBO-', '')
                if isinstance(selected, str) and selected.startswith('k='):
                    try:
                        reduce_index = int(selected.split('=')[1].split()[0])
                        reduce_mode = 'index'
                    except ValueError:
                        reduce_mode, reduce_index = 'index', 0
                else:
                    reduce_mode, reduce_index = 'index', 0
            else:
                reduce_mode, reduce_index = 'top', 0
            
            # Parse NoData values
            nodata_text = values.get('-NODATA-', '-99')
            nodata_vals = parse_nodata_values(nodata_text)
            
            # Build settings dictionary
            result = {
                'reduce_mode': reduce_mode,
                'reduce_index': reduce_index,
                'nodata_values': nodata_vals,
                'nodata_values_text': nodata_text,
                'auto_land_threshold': bool(values.get('-AUTO_ND-', True)),
                'basemap': values.get('-BASEMAP-', 'Google Satellite (imagery)') if values.get('-USE_TILES-') else 'None',
                'use_tiles': bool(values.get('-USE_TILES-', True)),
                'use_coastline': bool(values.get('-USE_COASTLINE-', True)),
                'tile_zoom': int(values.get('-TILE_ZOOM-', 12)),
                'fast_tiles': bool(values.get('-FAST_TILES-', True)),
                'colormap': values.get('-COLOR_SCALE-', 'rainbow'),
                'original': bool(values.get('-ORIGINAL-', True)),
                'vmin': float(values.get('-MINIMO-', 0)),
                'vmax': float(values.get('-MAXIMO-', 0)),
                'global_scale': bool(values.get('-GLOBAL_SCALE-', True)),
                'per_frame': bool(values.get('-PERFRAME-', False))
            }
            
            show_success_popup("Settings saved successfully!")
            break
    
    config_win.close()
    state.config_window = None
    return result


def handle_image_export(state: AppState) -> Optional[str]:
    """
    Handle image export window.
    
    Args:
        state: Application state
        
    Returns:
        Output directory path or None
    """
    if not state.hdf_path or not state.current_var:
        show_error_popup("Please load an HDF5 file and select a variable first!")
        return None
    
    img_win = make_image_export_window(state.settings)
    state.image_window = img_win
    
    result = None
    
    while True:
        event, values = img_win.read(timeout=100)
        
        if event in (sg.WINDOW_CLOSED, 'Close'):
            break
        
        if event == 'Start Export':
            # Determine format
            img_format = 'jpg' if values['-JPG-'] else 'png'
            
            # Update settings
            export_settings = state.settings.copy()
            export_settings.update({
                'name': state.current_var,
                'path': f"Results/{state.current_var}",
                'label': state.current_var.title(),
                'jpg_dpi': int(values.get('-IMG_DPI-', 120)),
                'jpg_quality': int(values.get('-JPG_QUALITY-', 95)),
            })
            
            output_folder = values.get('-OUT_FOLDER-', f'{img_format}_export_{state.current_var}')
            
            try:
                # Load data
                img_win['-PROG_TEXT-'].update("Loading data...")
                img_win.refresh()
                
                data, stamps, lat_full, lon_full = load_variable_data(
                    state.hdf_path, export_settings['path'], export_settings['name']
                )
                
                if data is None:
                    show_error_popup(get_message('loading_error'))
                    continue
                
                # Export with progress
                def progress_callback(current, total):
                    pct = int((current / total) * 100)
                    img_win['-PROG-'].update(pct)
                    img_win['-PROG_TEXT-'].update(f"Exporting frame {current}/{total} ({pct}%)")
                    img_win.refresh()
                
                img_paths, _ = export_as_jpgs(
                    data, stamps, lat_full, lon_full, output_folder, export_settings,
                    export_settings['vmax'], export_settings['vmin'],
                    on_tick=progress_callback,
                    per_frame_colors=not export_settings['global_scale'],
                    debug_stats=True
                )
                
                result = output_folder
                state.last_jpg_dir = output_folder
                
                img_win['-PROG_TEXT-'].update("Export completed!")
                show_success_popup(f"Successfully exported {len(img_paths)} images to:\n{output_folder}")
                
                if values.get('-OPEN_AFTER-', True):
                    os.startfile(output_folder)
                
                break
                
            except Exception as e:
                logger.error(f"Export error: {e}", exc_info=True)
                show_error_popup(f"Export error: {e}")
                img_win['-PROG_TEXT-'].update("Export failed!")
    
    img_win.close()
    state.image_window = None
    return result


def handle_animation_export(state: AppState) -> Optional[str]:
    """
    Handle animation export window.
    
    Args:
        state: Application state
        
    Returns:
        Output file path or None
    """
    if not state.hdf_path or not state.current_var:
        show_error_popup("Please load an HDF5 file and select a variable first!")
        return None
    
    anim_win = make_animation_export_window(state.settings)
    state.anim_window = anim_win
    
    result = None
    
    while True:
        event, values = anim_win.read(timeout=100)
        
        if event in (sg.WINDOW_CLOSED, 'Close'):
            break
        
        if event == 'Start Export':
            # Determine format
            if values['-MP4-']:
                ext = 'mp4'
            elif values['-GIF-']:
                ext = 'gif'
            else:
                ext = 'avi'
            
            # Update settings
            export_settings = state.settings.copy()
            export_settings.update({
                'name': state.current_var,
                'path': f"Results/{state.current_var}",
                'label': state.current_var.title(),
                'fps': int(values.get('-FPS-', 6)),
            })
            
            output_file = values.get('-OUT_FILE-', f'animation_{state.current_var}')
            if not output_file.endswith(f'.{ext}'):
                output_file = f"{output_file}.{ext}"
            
            try:
                # Load data
                anim_win['-PROG_TEXT_ANIM-'].update("Loading data...")
                anim_win.refresh()
                
                data, stamps, lat_full, lon_full = load_variable_data(
                    state.hdf_path, export_settings['path'], export_settings['name']
                )
                
                if data is None:
                    show_error_popup(get_message('loading_error'))
                    continue
                
                # Export with progress
                def progress_callback(current, total):
                    pct = int((current / total) * 100)
                    anim_win['-PROG_ANIM-'].update(pct)
                    anim_win['-PROG_TEXT_ANIM-'].update(f"Rendering frame {current}/{total} ({pct}%)")
                    anim_win.refresh()
                
                result = export_animation(
                    data, stamps, lat_full, lon_full, output_file, export_settings,
                    export_settings['vmax'], export_settings['vmin'],
                    on_tick=progress_callback,
                    fps=export_settings['fps']
                )
                
                anim_win['-PROG_TEXT_ANIM-'].update("Animation completed!")
                show_success_popup(f"Successfully created animation:\n{result}")
                
                if values.get('-OPEN_AFTER_ANIM-', True):
                    os.startfile(result)
                
                break
                
            except Exception as e:
                logger.error(f"Animation error: {e}", exc_info=True)
                show_error_popup(f"Animation error: {e}")
                anim_win['-PROG_TEXT_ANIM-'].update("Animation failed!")
    
    anim_win.close()
    state.anim_window = None
    return result


def handle_shapefile_export(state: AppState) -> Optional[str]:
    """
    Handle shapefile export window.
    
    Args:
        state: Application state
        
    Returns:
        Output directory path or None
    """
    if not state.hdf_path or not state.current_var:
        show_error_popup("Please load an HDF5 file and select a variable first!")
        return None
    
    shape_win = make_shapefile_export_window(state.settings)
    state.shape_window = shape_win
    
    result = None
    
    while True:
        event, values = shape_win.read(timeout=100)
        
        if event in (sg.WINDOW_CLOSED, 'Close'):
            break
        
        if event == 'Start Export':
            # Determine format
            if values['-GEOTIFF-']:
                export_func = export_as_geotiffs
                format_name = "GeoTIFF"
            elif values['-CSV_GEO-']:
                export_func = export_as_csvs
                format_name = "CSV"
            else:
                show_error_popup("This export format is not yet implemented!")
                continue
            
            # Update settings
            export_settings = state.settings.copy()
            export_settings.update({
                'name': state.current_var,
                'path': f"Results/{state.current_var}",
                'label': state.current_var.title(),
                'tiff_nodata': float(values.get('-TIFF_NODATA-', -9999)),
            })
            
            output_folder = values.get('-OUT_FOLDER_SHAPE-', f'shapefile_export_{state.current_var}')
            
            try:
                # Load data
                shape_win['-PROG_TEXT_SHAPE-'].update("Loading data...")
                shape_win.refresh()
                
                data, stamps, lat_full, lon_full = load_variable_data(
                    state.hdf_path, export_settings['path'], export_settings['name']
                )
                
                if data is None:
                    show_error_popup(get_message('loading_error'))
                    continue
                
                # Export with progress
                def progress_callback(current, total):
                    pct = int((current / total) * 100)
                    shape_win['-PROG_SHAPE-'].update(pct)
                    shape_win['-PROG_TEXT_SHAPE-'].update(f"Exporting {current}/{total} ({pct}%)")
                    shape_win.refresh()
                
                result = export_func(
                    data, stamps, lat_full, lon_full, output_folder, export_settings,
                    on_tick=progress_callback
                )
                
                shape_win['-PROG_TEXT_SHAPE-'].update(f"{format_name} export completed!")
                show_success_popup(f"Successfully exported {format_name} files to:\n{result}")
                
                break
                
            except Exception as e:
                logger.error(f"Export error: {e}", exc_info=True)
                show_error_popup(f"Export error: {e}")
                shape_win['-PROG_TEXT_SHAPE-'].update("Export failed!")
    
    shape_win.close()
    state.shape_window = None
    return result


def handle_vertical_section(state: AppState) -> None:
    """
    Handle vertical section visualization window.
    
    Args:
        state: Application state
    """
    if not state.hdf_path or not state.current_var:
        show_error_popup("Please load an HDF5 file and select a variable first!")
        return
    
   # Load geometry if not already loaded
    if state.geometry_info is None:
        #
        if state.geometry_path is None or not os.path.exists(state.geometry_path):
            # Try default location (same folder as HDF5)
            default_geometry = os.path.join(
                os.path.dirname(state.hdf_path), 
                "Geometry_1.dat"
            )
            
            if os.path.exists(default_geometry):
                state.geometry_path = default_geometry
                logger.info(f"Using default geometry file: {default_geometry}")
            else:
                show_error_popup(
                    f"Geometry file not found!\n\n"
                    f"Please specify the Geometry file path in the main window.\n"
                    f"Expected default location: {default_geometry}"
                )
                return
        
        # Parse geometry file
        state.geometry_info = parse_geometry_file(state.geometry_path)
        
        if state.geometry_info is None:
            show_error_popup(
                f"Failed to parse geometry file!\n"
                f"File: {state.geometry_path}"
            )
            return
        
        logger.info(f"Geometry successfully parsed from: {state.geometry_path}")


    try:
        import h5py
        with h5py.File(state.hdf_path, 'r') as f:
            lat_grid = np.asarray(f["Grid/Latitude"])
            lon_grid = np.asarray(f["Grid/Longitude"])
            
            # Try to load bathymetry
            if "Grid/Bathymetry" in f:
                bathymetry = np.asarray(f["Grid/Bathymetry"])
            elif "Grid/WaterColumn" in f:
                bathymetry = -np.asarray(f["Grid/WaterColumn"])
            else:
                # Estimate from vertical grid if available
                logger.warning("No bathymetry found, using default depth")
                bathymetry = np.full(lat_grid.shape, -50.0)
        
        # Build 3D depth grid
        if state.depth_grid_3d is None:
           print('Building 3d depth grid')
           if state.model_type == 'MOHID Water':
               state.depth_grid_3d = build_3d_depth_grid_water(
                                     state.geometry_info, bathymetry, vertical_exaggeration=1.0)
               original_depth_grid_3d = state.depth_grid_3d.copy()
           else:  # MOHID Land
               state.depth_grid_3d = build_3d_depth_grid_land(
                                     state.geometry_info, bathymetry, vertical_exaggeration=1.0)
               original_depth_grid_3d = state.depth_grid_3d.copy()

        
        # CRITICAL: Ensure all grids have compatible dimensions
        # The data might have shape (nk, ny, nx) but grids might be (ny+1, nx+1)
        logger.info("Validating grid dimensions...")
        logger.info(f"  lat_grid: {lat_grid.shape}")
        logger.info(f"  lon_grid: {lon_grid.shape}")
        logger.info(f"  depth_grid_3d: {state.depth_grid_3d.shape}")
        logger.info(f"  bathymetry: {bathymetry.shape}")
        
    except Exception as e:
        logger.error(f"Error loading grid data: {e}", exc_info=True)
        show_error_popup(f"Error loading grid data: {e}")
        return
    
    # Get coordinate ranges
    lat_range = (float(np.nanmin(lat_grid)), float(np.nanmax(lat_grid)))
    lon_range = (float(np.nanmin(lon_grid)), float(np.nanmax(lon_grid)))
    
    # Create window
    vs_win = make_vertical_section_window(lat_range, lon_range)
    state.vsection_window = vs_win

    # Disable VE for MOHID Water
    if state.model_type == 'MOHID Water':
        vs_win['-VS_VE-'].update(disabled=True, value='1.0')
        vs_win['-VS_APPLY_VE-'].update(disabled=True)
        vs_win['-VS_VE_NOTE-'].update('(Not applicable for MOHID Water)')
    else:
        vs_win['-VS_VE-'].update(disabled=False)
        vs_win['-VS_APPLY_VE-'].update(disabled=False)
        vs_win['-VS_VE_NOTE-'].update('(MOHID Land only - Rebuilds depth grid)')

    # Tracking variables for VE changes
    current_ve = 1.0
    original_depth_grid_3d = None  # Store original grid
    
    # Store original depth grid (without VE applied)
    if state.depth_grid_3d is not None:
        original_depth_grid_3d = state.depth_grid_3d.copy()
    
    # Set variable info
    vs_win['-VS_VAR-'].update(state.current_var)
    
    # Load timestamps
    try:
        with h5py.File(state.hdf_path, 'r') as f:
            var_path = f"Results/{state.current_var}"
            group = f[var_path]
            datasets = sorted([k for k in group.keys() if k.startswith(f"{state.current_var}_")])
            n_timesteps = len(datasets)
            
            vs_win['-VS_TIMESTEP-'].update(range=(0, n_timesteps-1))
            vs_win['-VS_TIME_INFO-'].update(f'0 / {n_timesteps}')
    except Exception as e:
        logger.warning(f"Could not load timesteps: {e}")
        n_timesteps = 1
    
    # Initialize canvases
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    
    # Current section data
    current_section_data = None
    current_section_coord = None
    current_section_depth = None
    current_section_type = 'longitude'
    
    def update_section():
        """Update the vertical section plot"""
        nonlocal current_section_data, current_section_coord, current_section_depth, current_section_type
        
        try:
            # Get parameters
            values = vs_win.read(timeout=0)[1]
           
            section_type = 'latitude' if values['-SECTION_LAT-'] else 'longitude'
            current_section_type = section_type
            
            if section_type == 'longitude':
                section_value = float(values['-SECTION_LAT_VAL-'])
            else:
                section_value = float(values['-SECTION_LON_VAL-'])
            
            timestep = int(values['-VS_TIMESTEP-'])
            colormap = values['-VS_CMAP-']
            show_bathy = values['-VS_BATHY-']
            
       # VE is already applied to depth_grid, don't apply again
            vertical_exaggeration = 1.0  # Use 1.0 here since grid is pre-scaled
            
            # Parse color limits
            try:
                vmin_str = values['-VS_VMIN-']
                vmin = None if vmin_str.lower() == 'auto' else float(vmin_str)
            except:
                vmin = None
            
            try:
                vmax_str = values['-VS_VMAX-']
                vmax = None if vmax_str.lower() == 'auto' else float(vmax_str)
            except:
                vmax = None

            # Parse point size to plot in vertical section
            try:
                p_size_str = values['-P_SIZE-']
                p_size = int(p_size_str)
            except:
                p_size = None

            # Load 3D data for this timestep
            data_3d = load_3d_variable_timestep(state.hdf_path, state.current_var, timestep)
            
            if data_3d is None:
                show_error_popup("Failed to load 3D data!")
                return
            
            logger.info(f"Loaded data shape: {data_3d.shape}")
            
            # AUTO-FIX: Ensure all grids match data dimensions
            nk, ny_data, nx_data = data_3d.shape
            
            # Create local copies for trimming
            lat_grid_local = lat_grid.copy()
            lon_grid_local = lon_grid.copy()
            depth_grid_local = state.depth_grid_3d.copy()
            bathymetry_local = bathymetry.copy()
            
            # Trim grids to match data if needed
            if lat_grid_local.shape != (ny_data, nx_data):
                logger.warning(f"Trimming lat_grid from {lat_grid_local.shape} to ({ny_data}, {nx_data})")
                lat_grid_local = lat_grid_local[:ny_data, :nx_data]
            
            if lon_grid_local.shape != (ny_data, nx_data):
                logger.warning(f"Trimming lon_grid from {lon_grid_local.shape} to ({ny_data}, {nx_data})")
                lon_grid_local = lon_grid_local[:ny_data, :nx_data]
            
            if depth_grid_local.shape != (nk, ny_data, nx_data):
                logger.warning(f"Trimming depth_grid from {depth_grid_local.shape} to ({nk}, {ny_data}, {nx_data})")
                depth_grid_local = depth_grid_local[:nk, :ny_data, :nx_data]
            
            if bathymetry_local.shape != (ny_data, nx_data):
                logger.warning(f"Trimming bathymetry from {bathymetry_local.shape} to ({ny_data}, {nx_data})")
                bathymetry_local = bathymetry_local[:ny_data, :nx_data]

            # Extract section
            if section_type == 'longitude':
                section_data, section_coord, section_depth = extract_longitudinal_section(
                    data_3d, lat_grid_local, lon_grid_local, depth_grid_local, section_value
                )
            else:
                section_data, section_coord, section_depth = extract_latitudinal_section(
                    data_3d, lat_grid_local, lon_grid_local, depth_grid_local, section_value
                )

            # Store for export
            current_section_data = section_data
            current_section_coord = section_coord
            current_section_depth = section_depth
                        
            # Clear previous plot
            if state.vs_canvas_agg:
                try:
                    state.vs_canvas_agg.get_tk_widget().destroy()
                except:
                    pass
                state.vs_canvas_agg = None
            
            # Get canvas dimensions (atualizados para os novos tamanhos)
            canvas_width = 700   # Aumentado de 700
            canvas_height = 300  # Aumentado de 300
            fig_width = canvas_width / 100.0  # 7 inches
            fig_height = canvas_height / 100.0  # 3 inches
            
            # Plot section with fixed size
            if show_bathy:
                # Extract bathymetry for this section
                if section_type == 'longitude':
                    lat_per_row = lat_grid[0,:]  # Shape: (,ny)
                    lat_diff = np.abs(lat_per_row - section_value)  # Array 1D (ny,)
                    j_idx = np.argmin(lat_diff)
                    bathy_section = bathymetry_local[:,j_idx]
                else:
                    lon_per_column = lon_grid[:,0]  # Shape: (,nx)
                    lon_diff = np.abs(lon_per_column - section_value)  # Array 1D (nx,)
                    i_idx = np.argmin(lon_diff)
                    bathy_section = bathymetry_local[i_idx,:]
                
                # Ensure bathymetry matches section_coord length
                if len(bathy_section) != len(section_coord):
                    logger.warning(
                        f"Trimming bathymetry: {len(bathy_section)} -> {len(section_coord)}"
                    )
                    bathy_section = bathy_section[:len(section_coord)]
                
                # Create figure with exact size
                fig = plt.figure(figsize=(fig_width, fig_height), dpi=100)
                ax = fig.add_subplot(111)
                
                fig, ax = plot_section_with_bathymetry(
                    section_data, section_coord, section_depth, bathy_section,
                    state.current_var, section_type, colormap, vmin, vmax, p_size,
                    model_type=state.model_type, vertical_exaggeration=vertical_exaggeration,
                    fig=fig, ax=ax
                )
            else:
                # Create figure with exact size
                fig = plt.figure(figsize=(fig_width, fig_height), dpi=100)
                ax = fig.add_subplot(111)
  
                fig, ax = plot_vertical_section(
                    section_data, section_coord, section_depth,
                    state.current_var, section_type, colormap, vmin, vmax, p_size,
                    model_type=state.model_type, vertical_exaggeration=vertical_exaggeration,
                    fig=fig, ax=ax
                )
            
            # Adjust layout to fit
            fig.tight_layout(pad=0.5)
            
            # Draw to canvas
            state.vs_canvas_agg = FigureCanvasTkAgg(fig, vs_win['-VS_CANVAS-'].TKCanvas)
            state.vs_canvas_agg.draw()
            state.vs_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=True)
            
            # Update location map
            if state.vs_map_canvas_agg:
                try:
                    state.vs_map_canvas_agg.get_tk_widget().destroy()
                except:
                    pass
                state.vs_map_canvas_agg = None
            
            # Map canvas dimensions
            map_width = 400
            map_height = 300
            map_fig_width = map_width / 100.0
            map_fig_height = map_height / 100.0
            
            fig_map = plt.figure(figsize=(map_fig_width, map_fig_height), dpi=100)
            ax_map = fig_map.add_subplot(111)
            
            fig_map, ax_map = plot_section_location_on_map(
                lat_grid_local, lon_grid_local, section_type, section_value,
                fig=fig_map, ax=ax_map
            )
            
            fig_map.tight_layout(pad=0.5)
            
            state.vs_map_canvas_agg = FigureCanvasTkAgg(fig_map, vs_win['-VS_MAP_CANVAS-'].TKCanvas)
            state.vs_map_canvas_agg.draw()
            state.vs_map_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=True)
            
            # Update statistics
            stats = compute_section_statistics(section_data)
            vs_win['-VS_STAT_MIN-'].update(f"{stats['min']:.4g}")
            vs_win['-VS_STAT_MAX-'].update(f"{stats['max']:.4g}")
            vs_win['-VS_STAT_MEAN-'].update(f"{stats['mean']:.4g}")
            vs_win['-VS_STAT_STD-'].update(f"{stats['std']:.4g}")
            vs_win['-VS_STAT_MEDIAN-'].update(f"{stats['median']:.4g}")
            vs_win['-VS_STAT_VALID-'].update(f"{stats['valid_points']} / {stats['total_points']}")
            
        except Exception as e:
            logger.error(f"Error updating section: {e}", exc_info=True)
#            show_error_popup(f"Error updating section: {e}")
    
    # Event loop
    while True:
        event, values = vs_win.read(timeout=100)
        
        if event in (sg.WINDOW_CLOSED, 'Close'):
            break
        
        # Enable/disable coordinate sliders based on section type
        if event in ('-SECTION_LON-', '-SECTION_LAT-'):
            if values['-SECTION_LON-']:
                # Longitudinal section - select latitude
                vs_win['-SECTION_LAT_VAL-'].update(disabled=False)
                vs_win['-SECTION_LAT_INPUT-'].update(disabled=False)
                vs_win['-SECTION_LON_VAL-'].update(disabled=True)
                vs_win['-SECTION_LON_INPUT-'].update(disabled=True)
            else:
                # Latitudinal section - select longitude
                vs_win['-SECTION_LAT_VAL-'].update(disabled=True)
                vs_win['-SECTION_LAT_INPUT-'].update(disabled=True)
                vs_win['-SECTION_LON_VAL-'].update(disabled=False)
                vs_win['-SECTION_LON_INPUT-'].update(disabled=False)
        
        # Sync slider and input
        if event == '-SECTION_LAT_VAL-':
            vs_win['-SECTION_LAT_INPUT-'].update(f"{values['-SECTION_LAT_VAL-']:.4f}")
        
        if event == '-SECTION_LON_VAL-':
            vs_win['-SECTION_LON_INPUT-'].update(f"{values['-SECTION_LON_VAL-']:.4f}")
        
        if event == '-SECTION_LAT_INPUT-':
            try:
                val = float(values['-SECTION_LAT_INPUT-'])
                vs_win['-SECTION_LAT_VAL-'].update(val)
            except:
                pass
        
        if event == '-SECTION_LON_INPUT-':
            try:
                val = float(values['-SECTION_LON_INPUT-'])
                vs_win['-SECTION_LON_VAL-'].update(val)
            except:
                pass
                
        # Timestep changed
        if event == '-VS_TIMESTEP-':
            timestep = int(values['-VS_TIMESTEP-'])
            vs_win['-VS_TIME_INFO-'].update(f'{timestep} / {n_timesteps}')
            vs_win['-VS_TIMESTAMP-'].update(f'{timestep}')
        
        # Apply VE button clicked
        if event == '-VS_APPLY_VE-':
            # Only works for MOHID Land
            if state.model_type != 'MOHID Land':
                show_error_popup("Vertical Exaggeration only applies to MOHID Land models!")
                continue
    
            try:
                new_ve = float(values['-VS_VE-'])
                if new_ve <= 0:
                    show_error_popup("Vertical Exaggeration must be positive!")
                    continue
        
                if abs(new_ve - current_ve) > 0.001:
                    logger.info(f"Rebuilding depth grid with VE={new_ve} (MOHID Land)")
                    
                    # Only rebuild for MOHID Land
                    state.depth_grid_3d = build_3d_depth_grid_land(
                        state.geometry_info, bathymetry, vertical_exaggeration=new_ve
                    )
            
                    current_ve = new_ve
                    logger.info("Depth grid rebuilt successfully")
            
                    # Auto-update section
                    update_section()
            
            except ValueError:
                show_error_popup("Invalid Vertical Exaggeration value!")
            except Exception as e:
                logger.error(f"Error applying VE: {e}", exc_info=True)
                show_error_popup(f"Error: {e}")
        
        # Update button
        if event == 'Update Section':
            update_section()
        
        # Reset color limits
        if event == '-VS_RESET_COLORS-':
            vs_win['-VS_VMIN-'].update('auto')
            vs_win['-VS_VMAX-'].update('auto')
        
        # Export to CSV
        if event == '-VS_EXPORT_CSV-':
            if current_section_data is not None:
                output_path = sg.popup_get_file(
                    'Save section as CSV',
                    save_as=True,
                    default_extension='.csv',
                    file_types=(("CSV Files", "*.csv"),),
                    default_path=f'section_{state.current_var}_{current_section_type}.csv'
                )
                
                if output_path:
                    try:
                        export_section_to_csv(
                            current_section_data, current_section_coord,
                            current_section_depth, output_path, current_section_type
                        )
                        show_success_popup(f"Section exported to:\n{output_path}")
                    except Exception as e:
                        show_error_popup(f"Export failed: {e}")
            else:
                show_error_popup("Please update the section first!")
        
        # Export image
        if event == '-VS_EXPORT_IMG-':
            if current_section_data is not None:
                output_path = sg.popup_get_file(
                    'Save section as image',
                    save_as=True,
                    default_extension='.png',
                    file_types=(("PNG Image", "*.png"), ("JPEG Image", "*.jpg")),
                    default_path=f'section_{state.current_var}_{current_section_type}.png'
                )
                
                if output_path:
                    try:
                        # Get current figure
                        if state.vs_canvas_agg and state.vs_canvas_agg.figure:
                            state.vs_canvas_agg.figure.savefig(output_path, dpi=300, bbox_inches='tight')
                            show_success_popup(f"Image saved to:\n{output_path}")
                    except Exception as e:
                        show_error_popup(f"Export failed: {e}")
            else:
                show_error_popup("Please update the section first!")
    
    # Cleanup
    try:
        if state.vs_canvas_agg:
            try:
                state.vs_canvas_agg.get_tk_widget().destroy()
            except:
                pass
            state.vs_canvas_agg = None
        
        if state.vs_map_canvas_agg:
            try:
                state.vs_map_canvas_agg.get_tk_widget().destroy()
            except:
                pass
            state.vs_map_canvas_agg = None
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")
    
    vs_win.close()
    state.vsection_window = None
    plt.close('all')


def main_event_loop():
    """Main application event loop"""
    
    # Initialize
    state = AppState()
    main_win = make_main_window()
    
    viewer_win = None
    viewer = None
    viewer_is_maximized = False
    
    # Main loop
    while True:
        window, event, values = sg.read_all_windows(timeout=100)
        
        if window is None:
            continue
        
        if window == sg.TIMEOUT_KEY:
            continue

        # ==================== MAIN WINDOW EVENTS ====================
        if window == main_win:

            # Show welcome window
            if event == 'Show welcome window':
                show_welcome_dialog()
                main_win['-STATUS-'].update("Welcome screen closed")
            
            if event in (sg.WINDOW_CLOSED, 'Quit'):
                break

            # Capturar tipo de modelo selecionado
            if values['-M_WATER-']:
                state.model_type = 'MOHID Water'
                logger.info("Model type set to: MOHID Water")
            elif values['-M_LAND-']:
                  state.model_type = 'MOHID Land'
                  logger.info("Model type set to: MOHID Land")                
            
            # Load variables from file
            if event == "Load Variables":
                path = values['-FILE-']
                if not path or not os.path.exists(path):
                    show_error_popup(f"{get_message('file_not_found')} '{path}'")
                    continue
                
                vars_list = get_available_variables(path)
                if not vars_list:
                    show_error_popup(get_message('no_variables'))
                    continue
    
                vars_list = get_available_variables(path)
                if not vars_list:
                        show_error_popup(get_message('no_variables'))
                        continue

                # Check if we're loading a different file
                if state.hdf_path != path:
                    logger.info(f"Loading new HDF5 file: {path}")
                    state.reset_geometry_data()  # Reset geometry data for new file
                    state.reset_k_metadata()      # Reset k metadata
                
                state.hdf_path = path
                state.variables_list = vars_list
                state.current_var = vars_list[0]
                
                main_win['-VAR-'].update(values=vars_list, value=vars_list[0])
                                
                # Try to auto-detect geometry file
                if not state.geometry_path:
                    default_geometry = os.path.join(os.path.dirname(path), "Geometry_1.dat")
                    if os.path.exists(default_geometry):
                        state.geometry_path = default_geometry
                        main_win['-STATS_GEOMETRY-'].update(default_geometry)
                        main_win['-STATUS-'].update(
                            f"Loaded {len(vars_list)} variables. Geometry file found."
                        )
                        logger.info(f"Auto-detected geometry file: {default_geometry}")
                    else:
                        main_win['-STATUS-'].update(
                            f"Loaded {len(vars_list)} variables. Please specify geometry file for vertical sections."
                        )
                else:
                    main_win['-STATUS-'].update(f"Loaded {len(vars_list)} variables from {os.path.basename(path)}")
            
            # Variable changed
            if event == '-VAR-':
                state.current_var = values['-VAR-']
                main_win['-STATUS-'].update(f"Selected variable: {state.current_var}")
            
            # Geometry file path changed
            if event == '-STATS_GEOMETRY-':
                geometry_path = values['-STATS_GEOMETRY-']
                
                # Check if geometry file changed
                if geometry_path != state.geometry_path:
                    logger.info(f"Geometry file changed to: {geometry_path}")
                    state.reset_geometry_data()  # Reset geometry data when file changes
                    
                    if geometry_path and os.path.exists(geometry_path):
                        state.geometry_path = geometry_path
                        main_win['-STATUS-'].update(f"Geometry file loaded: {os.path.basename(geometry_path)}")
                        logger.info(f"Geometry file set: {geometry_path}")
                    elif geometry_path:
                        show_error_popup(f"Geometry file not found: {geometry_path}")
                        state.geometry_path = None
                        main_win['-STATUS-'].update("Geometry file not found")
                    else:
                        state.geometry_path = None
                        main_win['-STATUS-'].update("Geometry file cleared")
            
            # Open configuration window
            if event == '-OPEN_CONFIG-':
                new_settings = handle_config_window(state)
                if new_settings:
                    state.update_settings(new_settings)
                    main_win['-STATUS-'].update("Configuration updated")
            
            # Open image export window
            if event == '-OPEN_IMAGE-':
                output = handle_image_export(state)
                if output:
                    main_win['-LAST_DIR-'].update(output)
                    main_win['-STATUS-'].update(f"Images exported to: {output}")
            
            # Open animation export window
            if event == '-OPEN_ANIM-':
                output = handle_animation_export(state)
                if output:
                    main_win['-STATUS-'].update(f"Animation saved: {output}")
            
            # Open shapefile export window
            if event == '-OPEN_SHAPE-':
                output = handle_shapefile_export(state)
                if output:
                    main_win['-STATUS-'].update(f"Shapefiles exported to: {output}")
            
            # Open vertical section window
            if event == '-OPEN_VSECTION-':
                handle_vertical_section(state)
                main_win['-STATUS-'].update("Vertical section viewer closed")
            
            # Browse last export folder
            if event == '-BROWSE_LAST-':
                folder = sg.popup_get_folder(
                    "Select JPG export folder",
                    default_path=values['-LAST_DIR-'] or os.getcwd()
                )
                if folder:
                    main_win['-LAST_DIR-'].update(folder)
                    state.last_jpg_dir = folder
            
            # Open viewer from last export
            if event == '-OPEN_VIEWER-':
                if not state.last_jpg_dir or not os.path.isdir(state.last_jpg_dir):
                    show_error_popup(get_message('no_jpg_export'))
                else:
                    viewer_win, viewer = open_viewer_window(state.last_jpg_dir)
                    state.viewer_dir = state.last_jpg_dir
                    viewer_is_maximized = False
            
            # Open viewer from chosen folder
            if event == '-OPEN_VIEWER_DIR-':
                chosen = sg.popup_get_folder("Select JPG frames folder")
                if chosen:
                    state.last_jpg_dir = chosen
                    main_win['-LAST_DIR-'].update(chosen)
                    viewer_win, viewer = open_viewer_window(chosen)
                    state.viewer_dir = chosen
                    viewer_is_maximized = False
        
        # ==================== VIEWER WINDOW EVENTS ====================
        elif viewer_win and window == viewer_win and viewer is not None:
            
            if event in (sg.WINDOW_CLOSED, '-V_CLOSE-'):
                try:
                    if viewer and viewer.fig_canvas:
                        widget = viewer.fig_canvas.get_tk_widget()
                        widget.pack_forget()
                        widget.destroy()
                except:
                    pass
                try:
                    viewer_win.close()
                except:
                    pass
                viewer_win = None
                viewer = None
                state.viewer_dir = None
                plt.close('all')
                continue
            
            # Maximize/restore
            if event == '-V_MAX-':
                try:
                    if not viewer_is_maximized:
                        viewer_win.maximize()
                        viewer_is_maximized = True
                    else:
                        viewer_win.normal()
                        viewer_is_maximized = False
                except Exception as e:
                    logger.warning(f"Could not toggle maximize: {e}")
            
            # Slider changed
            if event == '-V_SLIDER-':
                try:
                    idx = int(values['-V_SLIDER-'])
                    viewer.show(idx)
                    viewer_win['-V_IDX-'].update(f"{idx+1} / {viewer.count()}")
                    ts_list = viewer.timestamps()
                    if 0 <= idx < len(ts_list):
                        viewer_win['-V_TS-'].update(value=ts_list[idx])
                except Exception as e:
                    show_error_popup(f"Error updating frame: {e}")
            
            # Previous button
            if event == '-V_PREV-':
                idx = (viewer.idx - 1) % viewer.count()
                viewer.show(idx)
                viewer_win['-V_SLIDER-'].update(value=idx)
                viewer_win['-V_IDX-'].update(f"{idx+1} / {viewer.count()}")
                viewer_win['-V_TS-'].update(value=viewer.timestamps()[idx])
            
            # Next button
            if event == '-V_NEXT-':
                idx = (viewer.idx + 1) % viewer.count()
                viewer.show(idx)
                viewer_win['-V_SLIDER-'].update(value=idx)
                viewer_win['-V_IDX-'].update(f"{idx+1} / {viewer.count()}")
                viewer_win['-V_TS-'].update(value=viewer.timestamps()[idx])
            
            # Timestamp jump
            if event in ('-V_TS-', '-V_GO-'):
                ts_sel = values.get('-V_TS-')
                if ts_sel:
                    try:
                        idx = viewer.timestamps().index(ts_sel)
                        viewer.show(idx)
                        viewer_win['-V_SLIDER-'].update(value=idx)
                        viewer_win['-V_IDX-'].update(f"{idx+1} / {viewer.count()}")
                    except ValueError:
                        show_error_popup("Timestamp not found in folder.")
    
    # Cleanup
    try:
        if viewer_win:
            viewer_win.close()
        main_win.close()
        plt.close('all')
    except:
        pass
    
def main():
    """Application entry point"""
    # Configure stdout for better progress reporting
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except:
        pass
    
    # Show welcome dialog only if user hasn't disabled it
    if UserPreferences.should_show_welcome():
        show_welcome_dialog()
    
    # Run main loop
    logger.info("Starting MOHID HDF5 Viewer")
    main_event_loop()
    logger.info("Application closed")
    finalize_log(log_file_handler) #DS_18/1

if __name__ == "__main__":

    main()

"""
MOHID HDF5 Viewer - Export Functions
Functions for exporting data to various formats (JPG, animations, GeoTIFF, CSV)
"""
from typing import List, Tuple, Optional, Callable, Dict
import os
import re
import numpy as np
import numpy.typing as npt
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from config import (
    logger, DataConfig, UIConfig, Dependencies,
    BASEMAP_OPTIONS, FilePatterns
)
from processing import (
    ensure_2d_frames, compute_global_color_limits, print_frame_statistics
)


def safe_filename(name: str) -> str:
    """
    Convert string to safe filename (replace invalid characters).
    
    Args:
        name: Original filename
        
    Returns:
        Safe filename with invalid characters replaced by underscore
    """
    return re.sub(FilePatterns.SAFE_FILENAME_PATTERN, '_', name.strip())


def get_tiler_and_projection(settings: Dict) -> Tuple:
    """
    Get basemap tiler and projection based on settings.
    
    Args:
        settings: Export settings dictionary
        
    Returns:
        Tuple of (tiler, projection_crs, use_coastline, colormap, original)
    """
    basemap = settings.get('basemap', 'None')
    use_coastline = settings.get('use_coastline', True)
    colormap = settings.get('colormap', 'viridis')
    original = settings.get('original', True)
    
    # Google Satellite
    if basemap == "Google Satellite (imagery)" and Dependencies.HAS_GOOGLE:
        from cartopy.io.img_tiles import GoogleTiles
        tiler = GoogleTiles(style='satellite')
        return tiler, tiler.crs, use_coastline, colormap, original
    
    # Google Terrain
    if basemap == "Google Terrain" and Dependencies.HAS_GOOGLE:
        from cartopy.io.img_tiles import GoogleTiles
        tiler = GoogleTiles(style='terrain')
        return tiler, tiler.crs, use_coastline, colormap, original
    
    # OpenStreetMap
    if basemap == "OpenStreetMap" and Dependencies.HAS_OSM:
        from cartopy.io.img_tiles import OSM
        tiler = OSM()
        return tiler, tiler.crs, use_coastline, colormap, original
    
    # No tiles (default)
    return None, ccrs.PlateCarree(), use_coastline, colormap, original


def create_colormap_with_nodata(name: str) -> mpl.colors.Colormap:
    """
    Create a colormap with special color for NaN/NoData values.
    
    Args:
        name: Matplotlib colormap name
        
    Returns:
        Modified colormap with bad values shown in gray
    """
    cmap = mpl.colormaps.get_cmap(name).copy()
    try:
        cmap.set_bad(color='0.8', alpha=0.8)  # Light gray for NoData
    except Exception as e:
        logger.warning(f"Could not set bad color for colormap: {e}")
    return cmap


def pick_animation_writer(
    output_file: str,
    fps: int = None
) -> Tuple[str, animation.AbstractMovieWriter]:
    """
    Choose animation writer and adjust output filename if needed.
    
    Falls back to GIF if ffmpeg is unavailable for MP4/AVI.
    
    Args:
        output_file: Requested output filename
        fps: Frames per second
        
    Returns:
        Tuple of (actual_output_file, writer)
    """
    if fps is None:
        fps = DataConfig.DEFAULT_FPS
    
    base, ext = os.path.splitext(output_file)
    requested_format = ext.lower().lstrip('.')
    
    # Check for MP4/AVI formats
    if requested_format in ('mp4', 'avi'):
        if Dependencies.HAS_FFMPEG:
            writer = animation.FFMpegWriter(
                fps=fps,
                codec='libx264',
                extra_args=['-pix_fmt', 'yuv420p']
            )
            return output_file, writer
        else:
            # Fallback to GIF
            alt_file = f"{base}.gif"
            logger.warning(
                "FFmpeg not found. Saving as GIF instead. "
                "Tip: install ffmpeg or imageio-ffmpeg"
            )
            return alt_file, animation.PillowWriter(fps=fps)
    
    # GIF format
    if requested_format == 'gif':
        return output_file, animation.PillowWriter(fps=fps)
    
    # Unknown format - default to GIF
    alt_file = f"{base}.gif"
    logger.warning(f"Unknown format '.{requested_format}'. Saving as GIF")
    return alt_file, animation.PillowWriter(fps=fps)


def export_animation(
    all_var_data: List[npt.NDArray],
    all_timestamps: List[str],
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    output_file: str,
    settings: Dict,
    vmax_override: float = 0.0,
    vmin_override: float = 0.0,
    on_tick: Optional[Callable[[int, int], None]] = None,
    fps: int = None
) -> str:
    """
    Export data as animation (MP4, AVI, or GIF).
    
    Args:
        all_var_data: List of ND arrays (one per timestep)
        all_timestamps: List of timestamp strings
        lat_grid: Full latitude grid
        lon_grid: Full longitude grid
        output_file: Output filename
        settings: Export settings
        vmin_override: Manual minimum value (0 = auto)
        vmax_override: Manual maximum value (0 = auto)
        on_tick: Progress callback function(current, total)
        fps: Frames per second
        
    Returns:
        Path to saved animation file
    """
    # Sanitize filename
    base, ext = os.path.splitext(output_file)
    output_file = f"{safe_filename(base)}{ext}"
    
    # Process frames
    frames_2d, lat_grid, lon_grid = ensure_2d_frames(
        all_var_data, lat_grid, lon_grid, settings
    )

    logger.info(f"Frames shape: {len(frames_2d)}")
    logger.info(f"First frame stats: min={np.nanmin(frames_2d[0]):.6f}, max={np.nanmax(frames_2d[0]):.6f}")
    logger.info(f"Valid points: {np.sum(~np.isnan(frames_2d[0]))}/{frames_2d[0].size}")
    
    # Determine color limits
    if vmin_override == 0.0 and vmax_override == 0.0:
       vmin, vmax = compute_global_color_limits(frames_2d, settings['colormap'])
    else:
       vmin, vmax = vmin_override, vmax_override

    levels = np.linspace(vmin, vmax, DataConfig.DEFAULT_CONTOUR_LEVELS)
    cmap = create_colormap_with_nodata(settings['colormap'])


    # POR ESTE CÓDIGO CORRIGIDO:
    # Determine color limits
    if vmin_override == 0.0 and vmax_override == 0.0:
       vmin, vmax = compute_global_color_limits(frames_2d, settings['colormap'])
    else:
       vmin, vmax = vmin_override, vmax_override

    # CORREÇÃO: Validar vmin e vmax antes de criar levels
    if not np.isfinite(vmin) or not np.isfinite(vmax):
       logger.warning(f"Invalid color limits (vmin={vmin}, vmax={vmax}). Using default [0, 1]")
       vmin, vmax = 0.0, 1.0
    elif vmax <= vmin:
       logger.warning(f"vmax <= vmin ({vmax} <= {vmin}). Adjusting to vmax = vmin + 1")
       vmax = vmin + 1.0

    # Garantir que temos uma diferença mínima
    if abs(vmax - vmin) < 1e-10:
       logger.warning(f"Very small range ({vmin} to {vmax}). Expanding range.")
       center = (vmin + vmax) / 2.0
       vmin = center - 0.5
       vmax = center + 0.5

    levels = np.linspace(vmin, vmax, DataConfig.DEFAULT_CONTOUR_LEVELS)
    cmap = create_colormap_with_nodata(settings['colormap'])

    logger.info(f"Color limits: vmin={vmin:.6f}, vmax={vmax:.6f}")    

    # Pick writer
    target_path, writer = pick_animation_writer(output_file, fps)
    
    logger.info(f"Saving animation to {target_path}")
    
    # Create figure
    fig = plt.figure(figsize=UIConfig.FIGURE_SIZE)
    
    # Setup basemap
    tiler, proj, use_coastline, colormap, original = get_tiler_and_projection(settings)
    
    if tiler is not None:
        ax = fig.add_axes(UIConfig.MAIN_AXES, projection=proj)
        try:
            ax.add_image(tiler, int(settings.get('tile_zoom', 12)))
        except Exception as e:
            logger.warning(f"Could not add tiles: {e}")
        if use_coastline:
            ax.coastlines()
    else:
        ax = fig.add_axes(UIConfig.MAIN_AXES, projection=ccrs.PlateCarree())
        ax.stock_img()
        if use_coastline:
            ax.coastlines()
    
    # Set extent
    lon_min, lon_max = float(np.nanmin(lon_grid)), float(np.nanmax(lon_grid))
    lat_min, lat_max = float(np.nanmin(lat_grid)), float(np.nanmax(lat_grid))
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)
    
    # Gridlines
    try:
        gl = ax.gridlines(
            draw_labels=True, dms=True,
            x_inline=False, y_inline=False,
            color='black', alpha=0.3, linestyle='--'
        )
        gl.top_labels = False
        gl.right_labels = False
    except Exception as e:
        logger.warning(f"Could not add gridlines: {e}")
    
    # Colorbar
    cax = fig.add_axes(UIConfig.COLORBAR_AXES)
    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    
    cb_cmap = cmap if original else cmap.reversed()
    cb = mpl.colorbar.ColorbarBase(
        cax, cmap=cb_cmap, norm=norm,
        orientation='vertical', extend='both'
    )
    cb.set_label(settings.get('label', settings['name']).title(), fontsize=10)
    
    # Title and initial contour
    title = fig.suptitle('', fontsize=16, y=0.98)
    quad = [ax.contourf(
        lon_grid, lat_grid, frames_2d[0],
        levels=levels, cmap=cmap,
        transform=ccrs.PlateCarree(), alpha=0.8
    )]
    
    def update(i):
        """Update function for animation"""
        for c in quad:
            try:
                c.remove()
            except Exception:
                pass
        
        quad[0] = ax.contourf(
            lon_grid, lat_grid, frames_2d[i],
            levels=levels, cmap=cmap,
            transform=ccrs.PlateCarree(), alpha=0.8
        )
        title.set_text(
            f"{settings['name'].title()} @ {all_timestamps[i].replace('_', ' ')}"
        )
    
    # Create animation
    ani = animation.FuncAnimation(
        fig, update,
        frames=len(frames_2d),
        blit=False
    )
    
    def progress_callback(frame, total):
        """Progress reporting"""
        pct = (frame + 1) * 100.0 / max(1, total)
        logger.info(f"ANIM {frame + 1}/{total} ({pct:5.1f}%)")
        if on_tick:
            on_tick(frame + 1, total)
    
    # Save animation
    ani.save(target_path, writer=writer, dpi=200, progress_callback=progress_callback)
    plt.close(fig)
    
    logger.info(f"Animation saved: {target_path}")
    return target_path


def export_as_jpgs(
    all_var_data: List[npt.NDArray],
    all_timestamps: List[str],
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    output_dir: str,
    settings: Dict,
    vmax_override: float = 0.0,
    vmin_override: float = 0.0,
    on_tick: Optional[Callable[[int, int], None]] = None,
    per_frame_colors: bool = False,
    debug_stats: bool = True
) -> Tuple[List[str], List[str]]:
    """
    Export frames as individual JPG images (FAST method using pcolormesh).
    
    Args:
        all_var_data: List of ND arrays
        all_timestamps: List of timestamps
        lat_grid: Full latitude grid
        lon_grid: Full longitude grid
        output_dir: Output directory path
        settings: Export settings
        vmax_override: Manual max value (0 = auto)
        vmin_override: Manual min value (0 = auto)
        on_tick: Progress callback
        per_frame_colors: Use per-frame color scaling (slower)
        debug_stats: Print frame statistics
        
    Returns:
        Tuple of (image_paths, timestamps)
    """
    # Process frames
    frames_2d, lat_grid, lon_grid = ensure_2d_frames(
        all_var_data, lat_grid, lon_grid, settings
    )
    
    os.makedirs(output_dir, exist_ok=True)
    
    cmap = create_colormap_with_nodata(settings['colormap'])
    dpi = int(settings.get('jpg_dpi', UIConfig.FIGURE_DPI_DEFAULT))
    fast_tiles = bool(settings.get('fast_tiles', True))
    
    if debug_stats:
        print_frame_statistics(frames_2d)
    
    # Color scaling
    if per_frame_colors:
        logger.info("Color scaling: PER-FRAME (slower)")
        global_vmin, global_vmax = None, None
    else:
        logger.info("Color scaling: GLOBAL (faster)")
        if vmin_override == 0.0 and vmax_override == 0.0:
            global_vmin, global_vmax = compute_global_color_limits(
                frames_2d, settings['colormap']
            )
        else:
            global_vmin, global_vmax = vmin_override, vmax_override
    
    logger.info(f"Exporting {len(frames_2d)} JPG frames to {output_dir}")
    
    # Single figure setup
    fig = plt.figure(figsize=UIConfig.FIGURE_SIZE)
    
    # Basemap
    tiler, proj, use_coastline, colormap, original = get_tiler_and_projection(settings)
    
    if tiler is not None:
        ax = fig.add_axes(UIConfig.MAIN_AXES_NO_TILES, projection=proj)
        if fast_tiles:
            try:
                ax.add_image(tiler, int(settings.get('tile_zoom', 12)))
            except Exception as e:
                logger.warning(f"Could not add tiles: {e}")
        if use_coastline:
            ax.coastlines()
    else:
        ax = fig.add_axes(UIConfig.MAIN_AXES_NO_TILES, projection=ccrs.PlateCarree())
        if use_coastline:
            ax.coastlines()
    
    # Colorbar axis
    cax = fig.add_axes(UIConfig.COLORBAR_AXES_ALT)
    
    # Set extent
    lon_min, lon_max = float(np.nanmin(lon_grid)), float(np.nanmax(lon_grid))
    lat_min, lat_max = float(np.nanmin(lat_grid)), float(np.nanmax(lat_grid))
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    
    # Initial pcolormesh
    first_frame = frames_2d[0]
    
    if per_frame_colors:
        vmin, vmax = float(np.nanmin(first_frame)), float(np.nanmax(first_frame))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            vmin, vmax = 0.0, 1.0
    else:
        vmin, vmax = global_vmin, global_vmax
    
    mesh_cmap = cmap if original else cmap.reversed()
    mesh = ax.pcolormesh(
        lon_grid, lat_grid, first_frame,
        transform=ccrs.PlateCarree(),
        shading='auto', cmap=mesh_cmap,
        vmin=vmin, vmax=vmax, alpha=0.85
    )
    
    # Add tiles after mesh if not pre-drawn
    if tiler is not None and not fast_tiles:
        try:
            ax.add_image(tiler, int(settings.get('tile_zoom', 12)))
        except Exception as e:
            logger.warning(f"Could not add tiles: {e}")
    
    # Colorbar
    cb = fig.colorbar(mesh, cax=cax, orientation='vertical', extend='both')
    cb.set_label(settings.get('label', settings['name']).title(), fontsize=10)
    
    title = fig.suptitle(
        f"{settings['name'].title()} @ {all_timestamps[0].replace('_', ' ')}",
        fontsize=16, y=0.98
    )
    
    img_paths = []
    total = len(frames_2d)
    
    # Turn off interactive mode
    plt.ioff()
    
    def update_mesh_data(qmesh, data2d):
        """Update QuadMesh data efficiently"""
        try:
            h = int(qmesh._meshHeight)
            w = int(qmesh._meshWidth)
            arr = np.ma.masked_invalid(data2d[:h, :w])
        except Exception:
            arr = np.ma.masked_invalid(data2d)
        qmesh.set_array(arr.ravel())
    
    # Export loop
    for i, data2d in enumerate(frames_2d):
        # Progress
        pct = (i + 1) * 100.0 / total
        logger.info(f"JPG  {i + 1}/{total} ({pct:5.1f}%)")
        if on_tick:
            on_tick(i + 1, total)
        
        # Update colors if per-frame
        if per_frame_colors:
            vmin_i = float(np.nanmin(data2d))
            vmax_i = float(np.nanmax(data2d))
            if not np.isfinite(vmin_i) or not np.isfinite(vmax_i) or vmax_i <= vmin_i:
                vmin_i, vmax_i = 0.0, 1.0
            mesh.set_clim(vmin_i, vmax_i)
        
        # Update mesh data
        update_mesh_data(mesh, data2d)
        
        # Update title
        title.set_text(
            f"{settings['name'].title()} @ {all_timestamps[i].replace('_', ' ')}"
        )
        
        # Save
        output_path = os.path.join(
            output_dir,
            f"{settings['name']}_{all_timestamps[i]}.jpg"
        )
        fig.savefig(output_path, dpi=dpi)
        img_paths.append(output_path)
    
    plt.close(fig)
    logger.info(f"JPG images saved in: {output_dir}")
    
    return img_paths, list(all_timestamps)


def export_as_geotiffs(
    all_var_data: List[npt.NDArray],
    all_timestamps: List[str],
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    output_dir: str,
    settings: Dict,
    on_tick: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Export frames as GeoTIFF files.
    
    Requires rasterio to be installed.
    
    Args:
        all_var_data: List of ND arrays
        all_timestamps: List of timestamps
        lat_grid: Full latitude grid
        lon_grid: Full longitude grid
        output_dir: Output directory
        settings: Export settings
        on_tick: Progress callback
        
    Returns:
        Output directory path
    """
    if not Dependencies.HAS_RASTERIO:
        raise RuntimeError(
            "GeoTIFF export requires rasterio. "
            "Install with: conda install -c conda-forge rasterio"
        )
    
    import rasterio
    from rasterio.transform import from_origin
    
    # Process frames
    frames_2d, lat_grid, lon_grid = ensure_2d_frames(
        all_var_data, lat_grid, lon_grid, settings
    )
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate geotransform
    lon_min = float(np.nanmin(lon_grid))
    lat_max = float(np.nanmax(lat_grid))
    x_res = float(np.nanmean(np.diff(lon_grid, axis=1)))
    y_res = float(np.nanmean(np.diff(lat_grid, axis=0)))
    
    transform = from_origin(lon_min - x_res/2.0, lat_max + y_res/2.0, x_res, y_res)
    
    # Check if grid needs flipping
    flip = False
    try:
        if lat_grid.shape[0] > 1 and (lat_grid[1, 0] > lat_grid[0, 0]):
            flip = True
    except Exception:
        pass
    
    nodata_write = settings.get('tiff_nodata', DataConfig.TIFF_NODATA_VALUE)
    
    logger.info(f"Exporting {len(frames_2d)} GeoTIFF frames to {output_dir}")
    
    total = len(frames_2d)
    for i, arr2d in enumerate(frames_2d):
        # Progress
        pct = (i + 1) * 100.0 / total
        logger.info(f"GTiff {i + 1}/{total} ({pct:5.1f}%)")
        if on_tick:
            on_tick(i + 1, total)
        
        # Prepare data
        output = np.flipud(arr2d) if flip else arr2d
        output = np.where(np.isnan(output), nodata_write, output).astype('float32')
        
        # Write file
        path = os.path.join(output_dir, f"{settings['name']}_{all_timestamps[i]}.tif")
        
        with rasterio.open(
            path, 'w',
            driver='GTiff',
            height=output.shape[0],
            width=output.shape[1],
            count=1,
            dtype='float32',
            crs='EPSG:4326',
            transform=transform,
            nodata=nodata_write,
            compress='LZW',
            tiled=True,
            blockxsize=256,
            blockysize=256
        ) as dst:
            dst.write(output, 1)
    
    logger.info(f"GeoTIFFs saved in: {output_dir}")
    return output_dir


def export_as_csvs(
    all_var_data: List[npt.NDArray],
    all_timestamps: List[str],
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    output_dir: str,
    settings: Dict,
    on_tick: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Export frames as CSV files (latitude, longitude, value).
    
    Args:
        all_var_data: List of ND arrays
        all_timestamps: List of timestamps
        lat_grid: Full latitude grid
        lon_grid: Full longitude grid
        output_dir: Output directory
        settings: Export settings
        on_tick: Progress callback
        
    Returns:
        Output directory path
    """
    # Process frames
    frames_2d, lat_grid, lon_grid = ensure_2d_frames(
        all_var_data, lat_grid, lon_grid, settings
    )
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Flatten grids
    lats = lat_grid.flatten()
    lons = lon_grid.flatten()
    
    logger.info(f"Exporting {len(frames_2d)} CSV frames to {output_dir}")
    
    total = len(frames_2d)
    for i, data2d in enumerate(frames_2d):
        # Progress
        pct = (i + 1) * 100.0 / total
        logger.info(f"CSV  {i + 1}/{total} ({pct:5.1f}%)")
        if on_tick:
            on_tick(i + 1, total)
        
        # Stack data
        arr = np.stack((lats, lons, data2d.flatten()), axis=1)
        
        # Write CSV
        path = os.path.join(output_dir, f"{settings['name']}_{all_timestamps[i]}.csv")
        np.savetxt(
            path, arr,
            delimiter=',',
            fmt='%f',
            header='latitude,longitude,value',
            comments=''
        )
    
    logger.info(f"CSVs saved in: {output_dir}")
    return output_dir


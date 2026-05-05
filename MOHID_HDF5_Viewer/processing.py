"""
MOHID HDF5 Viewer - Data Processing Module
Functions for data transformation, masking, and grid alignment
"""
from typing import Dict, List, Tuple, Set
import numpy as np
import numpy.typing as npt
from .config import logger, DataConfig


def reduce_non_horizontal_axes(
    array: npt.NDArray,
    horiz_axes: Set[int],
    mode: str = 'top',
    index: int = 0) -> npt.NDArray:
    """
    Reduce an ND array to 2D by collapsing non-horizontal axes.
    
    Args:
        array: Input ND array
        horiz_axes: Set of axes to preserve (horizontal dimensions)
        mode: Reduction mode ('top', 'bottom', 'mean', 'max', 'min', 'index')
        index: Specific index to extract when mode='index'
        
    Returns:
        2D array with only horizontal axes remaining
    """
    result = array
    
    # Get non-horizontal axes in order
    non_horiz = sorted([ax for ax in range(array.ndim) if ax not in horiz_axes])
    
    # Reduce each non-horizontal axis (process in reverse to maintain indices)
    for axis in reversed(non_horiz):
        if mode == 'mean':
            result = np.nanmean(result, axis=axis)
        elif mode == 'max':
            result = np.nanmax(result, axis=axis)
        elif mode == 'min':
            result = np.nanmin(result, axis=axis)
        elif mode == 'bottom':
            result = np.take(result, 0, axis=axis)
        elif mode == 'index':
            idx = min(int(index), result.shape[axis] - 1)
            result = np.take(result, idx, axis=axis)
        else:  # 'top' (default)
            result = np.take(result, -1, axis=axis)
    
    return np.asarray(result)


def best_horizontal_axes_and_target(
    arr_shape: Tuple[int, ...],
    grid_shape: Tuple[int, int]) -> Tuple[int, int, int, int, str]:
    """
    Find best matching axes for lat/lon in an array with fuzzy matching.
    
    Args:
        arr_shape: Shape of the data array
        grid_shape: Expected grid shape (ny, nx)
        
    Returns:
        Tuple of (axis_i, axis_j, target_ny, target_nx, order)
        where order is 'ny_nx' or 'nx_ny'
    """
    ny_grid, nx_grid = grid_shape
    ndim = len(arr_shape)
    
    best_match = None
    best_score = float('inf')
    
    def distance_score(ny: int, nx: int) -> int:
        """Calculate matching score (lower is better)"""
        return abs(arr_shape[ax_i] - ny) + abs(arr_shape[ax_j] - nx)
    
    for ax_i in range(ndim):
        for ax_j in range(ndim):
            if ax_i == ax_j:
                continue
            
            dim_i, dim_j = arr_shape[ax_i], arr_shape[ax_j]
            
            # Try different grid size variations
            candidates = [
                (distance_score(ny_grid, nx_grid), ax_i, ax_j, dim_i, dim_j, 'ny_nx'),
                (distance_score(ny_grid-1, nx_grid-1), ax_i, ax_j, dim_i, dim_j, 'ny_nx'),
                (distance_score(nx_grid, ny_grid), ax_i, ax_j, dim_i, dim_j, 'nx_ny'),
                (distance_score(nx_grid-1, ny_grid-1), ax_i, ax_j, dim_i, dim_j, 'nx_ny'),
            ]
            
            for candidate in candidates:
                if candidate[0] < best_score:
                    best_score = candidate[0]
                    best_match = candidate
    
    if best_match is None:
        raise ValueError("Could not find matching horizontal axes")
    
    _, axis_i, axis_j, dim_i, dim_j, order = best_match
    
    target_ny = dim_i if order == 'ny_nx' else dim_j
    target_nx = dim_j if order == 'ny_nx' else dim_i
    
    return axis_i, axis_j, int(target_ny), int(target_nx), order


def align_grids_to_target(
    lat_full: npt.NDArray,
    lon_full: npt.NDArray,
    target_ny: int,
    target_nx: int) -> Tuple[npt.NDArray, npt.NDArray]:
    """
    Crop latitude and longitude grids to target size.
    
    Args:
        lat_full: Full latitude grid
        lon_full: Full longitude grid
        target_ny: Target number of latitude points
        target_nx: Target number of longitude points
        
    Returns:
        Tuple of cropped (lat_grid, lon_grid)
    """
    ny, nx = lat_full.shape
    
    cropped_lat = lat_full[:min(target_ny, ny), :min(target_nx, nx)]
    cropped_lon = lon_full[:min(target_ny, ny), :min(target_nx, nx)]
    
    return cropped_lat, cropped_lon


def mask_nodata(
    arr2d: npt.NDArray,
    settings: Dict) -> npt.NDArray[np.float64]:
    """
    Mask NoData values in array by converting them to NaN.
    
    Args:
        arr2d: 2D input array
        settings: Dictionary with 'nodata_values' and 'auto_land_threshold'
        
    Returns:
        Float array with NoData values replaced by NaN
    """
    output = np.array(arr2d, dtype=float, copy=True)
    
    # Apply explicit NoData values
    nodata_vals = settings.get('nodata_values', [])
    for val in nodata_vals:
        if np.isnan(val):
            # Already NaN values stay NaN
            output[np.isnan(output)] = np.nan
        else:
            # Use tolerance for floating point comparison
            tolerance = max(1.0, abs(val)) * DataConfig.NODATA_TOLERANCE_FACTOR
            mask = np.isclose(output, val, atol=tolerance, rtol=0.0)
            output[mask] = np.nan
    
    # Apply automatic land threshold if enabled
    if settings.get('auto_land_threshold', False):
        output[output <= DataConfig.AUTO_LAND_THRESHOLD] = np.nan
    
    return output


def ensure_2d_frames(
    all_var_data: List[npt.NDArray],
    lat_grid_full: npt.NDArray,
    lon_grid_full: npt.NDArray,
    settings: Dict) -> Tuple[List[npt.NDArray], npt.NDArray, npt.NDArray]:
    """
    Reduce all frames from ND to 2D, align with grid, and mask NoData.
    
    Args:
        all_var_data: List of ND arrays (one per timestep)
        lat_grid_full: Full latitude grid
        lon_grid_full: Full longitude grid
        settings: Processing settings dict
        
    Returns:
        Tuple of (frames_2d, aligned_lat_grid, aligned_lon_grid)
    """
    reduce_mode = settings.get('reduce_mode', 'top')
    reduce_index = settings.get('reduce_index', 0)
    
    if not all_var_data:
        raise ValueError("No data to process")
    
    first = np.asarray(all_var_data[0])
    
    # Determine target size
    if first.ndim == 2:
        target_ny, target_nx = first.shape
    else:
        _, _, target_ny, target_nx, _ = best_horizontal_axes_and_target(
            first.shape, lat_grid_full.shape
        )
    
    # Align grids
    lat_grid, lon_grid = align_grids_to_target(
        lat_grid_full, lon_grid_full, target_ny, target_nx
    )
    
    ny, nx = lat_grid.shape
    frames_2d = []
    
    logger.info(f"Processing {len(all_var_data)} frames to 2D ({ny}x{nx})")
    
    for arr in all_var_data:
        arr = np.asarray(arr)
        
        if arr.ndim == 2:
            # Already 2D, check if transposed
            if arr.shape == (nx, ny):
                arr = arr.T
        else:
            # ND array - find horizontal axes and reduce
            from .hdf5_utils import find_horizontal_axes
            ax_i, ax_j, _ = find_horizontal_axes(arr.shape, ny, nx)
            
            if ax_i is None:
                # Use default last two dimensions
                horiz_axes = {arr.ndim - 2, arr.ndim - 1}
            else:
                horiz_axes = {ax_i, ax_j}
            
            arr = reduce_non_horizontal_axes(
                arr, horiz_axes, mode=reduce_mode, index=reduce_index
            )
            
            # Check if needs transpose
            if arr.shape == (nx, ny):
                arr = arr.T
        
        # Mask NoData and append
        frames_2d.append(mask_nodata(arr, settings))
    
    return frames_2d, lat_grid, lon_grid


def compute_global_color_limits(
    frames_2d: List[npt.NDArray],
    cmap_name: str) -> Tuple[float, float]:
    """
    Compute global min/max across all frames for consistent color scaling.
    
    Args:
        frames_2d: List of 2D arrays
        cmap_name: Colormap name (used for symmetric scaling)
        
    Returns:
        Tuple of (vmin, vmax)
    """
    if not frames_2d:
        return 0.0, 1.0
    
    arr = np.asarray(frames_2d, dtype=float)
    
    try:
        vmin = float(np.nanmin(arr))
        vmax = float(np.nanmax(arr))
    except Exception as e:
        logger.warning(f"Error computing color limits: {e}")
        return 0.0, 1.0
    
    # Validate limits
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        logger.warning(f"Invalid color limits: vmin={vmin}, vmax={vmax}")
        return 0.0, 1.0
    
    # Symmetric scaling for diverging colormaps
    if cmap_name == 'coolwarm' and vmin < 0 < vmax:
        max_abs = max(abs(vmin), abs(vmax))
        vmin, vmax = -max_abs, max_abs
    
    return vmin, vmax


def print_frame_statistics(
    frames_2d: List[npt.NDArray],
    max_print: int = None) -> None:
    """
    Print statistics summary for frames (debugging/validation).
    
    Args:
        frames_2d: List of 2D arrays
        max_print: Maximum number of frames to print (default from config)
    """
    if max_print is None:
        max_print = DataConfig.DEFAULT_STATS_FRAMES
    
    n = len(frames_2d)
    if n == 0:
        logger.warning("No frames to analyze")
        return
    
    # Select frames to print (first few + last few)
    half = max_print // 2
    indices = list(range(min(n, half))) + list(range(max(0, n - half), n))
    
    # Remove duplicates while preserving order
    seen = set()
    indices = [i for i in indices if not (i in seen or seen.add(i))]
    
    logger.info("\nFrame statistics (min/max/mean) [NoData ignored]:")
    
    unique_means = set()
    
    for i in indices:
        frame = np.asarray(frames_2d[i], dtype=float)
        
        with np.errstate(invalid='ignore'):
            frame_min = np.nanmin(frame)
            frame_max = np.nanmax(frame)
            frame_mean = float(np.nanmean(frame))
        
        logger.info(
            f"  Frame {i+1:4d}: min={frame_min:.6g} "
            f"max={frame_max:.6g} mean={frame_mean:.6g}"
        )
        
        if np.isfinite(frame_mean):
            unique_means.add(round(frame_mean, 6))
    
    # Warning if all frames are identical
    if len(unique_means) <= 1 and n > 1:
        logger.warning(
            "All frame means are identical (or nearly). "
            "Consider trying different k/reduction mode."
        )
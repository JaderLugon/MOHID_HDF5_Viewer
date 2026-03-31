"""
MOHID HDF5 Viewer - HDF5 File Utilities
Functions for reading and parsing MOHID HDF5 files
"""
from typing import Dict, List, Optional, Tuple
import numpy as np
import numpy.typing as npt
import h5py

from .config import logger, DataConfig


def suffix_to_num(suffix: str) -> int:
    """
    Convert a suffix string to a numeric step value.
    
    Args:
        suffix: Suffix string (e.g., "00001" or "step_123")
        
    Returns:
        Integer step number, or -1 if parsing fails
        
    Examples:
        >>> suffix_to_num("00001")
        1
        >>> suffix_to_num("step_123")
        123
        >>> suffix_to_num("abc")
        -1
    """
    try:
        return int(suffix)
    except ValueError:
        # Extract digits from string
        digits = ''.join(ch for ch in suffix if ch.isdigit())
        return int(digits) if digits else -1


def build_suffix_map(group: h5py.Group, prefix: str) -> Dict[int, str]:
    """
    Build a mapping from step number to suffix for datasets with pattern prefix_suffix.
    
    Args:
        group: HDF5 group containing datasets
        prefix: Dataset name prefix (e.g., "Time" or variable name)
        
    Returns:
        Dictionary mapping step numbers to suffixes
        
    Example:
        >>> build_suffix_map(group, "Time")
        {1: "00001", 2: "00002", 3: "00003"}
    """
    suffix_map = {}
    
    for key in group.keys():
        if not key.startswith(f'{prefix}_'):
            continue
        
        suffix = key.split('_', 1)[1]
        step_num = suffix_to_num(suffix)
        
        if step_num >= 0:
            suffix_map[step_num] = suffix
    
    return suffix_map


def first_array_and_suffix(
    hdf_file: h5py.File, 
    var_path: str, 
    var_name: str
) -> Tuple[Optional[npt.NDArray], Optional[str]]:
    """
    Get the first available array and its suffix for a variable.
    
    Args:
        hdf_file: Open HDF5 file
        var_path: Path to variable group (e.g., "Results/temperature")
        var_name: Variable name
        
    Returns:
        Tuple of (array, suffix) or (None, None) if not found
    """
    try:
        group = hdf_file[var_path]
        var_map = build_suffix_map(group, var_name)
        
        if not var_map:
            logger.warning(f"No datasets found for variable '{var_name}'")
            return None, None
            
        step = sorted(var_map.keys())[0]
        suffix = var_map[step]
        array = np.asarray(group[f"{var_name}_{suffix}"])
        
        logger.debug(f"First array for '{var_name}': shape={array.shape}, suffix={suffix}")
        return array, suffix
        
    except (KeyError, IndexError) as e:
        logger.error(f"Error reading first array for {var_name}: {e}")
        return None, None


def find_horizontal_axes(
    shape: Tuple[int, ...], 
    ny: int, 
    nx: int
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Identify which axes in an ND array correspond to horizontal (lat/lon) dimensions.
    
    Args:
        shape: Array shape
        ny: Expected number of latitude points
        nx: Expected number of longitude points
        
    Returns:
        Tuple of (axis_i, axis_j, order) where order is 'ny_nx' or 'nx_ny',
        or (None, None, None) if not found
        
    Examples:
        >>> find_horizontal_axes((100, 150), 100, 150)
        (0, 1, 'ny_nx')
        >>> find_horizontal_axes((10, 100, 150), 100, 150)
        (1, 2, 'ny_nx')
    """
    ndim = len(shape)
    
    for ax_i in range(ndim):
        for ax_j in range(ndim):
            if ax_i == ax_j:
                continue
                
            dim_i, dim_j = shape[ax_i], shape[ax_j]
            
            # Check for ny, nx order
            if dim_i == ny and dim_j == nx:
                return ax_i, ax_j, 'ny_nx'
            
            # Check for nx, ny order
            if dim_i == nx and dim_j == ny:
                return ax_i, ax_j, 'nx_ny'
    
    logger.debug(f"Could not find horizontal axes for shape={shape}, ny={ny}, nx={nx}")
    return None, None, None


def probe_k_axis_and_count(
    hdf_file: h5py.File,
    var_path: str,
    var_name: str,
    lat2d_shape: Tuple[int, int]
) -> Tuple[Optional[int], int]:
    """
    Detect the vertical (k) axis and count for a 3D variable.
    
    Args:
        hdf_file: Open HDF5 file
        var_path: Path to variable group
        var_name: Variable name
        lat2d_shape: Shape of the latitude grid (ny, nx)
        
    Returns:
        Tuple of (k_axis, k_count) or (None, 0) for 2D variables
        
    Example:
        >>> probe_k_axis_and_count(f, "Results/temperature", "temperature", (100, 150))
        (0, 20)  # 20 vertical layers, k is first axis
    """
    array, _ = first_array_and_suffix(hdf_file, var_path, var_name)
    
    if array is None:
        return None, 0
    
    array = np.asarray(array)
    
    if array.ndim < 3:
        logger.debug(f"Variable '{var_name}' is 2D")
        return None, 0  # 2D variable
    
    ny, nx = lat2d_shape
    ax_i, ax_j, _ = find_horizontal_axes(array.shape, ny, nx)
    
    # Identify horizontal axes
    if ax_i is None:
        # Default to last two dimensions
        horiz_axes = {array.ndim - 2, array.ndim - 1}
    else:
        horiz_axes = {ax_i, ax_j}
    
    # Non-horizontal axes are candidates for k
    non_horiz = [ax for ax in range(array.ndim) if ax not in horiz_axes]
    
    if not non_horiz:
        logger.warning(f"Could not identify vertical axis for '{var_name}'")
        return None, 0
    
    k_axis = non_horiz[0]
    k_count = int(array.shape[k_axis])
    
    logger.info(f"Variable '{var_name}' is 3D: k_axis={k_axis}, k_count={k_count}")
    return k_axis, k_count


def compute_k_depths_mean(
    hdf_file: h5py.File,
    lat2d_shape: Tuple[int, int],
    k_count: int
) -> Optional[List[float]]:
    """
    Compute mean depth for each k layer from vertical grid data.
    
    Args:
        hdf_file: Open HDF5 file
        lat2d_shape: Shape of latitude grid
        k_count: Number of vertical layers
        
    Returns:
        List of mean depths per layer, or None if unavailable
        
    Example:
        >>> compute_k_depths_mean(f, (100, 150), 20)
        [-0.5, -1.5, -2.5, ..., -50.0]
    """
    try:
        vert_group = hdf_file["Grid/VerticalZ"]
    except KeyError:
        logger.debug("No Grid/VerticalZ found in HDF5 file")
        return None
    
    candidates = [k for k in vert_group.keys() if k.startswith("Vertical_")]
    
    if not candidates:
        logger.debug("No Vertical_ datasets found")
        return None
    
    # Use second candidate if available (often more reliable)
    dataset_name = candidates[1] if len(candidates) > 1 else candidates[0]
    
    try:
        data = np.asarray(vert_group[dataset_name])
    except Exception as e:
        logger.error(f"Error reading vertical data: {e}")
        return None
    
    if data.ndim < 3:
        logger.debug("Vertical data is not 3D")
        return None
    
    # Collapse spatial dimensions to get mean interface depths
    interfaces = np.nanmax(data, axis=tuple(range(1, data.ndim)))
    
    if interfaces.shape[0] < DataConfig.MIN_INTERFACE_SIZE:
        logger.warning(f"Not enough interface data: {interfaces.shape[0]}")
        return None
    
    # Layer depths are midpoints between interfaces
    depths = 0.5 * (interfaces[:-1] + interfaces[1:])
    
    if depths.shape[0] != k_count:
        logger.warning(
            f"Depth count mismatch: computed={depths.shape[0]}, expected={k_count}"
        )
        return None
    
    logger.info(f"Computed {k_count} layer depths from VerticalZ data")
    return depths.tolist()


def get_available_variables(hdf_path: str) -> List[str]:
    """
    Get list of available variables from HDF5 Results group.
    
    Args:
        hdf_path: Path to HDF5 file
        
    Returns:
        Sorted list of variable names
        
    Example:
        >>> get_available_variables("model.hdf5")
        ['salinity', 'temperature', 'velocity_U', 'velocity_V', 'water_level']
    """
    try:
        with h5py.File(hdf_path, "r") as hdf_file:
            if "Results" not in hdf_file:
                logger.error(f"No 'Results' group found in {hdf_path}")
                return []
            
            results_group = hdf_file["Results"]
            
            if len(results_group) == 0:
                logger.warning(f"Results group is empty in {hdf_path}")
                return []
            
            variables = sorted(list(results_group.keys()))
            logger.info(f"Found {len(variables)} variables in {hdf_path}")
            return variables
            
    except Exception as e:
        logger.error(f"Error reading file {hdf_path}: {e}")
        return []


def load_variable_data(
    hdf_path: str,
    var_path: str,
    var_name: str
) -> Tuple[Optional[List[npt.NDArray]], Optional[List[str]], 
           Optional[npt.NDArray], Optional[npt.NDArray]]:
    """
    Load all timesteps for a variable with matching timestamps.
    
    Robustly matches /Time/Time_<suffix> with /Results/<var>/<var>_<suffix> 
    by numeric step.
    
    Args:
        hdf_path: Path to HDF5 file
        var_path: Path to variable group (e.g., "Results/temperature")
        var_name: Variable name
        
    Returns:
        Tuple of (variable_data_list, timestamps_list, lat_grid, lon_grid)
        or (None, None, None, None) on failure
        
    Example:
        >>> data, stamps, lat, lon = load_variable_data("model.hdf5", 
        ...                                              "Results/temperature",
        ...                                              "temperature")
        >>> len(data)
        120  # 120 timesteps
    """
    all_var_data: List[npt.NDArray] = []
    all_timestamps: List[str] = []
    
    try:
        with h5py.File(hdf_path, "r") as hdf_file:
            # Load grids
            try:
                lat_grid_full = np.asarray(hdf_file["Grid/Latitude"])
                lon_grid_full = np.asarray(hdf_file["Grid/Longitude"])
            except KeyError as e:
                logger.error(f"Could not find Grid/Latitude or Grid/Longitude: {e}")
                return None, None, None, None
            
            # Build step mappings
            try:
                time_map = build_suffix_map(hdf_file["Time"], "Time")
                var_map = build_suffix_map(hdf_file[var_path], var_name)
            except KeyError as e:
                logger.error(f"Could not find Time or variable group: {e}")
                return None, None, None, None
            
            # Find common steps
            common_steps = sorted(set(time_map.keys()) & set(var_map.keys()))
            
            if not common_steps:
                logger.error(f"No matching timesteps found for {var_name}")
                return None, None, None, None
            
            logger.info(f"Loading {len(common_steps)} timesteps for '{var_name}'")
            
            # Load data for each step
            for step_num in common_steps:
                ts_suffix = time_map[step_num]
                var_suffix = var_map[step_num]
                
                # Load variable data
                try:
                    data = np.asarray(hdf_file[f"{var_path}/{var_name}_{var_suffix}"])
                    all_var_data.append(data)
                except Exception as e:
                    logger.warning(f"Could not load data for step {step_num}: {e}")
                    continue
                
                # Parse timestamp
                try:
                    time_array = np.asarray(hdf_file[f"Time/Time_{ts_suffix}"]).astype(int)
                    
                    year = int(time_array[0])
                    month = int(time_array[1])
                    day = int(time_array[2])
                    hour = int(time_array[3]) if time_array.size > 3 else 0
                    minute = int(time_array[4]) if time_array.size > 4 else 0
                    
                    timestamp = f"{year:04d}{month:02d}{day:02d}_{hour:02d}{minute:02d}"
                    all_timestamps.append(timestamp)
                    
                except Exception as e:
                    logger.warning(f"Could not parse timestamp for step {step_num}: {e}")
                    all_timestamps.append(f"step_{step_num:05d}")
        
        logger.info(f"Successfully loaded {len(all_var_data)} timesteps for '{var_name}'")
        return all_var_data, all_timestamps, lat_grid_full, lon_grid_full
        
    except Exception as e:
        logger.error(f"Error loading variable data: {e}", exc_info=True)
        return None, None, None, None


def validate_hdf5_structure(hdf_path: str) -> Tuple[bool, List[str]]:
    """
    Validate if HDF5 file has expected MOHID structure.
    
    Args:
        hdf_path: Path to HDF5 file
        
    Returns:
        Tuple of (is_valid, list_of_issues)
        
    Example:
        >>> valid, issues = validate_hdf5_structure("model.hdf5")
        >>> if not valid:
        ...     print("Issues:", issues)
    """
    issues = []
    
    try:
        with h5py.File(hdf_path, "r") as f:
            # Check required groups
            required_groups = ["Grid", "Time", "Results"]
            for group in required_groups:
                if group not in f:
                    issues.append(f"Missing required group: '{group}'")
            
            # Check Grid contents
            if "Grid" in f:
                if "Latitude" not in f["Grid"]:
                    issues.append("Missing Grid/Latitude")
                if "Longitude" not in f["Grid"]:
                    issues.append("Missing Grid/Longitude")
            
            # Check if Results has variables
            if "Results" in f:
                if len(f["Results"]) == 0:
                    issues.append("Results group is empty")
            
            # Check if Time has data
            if "Time" in f:
                if len(f["Time"]) == 0:
                    issues.append("Time group is empty")
    
    except Exception as e:
        issues.append(f"Error reading file: {e}")
    
    is_valid = len(issues) == 0
    
    if is_valid:
        logger.info(f"HDF5 structure validation passed: {hdf_path}")
    else:
        logger.warning(f"HDF5 structure validation failed: {len(issues)} issues")
        for issue in issues:
            logger.warning(f"  - {issue}")
    
    return is_valid, issues
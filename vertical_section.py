"""
MOHID HDF5 Viewer - Vertical Section Module
Functions for creating and visualizing vertical cross-sections
"""
from typing import Dict, List, Tuple, Optional
import numpy as np
import numpy.typing as npt
import matplotlib.pyplot as plt
#import matplotlib as mpl
#from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import h5py

from config import logger   #, UIConfig, DataConfig

from gui_components import show_error_popup #DS_18/11


def parse_geometry_file(geometry_path: str) -> Optional[Dict]:
    """
    Parse MOHID Geometry_1.dat file to extract vertical layer structure.
    
    CORRECTED INTERPRETATION:
    - CARTESIAN domain: Starts at DOMAINDEPTH and extends downward with fixed thicknesses
    - SIGMA domain: Starts at surface (0m) and extends to DOMAINDEPTH (or bathymetry if shallower)
    - CARTESIAN layers are ELIMINATED when they exceed bathymetry depth
    - CARTESIANTOP layers are possible in MOHID Land model, they go from top to bottom
    
    Args:
        geometry_path: Path to Geometry_1.dat file
        
    Returns:
        Dictionary with:
        - 'domains': List of domain dictionaries
        - 'total_layers': Total number of layers
        - 'cartesian_start_depth': Depth where CARTESIAN domain starts
        Or None if parsing fails
    """
    try:
        with open(geometry_path, 'r') as f:
            lines = f.readlines()
        
        domains = []
        current_domain = None
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines and comments
            if not line_stripped or line_stripped.startswith('!'):
                continue
            
            # Start new domain
            if line_stripped.startswith('<begindomain>'):
                current_domain = {}
                continue
            
            # End domain
            if line_stripped.startswith('<enddomain>'):
                if current_domain:
                    domains.append(current_domain)
                    current_domain = None
                continue
            
            # Parse domain parameters
            if current_domain is not None:
                if ':' in line_stripped:
                    parts = line_stripped.split(':', 1)
                    key = parts[0].strip()
                    value_str = parts[1].split('!')[0].strip()  # Remove inline comments
                    
                    if key == 'ID':
                        current_domain['id'] = int(value_str)
                    elif key == 'TYPE':
                        current_domain['type'] = value_str
                    elif key == 'LAYERS':
                        current_domain['layers'] = int(value_str)
                    elif key == 'LAYERTHICKNESS':
                        thicknesses = [float(x) for x in value_str.split()]
                        current_domain['layer_thickness'] = thicknesses
                    elif key == 'DOMAINDEPTH':
                        depth_val = float(value_str)
                        current_domain['domain_depth'] = depth_val if depth_val != -99 else None
        
        if not domains:
            logger.error("ERROR: No domains found in geometry file")
            show_error_popup("ERROR: No domains found in geometry file")
            return None
        
        # Separate domains
        cartesiantop_domain = None
        cartesian_domain = None
        sigma_domain = None
        cartesian_start_depth = None
        
        for domain in domains:
            if domain.get('type') == 'CARTESIAN':
                cartesian_domain = domain
                if domain.get('domain_depth'):
                    cartesian_start_depth = domain.get('domain_depth')
            elif domain.get('type') == 'CARTESIANTOP':
                cartesiantop_domain = domain
                cartesian_start_depth = 0
            elif domain.get('type') == 'SIGMA':
                sigma_domain = domain
        
        total_layers = sum(d.get('layers', 0) for d in domains)
        
        logger.info("\n=== GEOMETRY PARSED (CORRECTED - LAYER ELIMINATION) ===")
        logger.info(f"Total layers (maximum): {total_layers}")
        
        if sigma_domain:
            sigma_end = cartesian_start_depth if cartesian_start_depth else 25
            logger.info(f"\nSIGMA Domain (ID={sigma_domain['id']}): {sigma_domain['layers']} layers")
            logger.info("  From: 0m (surface)")
            logger.info(f"  To: -{sigma_end}m (or bathymetry if shallower)")
            logger.info(f"  Proportions: {sigma_domain.get('layer_thickness', [])}")
        
        if cartesiantop_domain:
            cart_thicknesses = cartesiantop_domain.get('layer_thickness', [])
            cart_total = sum(cart_thicknesses)
            logger.info(f"\nCARTESIANTOP Domain (ID={cartesiantop_domain['id']}): {cartesiantop_domain['layers']} layers (max)")
            logger.info(f"  Thicknesses: {cart_thicknesses}")
        
        if cartesian_domain:
            cart_start = cartesian_start_depth if cartesian_start_depth else 0
            cart_thicknesses = cartesian_domain.get('layer_thickness', [])
            cart_total = sum(cart_thicknesses)
            logger.info(f"\nCARTESIAN Domain (ID={cartesian_domain['id']}): {cartesian_domain['layers']} layers (max)")
            logger.info(f"  From: -{cart_start}m")
            logger.info(f"  To: -{cart_start + cart_total:.1f}m (if deep enough)")
            logger.info(f"  Thicknesses: {cart_thicknesses}")
            logger.info("  NOTE: Layers eliminated when exceeding bathymetry")
        
        return {
            'domains': domains,
            'total_layers': total_layers,
            'cartesian_start_depth': cartesian_start_depth,
            'cartesiantop_domain': cartesiantop_domain,
            'cartesian_domain': cartesian_domain,
            'sigma_domain': sigma_domain
        }
        
    except Exception as e:
        logger.error(f"ERROR parsing geometry file: {e}")
        show_error_popup(f"ERROR parsing geometry file: {e}")
        return None


def compute_layer_interfaces(domains: List[Dict], bathymetry: float = None) -> npt.NDArray:
    """
    Compute depth of layer interfaces from domain definitions.
    
    CORRECTED LOGIC WITH LAYER ELIMINATION:
    - SIGMA domain: from surface (0m) to DOMAINDEPTH or bathymetry (whichever is shallower)
    - CARTESIAN domain: from DOMAINDEPTH downward with fixed thicknesses
    - CARTESIAN layers are CUT OFF at bathymetry (layers beyond bottom are eliminated)
    
    Args:
        domains: List of domain dictionaries
        bathymetry: Bottom depth (negative value, e.g., -50m)
        
    Returns:
        Array of interface depths (surface = 0, deeper = more negative)
    """
    # Separate domains by type
    cartesian_domain = None
    sigma_domain = None
    cartesiantop_domain = None
    
    for domain in domains:
        if domain.get('type') == 'CARTESIAN':
            cartesian_domain = domain
        elif domain.get('type') == 'SIGMA':
            sigma_domain = domain
        elif domain.get('type') == 'CARTESIANTOP':
            cartesiantop_domain = domain
    
    interfaces = [0.0]  # Start at surface
    
    # Determine SIGMA domain bottom depth
    cartesian_start = -25.0  # Default
    if cartesian_domain and cartesian_domain.get('domain_depth'):
        cartesian_start = -abs(cartesian_domain.get('domain_depth'))
    # MOHID Land case
    elif cartesiantop_domain:
        cartesian_start = -bathymetry
    
    # If bathymetry is shallower than cartesian_start, SIGMA goes only to bathymetry
    if bathymetry is not None:
        sigma_bottom = max(bathymetry, cartesian_start)  # Use shallower depth
    else:
        sigma_bottom = cartesian_start
    
    # === SIGMA LAYERS (Surface to sigma_bottom) ===
    if sigma_domain:
        layers = sigma_domain.get('layers', 0)
        thicknesses = sigma_domain.get('layer_thickness', [])
        
        if thicknesses:
            total_thickness = sum(thicknesses)
            cumulative = 0.0
            
            for i in range(layers):
                if i < len(thicknesses):
                    cumulative += thicknesses[i]
                else:
                    cumulative += thicknesses[-1]
                
                # Proportional depth from surface to sigma_bottom
                proportion = cumulative / total_thickness
                interface_depth = proportion * sigma_bottom
                interfaces.append(interface_depth)
        else:
            # Uniform distribution if no thicknesses specified
            for i in range(1, layers + 1):
                proportion = i / layers
                interface_depth = proportion * sigma_bottom
                interfaces.append(interface_depth)
    
    # === CARTESIAN LAYERS (cartesian_start to bottom) ===
    # Only add if bathymetry is deeper than cartesian_start
    if cartesian_domain:
        if bathymetry is None or bathymetry < cartesian_start:
            layers = cartesian_domain.get('layers', 0)
            thicknesses = cartesian_domain.get('layer_thickness', [])
            
            current_depth = cartesian_start
            
            for i in range(layers):
                if i < len(thicknesses):
                    thickness = thicknesses[i]
                else:
                    thickness = thicknesses[-1] if thicknesses else 1.0
                
                current_depth -= thickness
                
                # CRITICAL: Stop if we've reached or passed bathymetry
                if bathymetry is not None and current_depth <= bathymetry:
                    # Add bathymetry as final interface and stop
                    if interfaces[-1] > bathymetry:  # Avoid duplicate
                        interfaces.append(bathymetry)
                    break
                
                interfaces.append(current_depth)
    
    if cartesiantop_domain:
        layers = cartesiantop_domain.get('layers', 0)
        thicknesses = cartesiantop_domain.get('layer_thickness', [])
            
        current_depth = cartesian_start
            
        for i in range(layers):
            if i < len(thicknesses):
                 thickness = thicknesses[i]
            else:
                 thickness = thicknesses[-1] if thicknesses else 1.0
                
            current_depth -= thickness
     
            interfaces.append(current_depth)
    
    return np.array(interfaces)


def build_3d_depth_grid_land(
    geometry_info: Dict,
    altimetry_2d: npt.NDArray,
    vertical_exaggeration: float = 1.0
) -> npt.NDArray:
    """
    Build 3D depth grid for MOHID Land models with vertical exaggeration.
    
    Args:
        geometry_info: Dictionary from parse_geometry_file()
        altimetry_2d: 2D array (ny, nx) of surface elevation
        vertical_exaggeration: Multiplier for vertical distances (default=1.0)
        
    Returns:
        3D array (nk, ny, nx) of layer center depths
    """
    ny, nx = altimetry_2d.shape
    total_layers = geometry_info['total_layers']
    cartesiantop_domain = geometry_info.get('cartesiantop_domain')
    
    # Initialize output
    depth_grid = np.full((total_layers, ny, nx), np.nan)
    
    cartesiantop_layers = cartesiantop_domain.get('layers', 0) if cartesiantop_domain else 0
    cartesiantop_thicknesses = cartesiantop_domain.get('layer_thickness', []) if cartesiantop_domain else []
    
    # Maximum soil depth (can be adjusted based on model configuration)
    max_soil_depth = 100.0  # meters below surface
    
    logger.info("\n=== BUILDING 3D DEPTH GRID: MOHID LAND ===")
    logger.info(f"Vertical Exaggeration: {vertical_exaggeration}x")
    logger.info("Surface level: altimetry (topography)")
    logger.info(f"Maximum soil depth: {max_soil_depth}m below surface")
    
    # For each horizontal cell
    for j in range(ny):
        for i in range(nx):
            surface_elevation = altimetry_2d[j, i]
            
            # Handle invalid cells
            if surface_elevation == 99 or np.isnan(surface_elevation):
                continue
            
#            max_depth = max_soil_depth
            
            layer_idx = 0         

            # === BUILD CARTESIANTOP LAYERS ===
            if cartesiantop_domain:
                current_depth = surface_elevation
                
                for k in range(cartesiantop_layers):
                    # Get layer thickness and apply VE
                    if k < len(cartesiantop_thicknesses):
                        thickness = cartesiantop_thicknesses[k] * vertical_exaggeration
                    else:
                        thickness = (cartesiantop_thicknesses[-1] if cartesiantop_thicknesses else 1.0) * vertical_exaggeration
                    
                    layer_top = current_depth
                    layer_bottom = current_depth - thickness
                    layer_center = (layer_top + layer_bottom) / 2.0
                    depth_grid[layer_idx, j, i] = layer_center
                    current_depth = layer_bottom
                    layer_idx += 1
    
    # Invert vertical axis (surface layers first)
    depth_grid = depth_grid[::-1, :, :]
    
    valid_cells = np.sum(~np.isnan(depth_grid))
    total_cells = depth_grid.size
    logger.info(f"\nBuilt 3D depth grid (MOHID Land): shape={depth_grid.shape}")
    logger.info(f"Valid cells: {valid_cells}/{total_cells} ({100*valid_cells/total_cells:.1f}%)")
    logger.info(f"Elevation range: {np.nanmin(depth_grid):.2f}m to {np.nanmax(depth_grid):.2f}m")
    
    return depth_grid


    
def build_3d_depth_grid_water(
    geometry_info: Dict,
    bathymetry_2d: npt.NDArray,
    vertical_exaggeration: float = 1.0  # Mantém o parâmetro mas ignora
) -> npt.NDArray:
    """
    Build 3D depth grid for MOHID Water models.
    NOTE: vertical_exaggeration is ignored for Water models.
    
    LOGIC FOR MOHID WATER:
    - Surface at 0m (sea level)
    - SIGMA layers: 0m to DOMAINDEPTH (or bathymetry if shallower)
    - CARTESIAN layers: DOMAINDEPTH to bottom (only if deep enough)
    - Depths are NEGATIVE (below sea level)
    - CARTESIAN layers beyond bathymetry are ELIMINATED (filled with NaN)
    
    Args:
        geometry_info: Dictionary from parse_geometry_file()
        bathymetry_2d: 2D array (ny, nx) of bottom depths (negative values for water depth)
        
    Returns:
        3D array (nk, ny, nx) of layer center depths (negative values)
        Layers that don't exist are filled with NaN
    """
    # Sempre usar VE = 1.0 para MOHID Water
    if vertical_exaggeration != 1.0:
        logger.warning("Vertical exaggeration ignored for MOHID Water (always 1.0)")

    ny, nx = bathymetry_2d.shape
    total_layers = geometry_info['total_layers']
    cartesian_domain = geometry_info.get('cartesian_domain')
    sigma_domain = geometry_info.get('sigma_domain')
    cartesian_start_depth = geometry_info.get('cartesian_start_depth', 25)
    
    # Initialize output
    depth_grid = np.full((total_layers, ny, nx), np.nan)
    
    # Get domain info
    sigma_layers = sigma_domain.get('layers', 0) if sigma_domain else 0
    sigma_thicknesses = sigma_domain.get('layer_thickness', []) if sigma_domain else []
    sigma_total = sum(sigma_thicknesses) if sigma_thicknesses else 1.0
    
    cartesian_layers = cartesian_domain.get('layers', 0) if cartesian_domain else 0
    cartesian_thicknesses = cartesian_domain.get('layer_thickness', []) if cartesian_domain else []
    
    logger.info("\n=== BUILDING 3D DEPTH GRID: MOHID WATER ===")
    logger.info("Surface level: 0m (sea level)")
    logger.info(f"SIGMA domain: 0m to -{abs(cartesian_start_depth)}m (or bathymetry)")
    logger.info(f"CARTESIAN domain: -{abs(cartesian_start_depth)}m to bottom")
    
    # For each horizontal cell
    for j in range(ny):
        for i in range(nx):
            # Water depth (negative value, e.g., -50m)
            bottom_depth = -bathymetry_2d[j, i]
            
            # Handle invalid/land cells
            if bathymetry_2d[j, i] == 99:
                bottom_depth = 1  # Shallow water
            
            # Skip if bathymetry is invalid
            if np.isnan(bottom_depth) or bottom_depth >= 0:
                continue
            
            layer_idx = 0
            
            # === BUILD SIGMA LAYERS (Surface to cartesian_start or bathymetry) ===
            if sigma_domain:
                # Determine where SIGMA domain ends
                # Use shallower of: bathymetry or cartesian_start_depth
                sigma_bottom = max(bottom_depth, -abs(cartesian_start_depth))
                
                cumulative = 0.0
                for k in range(sigma_layers):
                    # Get thickness proportion
                    if k < len(sigma_thicknesses):
                        layer_thickness = sigma_thicknesses[k]
                    else:
                        layer_thickness = sigma_thicknesses[-1] if sigma_thicknesses else (1.0 / sigma_layers)
                    
                    # Calculate interface depths
                    proportion_top = cumulative / sigma_total
                    cumulative += layer_thickness
                    proportion_bottom = cumulative / sigma_total
                    
                    # SIGMA spans from 0 (surface) to sigma_bottom
                    layer_top = proportion_top * sigma_bottom
                    layer_bottom = proportion_bottom * sigma_bottom
                    layer_center = (layer_top + layer_bottom) / 2.0
                    
                    depth_grid[layer_idx, j, i] = layer_center
                    layer_idx += 1
            
            # === BUILD CARTESIAN LAYERS (cartesian_start to bottom) ===
            if cartesian_domain:
                # Only add CARTESIAN layers if water is deep enough
                if bottom_depth < -abs(cartesian_start_depth):
                    current_depth = -abs(cartesian_start_depth)
                    
                    for k in range(cartesian_layers):
                        # Get layer thickness
                        if k < len(cartesian_thicknesses):
                            thickness = cartesian_thicknesses[k]
                        else:
                            thickness = cartesian_thicknesses[-1] if cartesian_thicknesses else 1.0
                        
                        layer_top = current_depth
                        layer_bottom = current_depth - thickness
                        
                        # CRITICAL: Check if layer exceeds bathymetry
                        if layer_bottom <= bottom_depth:
                            # Layer goes beyond bathymetry
                            if layer_top > bottom_depth:
                                # Partial layer: truncate at bathymetry
                                actual_bottom = bottom_depth
                                layer_center = (layer_top + actual_bottom) / 2.0
                                depth_grid[layer_idx, j, i] = layer_center
                            else:
                                # Entire layer is below bathymetry - eliminate (NaN)
                                depth_grid[layer_idx, j, i] = np.nan
                            
                            # All subsequent layers are also eliminated
                            layer_idx += 1
                            for remaining in range(k + 1, cartesian_layers):
                                depth_grid[layer_idx, j, i] = np.nan
                                layer_idx += 1
                            break
                        else:
                            # Layer is fully valid
                            layer_center = (layer_top + layer_bottom) / 2.0
                            depth_grid[layer_idx, j, i] = layer_center
                        
                        current_depth = layer_bottom
                        layer_idx += 1
                else:
                    # Water not deep enough for any CARTESIAN layers
                    for k in range(cartesian_layers):
                        depth_grid[layer_idx, j, i] = np.nan
                        layer_idx += 1
    
    # Invert vertical axis (surface layers first)
    depth_grid = depth_grid[::-1, :, :]
        
    valid_cells = np.sum(~np.isnan(depth_grid))
    total_cells = depth_grid.size
    logger.info(f"\nBuilt 3D depth grid (MOHID Water): shape={depth_grid.shape}")
    logger.info(f"Valid cells: {valid_cells}/{total_cells} ({100*valid_cells/total_cells:.1f}%)")
    logger.info(f"Depth range: {np.nanmin(depth_grid):.2f}m to {np.nanmax(depth_grid):.2f}m")
    
    return depth_grid
    
    
    

def get_layer_info(geometry_info: Dict, layer_index: int) -> Dict:
    """
    Get information about a specific layer.
    
    Args:
        geometry_info: Dictionary from parse_geometry_file()
        layer_index: Layer index (0-based, 0 is top layer)
        
    Returns:
        Dictionary with:
        - 'domain_type': 'SIGMA' or 'CARTESIAN'
        - 'domain_layer_index': Index within the domain
        - 'domain_id': Domain ID
    """
    sigma_domain = geometry_info.get('sigma_domain')
    cartesian_domain = geometry_info.get('cartesian_domain')
    
    sigma_layers = sigma_domain.get('layers', 0) if sigma_domain else 0
    
    if layer_index < sigma_layers:
        # SIGMA layer
        return {
            'domain_type': 'SIGMA',
            'domain_layer_index': layer_index,
            'domain_id': sigma_domain.get('id', 2) if sigma_domain else None
        }
    else:
        # CARTESIAN layer
        cart_layer_idx = layer_index - sigma_layers
        return {
            'domain_type': 'CARTESIAN',
            'domain_layer_index': cart_layer_idx,
            'domain_id': cartesian_domain.get('id', 1) if cartesian_domain else None
        }



# ===================== VERTICAL SECTION EXTRACTION =====================

def extract_longitudinal_section(
    data_3d: npt.NDArray,
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    depth_grid: npt.NDArray,
    lat_value: float
) -> Tuple[npt.NDArray, npt.NDArray, npt.NDArray]:
    """
    Extract longitudinal (along longitude) vertical section at given latitude.
    
    Args:
        data_3d: 3D data array (nk[211], nx[101], ny[128])
        lat_grid: 2D latitude grid (nx[101], ny[128])
        lon_grid: 2D longitude grid (nx[101], ny[128])
        depth_grid: 3D depth grid (nk[11], nx[101], ny[128]) with layer depths
        lat_value: Latitude value for the section
        
    Returns:
        Tuple of (section_data, section_lon, section_depth)
        - section_data: 2D array (nk, nx) of data values
        - section_lon: 1D array (nx,) of longitude values
        - section_depth: 2D array (nk, nx) of depth values
    """
    # Find nearest latitude index
    lat_per_row = lat_grid[0,:]  # Shape: (,ny)
    lat_diff = np.abs(lat_per_row - lat_value)  # Array 1D (ny,)
    j_index = np.argmin(lat_diff)
    logger.info(f"Extracting longitudinal section at j={j_index} (latâ‰ˆ{lat_grid[j_index,0]:.4f})")
        
    # Extract section (all k layers, selected j, all i)
    section_data = data_3d[:, :, j_index]  # (nk, nx)
    section_lon = lon_grid[:, j_index]      # (nx,)
    section_depth = depth_grid[:, :, j_index]  # (nk, nx)
   
    # Validate dimensions
    nk, nx = section_data.shape
    logger.info(f"Section dimensions: nk={nk}, nx={nx}")
    logger.info(f"  section_data: {section_data.shape}")
    logger.info(f"  section_lon: {section_lon.shape}")
    logger.info(f"  section_depth: {section_depth.shape}")
    
    # Ensure consistency
    if len(section_lon) != nx:
        logger.error(f"Longitude dimension mismatch: {len(section_lon)} vs {nx}")
        section_lon = section_lon[:nx]
   
    if section_depth.shape[1] != nx:
        logger.error(f"Depth dimension mismatch: {section_depth.shape[1]} vs {nx}")
        section_depth = section_depth[:, :nx]
    
    return section_data, section_lon, section_depth


def extract_latitudinal_section(
    data_3d: npt.NDArray,
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    depth_grid: npt.NDArray,
    lon_value: float
) -> Tuple[npt.NDArray, npt.NDArray, npt.NDArray]:
    """
    Extract latitudinal (along latitude) vertical section at given longitude.
    
    Args:
        data_3d: 3D data array (nk[25], nx[101], ny[128])
        lat_grid: 2D latitude grid (nx[101], ny[128])
        lon_grid: 2D longitude grid (nx[101], ny[128])
        depth_grid: 3D depth grid (nk[25], nx[101], ny[128]) with layer depths
        lon_value: Longitude value for the section
        
    Returns:
        Tuple of (section_data, section_lat, section_depth)
        - section_data: 2D array (nk, ny) of data values
        - section_lat: 1D array (ny,) of latitude values
        - section_depth: 2D array (nk, ny) of depth values
    """
    # Find nearest longitude index
    lon_per_column = lon_grid[:,0]  # Shape: (nx,)
    lon_diff = np.abs(lon_per_column - lon_value)  # Array 1D (nx,)
    i_index = np.argmin(lon_diff)
    logger.info(f"Extracting latitudinal section at i={i_index} (lonâ‰ˆ{lon_grid[0, i_index]:.4f})")
    
    # Extract section (all k layers, all j, selected i)
    section_data = data_3d[:, i_index, :]  # (nk, ny)
    section_lat = lat_grid[i_index, :]      # (ny,)
    section_depth = depth_grid[:, i_index, :]  # (nk, ny)
    
    # Validate dimensions
    nk, ny = section_data.shape
    logger.info(f"Section dimensions: nk={nk}, ny={ny}")
    logger.info(f"  section_data: {section_data.shape}")
    logger.info(f"  section_lat: {section_lat.shape}")
    logger.info(f"  section_depth: {section_depth.shape}")
    
    # Ensure consistency
    if len(section_lat) != ny:
        logger.error(f"Latitude dimension mismatch: {len(section_lat)} vs {ny}")
        section_lat = section_lat[:ny]
    
    if section_depth.shape[1] != ny:
        logger.error(f"Depth dimension mismatch: {section_depth.shape[1]} vs {ny}")
        section_depth = section_depth[:, :ny]
    
    return section_data, section_lat, section_depth


# ===================== 3D DATA LOADING =====================

def load_3d_variable_timestep(
    hdf_path: str,
    var_name: str,
    timestep_index: int = 0
) -> Optional[npt.NDArray]:
    """
    Load a single timestep of 3D variable data from HDF5 file.
    
    Args:
        hdf_path: Path to HDF5 file
        var_name: Variable name
        timestep_index: Which timestep to load (0-based)
        
    Returns:
        3D array (nk, ny, nx) or None if loading fails
    """
    try:
        with h5py.File(hdf_path, 'r') as f:
            var_path = f"Results/{var_name}"
            
            if var_path not in f:
                logger.error(f"Variable path not found: {var_path}")
                return None
            
            # Get list of timestep datasets
            group = f[var_path]
            datasets = sorted([k for k in group.keys() if k.startswith(f"{var_name}_")])
            
            if not datasets:
                logger.error(f"No datasets found for variable: {var_name}")
                return None
            
            if timestep_index >= len(datasets):
                logger.warning(f"Timestep {timestep_index} out of range, using last timestep")
                timestep_index = len(datasets) - 1
            
            dataset_name = datasets[timestep_index]
            data = np.asarray(group[dataset_name])
            
            logger.info(f"Loaded 3D data: {dataset_name}, shape={data.shape}")
            
            # Ensure 3D
            if data.ndim < 3:
                logger.error(f"Data is not 3D: shape={data.shape}")
                return None
            
            # If 4D (time, k, j, i), take first time
            if data.ndim == 4:
                data = data[0, :, :, :]
            
            return data
            
    except Exception as e:
        logger.error(f"Error loading 3D variable: {e}", exc_info=True)
        return None


# ===================== PLOTTING FUNCTIONS =====================

def plot_vertical_section(
    section_data: npt.NDArray,
    section_coord: npt.NDArray,
    section_depth: npt.NDArray,
    var_name: str,
    coord_type: str,
    colormap: str = 'rainbow',
    vmin: float = None,
    vmax: float = None,
    p_size: int = None,
    title: str = None,
    fig: plt.Figure = None,
    ax: plt.Axes = None,
    model_type: str = 'MOHID Water',
    vertical_exaggeration: float = 1.0,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot vertical section with depth on y-axis.
    
    Args:
        section_data: 2D array (nk, n_horizontal) of data values
        section_coord: 1D array of horizontal coordinates (lon or lat)
        section_depth: 2D array (nk, n_horizontal) of depth values
        var_name: Variable name for labeling
        coord_type: 'longitude' or 'latitude'
        colormap: Matplotlib colormap name
        vmin: Minimum value for color scale (None = auto)
        vmax: Maximum value for color scale (None = auto)
        p_size: Point size to plot
        title: Plot title (None = auto-generate)
        fig: Existing figure (None = create new)
        ax: Existing axes (None = create new)
        model_type: 'MOHID Water' or 'MOHID Land' 
        vertical_exaggeration: Vertical scale multiplier (default=1.0)
        
    Returns:
        Tuple of (figure, axes)
    """
    # Create figure if needed
    if fig is None or ax is None:
        fig, ax = plt.subplots(figsize=(5, 3))
    
    # Mask NoData
    section_data_masked = np.ma.masked_invalid(section_data)
        
    # Auto color limits
    if vmin is None:
        vmin = float(np.nanmin(section_data_masked))
    if vmax is None:
        vmax = float(np.nanmax(section_data_masked))
    if p_size is None:
        p_size = 10

    # Validate that vmin < vmax
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        logger.warning(f"Invalid color limits: vmin={vmin}, vmax={vmax}, using defaults")
        vmin, vmax = 0.0, 1.0
    
    # Get dimensions
    nk, n_horiz = section_data.shape
    
    # Apply vertical exaggeration to depths
    depth_mesh = section_depth * vertical_exaggeration
    # Create coordinate mesh - repeat coordinates for each layer
    coord_mesh = np.tile(section_coord, (nk, 1))
        
    # Plot using scatter for layer centers (optional - can remove)
    try:
        im = ax.scatter(
            coord_mesh, depth_mesh, 
            c=section_data_masked,
            cmap=colormap,
            vmin=vmin,
            vmax=vmax,
            s=p_size,
            marker='s',
            zorder=3
        )
        
    except Exception as e:
        logger.error(f"Error in scatter plot: {e}")
        # Fallback to contourf with fewer levels
        try:
            levels = np.linspace(vmin, vmax, 15)
            im = ax.contourf(
                coord_mesh, depth_mesh, section_data_masked,
                levels=levels,
                cmap=colormap,
                extend='both'
            )
        except Exception as e2:
            logger.error(f"Error in contourf fallback: {e2}")
            # Last resort: simple imshow
            extent = [section_coord[0], section_coord[-1], 
                     depth_mesh.min(), depth_mesh.max()]
            im = ax.imshow(
                section_data_masked,
                aspect='auto',
                cmap=colormap,
                vmin=vmin,
                vmax=vmax,
                extent=extent,
                origin='upper'
            )
    
    # === PLOT LAYER INTERFACES AS LINES ===
    # Plot horizontal lines for each layer interface (excluding surface, including bottom)
    for k in range(0, nk):  # Start from 0 (bottom) to nk (insted of nk+1) skip surface
        if k == 0:
            # Bottom interface (use last layer depth + estimated thickness)
            # Approximate by extrapolating from previous layers
            interface_depth = depth_mesh[0, :] + (depth_mesh[0, :] - depth_mesh[1, :])
        else:
            # Interface between layers: average of two adjacent layer centers
            interface_depth = (depth_mesh[k-1, :] + depth_mesh[k, :]) / 2.0
        
        # Plot the interface line
        ax.plot(
            section_coord, interface_depth,
            'k-', linewidth=0.8, alpha=0.5, zorder=2
        )
    
    # Colorbar
    cbar = fig.colorbar(im, ax=ax, orientation='vertical', pad=0.02)
    cbar.set_label(var_name.title(), fontsize=11)
    
    # Labels
    coord_label = 'Longitude (°E)' if coord_type == 'longitude' else 'Latitude (°N)'
    ax.set_xlabel(coord_label, fontsize=11)
    
    depth_label = 'Depth (m)'
    if vertical_exaggeration != 1.0:
        depth_label += f' [VE={vertical_exaggeration:.1f}x]'
    ax.set_ylabel(depth_label, fontsize=11)
    
    # Title
    if title is None:
        section_type = 'Longitudinal' if coord_type == 'longitude' else 'Latitudinal'
        title = f'{section_type} Vertical Section: {var_name.title()}'
        if vertical_exaggeration != 1.0:
            title += f' (VE={vertical_exaggeration:.1f}x)'
    ax.set_title(title, fontsize=13, fontweight='bold')
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    
    # Invert y-axis so surface is at top (already negative, so this works)
    if ax.get_ylim()[0] > ax.get_ylim()[1]:
        ax.invert_yaxis()
    
    fig.tight_layout()
    
    return fig, ax

def plot_section_with_bathymetry(
    section_data: npt.NDArray,
    section_coord: npt.NDArray,
    section_depth: npt.NDArray,
    bathymetry: npt.NDArray,
    var_name: str,
    coord_type: str,
    colormap: str = 'viridis',
    vmin: float = None,
    vmax: float = None,
    p_size: int = None,
    title: str = None,
    fig: plt.Figure = None,
    ax: plt.Axes = None,
    model_type: str = 'MOHID Water',
    vertical_exaggeration: float = 1.0,
    
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot vertical section with bottom bathymetry highlighted.
    
    Args:
        section_data: 2D array (nk, n_horizontal) of data values
        section_coord: 1D array of horizontal coordinates
        section_depth: 2D array (nk, n_horizontal) of depth values
        bathymetry: 1D array (n_horizontal,) of bottom depth
        var_name: Variable name
        coord_type: 'longitude' or 'latitude'
        colormap: Colormap name
        vmin: Min color value
        vmax: Max color value
        p_size: Point size to plot
        title: Plot title
        model_type: 'MOHID Water' or 'MOHID Land' 
        vertical_exaggeration: Vertical scale multiplier
        
    Returns:
        Tuple of (figure, axes)
    """
    fig, ax = plot_vertical_section(
    section_data, section_coord, section_depth,
    var_name, coord_type, colormap, vmin, vmax, p_size, title,
    fig=fig, ax=ax,
    vertical_exaggeration=vertical_exaggeration
    )
    
    # Apply vertical exaggeration to bathymetry
    if model_type == 'MOHID Water':
      bathy_plot = -bathymetry * vertical_exaggeration
    else:  
      bathy_plot = bathymetry * vertical_exaggeration
    
    #change all places with 99 por 1
    bathy_plot[bathy_plot == 99] = 1
    
    # Overlay bathymetry line
    try:
        ax.plot(
            section_coord, bathy_plot,
            'k-', linewidth=1.5, label='Bottom', zorder=10
        )
        ax.fill_between(
            section_coord, bathy_plot, ax.get_ylim()[0],
            color='saddlebrown', alpha=0.3, zorder=5
        )
        ax.legend(loc='upper right', fontsize=10)
    except Exception as e:
        logger.error(f"Error plotting bathymetry: {e}")
        logger.error(f"  section_coord shape: {section_coord.shape}")
        logger.error(f"  bathy_plot shape: {bathy_plot.shape}")
    
    return fig, ax


# ===================== INTERACTIVE SECTION SELECTOR =====================

def plot_section_location_on_map(
    lat_grid: npt.NDArray,
    lon_grid: npt.NDArray,
    section_type: str,
    section_value: float,
    fig: plt.Figure = None,
    ax: plt.Axes = None
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot map showing where the vertical section is located.
    
    Args:
        lat_grid: 2D latitude grid
        lon_grid: 2D longitude grid
        section_type: 'longitude' or 'latitude'
        section_value: Value of the section coordinate
        fig: Existing figure (None = create new)
        ax: Existing axes (None = create new)
        
    Returns:
        Tuple of (figure, axes)
    """
    if fig is None or ax is None:
        fig, ax = plt.subplots(figsize=(5, 3))
    
    # Plot domain
    ax.plot(lon_grid.flatten(), lat_grid.flatten(), 'k.', markersize=0.5, alpha=0.3)
        
    # Plot section line
    if section_type == 'longitude':
        # Latitudinal line at given longitude
       lon_range = [lon_grid.min(), lon_grid.max()]
       ax.plot(lon_range, [section_value, section_value], 'r-', linewidth=3, label='Section')
    else:
        # Longitudinal line at given latitude
       lat_range = [lat_grid.min(), lat_grid.max()]
       ax.plot([section_value, section_value], lat_range, 'r-', linewidth=3, label='Section')
    
    ax.set_xlabel('Longitude (Â°E)', fontsize=11)
    ax.set_ylabel('Latitude (Â°N)', fontsize=11)
    ax.set_title('Section Location', fontsize=12, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    
    fig.tight_layout()
    
    return fig, ax


# ===================== STATISTICS =====================

def compute_section_statistics(section_data: npt.NDArray) -> Dict[str, float]:
    """
    Compute statistics for a vertical section.
    
    Args:
        section_data: 2D array of section values
        
    Returns:
        Dictionary with statistics
    """
    valid_data = section_data[np.isfinite(section_data)]
    
    if len(valid_data) == 0:
        return {
            'min': np.nan,
            'max': np.nan,
            'mean': np.nan,
            'std': np.nan,
            'median': np.nan,
            'valid_points': 0,
            'total_points': section_data.size
        }
    
    return {
        'min': float(np.min(valid_data)),
        'max': float(np.max(valid_data)),
        'mean': float(np.mean(valid_data)),
        'std': float(np.std(valid_data)),
        'median': float(np.median(valid_data)),
        'valid_points': len(valid_data),
        'total_points': section_data.size
    }


# ===================== EXPORT FUNCTIONS =====================

def export_section_to_csv(
    section_data: npt.NDArray,
    section_coord: npt.NDArray,
    section_depth: npt.NDArray,
    output_path: str,
    coord_type: str = 'longitude'
) -> None:
    """
    Export vertical section data to CSV file.
    
    CSV format:
    coordinate, depth, value
    
    Args:
        section_data: 2D array (nk, n_horizontal)
        section_coord: 1D array of coordinates
        section_depth: 2D array (nk, n_horizontal) of depths
        output_path: Output CSV file path
        coord_type: 'longitude' or 'latitude'
    """
    nk, n_horiz = section_data.shape
    
    rows = []
    for k in range(nk):
        for i in range(n_horiz):
            coord = section_coord[i]
            depth = section_depth[k, i]
            value = section_data[k, i]
            
            if np.isfinite(value):
                rows.append([coord, depth, value])
    
    # Write CSV
    header = f'{coord_type},depth_m,value'
    np.savetxt(output_path, rows, delimiter=',', header=header, comments='', fmt='%f')
    
    logger.info(f"Section exported to CSV: {output_path}")
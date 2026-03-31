"""
MOHID HDF5 Viewer - Import Functions
Functions for Importing a text file and returning data from various formats (JPG, animations, GeoTIFF, CSV)
"""
import matplotlib.pyplot as plt
import argparse
from .hdf5_utils import (load_variable_data)
from .exporters import (export_as_jpgs, export_as_geotiffs, export_as_csvs, export_animation)
from .vertical_section import parse_geometry_file, build_3d_depth_grid_water, build_3d_depth_grid_land, \
    load_3d_variable_timestep, extract_longitudinal_section, extract_latitudinal_section, plot_section_with_bathymetry, \
    plot_vertical_section, export_section_to_csv

import numpy as np


def input_text_file(text_path: str) -> dict:
    """
    Receives the path to a text document and turns the contents into a dictionary
    Args:
        text_path:path to a text document with all the data we need to export
    Returns:
        A dictionary with the contents of the text file
    """
    info = {}
    with open(text_path, 'r', encoding="utf-8") as information:
        content = information.read().strip()
        list_data = content.split(";")
        for item in list_data:
            item = item.strip("\n")
            key, value = item.split("=", 1)
            if key == "nodata_values":
                value = [float(x) for x in value[1:-1].split(",")]
                info[key] = value
                continue
            if value == "True":
                value = True
                info[key] = value
                continue
            if value == "False":
                value = False
                info[key] = value
                continue
            try:
                if "." not in value:
                    value = int(value)
                    info[key] = value
                    continue
            except ValueError:
                pass
            try:
                value = float(value)
                info[key] = value
                continue
            except ValueError:
                pass
            info[key] = value
    return info


def export_vertical_section(info: dict):
    """
    Receives a dictionary with all the data we need to export into a vertical section
    Args:
        info: dictionary with all the data we need to export
    """
    geometry_info = parse_geometry_file(info['geometry_path'])
    try:
        import h5py
        with h5py.File(info['pathHDF5'], 'r') as h5:
            lat_grid = np.asarray(h5["Grid/Latitude"])
            lon_grid = np.asarray(h5["Grid/Longitude"])
            # Try to load bathymetry
            if "Grid/Bathymetry" in h5:
                bathymetry = np.asarray(h5["Grid/Bathymetry"])
            elif "Grid/WaterColumn" in h5:
                bathymetry = -np.asarray(h5["Grid/WaterColumn"])
            else:
                bathymetry = np.full(lat_grid.shape, -50.0)
        if info['model_type'] == 'MOHID Water':
            depth_grid_3d = build_3d_depth_grid_water(geometry_info, bathymetry, vertical_exaggeration=1.0)
        else:
            depth_grid_3d = build_3d_depth_grid_land(geometry_info, bathymetry, info['vertical_exaggeration'])
    except Exception as e:
        return

    data_3d = load_3d_variable_timestep(info['pathHDF5'], info['name'], info['timestep'])

    nk, ny_data, nx_data = data_3d.shape

    # Create local copies for trimming
    lat_grid_local = lat_grid.copy()
    lon_grid_local = lon_grid.copy()
    depth_grid_local = depth_grid_3d.copy()
    bathymetry_local = bathymetry.copy()

    # Trim grids to match data if needed
    if lat_grid_local.shape != (ny_data, nx_data):
        lat_grid_local = lat_grid_local[:ny_data, :nx_data]

    if lon_grid_local.shape != (ny_data, nx_data):
        lon_grid_local = lon_grid_local[:ny_data, :nx_data]

    if depth_grid_local.shape != (nk, ny_data, nx_data):
        depth_grid_local = depth_grid_local[:nk, :ny_data, :nx_data]

    if bathymetry_local.shape != (ny_data, nx_data):
        bathymetry_local = bathymetry_local[:ny_data, :nx_data]

    # extract section
    if info['section_type'] == 'longitude':
        section_data, section_coord, section_depth = extract_longitudinal_section(data_3d, lat_grid_local,
                                                                                  lon_grid_local, depth_grid_local,
                                                                                  info['section_value'])
    else:
        section_data, section_coord, section_depth = extract_latitudinal_section(data_3d, lat_grid_local,
                                                                                 lon_grid_local, depth_grid_local,
                                                                                 info['section_value'])

    if info['type'] == 'vertical section csv':
        export_section_to_csv(
            section_data, section_coord,
            section_depth, info['output_dir'], info['section_type']
        )
    if info['type'] == 'vertical section image':
        # Get canvas dimensions (atualizados para os novos tamanhos)
        canvas_width = 700  # Aumentado de 700
        canvas_height = 300  # Aumentado de 300
        fig_width = canvas_width / 100.0  # 7 inches
        fig_height = canvas_height / 100.0  # 3 inches

        # Plot section with fixed size
        if info['show_bathy']:
            # Extract bathymetry for this section
            if info['section_type'] == 'longitude':
                lat_per_row = lat_grid[0, :]  # Shape: (,ny)
                lat_diff = np.abs(lat_per_row - info['section_value'])  # Array 1D (ny,)
                j_idx = np.argmin(lat_diff)
                bathy_section = bathymetry_local[:, j_idx]
            else:
                lon_per_column = lon_grid[:, 0]  # Shape: (,nx)
                lon_diff = np.abs(lon_per_column - info['section_value'])  # Array 1D (nx,)
                i_idx = np.argmin(lon_diff)
                bathy_section = bathymetry_local[i_idx, :]

            # Ensure bathymetry matches section_coord length
            if len(bathy_section) != len(section_coord):
                bathy_section = bathy_section[:len(section_coord)]

            # Create figure with exact size
            fig = plt.figure(figsize=(fig_width, fig_height), dpi=100)
            ax = fig.add_subplot(111)

            fig, ax = plot_section_with_bathymetry(
                section_data, section_coord, section_depth, bathy_section,
                info['name'], info['section_type'], info['colormap'], info['vmin'], info['vmax'], info['p_size'],
                model_type=info['model_type'], vertical_exaggeration=info['vertical_exaggeration'],
                fig=fig, ax=ax
            )

        else:
            # Create figure with exact size
            fig = plt.figure(figsize=(fig_width, fig_height), dpi=100)
            ax = fig.add_subplot(111)

            fig, ax = plot_vertical_section(
                section_data, section_coord, section_depth,
                info['name'], info['section_type'], info['colormap'], info['vmin'], info['vmax'], info['p_size'],
                model_type=info['model_type'], vertical_exaggeration=info['vertical_exaggeration'],
                fig=fig, ax=ax
            )
        fig.tight_layout(pad=0.5)
        fig.savefig(info['output_dir'])


def direct_export(info: dict):
    """
    Receives a dictionary and calls the export function
    Args:
    info: dictionary with the contents of the text file
    """
    data, stamps, lat_full, lon_full = load_variable_data(info['pathHDF5'], info['path'], info['name'])
    if info['type'] == 'csv':
        export_as_csvs(data, stamps, lat_full, lon_full, info['output_dir'], info, on_tick=None)
    elif info['type'] == 'geotiff':
        export_as_geotiffs(data, stamps, lat_full, lon_full, info['output_dir'], info, on_tick=None)
    elif info['type'] == 'jpg':
        export_as_jpgs(data, stamps, lat_full, lon_full, info['output_dir'], info, info['vmax'], info['vmin'],
                       on_tick=None, per_frame_colors=info['per_frame_colors'], debug_stats=info['debug_stats'])
    elif info['type'] == 'animation':
        export_animation(data, stamps, lat_full, lon_full, info['output_dir'], info, info['vmax'], info['vmin'],
                         on_tick=None, fps=info['fps'])
    elif info['type'] == 'vertical section csv' or info['type'] == 'vertical section image':
        export_vertical_section(info)


def importHDF5() -> None:
    parser =argparse.ArgumentParser(description='Import a text file with parameters to export a graph')
    parser.add_argument('-p', '--format',action='store_true',help='shows the documentation')
    parser.add_argument('path', metavar='PATH', nargs='?', type=str,help='receives the path to the import file')
    args = parser.parse_args()
    if args.format:
        print("To export a file you will need the following parameters inside your text file:\n"
              "pathHDF5 = the HDF5 file we are going to read.\n"
              "path = the HDF5 folder we are going to use.\n"
              "name = the name of the file inside the HDF5 that we are going to use.\n"
              "type = what kind of exportation we are going to use.\n"
              "output_dir = the directory we are going to save the exported file.\n"
              "reduce mode = what layer we are going to use.\n"
              "reduce index = the exact layer we are going to use (reduce mode must be index).\n"
              "nodata_values= what values we are going to ignore.\n"
              "auto_land_treshold=if the value -1e12 is considered nodata.\n\n"

              "to export an image you will also need the following parameters:\n"
              "colormap=the color we are going to use on the graphs.\n"
              "fast_tiles=if all the tiles are draw at once.\n"
              "vmin=the minimum value portrayed in the colormap.\n"
              "vmax=the maximum value portrayed in the colormap.\n"
              "per_frame_color:if the values portrayed in the colormap are calculated in each frame.\n"
              "global_scale:if the values in the colormap are calculated only once and used in every frame.\n"
              "basemap=what map we are going to use.\n"
              "use_coastline=if the coastline is going to show up.\n"
              "original=if we are inverting the color of our colormap.\n"
              "tile_zoom=the zoom of our basemap.\n"
              "jpg_dpi=the jpgs dpi.\n"
              "jpg_quality=the quality of the jpgs\n\n"

              "to export an animation you will need the following parameters:\n"
              "colormap=the color we are going to use on the graphs.\n"
              "vmin=the minimum value portrayed in the colormap.\n"
              "vmax=the maximum value portrayed in the colormap.\n"
              "per_frame_color:if the values portrayed in the colormap are calculated in each frame.\n"
              "fps=how many frames per second.\n"
              "basemap=what map we are going to use.\n"
              "use_coastline=if the coastline is going to show up.\n"
              "original=if we are inverting the color of our colormap.\n"
              "tile_zoom=the zoom of our basemap.\n\n"

              "to export a geotiff file you need the following parameter:\n"
              "tiff_nodata=the value we are going to ignore.\n\n"

              "to export a csv file portraying the vertical section you will need the following parameters:\n"
              "geometry_path=the file that contains the geometry info we are going to use.\n"
              "model_type=what kind of model we are going to use(MOHID Water ou MOHID Land).\n"
              "vertical_exaggeration=The multiplier of the vertical distance\n"
              "timestep=what time frame we are going to use.\n"
              "section_type=if we are exporting latitude or the longitude.\n"
              "section_value=the value of the longitude/latitude.\n\n"

              "to export an image portraying the vertical section you will need the following parameters:\n"
              "geometry_path=the file that contains the geometry info we are going to use.\n"
              "model_type=what kind of model we are going to use(MOHID Water ou MOHID Land).\n"
              "vertical_exaggeration=The multiplier of the vertical distance\n"
              "timestep=what time frame we are going to use.\n"
              "section_type=if we are exporting latitude or the longitude.\n"
              "section_value=the value of the longitude/latitude.\n"
              "show_bathy=if we are going to use the bathymetry.\n"
              "p_size=the size of each dot in our graph.\n"
              "colormap=the color we are going to use on the graphs.\n"
              "vmin=the minimum value portrayed in the colormap.\n"
              "vmax=the maximum value portrayed in the colormap.\n")
    else:
        try:
            info = input_text_file(args.path)
            direct_export(info)
        except:
                print("Error while reading the path")



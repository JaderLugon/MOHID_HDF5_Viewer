import argparse

from .importer import importHDF5
from .MOHID_HDF5_Viewer import startInterface

def main():
    parser = argparse.ArgumentParser(description='Start the MOHID HDF5 Viewer')
    parser.add_argument("-i", "--input",type=str,help="starts the import process")
    parser.add_argument("-v", "--viewer",action="store_true", help="starts the interface")
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
    elif args.viewer:
        startInterface()
    else:
        importHDF5(args.input)

        return 0

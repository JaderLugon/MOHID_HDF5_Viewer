from setuptools import setup, find_packages
setup(name='MOHID_HDF5_Viewer',version='0.4',packages=find_packages(),requires=['hp5','numpy','matplotlib','cartopy','pillow','ffmpeg','rasterio','FreeSimpleGUI'],
      entry_points={'console_scripts':["MOHID_HDF5 = MOHID_HDF5_Viewer:main"]})

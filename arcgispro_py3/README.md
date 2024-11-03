# **OVERVIEW**

Since ESRI is phasing out support for ArcGIS Desktop and most ArcGIS shops are using primarily ArcGIS Pro these days, we've adapted the basic functionality of the original code to be usable with an ArcGIS Pro python environment.

### NEW

A few notable changes and/or omissions versus the original code are that this ArcGIS Pro version...
 - runs without needing an advanced license
 - focuses on a single entry type (two bearings)
 - recommends supplying input data in either UTM or State Plane
 - separates the core code `wedge_maker.py` from its driver script
    - core code contains all essentials needed to create wedge buffers
    - driver illustrates how to run with a shapefile with these fields:
        - a1 (numeric): first wedge bearing, in degrees
        - a2 (numeric): second wedge bearing, in degrees
        - r1 (numeric): outer wedge buffer, in meters
        - r2 (numeric): inner wedge buffer, in meters - **OPTIONAL**
 - does not (yet) come with an ArcGIS Toolbox GUI...

### USAGE

On Windows, for a normal ArcGIS Pro installation, python.exe will be located at:

 - `C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe`

To run the example `wedge_maker_driver.py` using this default env, simply clone this repo to whatever location you prefer (e.g., let's say it's `C:\GitHub`), then, in PowerShell, run:

 - `& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" C:\GitHub\wedge-maker-4-gis\arcgispro_py3\wedge_maker_driver.py`

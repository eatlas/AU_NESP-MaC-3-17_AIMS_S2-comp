# NESP MaC Project 3.17 - North Australia Sentinel 2 Satellite Composite Imagery

Marc Hammerton - Australian Institute of Marine Science - 06 February 2024

This repository contains the code to create clear water satellite imagery for the northern Australian seascape. The
scripts are written in Python and use the Google Earth Engine library
(https://developers.google.com/earth-engine/tutorials/community/intro-to-python-api).

## Changelog

This code will be progressively modified to improve the quality of the dataset and to provide different types of
datasets. These additions will be noted in this change log.  
2024-03-07 - Initial release draft composites using 15th percentile (Git tag: "composites_v1")

## Datasets

- ***15th percentile true colour - draft version 1 2024:***  
    A first draft version of clear-water composite images for the northern Australian seascape using the 15th 
    percentile from the filtered image collection and visualising with true-colour settings.  
    *Metadata:* https://eatlas.org.au/data/uuid/c38d2227-25c0-4d1e-adbc-bddb4aac1929  
    *Data download:* https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_S2-comp_p15-trueColour
    *Git tag:* "composites_v1"

## Prerequisites

To run this code a [Google Earth Engine account](https://earthengine.google.com/) and a
[Cloud Project](https://developers.google.com/earth-engine/cloud/projects) is required.

## Setup

### Install dependencies

This repository contains a `requirements.txt` file which can be used to install the necessary packages (e.g. either
using `pip` or `anaconda`).

The following code details how to set up the Python environment using `anaconda`:

```shell
# Create anaconda environment
conda create --name AU_NESP-MaC-3-17_AIMS_S2-comp

# Activate anaconda environment
conda activate AU_NESP-MaC-3-17_AIMS_S2-comp

# Add "conda-forge" channel to anaconda
conda config --add channels conda-forge

# Install requirements
conda install --file requirements.txt
```

### Authenticate with Google Earth Engine (GEE)

To use the GEE library you first need to authenticate yourself with GEE. Make sure the previously created conda
environment is activated.

```shell
earthengine authenticate
```

## Run the scripts

This repository contains four python scripts (located in the `./src` directory):

### `create-composite.py`

This script will create a composite image for each Sentinel 2 tile ID provided and export it to the . The tile IDs are 
read from a CSV file with the name and path of the file passed as argument:

```shell
python create-composite.py --data_file "path/to/tile-ids.csv"
```

Currently, the following three CSV files are available:

- `./data/tile-ids - all tiles.csv` - All tile IDs for the whole study region
- `./data/tile-ids - GOC.csv` - Tile IDs for the Gulf of Carpentaria region
- `./data/tile-ids - single.csv` - File used to process a single tile ID

The script has variables at the top of the file to manage settings:

| Variable                          | Description                                                                                                                                                             |
|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| THREADS                           | Number of threads to run the composite creation in parallel.                                                                                                            |
| MAX_CLOUD_COVER                   | ImageCollection filter: the maximum percentage of cloud cover per image.                                                                                                |
| START_DATE                        | ImageCollection filter: The beginning of the period for images to be included.                                                                                          |
| END_DATE                          | ImageCollection filter: The ending of the period for images to be included.                                                                                             |
| VIS_OPTION_NAME                   | Visualisation option for contrast enhancements. At the moment only 'TrueColour' is supported.                                                                           |
| SCALE                             | The image scale in meters. Sentinel 2 images have a maximum resolution of 10 meters.                                                                                    |
| MAX_NUMBER_OF_IMAGES_IN_COMPOSITE | The maximum number of images included in the image collection for creating the composite. The more images are included, the more processing per image needs to be done. |

### `create-preview-images.py`

This script will create JPEG preview images for GeoTIFFs in a directory. The source directory containing the GeoTIFFs
and the destination directory for the preview images are passed as arguments:

```shell
python create-preview-images.py --src_path "path/to/GeoTIFFs" --dest_path "path/to/previews"
```

> Note: The script requires GDAL to be installed.

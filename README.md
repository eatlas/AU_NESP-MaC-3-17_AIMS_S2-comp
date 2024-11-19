# NESP MaC Project 3.17 - North Australia Sentinel 2 Satellite Composite Imagery

Marc Hammerton - Australian Institute of Marine Science - 19 Nov 2024

This repository contains the code to create various datasets from satellite imagery for the northern Australian 
seascape. The scripts are written in Python and use the Google Earth Engine library
(https://developers.google.com/earth-engine/tutorials/community/intro-to-python-api).

## Changelog

This code will be progressively modified to improve the quality of the dataset and to provide different types of
datasets. These additions will be noted in this change log.  
- 2024-11-19 - Updated version of Australian coastline (V1-1) with manual editing of rivers and addition of Christmas Island, Cocos Island, Norfolk Island and Lord Howe Island. Included `split-land-shapefile.py` in this repo. (Git tag: "coastline_v1-1")
- 2024-08-29 - Publish Australian coastline (v1) (Git tag: "coastline_v1")
- 2024-07-22 - Publish version 2 composites using a noise prediction algorithm to only include low noise images in 
composite (Git tag: "composites_v2")
- 2024-05-16 - Add capability to create low-tide composites and near infrared false colour style (Git tag: 
"low_tide_composites_v1")  
- 2024-03-07 - Initial release draft composites using 15th percentile (Git tag: "composites_v1")

## Datasets

- ***Australian coastline - version 1-1 2024:***  
  A coastline of Australia generated from NDWI calculations on above mean sea level satellite image composites (10 m
  resolution Sentinel 2 imagery from 2022 – 2024).  
  *Dataset ID:* AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024
  *Metadata:* https://eatlas.org.au/data/uuid/c5438e91-20bf-4253-a006-9e9600981c5f  
  *Data download:* https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Australian-Coastline  
  *Git tag:* "coastline_v1-1"

- ***15th percentile true colour - version 2 2024:***  
  A final version of clear-water composite images for the northern Australian seascape using the 15th
  percentile from the filtered image collection and visualising with true-colour settings.  
  *Metadata:* https://eatlas.org.au/data/uuid/c38d2227-25c0-4d1e-adbc-bddb4aac1929  
  *Data download:* https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_S2-comp_p15-trueColour  
  *Git tag:* "composites_v2"

- ***low-tide 30th percentile true colour and near infrared false colour - version 1 2024:***  
  A variation to the previous composite images by focusing on low-tide input images for the northern Australian seascape 
  using the 30th percentile from the filtered image collection and visualising with true-colour and 
  near-infrared-false-colour settings.  
  *Metadata:* https://eatlas.org.au/data/uuid/ec1db691-3729-4635-a01c-378263e539b6  
  *Data download:* https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_S2-comp_low-tide_p30  
  *Git tag:* "low_tide_composites_v1"

- ***15th percentile true colour - draft version 1 2024:***  
  A first draft version of clear-water composite images for the northern Australian seascape using the 15th
  percentile from the filtered image collection and visualising with true-colour settings.  
  Note: As of July 2024 deprecated, see version 2. 
  *Metadata:* https://eatlas.org.au/data/uuid/c38d2227-25c0-4d1e-adbc-bddb4aac1929
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

### Download the tide model data
To generate low-tide composites, the tide model data needs to be downloaded and added to the project. For the tide
prediction we use the empirical ocean tide model EOT20 (Hart-Davis et al., 2021) which is freely accessible at 
https://doi.org/10.17882/79489.

1. Navigate to the website https://doi.org/10.17882/79489 and click the "Download" button towards the bottom of the page.
2. Extract the downloaded zip file
3. Copy the folder "ocean_tides" to `./src/data/EOT20`


## Run the scripts

This repository contains four python scripts (located in the `./src` directory):

### `create-composite.py` and `create-low-tide-composite.py` and `create-NDWI-composite.py`

`create-composite.py`: This script will create a composite image for each Sentinel 2 tile ID provided.  
`create-low-tide-composite.py`: This script will create a low-tide composite for each Sentinel 2 tile ID provided.
`create-NDWI-composite.py`: This script will create a gray scale NDWI composite from above mean sea level images for 
  each Sentinel 2 tile ID provided.

The scripts export the final composite to the cloud storage.The tile IDs are read from a CSV file with the name and 
path of the file passed as argument:

```shell
python create-composite.py --data_file "path/to/tile-ids.csv"
python create-low-tide-composite.py --data_file "path/to/tile-ids.csv"
python create-NDWI-composite.py --data_file "path/to/tile-ids.csv"
```

Currently, the following three CSV files are available:

- `./data/tile-ids - all coastal tiles.csv` - All coastal tile IDs for the whole study region
- `./data/tile-ids - all tiles.csv` - All tile IDs for the whole study region
- `./data/tile-ids - Darwin to Broome coastal area.csv` - File used for the low-tide composites focusing on the coastal
  area between Darwin and Broome
- `./data/tile-ids - GBR.csv` - File used for creating imagery in the GBR
- `./data/tile-ids - GBR coastal.csv` - File used for creating imagery along the coastline of the GBR
- `./data/tile-ids - GOC.csv` - Tile IDs for the Gulf of Carpentaria region
- `./data/tile-ids - rest of Australia.csv` - File used to create the coastline of Australia, containing the remaining 
  coastal tile IDs not included in the GBR and study area
- `./data/tile-ids - single.csv` - File used to process a single tile ID

The scripts have variables at the top of the file to manage settings:

| Variable                          | Description                                                                                                                                                                                                                            |
|-----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| THREADS                           | Number of threads to run the composite creation in parallel.                                                                                                                                                                           |
| MAX_CLOUD_COVER                   | ImageCollection filter: the maximum percentage of cloud cover per image.                                                                                                                                                               |
| MIN_NUMBER_OF_IMAGES_IN_COMPOSITE | `create-composite.py` only: The minimum number of images included in the image collection for creating the composite. This number of images is used to calculate the base noise level.                                                 |
| MAX_NUMBER_OF_IMAGES_IN_COMPOSITE | `create-low-tide-composite.py` and `create-NDWI-composite.py`: The maximum number of images included in the image collection for creating the composite. The more images are included, the more processing per image needs to be done. |
| PERCENTILE                        | The percentile to reduce the collection to the composite image.                                                                                                                                                                        |
| START_DATE                        | ImageCollection filter: The beginning of the period for images to be included.                                                                                                                                                         |
| END_DATE                          | ImageCollection filter: The ending of the period for images to be included.                                                                                                                                                            |
| VIS_OPTION_NAME                   | Visualisation option for contrast enhancements. At the moment only 'TrueColour' is supported.                                                                                                                                          |
| SCALE                             | The image scale in meters. Sentinel 2 images have a maximum resolution of 10 meters.                                                                                                                                                   |
| CORRECT_SUN_GLINT                 | Flag for turning sun glint correction off or on                                                                                                                                                                                        |
| BUCKET_NAME                       | The bucket name in Google Cloud Storage.                                                                                                                                                                                               |
| BUCKET_PATH                       | The path in the bucket in Google Cloud Storage.                                                                                                                                                                                        |

>Note: `create-NDWI-composite.py`
For GBR: modify sentinel2-water-centroids.csv: -11.353,142.889,54LXN  
`54LXN` has a coast on both sides of the tile. The water centroid in `sentinel2-water-centroids.csv` is set on the western
coast as this is included in the study area. If we want to extend the area to include the GBR, we need to modify the
water centroid for the eastern coast.

### `create-preview-images.py`

This script will create JPEG preview images for GeoTIFFs in a directory. The source directory containing the GeoTIFFs
and the destination directory for the preview images are passed as arguments:

```shell
python create-preview-images.py --src_path "path/to/GeoTIFFs" --dest_path "path/to/previews"
```

> Note: The script requires GDAL to be installed.

### `export-composite-images.py`

This script will export the images used to create a composite for each Sentinel 2 tile ID provided. This is a helper
script to visualise which images are used in a composite. The tile IDs are read from a CSV file with the name and
path of the file passed as argument:

```shell
python export-composite-images.py --data_file "path/to/tile-ids.csv"
```

Currently, the following three CSV files are available:

- `./data/tile-ids - all tiles.csv` - All tile IDs for the whole study region
- `./data/tile-ids - GOC.csv` - Tile IDs for the Gulf of Carpentaria region
- `./data/tile-ids - single.csv` - File used to process a single tile ID

The script has variables at the top of the file to manage settings:

| Variable                          | Description                                                                                   |
|-----------------------------------|-----------------------------------------------------------------------------------------------|
| MAX_CLOUD_COVER                   | ImageCollection filter: the maximum percentage of cloud cover per image.                      |
| START_DATE                        | ImageCollection filter: The beginning of the period for images to be included.                |
| END_DATE                          | ImageCollection filter: The ending of the period for images to be included.                   |
| VIS_OPTION_NAME                   | Visualisation option for contrast enhancements. At the moment only 'TrueColour' is supported. |
| SCALE                             | The image scale in meters. Sentinel 2 images have a maximum resolution of 10 meters.          |
| MAX_NUMBER_OF_IMAGES_IN_COMPOSITE | The maximum number of images in a image collection for creating the composite.                |




## AU_AIMS_Coastline_v1

In this dataset we created a coastline using a simplified approach based on https://doi.org/10.1016/j.rse.2021.112734 .

Process:
1. Create above mean sea level composites.
2. Create gray scale images from NDWI calculations.
3. Upscale images by factor 2
4. Vectorise NDWI images with NDWI threshold 0.15 (147.05 in the rescaled image with values between 1 and 255). This step also includes 'filling holes' in the land polygons to remove salt flats etc.
5. Merge and dissolve all vector layers in QGIS.
6. Clean up false polygons created by sun glint.
7. Perform smoothing (QGIS tool box, Iterations 1, Offset 0.25, Maximum node angle to smooth 180)
8. Perform simplification (QGIS tool box, tolerance 0.00003).
9. Split feature into singleparts (QGIS tool box, Mulitpart to Singleparts)
10. Remove very small features (1 - 1.5 pixel sized features, e.g. single mangrove trees) by calculating the area of each feature (in m2) and removing features smaller than 200m2.

### `vectorise-geotiffs.py`

This script generates polygons for landmasses detected in NDWI GeoTIFFs and saves them as shapefiles.

The script has variables at the top of the file to manage settings:

| Variable      | Description                                                 |
|---------------|-------------------------------------------------------------|
| INPUT_FOLDER  | Path to the folder containing input GeoTIFF files.          |
| OUTPUT_FOLDER | Path to the folder where the processed files will be saved. |
| SCALE_FACTOR  | Factor by which the input NDWI image will be upscaled.      |

### `split-land-shapefile.py`

_Added in version 1-1_

This script takes the Australian Coastline shapefile creates derivative products from it. These include a split of the polygons to a 2 degree grid to improve performance and a simplification of the full dataset.

1. Download the data from: 
https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Australian-Coastline-50K-2024

2. Save it into the `data/Aus-Coastline-50k_2024/' directory.

This script expects the full coastline dataset (with any manual edits) to be available in:
`data/Aus-Coastline-50k_2024/{VERSION}/Full/AU_NESP-MaC-3-17_AIMS_Aus-Coastline-50k_2024_V1-1.shp`

This script will save back the modified derived variants to:
`data/Aus-Coastline-50k_2024/{VERSION}/`

```shell
cd src
python split-land-shapefile.py
```

### Making new manual corrections to the Australian Coastline 50k 2024 dataset
To make improvements to the coastline dataset:
1. Clone this code repository to allow updates to the change log.
2. Download the latest version of the dataset from the metadata record (https://doi.org/10.26274/qfy8-hj59) or NextCloud: https://nextcloud.eatlas.org.au/apps/sharealias/a/AU_NESP-MaC-3-17_AIMS_Australian-Coastline-50K-2024 into the `data/Aus-Coastline-50k_2024` directory.
3. Create a directory for the new version, such as `V1-2/Full`. Copy over and rename (with the new version number) the coastline shapefile into the new folder. We want to ensure that the previous versions are unmodified.
4. Perform corrections to the new version, typically using QGIS.
5. Run the `src/split-land-shapefile.py` script to create the split and simplified versions of the dataset, ensuring that the version number in the script is updated to match the new version.
6. Update the change log in this README.md, update the change log in the metadata record on eAtlas, push the new version to NextCloud. Commit the changes to this repository in GitHub.
7. Copy the updates to the eAtlas enduring repository. Setup the new version in the eAtlas mapping system.
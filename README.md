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

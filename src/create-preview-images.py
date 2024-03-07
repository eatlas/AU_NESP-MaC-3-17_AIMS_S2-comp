# Copyright 2023 Marc Hammerton - Australian Institute of Marine Science
# Based on https://github.com/eatlas/CS_AIMS_Coral-Sea-Features_Img/blob/master/src/02-local/01-convert.py
#
# MIT License https://mit-license.org/
# This script creates preview images from GeoTIFFs exported from GEE.
#
# To run this Python script you will need GDAL installed and available in the same environment as this script.

import argparse
import os
import glob
from osgeo import gdal


# Create argument parser
parser = argparse.ArgumentParser(description='Create preview images for GeoTIFFs')

# Add arguments
parser.add_argument('--src_path', type=str, help='The path to the source GeoTIFFs. Example: '
                                                 '"/data/geoTiffs"')
parser.add_argument('--dest_path', type=str, help='The path to the destination folder for the previews. '
                                                  'Example: "/data/previews"')

# Parse arguments
args = parser.parse_args()

# Access arguments
print("Create preview images")
print("---------------------")
print("GeoTiffs folder:", args.src_path)
print("Preview image folder:", args.dest_path)
print("")

if not os.path.exists(args.dest_path):
    print("Creating output directory: " + args.dest_path)
    os.mkdir(args.dest_path)

# JPEG compressed preview image intended for quickly browsing through the imagery in an image gallery.
# --config GDAL_PAM_ENABLED NO    Disable the creation of the aux.xml files so the preview folders aren't cluttered.
# -outsize 50% 50%                Reduce the size of the imagery to 50% (about 5500 pixels) for smaller file sizes
# -r average                      Use averaging in the resizing to remove aliasing.
# -co QUALITY=80                  Improve the image quality slightly above the default of 75.
# -co EXIF_THUMBNAIL=YES          Embed a 128x128 pixel thumbnail. Might make browsing the previews faster?
GDAL_PREVIEW_CMD = ('gdal_translate -of JPEG -r average -outsize 50% 50% --config GDAL_PAM_ENABLED NO -co QUALITY=80 '
                    '-co EXIF_THUMBNAIL=YES')

# Find all GeoTIFF files in source directory
src_files = glob.glob(args.src_path + "/*.tif")

file_count = 0
num_files = len(src_files)
print("Processing " + str(num_files) + " files")

# Iterate over all files and create the preview image
for src_file in src_files:
    file_count = file_count + 1
    print("Processing " + str(file_count) + " of " + str(num_files) + " files")

    # Extract the filename from the path to create the destination path
    file_name = os.path.basename(src_file)

    # ------------- Preview images ----------------
    # Generate JPEG preview images.

    # Replace the .tif with .jpg in the filename
    dest_file = os.path.join(args.dest_path, file_name.replace(".tif", ".jpg"))

    # Test if the destination file already exists. If so skip over the conversion.
    if os.path.isfile(dest_file):
        print("Skipping " + file_name + " as output already exists " + dest_file)

    else:
        ds = gdal.Translate(dest_file, src_file,
                            options="-of JPEG -r average -outsize 50% 50% "
                                    "-co QUALITY=80 -co EXIF_THUMBNAIL=YES")

        ds = None  # close and save ds


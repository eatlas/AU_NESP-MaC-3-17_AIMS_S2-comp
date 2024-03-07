# Copyright 2024 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
# This script exports the images which would be used to create a composites for debugging purposes.

import argparse
import os
import sys
import pandas as pd
import ee
import logging
import concurrent.futures
from processors.s2processor import Sentinel2Processor

ee.Initialize()

#########################################################
# Configuration
#########################################################
MAX_CLOUD_COVER = 20
START_DATE = '2018-01-01'
END_DATE = '2022-12-31'
VIS_OPTION_NAME = 'TrueColour'
SCALE = 100
MAX_NUMBER_OF_IMAGES = 10

BUCKET_NAME = "aims-marb-test"
BUCKET_PATH = "/"
#########################################################
# End configuration
#########################################################

# Init processor
processor = Sentinel2Processor(BUCKET_NAME, BUCKET_PATH)


def export(image, index, tile_id):
    """
    Export an image to cloud storage.

    :param {ee.Image} image: The image to export
    :param {int} index: An index identifying the count of images
    :param {string} tile_id: The Sentinel 2 tile ID, e.g. "51KWB"
    :return: {int}
    """
    logging.info("starting to process %s: %s", index, tile_id)

    # Create the name of the image
    name = tile_id + "_" + str(index) + "_" + image.get('system:index').getInfo()

    # Export the image to cloud storage
    processor.export_to_cloud(image, name, tile_id, VIS_OPTION_NAME, SCALE)

    logging.info("finished processing %s: %s", index, tile_id)
    return index


# Create argument parser
parser = argparse.ArgumentParser(description='Export the images which would make a composite image')

# Add arguments
parser.add_argument('--data_file', type=str, help='Name of the data file containing the tile IDs. '
                                                  'Example: "data/tile-ids - single.csv"')

# Parse arguments
args = parser.parse_args()

# Access arguments
print("Export composite images")
print("-----------------------")
print("Using data file:", args.data_file)

# Do not proceed if the data file does not exist
if not os.path.exists(args.data_file):
    print(f"Error: File '{args.data_file}' does not exist.")
    sys.exit(1)

# Set up logging
logging.basicConfig(format="%(asctime)s: %(message)s", level=logging.INFO, datefmt="%H:%M:%S")

# Read tile ID CSV
tile_ids = pd.read_csv(args.data_file)

# Iterate over all tile IDs
for tile_index, tile_id_row in tile_ids.iterrows():
    logging.info("%s starting to process tile ID %s", tile_index, tile_id_row['TileID'])

    # Get the image collection for a tile ID
    image_collection = processor.get_composite_collection(tile_id_row['TileID'], MAX_CLOUD_COVER, MAX_NUMBER_OF_IMAGES,
                                                          START_DATE, END_DATE)
    # Transform image collection to a list
    collection_list = image_collection.toList(MAX_NUMBER_OF_IMAGES)

    # create thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_NUMBER_OF_IMAGES) as executor:
        futures = []

        # create a thread per row
        for index in range(0, MAX_NUMBER_OF_IMAGES):
            # Get the image and submit for export
            image = ee.Image(collection_list.get(index))
            futures.append(executor.submit(export, image, index, tile_id_row['TileID']))

        for future in concurrent.futures.as_completed(futures):
            logging.info("completed: %s", future.result())

    logging.info("%s Finished processing tile ID %s", tile_index, tile_id_row['TileID'])

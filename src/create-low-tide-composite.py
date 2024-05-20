# Copyright 2023 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
# This script creates composites from Sentinel 2 images based on tile IDs

import argparse
import os
import sys
import pandas as pd
import ee
import concurrent.futures
import logging
from processors.s2processor import Sentinel2Processor

ee.Initialize()

#########################################################
# Configuration
#########################################################
THREADS = 2

MAX_CLOUD_COVER = 0.1
MAX_NUMBER_OF_IMAGES_IN_COMPOSITE = 10
PERCENTILE = 30
START_DATE = '2018-01-01'
END_DATE = '2023-12-31'
BUCKET_NAME = "aims-marb"
SCALE = 10

# True-Colour settings
VIS_OPTION_NAME = 'TrueColour'
BUCKET_PATH = "low-tide-composites/true-colour/"
CORRECT_SUN_GLINT = True

# # Near-Infrared-False-Colour settings
# VIS_OPTION_NAME = 'NearInfraredFalseColour'
# BUCKET_PATH = "low-tide-composites/near-infrared-false-colour/"
# CORRECT_SUN_GLINT = False

#########################################################
# End configuration
#########################################################

# Init processor
processor = Sentinel2Processor(BUCKET_NAME, BUCKET_PATH)


def process_tile_id(tile_id, tile_index):
    """
    Create a composite and export it to cloud storage for a single tile ID.

    :param tile_id: The Sentinel 2 tile ID, e.g. "51KWB"
    :param tile_index: An index identifying the count of processed tile IDs.
    :return: The tile index.
    """
    logging.info("%s starting to process %s", tile_index, tile_id)
    composite = processor.get_low_tide_composite(tile_id, MAX_CLOUD_COVER, MAX_NUMBER_OF_IMAGES_IN_COMPOSITE,
                                                 START_DATE, END_DATE, CORRECT_SUN_GLINT, percentile=PERCENTILE)
    processor.export_to_cloud(composite, "AU_AIMS_MARB-S2-comp_low-tide_p" + str(PERCENTILE) + "_" + VIS_OPTION_NAME +
                              "_" + tile_id, tile_id, VIS_OPTION_NAME, SCALE)
    logging.info("%s finished processing %s", tile_index, tile_id)
    return tile_index


# Create argument parser
parser = argparse.ArgumentParser(description='Create a low tide composite image for Sentinel 2 tile IDs')

# Add arguments
parser.add_argument('--data_file', type=str, help='Name of the data file containing the tile IDs. '
                                                  'Example: "data/tile-ids - single.csv"')

# Parse arguments
args = parser.parse_args()

# Access arguments
print("Create composite")
print("----------------")
print("Using data file:", args.data_file)

# Do not proceed if the data file does not exist
if not os.path.exists(args.data_file):
    print(f"Error: File '{args.data_file}' does not exist.")
    sys.exit(1)

# Set up logging
logging.basicConfig(format="%(asctime)s: %(message)s", level=logging.INFO, datefmt="%H:%M:%S")

# read tile ID CSV in chunks
with pd.read_csv(args.data_file, chunksize=THREADS) as reader:

    # process each chunk
    for tile_ids_chunk in reader:
        # create thread pool for chunk
        with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = []

            # create a thread per row in chunk
            for index, tile_id_row in tile_ids_chunk.iterrows():
                futures.append(executor.submit(process_tile_id, tile_id_row['TileID'], index))

            for future in concurrent.futures.as_completed(futures):
                logging.info("completed: %s", future.result())

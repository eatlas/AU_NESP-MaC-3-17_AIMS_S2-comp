# Copyright 2023 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
# This script vectorises the NDWI images to create a coastline shapefile

from utilities.ndwi_vectoriser import NdwiVectoriser

#########################################################
# Configuration
#########################################################

INPUT_FOLDER = 'data/NDWI'
OUTPUT_FOLDER = 'data/coastline'

SCALE_FACTOR = 2  # up-scale image from 10m to 5m resolution

#########################################################
# End configuration
#########################################################

print("Create coastline")
print("----------------")
print("Input folder:", INPUT_FOLDER)
print("Output folder:", OUTPUT_FOLDER)
print("")
print("Processing ...")
ndwi_vectoriser = NdwiVectoriser(INPUT_FOLDER, OUTPUT_FOLDER, scale_factor=SCALE_FACTOR)
ndwi_vectoriser.process_all()

print("Done")

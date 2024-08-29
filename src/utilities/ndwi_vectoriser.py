# Copyright 2024 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
#
# This class provides all functionality for vectorising NDWI GeoTiff images.

import os
import numpy as np
import scipy.ndimage
import rasterio
from rasterio.transform import Affine
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape, Polygon, MultiPolygon
import logging


class NdwiVectoriser:
    def __init__(self, input_folder, output_folder, scale_factor=2):
        """
        Initialise the NdwiVectoriser class.

        :param input_folder: Path to the folder containing input GeoTIFF files.
        :param output_folder: Path to the folder where the processed files will be saved.
        :param scale_factor: Factor by which the input NDWI image will be upscaled.
        """
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.scale_factor = scale_factor

        # From https://eos.com/make-an-analysis/ndwi/
        # The NDWI values correspond to the following ranges:
        # 0.2 – 1: Water surface,
        # 0 – 0.2: Flooding, humidity,
        # -0.3 – 0: Moderate drought, non-aqueous surfaces,
        # -1 – -0.3: Drought, non-aqueous surfaces
        #
        # Our images are scaled to be between 1 and 255 (instead of being between -1 and +1) with 128 being "0".
        self.ndwi_threshold = 0.15 * 127 + 128  # 147.05

        self.nodata_value = 0

        # Initialize logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        self.logger.info(
            f"NdwiVectoriser initialized with input folder: {self.input_folder}, output folder: {self.output_folder}, "
            f"scale factor: {self.scale_factor}")

    def upscale_image(self, image, meta, filename):
        """
        Upscale the NDWI image using bi-linear interpolation.

        :param image: The NDWI image array to be upscaled.
        :param meta: Metadata associated with the original NDWI image.
        :param filename: The filename of the image being processed.
        :return: A tuple containing the upscaled image and the updated metadata.
        """
        self.logger.info(f"Upscaling image: {filename}")

        # Mask the no-data values
        mask = image != self.nodata_value
        masked_image = np.where(mask, image, np.nan)

        # Use scipy's zoom function for bi-linear interpolation
        upscaled_image = scipy.ndimage.zoom(masked_image, self.scale_factor, order=1)

        # Calculate the new transform
        transform = meta['transform']
        new_transform = Affine(transform.a / self.scale_factor, transform.b, transform.c,
                               transform.d, transform.e / self.scale_factor, transform.f)

        # Reapply the no-data mask
        upscaled_image = np.where(np.isnan(upscaled_image), self.nodata_value, upscaled_image)

        # Update metadata with new dimensions and transform
        new_meta = meta.copy()
        new_meta.update({
            "height": upscaled_image.shape[0],
            "width": upscaled_image.shape[1],
            "transform": new_transform
        })

        return upscaled_image, new_meta

    def create_binary_image(self, image, meta, filename):
        """
        Convert the NDWI image into a binary image where water and land are differentiated.

        :param image: The NDWI image array to be converted.
        :param meta: Metadata associated with the original NDWI image.
        :param filename: The filename of the image being processed.
        :return: A tuple containing the binary image and the updated metadata.
        """
        self.logger.info(f"Creating binary image: {filename}")

        # Mask the no-data values
        mask = image != self.nodata_value
        masked_image = np.where(mask, image, np.nan)

        # Apply the threshold to create a binary image
        binary_image = np.where(masked_image > self.ndwi_threshold, 2, 1)  # 2 for water, 1 for land

        # Reapply the no-data mask
        binary_image = np.where(np.isnan(masked_image), self.nodata_value, binary_image)

        # Update metadata for binary image
        new_meta = meta.copy()
        new_meta.update({
            "dtype": 'uint8',  # Use uint8 to accommodate the values 0, 1, and 2
            "nodata": self.nodata_value
        })

        return binary_image.astype(np.uint8), new_meta

    def vectorise_binary_image(self, image, transform, output_path, filename):
        """
        Vectorise the binary image into polygons, representing land areas.

        :param image: The binary image array to be vectorised.
        :param transform: The affine transform associated with the image.
        :param output_path: The path where the vectorized shapefile will be saved.
        :param filename: The filename of the image being processed.
        """
        self.logger.info(f"Vectorising binary image for {filename} to {output_path}...")

        # Extract shapes for all pixels with value 1 (land)
        mask = (image == 1) & (image != self.nodata_value)
        shapes_and_values = shapes(image, mask=mask, transform=transform)

        # Create a list of polygons
        polygons = [shape(geom) for geom, value in shapes_and_values if value == 1]

        # Create a GeoDataFrame with the extracted polygons
        gdf = gpd.GeoDataFrame({'geometry': polygons}, crs='EPSG:4326')

        # Ensure the GeoDataFrame has the correct CRS
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)

        # Fill holes in the land polygons
        gdf['geometry'] = gdf['geometry'].apply(lambda geom: Polygon(geom.exterior))

        # Save the vectorised polygons as a shapefile
        gdf.to_file(output_path)

    @staticmethod
    def remove_holes(geometry):
        """
        Remove holes from a Polygon or MultiPolygon geometry.

        :param geometry: The geometry object to process.
        :return: The geometry with holes removed.
        """
        if isinstance(geometry, Polygon):
            return Polygon(geometry.exterior)
        elif isinstance(geometry, MultiPolygon):
            return MultiPolygon([Polygon(poly.exterior) for poly in geometry.geoms])
        else:
            return geometry

    @staticmethod
    def read_geotiff(input_path):
        """
        Read a GeoTIFF file and return the image array and metadata.

        :param input_path: Path to the GeoTIFF file.
        :return: A tuple containing the image array and the associated metadata.
        """
        with rasterio.open(input_path) as src:
            image = src.read(1)
            meta = src.meta
        return image, meta

    @staticmethod
    def write_geotiff(output_path, image, meta):
        """
        Write an image array to a GeoTIFF file.

        :param output_path: Path where the GeoTIFF file will be saved.
        :param image: The image array to write.
        :param meta: The metadata to associate with the GeoTIFF file.
        """
        with rasterio.open(output_path, 'w', **meta) as dst:
            dst.write(image, 1)

    def process_single(self, image_path):
        """
        Process a single NDWI GeoTIFF image: upscale, binarise, and vectorise it.

        :param image_path: Path to the input NDWI GeoTIFF file.
        """
        # Extract the filename with extension
        filename_with_extension = os.path.basename(image_path)
        self.logger.info(f"Processing single image: {filename_with_extension}")

        # Remove the extension to get the desired part
        filename_without_extension = os.path.splitext(filename_with_extension)[0]

        # Set path variables
        upscaled_path = os.path.join(self.output_folder, filename_without_extension + '_upscaled.tif')
        binary_path = os.path.join(self.output_folder, filename_without_extension + '_binary.tif')
        vectorised_path = os.path.join(self.output_folder, filename_without_extension + '_vectorised.shp')

        # Read the input image
        image, image_meta = self.read_geotiff(image_path)

        # Step 1: Upscale the GeoTIFF
        if not os.path.exists(upscaled_path):
            upscaled_image, upscaled_meta = self.upscale_image(image, image_meta, filename_with_extension)
            self.write_geotiff(upscaled_path, upscaled_image, upscaled_meta)
        else:
            self.logger.info(f"Upscaled image already exists: {upscaled_path}")
            upscaled_image, upscaled_meta = self.read_geotiff(upscaled_path)

        # Step 2: Apply threshold to the upscaled image
        if not os.path.exists(binary_path):
            binary_image, binary_meta = self.create_binary_image(upscaled_image, upscaled_meta, filename_with_extension)
            self.write_geotiff(binary_path, binary_image, binary_meta)
        else:
            self.logger.info(f"Binary image already exists: {binary_path}")
            binary_image, binary_meta = self.read_geotiff(binary_path)

        # Step 3: Vectorise the binary image and remove lakes
        if not os.path.exists(vectorised_path):
            self.vectorise_binary_image(binary_image, binary_meta['transform'], vectorised_path,
                                        filename_with_extension)
        else:
            self.logger.info(f"Vector shapefile already exists: {vectorised_path}")

    def process_all(self):
        """
        Process all NDWI GeoTIFF images in the input folder: upscale, binarise, and vectorise each one.
        """
        self.logger.info(f"Processing all images in folder: {self.input_folder}")
        geotiff_paths = [os.path.join(self.input_folder, file_name) for file_name in os.listdir(self.input_folder) if
                         file_name.endswith('.tif')]

        for path in geotiff_paths:
            self.process_single(path)

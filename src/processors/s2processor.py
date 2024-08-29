# Copyright 2024 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
#
# This class provides all functionality for processing Sentinel 2 images.
# Reference: https://github.com/eatlas/CS_AIMS_Coral-Sea-Features_Img

from datetime import datetime, timezone
import ee
import time

import os
import sys

# Adjust sys path to include utility classes
current_dir = os.path.dirname(os.path.abspath(__file__))
utilities_path = os.path.join(current_dir, "../utilities")
sys.path.append(utilities_path)

from tide_predictor import TidePredictor
from noise_predictor import NoisePredictor
from logger_setup import LoggerSetup
from sun_glint_handler import SunGlintHandler
from cloud_handler import CloudHandler


class Sentinel2Processor:
    """This class represents a processor for Sentinel 2 data."""

    def __init__(self, bucket_name, bucket_path):
        """
        Initialise the processor by setting the collection ID (Google Earth Engine) and the visualisation option
        configurations. Furthermore, the cloud storage bucket name and path are set for the export functionality.

        :param bucket_name: The cloud storage bucket name for exporting composites.
        :param bucket_path:  The cloud storage path in the bucket for exporting composites.
        """
        # GEE collection ID for Sentinel 2 images
        self.COLLECTION_ID = "COPERNICUS/S2_HARMONIZED"

        # Define all possible visualisation configurations
        self.VIS_OPTIONS = {
            "TrueColour": {
                "description": "True colour imagery. This is useful to interpreting what shallow features are and in "
                               "mapping the vegetation on cays and identifying beach rock. Bands: B2, B3, B4. "
                               "(Level-2A)",
                "visParams": {
                    "bands": ["B4", "B3", "B2"],
                    "gamma": [2, 2, 2.3],
                    "min": [0, 0, 0],
                    "max": [1, 1, 1],
                    "multiplier": [6, 6, 6],
                    "black_point_correction": [0.012, 0.031, 0.064],
                    "brightness_correction": [0.005, 0.005, 0.0015]
                },
            },
            "RedEdgeB5": {
                "description": "Only the red edge band B5",
                "visParams": {
                    "bands": ["B5"],
                    "gamma": [1],
                    "min": [0.0],
                    "max": [0.45],
                    "multiplier": [1],
                    "black_point_correction": [0],
                    "brightness_correction": [0]
                },
            },
            "NearInfraredB8": {
                "description": "Only the near infrared band B8",
                "visParams": {
                    "bands": ["B8"],
                    "gamma": [1],
                    "min": [0.0],
                    "max": [0.45],
                    "multiplier": [1],
                    "black_point_correction": [0],
                    "brightness_correction": [0]
                },
            },
            "NearInfraredFalseColour": {
                "description": "False colour image from infrared bands using B12, B8, B5",
                "visParams": {
                    "bands": ["B12", "B8", "B5"],
                    "gamma": [1.25, 1.25, 1.25],
                    "min": [0.0, 0.0, 0.0],
                    "max": [1, 1, 1],
                    "multiplier": [6, 4, 4],
                    "black_point_correction": [0, 0, 0],
                    "brightness_correction": [0, 0, 0]
                },
            },
            "NDWI": {
                "description": "Water mask using NDWI",
                "visParams": {
                    "bands": ["NDWI"],
                    "gamma": [1],
                    "min": [0.0],
                    "max": [255],
                    "multiplier": [1],
                    "black_point_correction": [0],
                    "brightness_correction": [0]
                },
            },
        }

        # Initialise the logger
        self.logger = LoggerSetup().get_logger()

        # Initialise the handlers
        self.sun_glint_handler = SunGlintHandler()
        self.exclude_tile_ids = [
            '20160605T015625_20160605T065121_T51KWB',
            '20160605T015625_20160605T065121_T51KXB'
        ]
        self.cloud_handler = CloudHandler()

        # List of tile IDs which cause errors. These IDs will be filtered out of the image collection.

        # Settings for exporting images to cloud storage
        self.bucket_name = bucket_name
        self.bucket_path = bucket_path

    def get_composite(
            self,
            tile_id,
            max_cloud_cover,
            min_images_in_collection,
            start_date,
            end_date,
            correct_sun_glint=True,
            percentile=15
    ):
        """
        Create a composite for the given dates for a certain tile.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {Float} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {Integer} min_images_in_collection: Minimum number of images used to create the composite
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :param {Boolean} correct_sun_glint: Should sun-glint correction be applied? Default is True
        :param {Integer} percentile: The percentile to reduce the collection to the composite image
        :return: {ee.Image}
        """
        self.logger.info(
            f"{tile_id} - get_composite with max_cloud_cover: {max_cloud_cover}, min_images_in_collection: "
            + f"{min_images_in_collection}, start_date: {start_date}, end_date: {end_date}, correct_sun_glint: "
            + f"{correct_sun_glint}, percentile: {percentile}")

        # Get the initial image collection filtered by date and maximum cloud cover
        composite_collection = self._get_composite_collection(
            tile_id, max_cloud_cover, start_date, end_date
        )

        # Initiate noise-predictor
        noise_predictor = NoisePredictor(self.logger)

        # Split collection by "SENSING_ORBIT_NUMBER". A tile is made up of different sections depending on the
        # "SENSING_ORBIT_NUMBER". For example, you can have a smaller triangle on the left side of a tile and a bigger
        # section on the right side. If you filter for low tide images, you could end up with 9 small triangle images
        # for the left side and only 1 bigger section for the right side. This would make using 10 images for a
        # composite redundant.
        orbit_numbers = composite_collection.aggregate_array(
            "SENSING_ORBIT_NUMBER"
        ).distinct().getInfo()
        self.logger.info(f"{tile_id} - Orbit numbers: {len(orbit_numbers)}")

        # Create ImageCollections for each orbit number and filter for low noise images
        system_index_values = []
        for orbit_number in orbit_numbers:
            orbit_collection = composite_collection.filter(
                ee.Filter.eq("SENSING_ORBIT_NUMBER", orbit_number)
            )

            noise_filtered_collection = noise_predictor.filter_noise_adding_images(orbit_collection,
                                                                                   min_images_in_collection,
                                                                                   tile_id, orbit_number)

            id_properties_list = noise_filtered_collection.aggregate_array("system:index").getInfo()
            self.logger.info(f"{tile_id} - Images in orbit number {orbit_number}: {len(id_properties_list)}")
            system_index_values += id_properties_list

        self.logger.info(f"{tile_id} - Images in composite: {len(system_index_values)}")

        # Construct an Earth Engine list from the Python list
        index_list = ee.List(system_index_values)

        # Create a filter based on the 'system:index' property
        index_filter = ee.Filter.inList("system:index", index_list)
        filtered_collection = composite_collection.filter(index_filter)

        # apply corrections
        if correct_sun_glint:
            filtered_collection = filtered_collection.map(self.sun_glint_handler.remove_sun_glint)

        # create and return composite from filtered collection
        return self._create_composite(filtered_collection, percentile)

    def get_low_tide_composite(
            self,
            tile_id,
            max_cloud_cover,
            max_images_in_collection,
            start_date,
            end_date,
            correct_sun_glint=True,
            percentile=15
    ):
        """
        Create a low-tide composite for the given dates for a certain tile.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {Float} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {Integer} max_images_in_collection: Maximum number of images used to create the composite
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :param {Boolean} correct_sun_glint: Should sun-glint correction be applied? Default is True
        :param {Integer} percentile: The percentile to reduce the collection to the composite image
        :return: {ee.Image}
        """
        self.logger.info(
            f"{tile_id} - get_low_tide_composite with max_cloud_cover: {max_cloud_cover}, max_images_in_collection: "
            + f"{max_images_in_collection}, start_date: {start_date}, end_date: {end_date}, correct_sun_glint: "
            + f"{correct_sun_glint}, percentile: {percentile}")

        tide_predictor = TidePredictor(tile_id)

        composite_collection = self._get_composite_collection(
            tile_id, max_cloud_cover, start_date, end_date
        )

        # Remove images with a high level of sun-glint
        composite_collection = self.sun_glint_handler.filter_high_sun_glint_images(composite_collection)

        # add a dictionary with relevant properties for easier access later
        def add_dictionary(image):
            properties = ["system:time_start", "system:index"]
            # Get the dictionary of properties with only wanted keys
            properties = ee.Dictionary(image.toDictionary(properties))
            # Set the dictionary as a property of the image
            return image.set("tide_properties", properties)

        composite_collection = composite_collection.map(add_dictionary)

        # Split collection by "SENSING_ORBIT_NUMBER". A tile is made up of different sections depending on the
        # "SENSING_ORBIT_NUMBER". For example, you can have a smaller triangle on the left side of a tile and a bigger
        # section on the right side. If you filter for low tide images, you could end up with 9 small triangle images
        # for the left side and only 1 bigger section for the right side. This would make using 10 images for a
        # composite redundant.
        orbit_numbers = composite_collection.aggregate_array(
            "SENSING_ORBIT_NUMBER"
        ).distinct().getInfo()
        self.logger.info(f"{tile_id} - Orbit numbers: {len(orbit_numbers)}")

        # Create ImageCollections for each orbit number and filter for low tide images
        system_index_values = []
        for orbit_number in orbit_numbers:
            orbit_collection = composite_collection.filter(
                ee.Filter.eq("SENSING_ORBIT_NUMBER", orbit_number)
            )

            tide_properties_list = orbit_collection.aggregate_array(
                "tide_properties"
            ).getInfo()

            # Iterate over all images and add tide elevation
            for tide_properties in tide_properties_list:
                image_date_time = datetime.fromtimestamp(
                    tide_properties["system:time_start"] / 1000.0,
                    tz=timezone.utc
                )
                tide_elevation = tide_predictor.get_tide_elevation(image_date_time)
                tide_properties["tide_elevation"] = tide_elevation

            # Filter for images which are below mean sea level (msl) (negative tide elevation value)
            below_msl_tide_properties_list = [
                entry
                for entry in tide_properties_list
                if entry.get("tide_elevation") < 0
            ]

            # Sort the below MSL list to get the lowest tide images in each category
            below_msl_tide_properties_list = sorted(
                below_msl_tide_properties_list, key=lambda x: x["tide_elevation"]
            )

            # Select max_images_in_collection of lowest tide images
            tide_image_list = below_msl_tide_properties_list[0:max_images_in_collection]

            # Extract the ID for filtering
            orbit_system_index_values = [d["system:index"] for d in tide_image_list]
            self.logger.info(f"{tile_id} - Images in orbit number {orbit_number}: {len(orbit_system_index_values)}")
            system_index_values += orbit_system_index_values

        self.logger.info(f"{tile_id} - Images in composite: {len(system_index_values)}")

        # Construct an Earth Engine list from the Python list
        index_list = ee.List(system_index_values)

        # Create a filter based on the 'system:index' property
        index_filter = ee.Filter.inList("system:index", index_list)
        filtered_collection = composite_collection.filter(index_filter)

        # apply corrections
        if correct_sun_glint:
            filtered_collection = filtered_collection.map(self.sun_glint_handler.remove_sun_glint)

        # create and return composite from filtered collection
        return self._create_composite(filtered_collection, percentile)

    def get_above_mean_sea_level_composite(
            self,
            tile_id,
            max_cloud_cover,
            max_images_in_collection,
            start_date,
            end_date,
            correct_sun_glint=True,
            percentile=15
    ):
        """
        Create an above mean sea level composite for the given dates for a certain tile.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {Float} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {Integer} max_images_in_collection: Maximum number of images used to create the composite
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :param {Boolean} correct_sun_glint: Should sun-glint correction be applied? Default is True
        :param {Integer} percentile: The percentile to reduce the collection to the composite image
        :return: {ee.Image}
        """
        self.logger.info(
            f"{tile_id} - get_above_mean_sea_level_composite with max_cloud_cover: {max_cloud_cover}, max_images_in_collection: "
            + f"{max_images_in_collection}, start_date: {start_date}, end_date: {end_date}, correct_sun_glint: "
            + f"{correct_sun_glint}, percentile: {percentile}")

        tide_predictor = TidePredictor(tile_id)

        composite_collection = self._get_composite_collection(
            tile_id, max_cloud_cover, start_date, end_date
        )

        # Remove images with a high level of sun-glint
        composite_collection = self.sun_glint_handler.filter_high_sun_glint_images(composite_collection)

        # add a dictionary with relevant properties for easier access later
        def add_dictionary(image):
            properties = ["system:time_start", "system:index"]
            # Get the dictionary of properties with only wanted keys
            properties = ee.Dictionary(image.toDictionary(properties))
            # Set the dictionary as a property of the image
            return image.set("tide_properties", properties)

        composite_collection = composite_collection.map(add_dictionary)

        # Split collection by "SENSING_ORBIT_NUMBER". A tile is made up of different sections depending on the
        # "SENSING_ORBIT_NUMBER". For example, you can have a smaller triangle on the left side of a tile and a bigger
        # section on the right side. If you filter for low tide images, you could end up with 9 small triangle images
        # for the left side and only 1 bigger section for the right side. This would make using 10 images for a
        # composite redundant.
        orbit_numbers = composite_collection.aggregate_array(
            "SENSING_ORBIT_NUMBER"
        ).distinct().getInfo()
        self.logger.info(f"{tile_id} - Orbit numbers: {len(orbit_numbers)}")

        # Create ImageCollections for each orbit number and filter for high tide images
        system_index_values = []
        for orbit_number in orbit_numbers:
            orbit_collection = composite_collection.filter(
                ee.Filter.eq("SENSING_ORBIT_NUMBER", orbit_number)
            )

            tide_properties_list = orbit_collection.aggregate_array(
                "tide_properties"
            ).getInfo()

            # Iterate over all images and add tide elevation
            for tide_properties in tide_properties_list:
                image_date_time = datetime.fromtimestamp(
                    tide_properties["system:time_start"] / 1000.0,
                    tz=timezone.utc
                )
                tide_elevation = tide_predictor.get_tide_elevation(image_date_time)
                tide_properties["tide_elevation"] = tide_elevation

            # Filter for images which are above mean sea level (msl) (positive tide elevation value)
            above_msl_tide_properties_list = [
                entry
                for entry in tide_properties_list
                if entry.get("tide_elevation") > 0
            ]

            # Sort the above MSL list to get the highest tide images in each category
            above_msl_tide_properties_list = sorted(
                above_msl_tide_properties_list, key=lambda x: x["tide_elevation"], reverse=True
            )

            # Select max_images_in_collection of highest tide images
            tide_image_list = above_msl_tide_properties_list[0:max_images_in_collection]

            # Extract the ID for filtering
            orbit_system_index_values = [d["system:index"] for d in tide_image_list]
            self.logger.info(f"{tile_id} - Images in orbit number {orbit_number}: {len(orbit_system_index_values)}")
            system_index_values += orbit_system_index_values

        self.logger.info(f"{tile_id} - Images in composite: {len(system_index_values)}")

        # Construct an Earth Engine list from the Python list
        index_list = ee.List(system_index_values)

        # Create a filter based on the 'system:index' property
        index_filter = ee.Filter.inList("system:index", index_list)
        filtered_collection = composite_collection.filter(index_filter)

        # apply corrections
        if correct_sun_glint:
            filtered_collection = filtered_collection.map(self.sun_glint_handler.remove_sun_glint)

        # create and return composite from filtered collection
        return self._create_composite(filtered_collection, percentile)

    def export_to_cloud(
            self, normalised_image, name, tile_id, selected_vis_option, scale=10
    ):
        """
        Export the composite image to cloud storage.

        :param {ee.Image} normalised_image: The image to export with normalised values between 0 and 1
        :param {String} name: The file name for the image
        :param {String} tile_id: The Sentinel 2 tile ID (needed to determine the original geometry for setting the region)
        :param {String} selected_vis_option: The name of the visualisation configuration. The name needs to correspond
                                                to the values in `self.VIS_OPTIONS`.
        :param {Integer} scale: The image scale in meters. Sentinel 2 images have a maximum resolution of 10 meters.
        :return: {ee.Image.rgb}
        """

        # Set a nodata value
        no_data_value = 0

        # Apply contract enhancements
        export_image = self.visualise_image(normalised_image, selected_vis_option)

        if selected_vis_option == "NDWI":
            # The results from the NDWI calculations are values between -1 and +1. We need to shift this to values
            # between 1 and 255 (0 will be the no-data value).
            export_image = (
                export_image
                .multiply(127)
                .add(128)
            )
        else:
            # Apply transformations (bring values into range between 1 and 254; 0 will be the no-data value)
            export_image = (
                export_image
                .multiply(254)
                .add(1)
            )

        # Replace masked pixels around the image edge with the no_data_value
        export_image = export_image.unmask(no_data_value)

        # Convert image data values to unsigned int values
        export_image = export_image.toUint8()

        # Extract the tile geometry
        region = self.get_tile_geometry(tile_id, ee.Geometry.BBox(86, -45, 166, -7))

        # Export the image, specifying scale and region.
        task = ee.batch.Export.image.toCloudStorage(
            **{
                "image": export_image,
                "description": name,
                "scale": scale,
                "fileFormat": "GeoTIFF",
                "bucket": self.bucket_name,
                "fileNamePrefix": self.bucket_path + name,
                "region": region,
                "formatOptions": {"cloudOptimized": True, "noData": no_data_value},
                "maxPixels": 6e8,  # Raise the default limit of 1e8 to fit the export
            }
        )

        # Start processing the image and wait for task to be finished
        task.start()
        while task.active():
            print("Polling for task (id: {}).".format(task.id))
            time.sleep(10)
        print("Task finished: " + task.status()["state"])

    def visualise_image(self, normalised_image, selected_vis_option):
        """
        Apply band modifications according to the visualisation parameters and return the updated image.

        :param {ee.Image} normalised_image: The image to visualise with normalised values between 0 and 1.
        :param {String} selected_vis_option: The selected visualisation parameter. The name needs to correspond to the
                                                values in `self.VIS_OPTIONS`.
        :return: {ee.Image.rgb}
        """
        vis_params = self.VIS_OPTIONS[selected_vis_option]["visParams"]

        if selected_vis_option == "NDWI":
            result_image = normalised_image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        else:
            if len(vis_params["bands"]) == 3:
                bands = []
                for band_index, band_name in enumerate(vis_params["bands"]):
                    band = normalised_image.select(band_name)

                    # Correct black point
                    band = band.subtract(vis_params["black_point_correction"][band_index])

                    # Enhance the contrast by stretching the band values
                    band = self.enhance_contrast(
                        band,
                        vis_params["min"][band_index],
                        vis_params["max"][band_index],
                        vis_params["gamma"][band_index],
                        vis_params["multiplier"][band_index]
                    )

                    # Correct the brightness
                    band = band.add(vis_params["brightness_correction"][band_index])

                    bands.append(band)

                result_image = ee.Image.rgb(bands[0], bands[1], bands[2])

            else:
                result_image = normalised_image.select(vis_params["bands"][0])

                # Correct black point
                result_image = result_image.subtract(vis_params["black_point_correction"][0])

                # Enhance the contrast by stretching the band values
                result_image = self.enhance_contrast(
                    result_image,
                    vis_params["min"][0],
                    vis_params["max"][0],
                    vis_params["gamma"][0],
                    vis_params["multiplier"][0]
                )

                # Correct the brightness
                result_image = result_image.add(vis_params["brightness_correction"][0])

        return result_image

    def _create_composite(self, composite_collection, percentile=15):
        """
        Creates a single composite image from a collection of images by using a 15th percentile reducer. Initially it
        creates two composite images: one without cloud masking, and one with cloud masking. The composite without cloud
        masking is put behind the composite with cloud masking to make sure there are no holes in the image.

        :param composite_collection: The collection of images to build the composite image.
        :param {Integer} percentile: The percentile to reduce the collection to the composite image.
        :return: {ee.Image}
        """

        img_bands = [
            "B1",
            "B2",
            "B3",
            "B4",
            "B5",
            "B6",
            "B7",
            "B8",
            "B8A",
            "B9",
            "B10",
            "B11",
            "B12",
            "QA10",
            "QA20",
            "QA60"
        ]
        composite_collection = composite_collection.select(img_bands)

        # Create a duplicate to keep without cloud masks
        composite_collection_no_cloud_mask = composite_collection.reduce(
            ee.Reducer.percentile([percentile], ["p" + str(percentile)])
        ).rename(img_bands)

        # Only process with cloud mask if there is more than one image
        if composite_collection.size().getInfo() > 1:
            composite_collection_with_cloud_mask = (
                composite_collection.map(self.cloud_handler.mask_clouds)
                .reduce(ee.Reducer.percentile([percentile], ["p" + str(percentile)]))
                .rename(img_bands + ["cloudmask"])
            )

            # Remove the cloudmask so that the bands match in the mosaic process
            cloudmask = composite_collection_with_cloud_mask.select("cloudmask")
            composite_collection_with_cloud_mask = (
                composite_collection_with_cloud_mask.select(img_bands)
            )

            # Layer the Cloud masked image over the composite with no cloud masking.
            # The Cloud masked composite should be a better image than
            # the no cloud masked composite everywhere except over coral cays (as they
            # are sometimes interpreted as clouds and thus are holes in the image).
            # Layer the images so there are no holes.
            # Last layer is on top
            composite = ee.ImageCollection(
                [
                    composite_collection_no_cloud_mask,
                    composite_collection_with_cloud_mask,
                ]
            ).mosaic()

            # Add the cloud mask back into the image as a band
            composite = composite.addBands(cloudmask)
        else:
            # If there is only a single image then don't use cloud masking.
            composite = composite_collection_no_cloud_mask

        # Correct for a bug in the reduce process. The reduce process
        # does not generate an image with the correct geometry. Instead
        # the composite generated as a geometry set to the whole world.
        # this can result in subsequent processing to fail or be very
        # inefficient.
        # We work around this by clipping the output to the dissolved
        # geometry of the input collection of images.
        composite = composite.clip(composite_collection.geometry().dissolve())

        return composite

    def _get_composite_collection(self, tile_id, max_cloud_cover, start_date, end_date):
        """
        Get the filtered image collection for a composite image.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {String} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :return: {ee.ImageCollection}
        """

        # get image collection for a point filtered by cloud cover and dates
        composite_collection = (
            ee.ImageCollection(self.COLLECTION_ID)
            .filter(ee.Filter.eq("MGRS_TILE", tile_id))
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover))
            .filterDate(ee.Date(start_date), ee.Date(end_date))
            .filter(
                ee.Filter.gt("system:asset_size", 100000000)
            )  # Remove small fragments of tiles
            .filter(
                ee.Filter.inList('system:index', self.exclude_tile_ids).Not()
            )  # Remove broken images
        )

        composite_collection = composite_collection.map(self.normalise_image)

        return composite_collection

    @staticmethod
    def normalise_image(image):
        """
        Normalised the bands "B2", "B3", "B4", "B5", "B8", "B9", "B11", and "B12" to values between 0 and 1.

        :param {ee.Image} image: The image to be normalised
        :return: {ee.Image}
        """
        scale_factor = ee.Number(0.0001)  # Sentinel2 channels are 0 - 10000.

        band_b2 = image.select("B2").multiply(scale_factor)
        band_b3 = image.select("B3").multiply(scale_factor)
        band_b4 = image.select("B4").multiply(scale_factor)
        band_b5 = image.select("B5").multiply(scale_factor)
        band_b8 = image.select("B8").multiply(scale_factor)
        band_b9 = image.select("B9").multiply(scale_factor)
        band_b11 = image.select("B11").multiply(scale_factor)
        band_b12 = image.select("B12").multiply(scale_factor)

        return image.addBands(
            [band_b2, band_b3, band_b4, band_b5, band_b8, band_b9, band_b11, band_b12],
            ["B2", "B3", "B4", "B5", "B8", "B9", "B11", "B12"],
            True,
        )

    @staticmethod
    def enhance_contrast(normalised_image, min, max, gamma, multiplier):
        """
        Applies a contrast enhancement to the image, limiting the image between the min and max and applying a gamma
        correction.

        :param {ee.Image} normalised_image: The image to modify with normalised values between 0 and 1.
        :param {float} min: The minimum value for the value range.
        :param {float} max: The maximum value for the value range.
        :param {float} gamma: The gamma correction value.
        :param {float} multiplier: A value which is applied before the gamma correction.
        :return: {ee.Image} The modified image.
        """
        return (
            normalised_image
            .subtract(min)
            .divide(max - min)
            .multiply(multiplier)
            .clamp(0, 1)
            .pow(1 / gamma)
        )

    @staticmethod
    def get_tile_geometry(tile_id, search_bbox):
        """
        Returns the geometry for a certain tile.

        :param {string} tile_id: The Sentinel 2 tile ID
        :param {ee.Geometry} search_bbox: Bounding box to search for the image tiles. This is used to limit the search
                                            size. A search size of Australia seems to be performant.
                                            Australia = ee.Geometry.BBox(86, -45, 166, -7)
        :return: {ee.Geometry}
        """

        # Used to find the geometry of the selected images. For more info checkout
        # https://eatlas.org.au/data/uuid/f7468d15-12be-4e3f-a246-b2882a324f59
        s2_tiles = ee.FeatureCollection(
            "users/ericlawrey/World_ESA_Sentinel-2-tiling-grid"
        )

        # Find the feature that corresponds to the specified tileID.
        # Filter to the search region. This is to reduce the number of tiles that need
        # to be searched (maybe).
        search_tiles = s2_tiles.filterBounds(search_bbox)
        tile_feature = search_tiles.filter(ee.Filter.eq("Name", tile_id)).first()

        # Merge all the features together
        return tile_feature.geometry(0.1)

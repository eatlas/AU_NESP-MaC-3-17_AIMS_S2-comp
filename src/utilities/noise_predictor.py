import ee
import numpy as np


class NoisePredictor:

    def __init__(self, logger):
        self.logger = logger

    def filter_noise_adding_images(self, composite_collection, min_images_in_collection, tile_id, orbit_number):
        """
        Filter out images from collection that add more noise to the final composite.

        :param min_images_in_collection: The minimum number of images to use in the collection. This number of images
                                                            is used to calculate the base noise level.
        :param tile_id: The Sentinel 2 tile ID (used for logging)
        :param orbit_number: The Sentinel 2 SENSING_ORBIT_NUMBER (used for logging)
        :param {ee.ImageCollection} composite_collection: The image collection where noise adding images need to be
                                                            removed.
        :return: {ee.ImageCollection} The collection containing no noise-adding images.
        """

        # Add image noise index value as property to the all images
        composite_collection = composite_collection.map(self.calculate_image_noise)

        # Add a dictionary with relevant properties for easier access later
        def add_dictionary(image):
            properties = ["system:index", "CLOUDY_PIXEL_PERCENTAGE", "noise_index"]
            # Get the dictionary of properties with only wanted keys
            properties = ee.Dictionary(image.toDictionary(properties))
            # Set the dictionary as a property of the image
            return image.set("noise_properties", properties)

        composite_collection = composite_collection.map(add_dictionary)

        # Create a list of only the noise property values
        noise_properties_list = composite_collection.aggregate_array(
            "noise_properties"
        ).getInfo()

        # Sort the list by noise_index
        noise_properties_list = sorted(
            noise_properties_list, key=lambda x: x["noise_index"]
        )

        # Remove all entries with noise_index >= 15 as they don't provide any value
        noise_properties_list = [item for item in noise_properties_list if item["noise_index"] < 15]

        # Calculate initial noise level for minimum number of images as a baseline
        filtered_list = noise_properties_list[0:min_images_in_collection]
        base_noise_level = self.calculate_noise_in_property_list(filtered_list)
        self.logger.info(
            f"{tile_id} - {orbit_number} - Base composite noise level for {min_images_in_collection} "
            + f"images: {base_noise_level}")

        # Iterate over remaining images (without images used in base noise level calculation) and test if adding images
        # adds to the noise or reduces the noise. If it reduces the noise add it to the composite. If it increases the
        # noise stop checking images and return list.
        for end_row in range(min_images_in_collection + 1, len(noise_properties_list)):
            next_filtered_list = noise_properties_list[0:end_row]
            composite_noise_level = self.calculate_noise_in_property_list(next_filtered_list)
            self.logger.info(
                f"{tile_id} - {orbit_number} - Composite noise level for {end_row} images: "
                + f"{composite_noise_level}")
            if composite_noise_level > base_noise_level:
                self.logger.info(
                    f"{tile_id} - {orbit_number} - Breaking because new level is higher than previous")
                break
            else:
                base_noise_level = composite_noise_level
                filtered_list = next_filtered_list

        self.logger.info(
            f"{tile_id} - {orbit_number} - Using {len(filtered_list)} images for composite")
        # Create array of image IDs from filtered list
        system_index_values = [d["system:index"] for d in filtered_list]

        # Construct an Earth Engine list from the Python list
        index_list = ee.List(system_index_values)

        # Create a filter based on the 'system:index' property
        index_filter = ee.Filter.inList("system:index", index_list)
        filtered_collection = composite_collection.filter(index_filter).sort("noise_index")

        return filtered_collection

    @staticmethod
    def calculate_noise_in_property_list(filtered_list):
        # Add a benefit for more images
        noise_index = [item["noise_index"] + 3 / (index + 1) for index, item in enumerate(filtered_list)]

        # Calculate the average
        average = np.mean(noise_index)

        # Count the number of values in the range
        count = len(noise_index)

        # Calculate the standard error of the mean (SEM)
        sem = average / np.sqrt(count)

        return sem

    @staticmethod
    def calculate_image_noise(image):
        """
        :param {ee.Image} image: The image for which to calculate the noise.
        :return: {float} The noise index expressed as a float number.
        """
        # Define factors to calculate the noise
        noise_power = 0.6
        noise_offset = 1.5

        # Define the thresholds for high reflectance in NIR and SWIR bands
        noise_threshold_nir = 0.08
        noise_threshold_swir = 0.03

        # Create a water mask using NDWI
        def create_water_mask(image):
            ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
            water_mask = ndwi.gt(0)
            return water_mask

        # Create the water mask
        water_mask = create_water_mask(image)

        # NIR and average of SWIR bands
        nir_band = image.select('B8')
        swir_band = image.select('B11').add(image.select('B12')).divide(2)

        # Create sun-glint mask by comparing the NIR and SWIR bands against high reflectance thresholds
        noise_mask = nir_band.gt(noise_threshold_nir).Or(swir_band.gt(noise_threshold_swir))

        # Apply water mask to the sun-glint mask
        noise_in_water_mask = noise_mask.updateMask(water_mask)

        # Calculate the proportion of high sun-glint pixels in water areas
        noise_proportion = noise_in_water_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=image.geometry(),
            scale=30,
            maxPixels=1e19
        )
        value = noise_proportion.values().get(0)

        # Calculate "noise" by amplifying the noise proportion
        noise_index = ee.Algorithms.If(
            ee.Algorithms.IsEqual(value, None),  # Check if value is None
            99999999,  # If value==None: set noise_index to very high value
            (ee.Number(value).multiply(100).add(noise_offset)).pow(noise_power)  # Calculate noise_index otherwise
        )

        return image.set('noise_index', noise_index)

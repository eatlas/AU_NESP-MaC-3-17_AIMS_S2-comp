import ee


class SunGlintHandler:

    @staticmethod
    def filter_high_sun_glint_images(composite_collection):
        """
        Filter out high sun-glint images from collection. To determine high sun-glint images, a mask is created for
        all pixels above a high reflectance threshold for the near-infrared and short-wave infrared bands. Then the
        proportion of this is calculated and compared against a sun-glint threshold. If the image exceeds this threshold,
        it is filtered out. As we are only interested in the water pixels, a water mask is created using NDWI.

        Note: The threshold values have been manually determined by looking at various scenes around the north/
        north-west coast of Australia.

        :param {ee.ImageCollection} composite_collection: The collection of images to build the composite image.
        :return: {ee.ImageCollection} The collection containing no high sun-glint images.
        """
        # Define the thresholds for high reflectance in NIR and SWIR bands
        sun_glint_threshold_nir = 0.1
        sun_glint_threshold_swir = 0.05

        # Define a threshold for acceptable sun-glint proportion
        sun_glint_proportion_threshold = 0.2

        # Create a water mask using NDWI
        def create_water_mask(image):
            ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
            water_mask = ndwi.gt(0)
            return water_mask

        # Function to create a sun-glint mask and calculate the proportion of high-glint pixels
        def calculate_sun_glint_proportion(image):
            # Create the water mask
            water_mask = create_water_mask(image)

            # NIR and average of SWIR bands
            nir_band = image.select('B8')
            swir_band = image.select('B11').add(image.select('B12')).divide(2)

            # Create sun-glint mask by comparign the NIR and SWIR bands against high reflectance thresholds
            sun_glint_mask = nir_band.gt(sun_glint_threshold_nir).Or(swir_band.gt(sun_glint_threshold_swir))

            # Apply water mask to the sun-glint mask
            sun_glint_in_water_mask = sun_glint_mask.updateMask(water_mask)

            # Calculate the proportion of high sun-glint pixels in water areas
            sun_glint_proportion = sun_glint_in_water_mask.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=image.geometry(),
                scale=30,
                maxPixels=1e19
            ).values().get(0)

            # Add a property with the sun-glint proportion to the image
            return image.set('sun_glint_proportion', sun_glint_proportion)

        # Apply the function to each image in the collection
        images_with_sun_glint_proportion = composite_collection.map(calculate_sun_glint_proportion)

        # Filter the collection to exclude images with high glint proportion
        filtered_collection = images_with_sun_glint_proportion.filter(
            ee.Filter.lt('sun_glint_proportion', sun_glint_proportion_threshold))

        return filtered_collection

    @staticmethod
    def remove_sun_glint(normalised_image):
        """
        This algorithm with its specific values was developed by Eric Lawrey as part of the NESP MaC 3.17 project.
        The values were determined by fine-tuning the scale between the B8 channel and each individual visible channel
        (B2, B3 and B4) so that the maximum level of sung lint would be removed. This work was based on a representative
        set of images, trying to determine a set of values that represent a good compromise across different water
        surface conditions.

        :param {ee.Image} normalised_image: The image for which the sun glint should be removed with normalised values between 0 and 1
        :return: {ee.Image}
        """

        sun_glint_threshold = 0.04

        # select relevant bands and transform values to be withing 0 to 1
        band_b2 = normalised_image.select("B2")
        band_b3 = normalised_image.select("B3")
        band_b4 = normalised_image.select("B4")
        band_b8 = normalised_image.select("B8")

        # If the B8 value is lower than the threshold, use the threshold. This is to overcome the problem in shallow
        # areas where B08 infrared channel penetrates the water enough to pick up benthic reflection, making these
        # regions brighter than just the sun glint.
        sun_glint = normalised_image.expression(
            "band_b8 < sun_glint_threshold ? band_b8 : sun_glint_threshold",
            {"band_b8": band_b8, "sun_glint_threshold": sun_glint_threshold},
        )

        # Apply sun glint corrections to each visible band
        band_b2 = (band_b2.subtract(sun_glint.multiply(0.85))).clamp(0, 1)
        band_b3 = (band_b3.subtract(sun_glint.multiply(0.9))).clamp(0, 1)
        band_b4 = (band_b4.subtract(sun_glint.multiply(0.95))).clamp(0, 1)

        # Replace the visible bands in the image with the corrected bands
        return normalised_image.addBands(
            [band_b2, band_b3, band_b4], ["B2", "B3", "B4"], True
        )

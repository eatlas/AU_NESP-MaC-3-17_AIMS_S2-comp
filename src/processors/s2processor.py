# Copyright 2024 Marc Hammerton - Australian Institute of Marine Science
#
# MIT License https://mit-license.org/
#
# This class provides all functionality for processing Sentinel 2 images.
# Reference: https://github.com/eatlas/CS_AIMS_Coral-Sea-Features_Img

from datetime import datetime
import sys

sys.path.append("../utilities")

import ee
import time
from tidePredictor import TidePredictor


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
                    "gamma": [1, 1, 1],
                    "min": [0, 0, 0],
                    "max": [1, 1, 1],
                },
            },
            "Infrared": {
                "description": "Only the infrared band",
                "visParams": {
                    "bands": ['B8'],
                    "gamma": [1],
                    "min": [0.0],
                    "max": [0.3],
                },
            }
        }

        # Settings for exporting images to cloud storage
        self.bucket_name = bucket_name
        self.bucket_path = bucket_path

    def get_composite(
        self,
        tile_id,
        max_cloud_cover,
        max_images_in_collection,
        start_date,
        end_date,
        correct_sunglint=True,
    ):
        """
        Create a composite for the given dates for a certain tile.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {String} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {String} max_images_in_collection: Maximum number of images used to create the composite
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :return: {ee.Image}
        """

        composite_collection = self.get_composite_collection(
            tile_id, max_cloud_cover, start_date, end_date
        )
        composite_collection = composite_collection.limit(
            max_images_in_collection, "CLOUDY_PIXEL_PERCENTAGE", True
        )

        # apply corrections
        if correct_sunglint:
            composite_collection = composite_collection.map(self.remove_sun_glint)

        return self._create_composite(composite_collection)

    def get_low_tide_composite(
        self,
        tile_id,
        max_cloud_cover,
        min_images_in_collection,
        max_images_in_collection,
        start_date,
        end_date,
        correct_sunglint=True,
        tide_type_focus=TidePredictor.TIDE_TYPE.OUTGOING_TIDE,
    ):
        """
        Create a low-tide composite for the given dates for a certain tile.

        :param {String} tile_id: The Sentinel 2 tile ID
        :param {String} max_cloud_cover: Maximum percentage of cloud cover per image
        :param {String} min_images_in_collection: Minimum number of images used to create the composite
        :param {String} max_images_in_collection: Maximum number of images used to create the composite
        :param {String} start_date: Format yyyy-mm-dd
        :param {String} end_date: Format yyyy-mm-dd
        :param {Boolean} correct_sunglint: Should sun glint correction be applied?
        :param {String} tide_type_focus: Deternine on which tide type the focus should be
        :return: {ee.Image}
        """

        tide_predictor = TidePredictor(tile_id)
        tide_type_order = []
        if tide_type_focus == TidePredictor.TIDE_TYPE.OUTGOING_TIDE:
            tide_type_order = [
                TidePredictor.TIDE_TYPE.OUTGOING_TIDE,
                TidePredictor.TIDE_TYPE.PEAK_LOW_TIDE,
                TidePredictor.TIDE_TYPE.INCOMING_TIDE,
            ]
        elif tide_type_focus == TidePredictor.TIDE_TYPE.PEAK_LOW_TIDE:
            tide_type_order = [
                TidePredictor.TIDE_TYPE.PEAK_LOW_TIDE,
                TidePredictor.TIDE_TYPE.OUTGOING_TIDE,
                TidePredictor.TIDE_TYPE.INCOMING_TIDE,
            ]
        elif tide_type_focus == TidePredictor.TIDE_TYPE.INCOMING_TIDE:
            tide_type_order = [
                TidePredictor.TIDE_TYPE.INCOMING_TIDE,
                TidePredictor.TIDE_TYPE.PEAK_LOW_TIDE,
                TidePredictor.TIDE_TYPE.OUTGOING_TIDE,
            ]

        composite_collection = self.get_composite_collection(
            tile_id, max_cloud_cover, start_date, end_date
        )

        # apply corrections
        if correct_sunglint:
            composite_collection = composite_collection.map(self.remove_sun_glint)

        def add_dictionary(image):
            properties = ["system:time_start", "system:index"]
            # Get the dictionary of properties with only wanted keys
            properties = ee.Dictionary(image.toDictionary(properties))
            # Set the dictionary as a property of the image
            return image.set("tide_properties", properties)

        composite_collection = composite_collection.map(add_dictionary)

        # split collectin by "SENSING_ORBIT_NUMBER". A tile is made up of different sections depending on the "SENSING_ORBIT_NUMBER".
        # For example you can have a smaller triangle on the left side of a tile and a bigger section on the right side. If you filter
        # for low tide images, you could end up with 9 small triangle images for the left side and only 1 bigger section for the right
        # side. This would make using 10 images for a composite redundant.
        orbit_numbers = composite_collection.aggregate_array(
            "SENSING_ORBIT_NUMBER"
        ).distinct()

        # Create ImageCollections for each orbit number and filter for low tide images
        system_index_values = []
        for orbit_number in orbit_numbers.getInfo():
            orbit_collection = composite_collection.filter(
                ee.Filter.eq("SENSING_ORBIT_NUMBER", orbit_number)
            )

            tide_properties_list = orbit_collection.aggregate_array(
                "tide_properties"
            ).getInfo()

            # Iterate over all images and add tide elevation and tide type (incoming, outgoing, peak high, peak low tide)
            for tide_properties in tide_properties_list:
                image_date_time = datetime.fromtimestamp(
                    tide_properties["system:time_start"] / 1000.0
                )
                tide_elevation, tide_type = tide_predictor.get_tide_elevation(
                    image_date_time
                )
                tide_properties["tide_elevation"] = tide_elevation
                tide_properties["tide_type"] = tide_type

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

            tide_image_list = []
            for tide_type in tide_type_order:
                if len(tide_image_list) < min_images_in_collection:
                    tide_type_list = [
                        entry
                        for entry in below_msl_tide_properties_list
                        if entry.get("tide_type") == tide_type
                    ]
                    tide_image_list.extend(tide_type_list)
                    print(f"Added {len(tide_type_list)} {tide_type} images")

            # Have we now found enough images? If not, we will add incoming tide images
            if len(tide_image_list) < min_images_in_collection:
                incoming_tide_list = [
                    entry
                    for entry in below_msl_tide_properties_list
                    if entry.get("tide_type") == tide_predictor.TIDE_TYPE.INCOMING_TIDE
                ]
                tide_image_list.extend(incoming_tide_list)
                print(f"Added {len(incoming_tide_list)} incoming tide images")

            # Fallback: if there not enough low tide images, sort by tide elevtion and use the lowest tide images
            if len(tide_image_list) < min_images_in_collection:
                # Sort the list of dictionaries by the 'tide' key in ascending order
                sorted_list = sorted(
                    tide_properties_list, key=lambda x: x["tide_elevation"]
                )

                # Get the number of lowest tide images from list according to the value in max_images_in_collection
                tide_image_list = sorted_list[0:max_images_in_collection]
            else:
                # Get the number of lowest tide images from list according to the value in max_images_in_collection
                tide_image_list = tide_image_list[0:max_images_in_collection]

            orbit_system_index_values = [d["system:index"] for d in tide_image_list]

            # Extract the ID for filtering
            system_index_values += orbit_system_index_values

        # Construct an Earth Engine list from the Python list
        index_list = ee.List(system_index_values)

        # Create a filter based on the 'system:index' property
        index_filter = ee.Filter.inList("system:index", index_list)
        filtered_collection = composite_collection.filter(index_filter)

        # return filtered_collection
        return self._create_composite(filtered_collection)

    def _create_composite(self, composite_collection):

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
            "QA60",
        ]

        # Create a duplicate to keep without cloud masks
        composite_collection_no_cloud_mask = composite_collection.reduce(
            ee.Reducer.percentile([50], ["p50"])
        ).rename(img_bands)

        # Only process with cloud mask if there is more than one image
        if composite_collection.size().getInfo() > 1:
            composite_collection_with_cloud_mask = (
                composite_collection.map(self.mask_clouds)
                .reduce(ee.Reducer.percentile([15], ["p15"]))
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

    def get_composite_collection(self, tile_id, max_cloud_cover, start_date, end_date):
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
        )

        composite_collection = composite_collection.map(self.normalise_image)

        return composite_collection

    def export_to_cloud(
        self, normalised_image, name, tile_id, selected_vis_option, scale=10
    ):
        """
        Export the composite image to cloud storage.

        :param {ee.Image} normalised_image: The image to export with normalised values between 0 and 1
        :param {String} name: The file name for the image
        :param tile_id: The Sentinel 2 tile ID (needed to determine the original geometry for setting the region)
        :param {String} selected_vis_option: The name of the visualisation configuration. The name needs to correspond
                                                to the values in `self.VIS_OPTIONS`.
        :param {Integer} scale: The image scale in meters. Sentinel 2 images have a maximum resolution of 10 meters.
        :return: {ee.Image.rgb}
        """

        # Set a nodata value and replace masked pixels around the image edge with it.
        no_data_value = 0
        normalised_image = normalised_image.unmask(no_data_value)

        # Apply contract enhancements and transformations
        export_image = (
            self.visualise_image(normalised_image, selected_vis_option)
            .multiply(254)
            .add(1)
            .toUint8()
        )

        # Extract the tile geometry
        region = self.get_tile_geometry(tile_id, ee.Geometry.BBox(-180, -33, 180, 33))

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

    @staticmethod
    def normalise_image(image):
        """
        Normalised the bands "B2", "B3", "B4", "B8", and "B9" to values between 0 and 1.

        :param {ee.Image} image: The image to be normalised
        :return: {ee.Image}
        """
        scale_factor = ee.Number(0.0001) # Sentinel2 channels are 0 - 10000.

        # band_b2 = image.select("B2").mulitply(scale_factor)
        band_b2 = image.select("B2").multiply(scale_factor)
        band_b3 = image.select("B3").multiply(scale_factor)
        band_b4 = image.select("B4").multiply(scale_factor)
        band_b8 = image.select("B8").multiply(scale_factor)
        band_b9 = image.select("B9").multiply(scale_factor)

        return image.addBands([band_b2, band_b3, band_b4, band_b8, band_b9], ["B2", "B3", "B4", "B8", "B9"], True)


    @staticmethod
    def remove_sun_glint(normalised_image):
        """
        This algorithm with its specific values was developed by Eric Lawrey as part of the NESP MaC 3.17 project.
        The values were determined by fine-tuning the scale between the B8 channel and each individual visible channel
        (B2, B3 and B4) so that the maximum level of sung lint would be removed. This work was based on a representative
        set of images, trying to determine a set of values that represent a good compromise across different water
        surface conditions.

        Algorithm:
        threshold = 0.04
        g = 0.5

        sg = s8 < threshold? s8: threshold

        b2 = Math.pow(6 * (s2 - (sg*0.85)-0.058),g)
        b3 = Math.pow(6 * (s3 - (sg*0.9)-0.030),g)
        b4 = Math.pow(6 * (s4 - (sg*0.95)-0.01),g)

        :param {ee.Image} normalised_image: The image for which the sun glint should be removed with normalised values between 0 and 1
        :return: {ee.Image}
        """

        sun_glint_threshold = 0.04
        gamma = 0.5

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
        band_b2 = (
            (band_b2.subtract(sun_glint.multiply(0.85)).subtract(0.058))
            .multiply(6)
            .pow(gamma)
        )
        band_b3 = (
            (band_b3.subtract(sun_glint.multiply(0.9)).subtract(0.03))
            .multiply(6)
            .pow(gamma)
        )
        band_b4 = (
            (band_b4.subtract(sun_glint.multiply(0.95)).subtract(0.01))
            .multiply(6)
            .pow(gamma)
        )

        # Replace the visible bands in the image with the corrected bands
        return normalised_image.addBands(
            [band_b2, band_b3, band_b4], ["B2", "B3", "B4"], True
        )

    def mask_clouds(self, normalised_image):
        """
        Apply the cloud mask to each of the image bands. This should be
        done prior to reducing all the images using median or percentile.

        :param {ee.Image} normalised_image: The image where clouds should be masked with normalised values between 0 and 1
        :return: {ee.Image}
        """
        normalised_image = self._add_s2_cloud_mask(normalised_image)
        normalised_image = self._add_s2_cloud_shadow_mask(normalised_image)

        # Subset the cloudmask band and invert it so clouds/shadow are 0, else 1.
        not_cld_shdw = normalised_image.select("cloudmask").Not()

        masked_img = normalised_image.select("B.*").updateMask(not_cld_shdw)
        # Get remaining QA bands
        qa_img = normalised_image.select("QA.*")

        # Subset reflectance bands and update their masks, return the result.
        return masked_img.addBands(qa_img).addBands(
            normalised_image.select("cloudmask")
        )

    def visualise_image(self, normalised_image, selected_vis_option):
        """
        Apply band modifications according to the visualisation parameters and return the updated image.

        :param {ee.Image} normalised_image: The image to visualise with normalised values between 0 and 1.
        :param {String} selected_vis_option: The selected visualisation parameter. The name needs to correspond to the
                                                values in `self.VIS_OPTIONS`.
        :return: {ee.Image.rgb}
        """
        vis_params = self.VIS_OPTIONS[selected_vis_option]["visParams"]

        if len(vis_params["bands"]) == 3:
            red_band = self.enhance_contrast(
                normalised_image.select(vis_params["bands"][0]),
                vis_params["min"][0],
                vis_params["max"][0],
                vis_params["gamma"][0],
            )
            green_band = self.enhance_contrast(
                normalised_image.select(vis_params["bands"][1]),
                vis_params["min"][1],
                vis_params["max"][1],
                vis_params["gamma"][1],
            )
            blue_band = self.enhance_contrast(
                normalised_image.select(vis_params["bands"][2]),
                vis_params["min"][2],
                vis_params["max"][2],
                vis_params["gamma"][2],
            )

            result_image = ee.Image.rgb(red_band, green_band, blue_band)
        else:
            result_image = self.enhance_contrast(
                normalised_image.select(vis_params["bands"][0]),
                vis_params["min"][0],
                vis_params["max"][0],
                vis_params["gamma"][0],
            )

        return result_image

    @staticmethod
    def enhance_contrast(normalised_image, min, max, gamma):
        """
        Applies a contrast enhancement to the image, limiting the image between the min and max and applying a gamma
        correction.

        :param {ee.Image} normalised_image: The image to modify with normalised values between 0 and 1.
        :param {float} min: The minimum value for the value range.
        :param {float} max: The maximum value for the value range.
        :param {float} gamma: The gamma correction value.
        :return: {ee.Image} The modified image.
        """
        return (
            normalised_image.subtract(min).divide(max - min).clamp(0, 1).pow(1 / gamma)
        )

    @staticmethod
    def _add_s2_cloud_mask(normalised_image):
        """
        This function creates a Sentinel 2 image with matching cloud mask from the COPERNICUS/S2_CLOUD_PROBABILITY
        dataset.

        Reference: https://github.com/eatlas/CS_AIMS_Coral-Sea-Features_Img

        :param {ee.Image} normalised_image: The image to modify with normalised values between 0 and 1.
        :return: {ee.Image}
        """
        # Preserve a copy of the system:index that is not modified
        # by the merging of image collections.
        normalised_image = normalised_image.set(
            "original_id", normalised_image.get("system:index")
        )

        # The masks for the 10m bands sometimes do not exclude bad data at
        # scene edges, so we apply masks from the 20m and 60m bands as well.
        # Example asset that needs this operation:
        # COPERNICUS/S2_CLOUD_PROBABILITY/20190301T000239_20190301T000238_T55GDP
        normalised_image = normalised_image.updateMask(
            normalised_image.select("B8A")
            .mask()
            .updateMask(normalised_image.select("B9").mask())
        )

        # Get the dataset containing high quality cloud masks. Use
        # this to mask off clouds from the composite. This masking
        # does not consider cloud shadows and so these can still
        # affect the final composite.
        s2_cloud_image = (
            ee.ImageCollection("COPERNICUS/S2_CLOUD_PROBABILITY")
            .filter(
                ee.Filter.equals("system:index", normalised_image.get("original_id"))
            )
            .first()
        )
        s2_cloud_image = s2_cloud_image.set(
            "original_id", s2_cloud_image.get("system:index")
        )

        return normalised_image.set("s2cloudless", s2_cloud_image)

    def _add_s2_cloud_shadow_mask(self, normalised_image):
        """
        This function estimates a mask for the clouds and the shadows and adds
        this as additional bands (highcloudmask, lowcloudmask and cloudmask).

        This assumes that the img has the cloud probability setup from
        COPERNICUS/S2_CLOUD_PROBABILITY (see `_add_s2_cloud_mask`).

        The mask includes the cloud areas, plus a mask to remove cloud shadows.
        The shadows are estimated by projecting the cloud mask in the direction
        opposite the angle to the sun.

        The algorithm does not try to estimate the actual bounds of the shadows
        based on the image, other than splitting the clouds into two categories.

        This masking process assumes most small clouds are low and thus throw
        short shadows. It assumes that large clouds are taller and throw
        longer shadows. The height of the clouds is estimated based on the
        confidence in the cloud prediction level from COPERNICUS/S2_CLOUD_PROBABILITY,
        where high probability corresponds to obvious large clouds and lower
        probabilities pick up smaller clouds. The filtering of high clouds is
        further refined by performing an erosion and dilation to remove all
        clouds smaller than 300 m.

        Reference: https://github.com/eatlas/CS_AIMS_Coral-Sea-Features_Img

        :param {ee.Image} normalised_image: Sentinel 2 image to add the cloud masks to. Its values should be between 0 and 1.
        :return: {ee.Image}
        """

        # Treat the cloud shadow distance differently for low and high cloud.
        # High thick clouds can produce long shadows that can muck up the image.
        # There is no direct way to determine which clouds will throw long dark shadows
        # however it was found from experimentation that setting a high cloud
        # probability tended to pick out the thicker clouds that also through
        # long shadows. It is unclear how robust this approach is though.
        # Cloud probability threshold (%); values greater are considered cloud
        low_cloud_mask = self._get_s2_cloud_shadow_mask(
            normalised_image,
            35,
            # (cloud predication prob) Use low probability to pick up smaller
            # clouds. This threshold still misses a lot of small clouds.
            # unfortunately lowering the threshold anymore results in sand cays
            # being detected as clouds.
            # Note that for the atolls on 06LUJ and 06LWH the cays and shallow
            # reefs are considered clouds to a high probability. Having a threshold
            # of 40 results in approx 80% of the atoll rim being masked as a cloud.
            # Raising the threshold to 60 still results in about 60% being masked
            # as cloud. A threshold of 80 still masks about 30% of the cay area.
            # Setting the threshold to 60 results in lots of small clouds remaining
            # in images. We therefore use a lower threshold to cover off on these
            # clouds, at the expense of making out from of the cays.
            0,  # (m) Erosion. Keep small clouds.
            0.4,  # (km) Use a shorter cloud shadow
            150,  # (m) buffer distance
        ).rename("lowcloudmask")

        # Try to detect high thick clouds. Assume that this throw a longer shadow.
        high_cloud_mask = self._get_s2_cloud_shadow_mask(
            normalised_image,
            80,
            # Use high cloud probability to pick up mainly larger solid clouds
            300,
            # (m)  Erosion. Remove small clouds because we are trying to just detect
            #      the large clouds that will throw long shadows.
            1.5,  # (km) Use a longer cloud shadow
            300,  # (m) buffer distance
        ).rename("highcloudmask")

        # Combine both masks
        cloud_mask = high_cloud_mask.add(low_cloud_mask).gt(0).rename("cloudmask")

        return (
            normalised_image.addBands(cloud_mask)
            .addBands(high_cloud_mask)
            .addBands(low_cloud_mask)
        )

    @staticmethod
    def _get_s2_cloud_shadow_mask(
        normalised_image, cloud_prob_thresh, erosion, cloud_proj_dist, buffer
    ):
        """
        Estimate the cloud and shadow mask for a given image. This uses the following
        algorithm:
        1. Estimate the dark pixels corresponding to cloud shadow pixels using a
           threshold on the B8 channel. Note that this only works on land. On water
           this algorithm treats all water as a shadow.
        2. Calculate the angle of the shadows using the MEAN_SOLAR_AZIMUTH_ANGLE
        3. Create a cloud mask based on a probability threshold (cloud_prob_thresh) to
           apply to the COPERNICUS/S2_CLOUD_PROBABILITY data.
        4. Apply an erosion and dilation (negative then positive buffer) to the
           cloud mask. This removes all cloud features smaller than the
           erosion distance.
        5. Project this cloud mask along the line of the shadow for a distance specified
           by cloud_proj_dist. The shadows of low clouds will only need a short
           project distance (~ 0.4 km), whereas high clouds throw longer shadows (~ 1 - 2 km).
        6. Multiply the dark pixels by the projected cloud shadow. On land this will crop
           the mask to just the cloud shadow. On water this will retain the whole cloud
           mask and cloud projection as all the water are considered dark pixels.
        7. Add the shadow and cloud masks together to get a complete mask. This will
           ensure a full mask on land, and will have no effect on water areas as the
           shadow mask already includes the clouded areas.
        8. Apply a buffer to the mask to expand the area masked out. This is to
           slightly overcome the imperfect nature of the cloud masks.

        This assumes that the img has the cloud probability setup from
        COPERNICUS/S2_CLOUD_PROBABILITY (see `_add_s2_cloud_mask`).

        :param {ee.Image} normalised_image: Sentinel 2 image to add the cloud mask to. Assumes that
                                   the COPERNICUS/S2_CLOUD_PROBABILITY dataset has been merged with
                                   image (see `_add_s2_cloud_mask`). In this case the probability
                                   band in the image stored under the s2cloudless property is used.
                                   The values should normalised to be between 0 and 1.
        :param {int} cloud_prob_thresh: (0-100) probability threshold to
                                   apply to the COPERNICUS/S2_CLOUD_PROBABILITY layer to create the
                                   cloud mask. This basic mask is then has the erosion apply to it,
                                   is projected along the shadow and a final buffer applied.
        :param {int} erosion: (m) erosion applied to the initial cloud mask
                                   prior to creating the cloud shadow project. This can be used to remove
                                   small cloud features. A dilation (buffer) is applied after the erosion to
                                   bring the cloud mask features back to their original size (except those
                                   that were too small and thus disappeared) prior to shadow projection.
                                   This dilation has the same distance as the erosion.
        :param {int} cloud_proj_dist: (m) distance to project the cloud mask
                                   in the direction of shadows.
        :param {int} buffer: (m) Final buffer to apply to the shadow projected
                                   cloud mask. This expands the mask in all directions and can be used to
                                   catch more of the neighbouring cloud areas just outside the cloud
                                   masking.
        :return: {ee.Image}
        """

        nir_drk_thresh = 0.15  # Near-infrared reflectance; values less than are
        # considered potential cloud shadow. This threshold was
        # chosen to detect cloud shadows on land areas where
        # the B8 channel is consistently bright (except in shadows).
        # All water areas are considered dark by this threshold.
        # Determine the dark areas on land. This doesn't work on water because all
        # water appears too dark. As such the simple dark pixels approach only refines
        # the masking of shadows on land areas. In the water it is determined by
        # the cloud_proj_dist.
        dark_pixels = (
            normalised_image.select("B8").lt(nir_drk_thresh).rename("dark_pixels")
        )

        # Determine the direction to project cloud shadow from clouds (assumes UTM projection).
        shadow_azimuth = ee.Number(90).subtract(
            ee.Number(normalised_image.get("MEAN_SOLAR_AZIMUTH_ANGLE"))
        )

        # Condition s2cloudless by the probability threshold value.
        is_cloud = (
            ee.Image(normalised_image.get("s2cloudless"))
            .select("probability")
            .gt(cloud_prob_thresh)
            .rename("allclouds")
        )

        if erosion > 0:
            # Make sure the erosion and dilation filters don't get too large as this
            # will become too computationally expensive.
            # We want the filter size to be approximately 4 pixels in size so that
            # the calculations are smooth enough, but the computations are not too
            # expensive.
            # We also have a lower resolution limit of 20 m to save on computations
            # for full image exports.
            # Find the scale that would give us approximately a 4 pixel filter or
            # our lower resolution limit.
            approx_erosion_pixels = 4  # pixels
            # Find the resolution of the filter rounded to the nearest 10 m (Sentinel 2 resolution)
            # Make sure that it isn't smaller than 20 m
            erosion_scale = max(round(erosion / approx_erosion_pixels / 10) * 10, 20)

            # Operate at a erosion_scale m pixel scale. The focal_min and focal_max operators require
            # units of pixels and adjust the erosion variable from m to pixels
            is_cloud_erosion_dilation = (
                is_cloud.focal_min(erosion / erosion_scale)
                .focal_max(erosion / erosion_scale)
                .reproject(
                    normalised_image.select([0]).projection(), None, erosion_scale
                )
                .rename("cloudmask")
            )
        else:
            is_cloud_erosion_dilation = is_cloud

        # Project shadows from clouds for the distance specified by the cloud_proj_dist input.
        # We use a scale of 100 m to reduce the computations. This results is pixelated
        # results, however the buffer stage smooths this out.
        cloud_proj = (
            is_cloud_erosion_dilation.directionalDistanceTransform(
                shadow_azimuth, cloud_proj_dist * 10
            )
            .reproject(normalised_image.select([0]).projection(), None, 100)
            .select("distance")
            .mask()
            .rename("cloud_transform")
        )

        # Identify the intersection of dark pixels with cloud shadow projection.
        shadows = cloud_proj.multiply(dark_pixels).rename("shadows")

        # Add the cloud mask to the shadows. On water the clouds are already
        # masked off because all the water pixels are considered shadows due to
        # the limited shadow detection algorith. For land areas the shadows
        # don't include the cloud mask.
        # is_cloud_or_shadow = is_cloud.add(shadows).gt(0)
        is_cloud_or_shadow = cloud_proj

        approx_buffer_pixels = 4  # pixels
        # Find the resolution of the filter rounded to the nearest 10 m (Sentinel 2 resolution)
        # Make sure that it isn't smaller than 20 m
        buffer_scale = max(round(buffer / approx_buffer_pixels / 10) * 10, 20)

        # Remove small cloud-shadow patches and dilate remaining pixels by BUFFER input.
        # 20 m scale is for speed, and assumes clouds don't require 10 m precision.
        # Removing the small patches also reduces the False positive rate on
        # beaches significantly.
        return (
            is_cloud_or_shadow.focal_max(buffer / buffer_scale)
            .reproject(normalised_image.select([0]).projection(), None, buffer_scale)
            .rename("cloudmask")
        )

    @staticmethod
    def get_tile_geometry(tile_id, search_bbox):
        """
        Returns the geometry for a certain tile.

        :param {string} tile_id: The Sentinel 2 tile ID
        :param {ee.Geometry} search_bbox: Bounding box to search for the image tiles. This is used to limit the search
                                            size. A search size of Australia seems to be performant.
                                            Australia = ee.Geometry.BBox(109, -33, 158, -7)
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

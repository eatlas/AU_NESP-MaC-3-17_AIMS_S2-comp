import ee


class CloudHandler:

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

        :param {ee.Image} normalised_image: Sentinel 2 image to add the cloud masks to. Its values should be between 0
                                            and 1.
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

import os
import numpy as np
import pyTMD.io
import pyTMD.time
import pyTMD.predict
import pyTMD.tools
import pyTMD.utilities

# Set data directory
current_dir = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(current_dir, "../data/")


class TidePredictor:
    """This class can be used to predict tide elevation for a certain date time."""

    def __init__(self, tile_id):
        """
        Initialise the TidePredictor for a specified Sentinel 2 tile.

        :param {String} tile_id: The Sentinel 2 tile ID.
        :return: {float} The tide elevation as signed int and a string describing incoming tide, 
                                    peak high tide, peak low tide, outgoing tide.
        """
        # get model parameters
        self.model = pyTMD.io.model(
            DATA_PATH, format="FES", compressed=False
        ).elevation("EOT20")

        # get constituents
        self.constant_constituents = pyTMD.io.FES.read_constants(
            self.model.model_file,
            type=self.model.type,
            version=self.model.version,
            compressed=self.model.compressed,
        )
        self.model_constituents = self.model.constituents

        # read tile centroids
        self.tile_water_centroids = np.genfromtxt(
            DATA_PATH + "sentinel2-study-area-water-centroids.csv",
            dtype=None,
            delimiter=",",
            names=True,
            encoding=None
        )

        self.hc = None
        self._set_hc(tile_id)

    def get_tide_elevation(self, image_date_time):
        """
        Predict the tide elevation for an image timestamp.

        :param {datetime} image_date_time: The image time stamp as datetime object
        :return: {float} The tide elevation as signed float.
        """

        # convert time from MJD to days relative to Jan 1, 1992 (48622 MJD)
        tide_time = pyTMD.time.convert_calendar_dates(
            image_date_time.year,
            image_date_time.month,
            image_date_time.day,
            image_date_time.hour,
            image_date_time.minute
        )

        tide_height = pyTMD.predict.map(
            tide_time, self.hc, self.model_constituents, corrections=self.model.format
        )
        tide_data = tide_height.data

        return tide_data

    def _get_tile_water_centroid(self, tile_id):
        """
        Get the coordinates of the water centroid for a Sentinel 2 tile.

        :param {String} tile_id: The Sentinel 2 tile ID.
        :return {Dict}
        """
        filtered_data = self.tile_water_centroids[
            self.tile_water_centroids["Name"] == tile_id
            ]
        return {"lat": filtered_data["Y"], "lon": filtered_data["X"]}

    def _set_hc(self, tile_id):
        """
        Set the harmonic constituants for a specified Sentinel 2 tile.

        :param {String} tile_id: The Sentinel 2 tile ID.
        """
        # get coordinates for center of image
        centroid = self._get_tile_water_centroid(tile_id)

        amp, ph = pyTMD.io.FES.interpolate_constants(
            centroid["lon"],
            centroid["lat"],
            self.constant_constituents,
            scale=self.model.scale,
            method="spline",
            extrapolate=True,
        )

        # calculate complex phase in radians for Euler's
        cph = -1j * ph * np.pi / 180.0

        # calculate constituent oscillation
        self.hc = amp * np.exp(cph)

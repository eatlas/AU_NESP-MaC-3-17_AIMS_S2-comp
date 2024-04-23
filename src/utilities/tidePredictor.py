from datetime import timedelta
import numpy as np
import pyTMD.io
import pyTMD.time
import pyTMD.predict
import pyTMD.tools
import pyTMD.utilities

DATA_PATH = "./../data/"


class TidePredictor:
    """This class can be used to predict tide elevation for a certain date time"""

    class TIDE_TYPE:
        INCOMING_TIDE= "incoming tide"
        PEAK_HIGH_TIDE= "peak high tide"
        OUTGOING_TIDE= "outgoing tide"
        PEAK_LOW_TIDE= "peak low tide"


    def __init__(self, tile_id):
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
            delimiter=",",
            names=True,
            dtype=None,
            encoding=None,
        )

        self.hc = None
        self._set_hc(tile_id)

    def get_tide_elevation(self, image_date_time):
        """
        Predict the tide elevation for an image time stamp.

        :param {datetime} image_date_time: The image time stamp as datetime object
        :return: {int, string} The tide elevation as signed int and a string describing incoming tide, 
                                    peak high tide, peak low tide, outgoing tide.
        """
        # move image date time back one hour to add tw0 hours before and after, covering a five hour period
        # to determine the tide type (incoming, outgoing, etc). 
        date_time = image_date_time - timedelta(hours=2)
        time_series_minutes =  np.arange(300, step=120)

        # convert time from MJD to days relative to Jan 1, 1992 (48622 MJD)
        tide_time = pyTMD.time.convert_calendar_dates(
            date_time.year, date_time.month, date_time.day, date_time.hour, minute=time_series_minutes
        )

        DELTAT = pyTMD.time.interpolate_delta_time(
            pyTMD.utilities.get_data_path(["data", "merged_deltat.data"]), tide_time
        )

        tide_height = pyTMD.predict.time_series(
            tide_time, self.hc, self.model_constituents, deltat=DELTAT, corrections=self.model.format
        )
        tide_data = tide_height.data

        # determine tide type
        tide_type = ""
        if tide_data[0] > tide_data[1] > tide_data[2]:
            tide_type = self.TIDE_TYPE.OUTGOING_TIDE
        elif tide_data[0] < tide_data[1] > tide_data[2]:
            tide_type = self.TIDE_TYPE.PEAK_HIGH_TIDE
        elif tide_data[0] < tide_data[1] < tide_data[2]:
            tide_type = self.TIDE_TYPE.INCOMING_TIDE
        elif tide_data[0] > tide_data[1] < tide_data[2]:
            tide_type = self.TIDE_TYPE.PEAK_LOW_TIDE

        return tide_data[1], tide_type

    def _get_tile_water_centroid(self, tile_id):
        filtered_data = self.tile_water_centroids[
            self.tile_water_centroids["Name"] == tile_id
        ]
        return {"lat": filtered_data["Y"], "lon": filtered_data["X"]}

    
    def _set_hc(self, tile_id):
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
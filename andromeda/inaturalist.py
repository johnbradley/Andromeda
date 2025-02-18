import io
import csv
import pandas as pd
from pyinaturalist import get_observations
from satellitedata import add_satellite_rgb_data, add_satellite_landcover_data

LABEL_FIELD = "Image_Label"
URL_FIELD = "Image_Link"
SPECIES_FIELD = "Species"
USER_FIELD = "User"
DATE_FIELD = "Date"
TIME_FIELD = "Time"
SECONDS_FIELD = "Seconds"
PLACE_FIELD = "Place"
LAT_FIELD = "Lat"
LON_FIELD = "Long"
CSV_FIELDS = [
    LABEL_FIELD,
    URL_FIELD,
    SPECIES_FIELD,
    USER_FIELD,
    DATE_FIELD,
    TIME_FIELD,
    SECONDS_FIELD,
    PLACE_FIELD,
    LAT_FIELD,
    LON_FIELD,
]
OBSERVED_ON_MISSING_MSG = """
One or more observations are missing the 'Observed' date/time value.
Please manually add this information to the observation(s) in the inaturalist.org website.
"""


class BadObservationException(Exception):
    pass


class Observations(object):
    def __init__(self, fieldnames):
        self.fieldnames = fieldnames
        self.data = []
        self.warnings = set()

    def add(self, row):
        self.data.append(row)

    def add_warning(self, warning):
        self.warnings.add(warning)

    def add_fieldnames(self, new_fieldnames):
        self.fieldnames.extend(new_fieldnames)


def get_inaturalist_observations(user_id, add_sat_rgb_data, add_landcover_data):
    idx = 0
    missing_lat_long = False
    observations = Observations(fieldnames=CSV_FIELDS[:])
    observations_response = get_observations(user_id=user_id, page="all")
    for obs in observations_response["results"]:
        observed_on = obs.get("observed_on")
        if not observed_on:
            raise BadObservationException(OBSERVED_ON_MISSING_MSG)
        idx += 1
        label = f"p{idx}"
        df = pd.DataFrame.from_dict(obs, orient="index")
        # Get image urls
        if obs.get("photos"):
            # Replace image size from 'square' to 'medium' and 'large'
            image_url = obs.get("photos")[0].get("url").replace("square", "medium")
        else:
            image_url = None
        observed_on = pd.to_datetime(observed_on)
        observed_seconds = (
            observed_on.hour * 3600 + observed_on.minute * 60 + observed_on.second
        )
        if obs.get("location"):
            lat = obs.get("location")[0]
            lon = obs.get("location")[1]
        else:
            lat = None
            lon = None
        place_guess = obs.get("place_guess")
        user_login = obs.get("user", {}).get("login")
        if not lat or not lon:
            missing_lat_long = True
        observations.add(
            {
                LABEL_FIELD: label,
                URL_FIELD: image_url,
                SPECIES_FIELD: obs.get("species_guess"),
                USER_FIELD: user_login,
                DATE_FIELD: observed_on.strftime("%Y-%m-%d"),
                TIME_FIELD: observed_on.strftime("%H:%M:%S"),
                SECONDS_FIELD: observed_seconds,
                PLACE_FIELD: place_guess,
                LAT_FIELD: lat,
                LON_FIELD: lon,
            }
        )
    if missing_lat_long:
        observations.add_warning("missing_lat_long")

    if add_sat_rgb_data:
        add_satellite_rgb_data(observations, LAT_FIELD, LON_FIELD)

    if add_landcover_data:
        add_satellite_landcover_data(observations, LAT_FIELD, LON_FIELD)

    return observations


def create_csv_str(fieldnames, observations):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for obs in observations:
        writer.writerow(obs)
    return output.getvalue()

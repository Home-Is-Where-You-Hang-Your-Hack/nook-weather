"""Zip to latitude and longitude."""

from geopy.geocoders import Nominatim  # type: ignore


class zipToLatLong:
    """Zip to latitude and longitude."""

    latitude: float = 0
    longitude: float = 0

    def query(self, zip_code: str) -> None:
        """Convert US Zip code to Latitude/longitude."""
        if self.latitude == 0:
            parameters = {"postalcode": zip_code, "country": "US"}
            geolocator = Nominatim(user_agent="thecase/nook-weather")
            location = geolocator.geocode(parameters)

            if location is not None:
                self.latitude = float(location.latitude)
                self.longitude = float(location.longitude)
            else:
                raise ValueError

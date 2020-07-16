"""NWS Nook Weather."""
import sys
import aiohttp
import asyncio

from dateutil.parser import parse
from dateutil import tz
from datetime import datetime, tzinfo

from typing import Union, List, Optional

import pynws  # type: ignore

from const import NWS_WEATHER_ICON_MAP


def compass(bearing: Union[str, None]) -> str:
    """Wind degrees to direction."""
    if bearing is None:
        return ""

    coords = {
        "N": [0, 22.5],
        "NE": [22.5, 67.5],
        "E": [67.5, 112.5],
        "SE": [112.5, 157.5],
        "S": [157.5, 202.5],
        "SW": [202.5, 247.5],
        "W": [247.5, 292.5],
        "NW": [292.5, 337.5],
    }
    for key, val in coords.items():
        if val[0] <= float(bearing) < val[1]:
            return key

    # "N": [337.5, 360],
    return "N"


def convert_to_f(temperature: Union[float, None]) -> Union[float, None]:
    """Convert celsius to fahrenheit."""
    if isinstance(temperature, float) or isinstance(temperature, int):
        return float((temperature * 1.8) + 32)
    return None


def format_temperature(temperature: Union[float, None]) -> str:
    """Format temperature value for display."""
    if isinstance(temperature, float) or isinstance(temperature, int):
        return str(int(temperature)) + "°"
    return "N/A"


def weather_icon(nws_icon_url: str, is_daytime: bool) -> str:
    """Determine Eink friendly icon from icon provided from API."""
    condition = nws_icon_url.split("?")[0].split(",")[0].split("/")[-1]

    if is_daytime or "night" not in NWS_WEATHER_ICON_MAP[condition]:
        wi_icon = NWS_WEATHER_ICON_MAP[condition]["day"]
    else:
        wi_icon = NWS_WEATHER_ICON_MAP[condition]["night"]

    return "/static/png/" + wi_icon + ".png"


class nwsDailyForecast:
    """NWS Daily Forecast."""

    _datetime_obj: datetime
    _high_temp_in_f: Optional[float]
    _low_temp_in_f: Optional[float]
    icon: str
    shortForecast: str

    def __init__(self, day_one={}, day_two={}) -> None:
        """Initialize."""
        if day_one.get("isDaytime"):
            self.icon = day_one.get("icon")
            self._date_time_obj = parse(day_one.get("startTime"))
            self.short_forecast = day_one.get("shortForecast")
        else:
            self.icon = day_two.get("icon")
            self._date_time_obj = parse(day_two.get("startTime"))
            self.short_forecast = day_two.get("shortForecast")

        temp_one = day_one.get("temperature")
        temp_two = day_two.get("temperature")

        self._low_temp_in_f = min(temp_one, temp_two)
        self._high_temp_in_f = max(temp_one, temp_two)

    @property
    def day_of_week(self) -> str:
        """Return day of week."""
        return self._date_time_obj.strftime("%A")

    @property
    def date(self) -> str:
        """Return month/day (example: 7/4 for July 4th)."""
        return self._date_time_obj.strftime("%A")

    @property
    def low_temperature(self) -> str:
        """Today's low in Fahrenheit."""
        return format_temperature(self._low_temp_in_f)

    @property
    def high_temperature(self) -> str:
        """Today's ligh in Fahrenheit."""
        return format_temperature(self._high_temp_in_f)

    @property
    def icon_src(self) -> str:
        """Image src path for icon."""
        return weather_icon(self.icon, True)


class nwsHourlyForecast:
    """NWS Hourly Forecast."""

    _datetime_obj: datetime
    _temp_in_f: Optional[float]
    icon: str
    isDaytime: bool
    shortForecast: str

    def __init__(self, hourly_data={}) -> None:
        """Initialize."""
        self._datetime_obj = parse(hourly_data.get("startTime"))
        self._temp_in_f = hourly_data.get("temperature")
        self.icon = hourly_data.get("icon")
        self.isDaytime = hourly_data.get("isDaytime")
        self.short_forecast = hourly_data.get("shortForecast")

    @property
    def time(self) -> str:
        """Return 12 hour time format of hour."""
        return self._datetime_obj.strftime("%-I %p")

    @property
    def temperature(self) -> str:
        """Hour's temperature in Fahrenheit."""
        return format_temperature(self._temp_in_f)

    @property
    def icon_src(self) -> str:
        """Image src path for icon."""
        return weather_icon(self.icon, self.isDaytime)


class nookDisplayedWeather:
    """Cast NWS forecast from pynws."""

    _datetime_obj: datetime
    _temp_in_c: float
    _temp_in_f: Optional[float]
    _barometric_pressure: Optional[float]
    _relative_humidity: Optional[float]
    _todays_high_in_f: Optional[float]
    _todays_low_in_f: Optional[float]
    _wind_direction: str
    _wind_speed: Optional[float]
    timeZone: Optional[tzinfo]
    isDaytime: bool

    detailed_forecast: str
    short_forecast: str

    icon: str
    is_valid: bool

    hourly_forecast: List[nwsHourlyForecast]
    daily_forecast: List[nwsDailyForecast]

    def __init__(self, timeZone: str, location: str) -> None:
        """Initialize."""
        self.is_valid = False
        self.hourly_forecast = []
        self.daily_forecast = []
        if timeZone:
            self.timeZone = tz.gettz(timeZone)

        self.location = location

    @property
    def todays_date(self) -> str:
        """Date from timestamp (example: 'Saturday, July 11 2020')."""
        return self._datetime_obj.strftime("%A, %B %d %Y")

    @property
    def last_updated(self) -> str:
        """Last updated timestamp (example: '2020-07-11 7:52PM EDT')."""
        return self._datetime_obj.strftime("%Y-%m-%d %I:%M%p %Z")

    @property
    def temperature(self) -> str:
        """Hour's temperature in Fahrenheit."""
        return format_temperature(self._temp_in_f)

    @property
    def icon_src(self) -> str:
        """Image src path for icon."""
        return weather_icon(self.icon, self.isDaytime)

    @property
    def todays_high_temperature(self) -> str:
        """Today high temperature in Fahrenheit."""
        return format_temperature(self._todays_high_in_f)

    @property
    def todays_low_temperature(self) -> str:
        """Today low temperature in Fahrenheit."""
        return format_temperature(self._todays_low_in_f)

    @property
    def current_wind(self) -> str:
        """Return current wind conditions."""
        if self._wind_speed is None:
            return "N/A"
        return str(int(self._wind_speed)) + " MPH " + self._wind_direction

    @property
    def current_humidity(self) -> str:
        """Return current humidity."""
        if self._relative_humidity is None:
            return "N/A"
        return str(int(self._relative_humidity)) + "%"

    @property
    def current_pressure(self) -> str:
        """Return current barometric pressure."""
        if self._barometric_pressure is None:
            return "N/A"
        return str(int(self._barometric_pressure) / 100) + " mb"

    def updateWeather(self, current_data, hourly_data, daily_data) -> None:
        """Update weather data."""
        if len(hourly_data) < 11 or len(daily_data) < 11:
            self.is_valid = False
            return
        if current_data.get("timestamp") and self.timeZone:
            utc_date_time_obj = parse(current_data.get("timestamp"))
            self._datetime_obj = utc_date_time_obj.astimezone(self.timeZone)

        self._wind_speed = current_data.get("windSpeed")
        self._wind_direction = compass(current_data.get("windDirection"))
        self._relative_humidity = current_data.get("relativeHumidity")
        self._barometric_pressure = current_data.get("barometricPressure")

        first_daily_temp = daily_data[0].get("temperature")
        second_daily_temp = daily_data[1].get("temperature")
        self.isDaytime = hourly_data[0].get("isDaytime")

        self._temp_in_c = current_data.get("temperature")
        self._temp_in_f = convert_to_f(self._temp_in_c)

        # NOTE: only available when all stations are reporing
        self.short_forecast = hourly_data[0].get("shortForecast")
        self.detailed_forecast = daily_data[0].get("detailedForecast")

        self._todays_high_in_f = max(first_daily_temp, second_daily_temp)
        self._todays_low_in_f = min(first_daily_temp, second_daily_temp)

        self.icon = hourly_data[0].get("icon")

        # Hourly forecast for next few hours
        for i in [2, 4, 6, 8, 10, 12]:
            self.hourly_forecast.append(nwsHourlyForecast(hourly_data[i]))

        # Daily forecast in 12 hour sements, determine weather for next 6 days
        for i in [0, 2, 4, 6, 8, 10]:
            self.daily_forecast.append(
                nwsDailyForecast(daily_data[i], daily_data[i + 1])
            )
        self.is_valid = True


class nwsNookWeather:
    """NWS Nook Weather."""

    zip_code: str
    nws_user_id: str
    latitude: float
    longitude: float
    station: str
    displayedWeather: nookDisplayedWeather

    def setLocation(self, latitude: float, longitude: float) -> None:
        """Set Latitude and longitude."""
        self.latitude = latitude
        self.longitude = longitude

    def setUserName(self, nws_user_id: str) -> None:
        """Set Latitude and longitude."""
        self.nws_user_id = nws_user_id

    async def get_weather_station(self, session) -> None:
        """Query weather station information."""
        try:
            res = await pynws.raw_points_stations(
                self.latitude, self.longitude, session, self.nws_user_id
            )
            station = res["features"][0]["properties"]
            self.station = str(station["stationIdentifier"])
            self.location = str(station["name"])
            self.timeZone = str(station["timeZone"])
        except Exception:
            print("Failed to determine weather station", sys.exc_info()[0])

    async def get_async_weather(self) -> None:
        """Call NWS API."""
        async with aiohttp.ClientSession() as session:
            if not hasattr(self, "station"):
                await self.get_weather_station(session)
            try:
                nws = pynws.SimpleNWS(
                    self.latitude, self.longitude, self.nws_user_id, session
                )

                await nws.set_station()
                await nws.update_observation(1)
                await nws.update_forecast()
                await nws.update_forecast_hourly()

                self.displayedWeather = nookDisplayedWeather(
                    self.timeZone, self.location
                )

                if nws.observation and nws.forecast_hourly and nws.forecast:
                    self.displayedWeather.updateWeather(
                        nws.observation, nws.forecast_hourly, nws.forecast
                    )

            except aiohttp.ClientResponseError:
                pass

    def get_weather(self) -> Union[nookDisplayedWeather, None]:
        """Fetch weather from NWS API for the given postalcode."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.get_async_weather())

        if hasattr(self, "displayedWeather"):
            return self.displayedWeather
        return None

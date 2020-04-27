"""Host NWS weather forcast for Nook Siple Touch."""
#!/usr/bin/env python

import os
import sys
import time
import asyncio
from dateutil.parser import parse
from dateutil import tz
from datetime import timezone

import aiohttp

import pynws
from flask import Flask
from flask import render_template
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError

from const import NWS_WEATHER_ICON_MAP


class nwsNookWeather:
    """NWS Nook Weather."""

    def __init__(self):
        self.zip_code = os.environ["ZIP_CODE"]
        self.nws_user_id = os.environ["EMAIL"]

        # Start off on Null Island
        self.lat = 0
        self.long = 0
        self.station = None

        self.get_location()

    def compass(self, bearing):
        """Wind degrees to direction"""
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
            if val[0] <= bearing < val[1]:
                return key

        # "N": [337.5, 360],
        return "N"

    def convert_to_fahrenheit(self, temperature):
        if temperature["value"] is None:
            return "N/A"

        """Convert celsius to fahrenheit"""
        if temperature["unitCode"] == "unit:degC":
            return (temperature["value"] * 1.8) + 32
        return temperature["value"]

    def get_location(self):
        """Latitude and longitude from postal zip code."""
        ZIP_ERROR_MSG = "ERROR Cannot determine location from ZIP_CODE."

        try:
            parameters = {"postalcode": str(self.zip_code), "country": "US"}

            geolocator = Nominatim(user_agent="thecase/nook-weather")
            location = geolocator.geocode(parameters)

            if location is None:
                print(ZIP_ERROR_MSG, "please try another")
                sys.exit(1)

            self.lat = location.latitude
            self.long = location.longitude
        except GeopyError:
            print(ZIP_ERROR_MSG, sys.exc_info()[0])
            sys.exit(1)
        except:
            print("Unexpected error:", sys.exc_info()[0])
            sys.exit(1)

    def template_data(self):
        return {
            "now": self.now,
            "hourly": self.hourly,
            "daily": self.daily,
        }

    async def get_async_weather(self):
        """Call NWS API"""
        async with aiohttp.ClientSession() as session:
            if self.station is None:
                try:
                    res = await pynws.get_stn_from_pnt(
                        self.lat, self.long, session, self.nws_user_id
                    )
                    station = res["features"][0]["properties"]

                    self.station = station["stationIdentifier"]
                    self.location = station["name"]
                    self.timeZone = station["timeZone"]

                except:
                    print("Failed to determine weather station", sys.exc_info()[0])

            latlong = (self.lat, self.long)
            nws = pynws.Nws(
                session, latlon=latlong, station=self.station, userid=self.nws_user_id,
            )

            observation = await nws.observations(1)
            daily = await nws.forecast()
            hourly = await nws.forecast_hourly()

            if observation and daily and hourly:
                return self.format_data(observation[0], hourly, daily)

            return self.template_data()

    def get_weather(self):
        """Fetch weather from NWS API for the given postalcode."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        nws = loop.run_until_complete(self.get_async_weather())
        return nws

    def weather_icon(self, nws_icon_url, is_daytime):
        """Determine Eink friendly icon from icon provided from API."""
        condition = nws_icon_url.split("?")[0].split(",")[0].split("/")[-1]

        if is_daytime or "night" not in NWS_WEATHER_ICON_MAP[condition]:
            wi_icon = NWS_WEATHER_ICON_MAP[condition]["day"]
        else:
            wi_icon = NWS_WEATHER_ICON_MAP[condition]["night"]

        return "/static/png/" + wi_icon + ".png"

    def format_data(self, observation_data, hourly_data, daily_data):
        """Format weather data."""
        utc_date_time_obj = parse(observation_data["timestamp"])
        date_time_obj = utc_date_time_obj.astimezone(tz.gettz(self.timeZone))

        now = {}
        now["time"] = date_time_obj.strftime("%A, %B %d %Y")
        now["timestamp"] = date_time_obj.strftime("%Y-%m-%d %I:%M%p %Z")
        now["city"] = self.location

        # only available when all stations are reporing
        now["hour"] = hourly_data[0]["shortForecast"]
        now["forecast"] = daily_data[0]["detailedForecast"]

        now["high"] = max(daily_data[0]["temperature"], daily_data[1]["temperature"])
        now["low"] = min(daily_data[0]["temperature"], daily_data[1]["temperature"])
        now["windSpeed"] = observation_data["windSpeed"]["value"]
        now["windDir"] = self.compass(observation_data["windDirection"]["value"])
        now["icon"] = self.weather_icon(
            hourly_data[0]["icon"], hourly_data[0]["isDaytime"]
        )

        now["humidity"] = observation_data["relativeHumidity"]["value"]
        now["pressure"] = observation_data["barometricPressure"]["value"]
        now["temperature"] = self.convert_to_fahrenheit(observation_data["temperature"])

        hourly = list()
        for i in [2, 4, 6, 8, 10, 12]:
            date_time_obj = parse(hourly_data[i]["startTime"])
            hour = date_time_obj.strftime("%-I %p")
            hourly.append(
                {
                    "time": hour,
                    "icon": self.weather_icon(
                        hourly_data[i]["icon"], hourly_data[i]["isDaytime"]
                    ),
                    "shortForecast": hourly_data[i]["shortForecast"],
                    "temp": hourly_data[i]["temperature"],
                }
            )

        daily = list()
        i = 0
        while i < 12:
            if daily_data[i]["isDaytime"]:
                day_forecast = daily_data[i]
                night_forecast = daily_data[i + 1]
            else:
                day_forecast = daily_data[i + 1]
                night_forecast = daily_data[i]

            date_time_obj = parse(day_forecast["startTime"])
            date = date_time_obj.strftime("%m/%d")
            day = date_time_obj.strftime("%A")

            high = max(day_forecast["temperature"], night_forecast["temperature"])
            low = min(day_forecast["temperature"], night_forecast["temperature"])

            daily.append(
                {
                    "day": day,
                    "date": date,
                    "icon": self.weather_icon(
                        day_forecast["icon"], day_forecast["isDaytime"]
                    ),
                    "shortForecast": day_forecast["shortForecast"],
                    "high": high,
                    "low": low,
                }
            )
            i += 2

        self.now = now
        self.hourly = hourly
        self.daily = daily

        return self.template_data()


app = Flask(__name__)
nws = nwsNookWeather()


@app.route("/")
def index():
    """ index page function. """
    data = nws.get_weather()

    return render_template(
        "index.html", now=data["now"], hourly=data["hourly"], daily=data["daily"]
    )


if __name__ == "__main__":
    port = 3099

    if "ZIP_CODE" not in os.environ:
        print("ERROR Please set the environment variable ZIP_CODE")
        sys.exit(1)
    if "EMAIL" not in os.environ:
        print("ERROR Please set the environment variable EMAIL")
        sys.exit(1)
    if "BIND_PORT" in os.environ:
        port = int(os.environ["BIND_PORT"])

    app.run(debug=False, host="0.0.0.0", port=port)

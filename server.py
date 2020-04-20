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

from const import NWS_WEATHER_ICON_MAP


def compass(bearing):
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


def get_location():
    """Latitude and longitude from postal zip code."""
    geolocator = Nominatim(user_agent="thecase/nook-weather")
    location = geolocator.geocode(
        {"postalcode": str(os.environ["ZIP_CODE"]), "country": "US"}
    )

    if location is None:
        print("ERROR Cannot determine location from ZIP_CODE, please try another")
        sys.exit(1)

    return (location.latitude, location.longitude)


async def get_station(session, station):
    """NWS weather station name."""
    async with session.get("https://api.weather.gov/stations/" + station) as res:
        res.raise_for_status()
        obs = await res.json()
    return obs["properties"]


async def get_weather(latlong):
    """Call NWS API"""
    async with aiohttp.ClientSession() as session:
        nws = pynws.Nws(session, latlon=latlong, userid=os.environ["EMAIL"])
        stations = await nws.stations()
        nws.station = stations[0]
        station = await get_station(session, nws.station)

        observations = await nws.observations(1)
        daily = await nws.forecast()
        hourly = await nws.forecast_hourly()
        return {
            "currently": observations[0],
            "hourly": hourly,
            "daily": daily,
            "location": station["name"],
            "timeZone": station["timeZone"],
        }


def get_local_weather():
    """Fetch weather from NWS API for the given postalcode."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    latlong = get_location()
    nws = loop.run_until_complete(get_weather(latlong))
    return nws


def format_temperature(temperature):
    if temperature["value"] is None:
        return "N/A"

    """Convert celsius to fahrenheit"""
    if temperature["unitCode"] == "unit:degC":
        return (temperature["value"] * 1.8) + 32
    return temperature["value"]


def weather_icon(nws_icon_url, is_daytime):
    """Determine Eink friendly icon from icon provided from API."""
    condition = nws_icon_url.split("?")[0].split(",")[0].split("/")[-1]

    if is_daytime or "night" not in NWS_WEATHER_ICON_MAP[condition]:
        wi_icon = NWS_WEATHER_ICON_MAP[condition]["day"]
    else:
        wi_icon = NWS_WEATHER_ICON_MAP[condition]["night"]

    return "/static/png/" + wi_icon + ".png"


def process_data():
    """Format weather data."""
    data = get_local_weather()

    utc_date_time_obj = parse(data["currently"]["timestamp"])
    date_time_obj = utc_date_time_obj.astimezone(tz.gettz(data["timeZone"]))

    now = {}
    now["time"] = date_time_obj.strftime("%A, %B %d %Y")
    now["timestamp"] = date_time_obj.strftime("%Y-%m-%d %I:%M%p %Z")
    now["city"] = data["location"]

    # only available when all stations are reporing
    now["hour"] = data["hourly"][0]["shortForecast"]
    now["forecast"] = data["daily"][0]["detailedForecast"]

    now["high"] = max(data["daily"][0]["temperature"], data["daily"][1]["temperature"])
    now["low"] = min(data["daily"][0]["temperature"], data["daily"][1]["temperature"])
    now["windSpeed"] = data["currently"]["windSpeed"]["value"]
    now["windDir"] = compass(data["currently"]["windDirection"]["value"])
    now["icon"] = weather_icon(
        data["hourly"][0]["icon"], data["hourly"][0]["isDaytime"]
    )

    now["humidity"] = data["currently"]["relativeHumidity"]["value"]
    now["pressure"] = data["currently"]["barometricPressure"]["value"]
    now["temperature"] = format_temperature(data["currently"]["temperature"])

    hourly = list()
    for i in [2, 4, 6, 8, 10, 12]:
        forecast = data["hourly"][i]
        date_time_obj = parse(forecast["startTime"])
        hour = date_time_obj.strftime("%-I %p")
        hourly.append(
            {
                "time": hour,
                "icon": weather_icon(forecast["icon"], forecast["isDaytime"]),
                "shortForecast": forecast["shortForecast"],
                "temp": forecast["temperature"],
            }
        )

    daily = list()

    i = 0
    while i < 12:
        if data["daily"][i]["isDaytime"]:
            day_forecast = data["daily"][i]
            night_forecast = data["daily"][i + 1]
        else:
            day_forecast = data["daily"][i + 1]
            night_forecast = data["daily"][i]

        date_time_obj = parse(day_forecast["startTime"])
        date = date_time_obj.strftime("%m/%d")
        day = date_time_obj.strftime("%A")

        high = max(day_forecast["temperature"], night_forecast["temperature"])
        low = min(day_forecast["temperature"], night_forecast["temperature"])

        daily.append(
            {
                "day": day,
                "date": date,
                "icon": weather_icon(day_forecast["icon"], day_forecast["isDaytime"]),
                "shortForecast": day_forecast["shortForecast"],
                "high": high,
                "low": low,
            }
        )
        i += 2
    return {"now": now, "hourly": hourly, "daily": daily}


app = Flask(__name__)


@app.route("/")
def index():
    """ index page function. """
    data = process_data()
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

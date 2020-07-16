#!/usr/bin/env python
"""Host NWS weather forcast for Nook Siple Touch."""
import os
import sys

from flask import Flask
from flask import render_template

from zip_to_latlong import zipToLatLong
from nws_nook_weather import nwsNookWeather

app = Flask(__name__)
location = zipToLatLong()
nws = nwsNookWeather()


@app.route("/")
def index():
    """Index page function."""
    return render_template("index.html", data=nws.get_weather())


if __name__ == "__main__":
    port = 3099

    if "EMAIL" not in os.environ:
        print("ERROR Please set the environment variable EMAIL")
        sys.exit(1)
    else:
        nws.setUserName(str(os.environ["EMAIL"]))

    if "ZIP_CODE" not in os.environ:
        print("ERROR Please set the environment variable ZIP_CODE")
        sys.exit(1)
    try:
        location.query(str(os.environ["ZIP_CODE"]))
        nws.setLocation(location.latitude, location.longitude)
    except Exception:
        # TODO: retry if a 500 is given
        print("ERROR Cannot determine location from ZIP_CODE.")
        sys.exit(1)

    if "BIND_PORT" in os.environ:
        port = int(os.environ["BIND_PORT"])

    app.run(debug=True, host="0.0.0.0", port=port)

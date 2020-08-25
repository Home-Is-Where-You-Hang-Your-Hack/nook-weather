FROM python:3.7

RUN pip install requests flask pynws geopy python-dateutil

COPY const.py /
COPY ha_outdoor_values.py /
COPY nws_nook_weather.py /
COPY server.py /
COPY zip_to_latlong.py /
COPY static /static
COPY templates /templates

CMD ["python", "/server.py"]

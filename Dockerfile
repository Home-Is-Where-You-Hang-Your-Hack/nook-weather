FROM python:3.7

RUN pip install requests flask pynws geopy python-dateutil

COPY server.py /
COPY const.py /
COPY static /static
COPY templates /templates

CMD ["python", "/server.py"]

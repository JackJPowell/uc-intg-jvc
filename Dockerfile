FROM python:3.12-slim-bullseye

WORKDIR /app

COPY ./requirements.txt requirements.txt
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt
RUN mkdir /config

ADD . .

ENV UC_DISABLE_MDNS_PUBLISH="false"
ENV UC_MDNS_LOCAL_HOSTNAME=""

ENV UC_INTEGRATION_INTERFACE="0.0.0.0"
ENV UC_INTEGRATION_HTTP_PORT="9090"

ENV UC_CONFIG_HOME="/config"

CMD ["python3", "-u", "intg-jvc/driver.py"]
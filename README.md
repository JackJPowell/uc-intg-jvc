# JVC Projector integration for Remote Two

Using [uc-integration-api](https://github.com/aitatoi/integration-python-library)

The driver lets you enter the IP address of your JVC Projector and control it via your Unfolded Circle Remote.

## Media Player
Supported attributes:
- State
- Input

Supported commands:
- Turn on & off
- Back
- Directional pad navigation and select
- Top menu
- All supported JVC commands

## Remote
- Preconfigured UI with all available JVC Projector commands
- Preconfigured button layout to navigate the projector's UI

## Usage
The simpliest way to get started is by uploading this integration to your unfolded circle remote. You'll find the option on the integration tab in the web configurator. Simply upload the .tar.gz file attached to the release. This option is nice and doesn't require a separate docker instance to host the package. However, upgrading is a fully manual process. To help with this, a docker image is also provided that allows you to run it externally from the remote and easily upgrade when new versions are released. 

### Install on Remote

- Download tar.gz file from Releases section of this repository
- Upload the file to the remove via the integrations tab (Requires Remote firmware >= 2.0.0)

### Docker
```docker run -d --name=uc-intg-jvc -p 9090:9090 --restart unless-stopped ghcr.io/jackjpowell/uc-intg-jvc:latest```

### Docker Compose
```services:
     uc-intg-jvc:
       image: ghcr.io/jackjpowell/uc-intg-jvc:latest
       container_name: uc-intg-jvc
       ports:
         - 9090:9090
       restart: unless-stopped```

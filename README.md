# JVC Projector integration for Remote Two

Using [uc-integration-api](https://github.com/aitatoi/integration-python-library)

The driver lets you enter the IP address of your JVC Projector and control it via the Remote Two.

Supported attributes:
- State (on, standby, playing, paused, seeking, buffering, unknown)

Supported commands:
- Turn on & off (device will be put into standby)
- Back
- Directional pad navigation and select
- Top menu

## Usage
### Setup

- Requires Python 3.11
- Install required libraries:  
  (using a [virtual environment](https://docs.python.org/3/library/venv.html) is highly recommended)
```shell
pip3 install -r requirements.txt
```

### Run

```shell
python3 intg-jvc/driver.py
```

See available [environment variables](https://github.com/unfoldedcircle/integration-python-library#environment-variables)
in the Python integration library to control certain runtime features like listening interface and configuration directory.

The configuration file is loaded & saved from the path specified in the environment variable `UC_CONFIG_HOME`.
Otherwise, the `HOME` path is used or the working directory as fallback.

## Build Docker image

Simply run:
```shell
docker build .
```

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the
[tags and releases in this repository](https://github.com/jackjpowell/ucr2-integration-jvc/releases).

## Changelog

The major changes found in each new release are listed in the [changelog](CHANGELOG.md)
and under the GitHub [releases](https://github.com/jackjpowell/ucr2-integration-jvc/releases).

## License

This project is licensed under the [**Mozilla Public License 2.0**](https://choosealicense.com/licenses/mpl-2.0/).
See the [LICENSE](LICENSE) file for details.

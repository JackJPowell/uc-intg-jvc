"""This module contains some fixed variables, the media player entity definition class and the Setup class which includes all fixed and customizable variables"""

import json
import os
import logging
import ucapi

_LOG = logging.getLogger(__name__)

# TODO Integrate SDCP and SDAP port and PJTalk community as variables into the command handlers to replace the pySDCP default values
# TODO Make SDCP & SDAP ports and PJTalk community user configurable in an advanced setup option

# Fixed variables
SDCP_PORT = 53484  # Currently only used for port check during setup
SDAP_PORT = 53862  # Currently only used for port check during setup

simple_commands = [
    "LENS_MEMORY_1",
    "LENS_MEMORY_2",
    "LENS_MEMORY_3",
    "LENS_MEMORY_4",
    "LENS_MEMORY_5",
    "LENS_MEMORY_6",
    "LENS_MEMORY_7",
    "LENS_MEMORY_8",
    "LENS_MEMORY_9",
    "LENS_MEMORY_10",
    "INPUT_HDMI_1",
    "INPUT_HDMI_2",
    "PICTURE_MODE_FILM",
    "PICTURE_MODE_CINEMA",
    "PICTURE_MODE_NATURAL",
    "PICTURE_MODE_HDR10",
    "PICTURE_MODE_THX",
    "PICTURE_MODE_USER1",
    "PICTURE_MODE_USER2",
    "PICTURE_MODE_USER3",
    "PICTURE_MODE_USER4",
    "PICTURE_MODE_USER5",
    "PICTURE_MODE_USER6",
    "PICTURE_MODE_HLG",
    "PICTURE_MODE_FRAME_ADAPT_HDR",
    "PICTURE_MODE_HDR10P",
    "PICTURE_MODE_PANA_PQ",
    "LOW_LATENCY_ON",
    "LOW_LATENCY_OFF",
    "MASK_OFF",
    "MASK_CUSTOM1",
    "MASK_CUSTOM2",
    "MASK_CUSTOM3",
    "LAMP_LOW",
    "LAMP_MID",
    "LAMP_HIGH",
    "LENS_APERTURE_OFF",
    "LENS_APERTURE_AUTO1",
    "LENS_APERTURE_AUTO2",
    "LENS_ANIMORPHIC_OFF",
    "LENS_ANIMORPHIC_A",
    "LENS_ANIMORPHIC_B",
    "LENS_ANIMORPHIC_C",
    "LENS_ANIMORPHIC_D",
]


class MpDef:
    """Media player entity definition class that includes the device class, features, attributes and options"""

    device_class = ucapi.media_player.DeviceClasses.TV
    features = [
        ucapi.media_player.Features.ON_OFF,
        ucapi.media_player.Features.TOGGLE,
        ucapi.media_player.Features.DPAD,
        ucapi.media_player.Features.HOME,
        ucapi.media_player.Features.SELECT_SOURCE,
    ]
    attributes = {
        ucapi.media_player.Attributes.STATE: ucapi.media_player.States.UNKNOWN,
        ucapi.media_player.Attributes.SOURCE: "",
        ucapi.media_player.Attributes.SOURCE_LIST: ["HDMI 1", "HDMI 2"],
    }
    options = {ucapi.media_player.Options.SIMPLE_COMMANDS: simple_commands}


# class RemoteDef:
#     """Remote entity definition class that includes the features, attributes and simple commands"""
#     features = [
#         ucapi.remote.Features.ON_OFF,
#         ucapi.remote.Features.TOGGLE,
#         ]
#     attributes = {
#         ucapi.remote.Attributes.STATE: ucapi.remote.States.UNKNOWN
#         }
#     simple_commands = simple_commands


# class LTSensorDef:
#     """Lamp timer sensor entity definition class that includes the device class, attributes and options"""
#     device_class = ucapi.sensor.DeviceClasses.CUSTOM
#     attributes = {
#         ucapi.sensor.Attributes.STATE: ucapi.sensor.States.ON,
#         ucapi.sensor.Attributes.UNIT: "h"
#         }
#     options = {
#         ucapi.sensor.Options.CUSTOM_UNIT: "h"
#         }


class Setup:
    """Setup class which includes all fixed and customizable variables including functions to set() and get() them from a runtime storage
    which includes storing them in a json config file and as well as load() them from this file"""

    __conf = {
        "ip": "",
        "id": "",
        "name": "",
        "password":"",
        "setup_complete": False,
        "setup_reconfigure": False,
        "standby": False,
        "bundle_mode": False,
        "mp_poller_interval": 20,  # Use 0 to deactivate; will be automatically set to 0 when running on the remote (bundle_mode: True)
        "cfg_path": "config.json",
    }
    __setters = [
        "ip",
        "id",
        "name",
        "password",
        "setup_complete",
        "setup_reconfigure",
        "standby",
        "bundle_mode",
        "mp_poller_interval",
        "cfg_path",
    ]
    __storers = [
        "setup_complete",
        "ip",
        "id",
        "name",
        "password",
        "standby",
    ]  # Skip runtime only related keys in config file

    @staticmethod
    def get(key):
        """Get the value from the specified key in __conf"""
        if Setup.__conf[key] == "":
            raise ValueError("Got empty value for key " + key + " from runtime storage")
        return Setup.__conf[key]

    @staticmethod
    def set(key, value):
        """Set and store a value for the specified key into the runtime storage and config file.
        Storing setup_complete flag during reconfiguration will be ignored"""
        if key in Setup.__setters:
            if Setup.__conf["setup_reconfigure"] and key == "setup_complete":
                _LOG.debug(
                    "Ignore setting and storing setup_complete flag during reconfiguration"
                )
            else:
                Setup.__conf[key] = value
                _LOG.debug(
                    "Stored " + key + ": " + str(value) + " into runtime storage"
                )

                # Store key/value pair in config file
                if key in Setup.__storers:
                    jsondata = {key: value}
                    if os.path.isfile(Setup.__conf["cfg_path"]):
                        try:
                            with open(
                                Setup.__conf["cfg_path"], "r+", encoding="utf-8"
                            ) as f:
                                l = json.load(f)
                                l.update(jsondata)
                                f.seek(0)
                                f.truncate()  # Needed when the new value has less characters than the old value (e.g. false to true)
                                json.dump(l, f)
                                _LOG.debug(
                                    "Stored "
                                    + key
                                    + ": "
                                    + str(value)
                                    + " into "
                                    + Setup.__conf["cfg_path"]
                                )
                        except OSError as o:
                            raise OSError(o) from o
                        except Exception as e:
                            raise Exception(
                                "Error while storing "
                                + key
                                + ": "
                                + str(value)
                                + " into "
                                + Setup.__conf["cfg_path"]
                            ) from e

                    # Create config file first if it doesn't exists yet
                    else:
                        # Skip storing setup_complete if no config files exists
                        if key != "setup_complete":
                            try:
                                with open(
                                    Setup.__conf["cfg_path"], "w", encoding="utf-8"
                                ) as f:
                                    json.dump(jsondata, f)
                                _LOG.debug(
                                    "Stored "
                                    + key
                                    + ": "
                                    + str(value)
                                    + " into "
                                    + Setup.__conf["cfg_path"]
                                )
                            except OSError as o:
                                raise OSError(o) from o
                            except Exception as e:
                                raise Exception(
                                    "Error while storing "
                                    + key
                                    + ": "
                                    + str(value)
                                    + " into "
                                    + Setup.__conf["cfg_path"]
                                ) from e
                else:
                    _LOG.debug(
                        key
                        + " not found in __storers because it should not be stored in the config file"
                    )
        else:
            raise NameError(
                key + " not found in __setters because it should not be changed"
            )

    @staticmethod
    def load():
        """Load all variables from the config json file into the runtime storage"""
        if os.path.isfile(Setup.__conf["cfg_path"]):
            try:
                with open(Setup.__conf["cfg_path"], "r", encoding="utf-8") as f:
                    configfile = json.load(f)
            except Exception as e:
                raise OSError("Error while reading " + Setup.__conf["cfg_path"]) from e
            if configfile == "":
                raise OSError("Error in " + Setup.__conf["cfg_path"] + ". No data")

            Setup.__conf["setup_complete"] = configfile["setup_complete"]
            _LOG.debug(
                "Loaded setup_complete: "
                + str(configfile["setup_complete"])
                + " into runtime storage from "
                + Setup.__conf["cfg_path"]
            )

            if not Setup.__conf["setup_complete"]:
                _LOG.warning(
                    "The setup was not completed the last time. Please restart the setup process"
                )
            else:
                if "ip" in configfile:
                    Setup.__conf["ip"] = configfile["ip"]
                    _LOG.debug(
                        "Loaded ip into runtime storage from "
                        + Setup.__conf["cfg_path"]
                    )
                else:
                    _LOG.debug(
                        "Skip loading ip as it's not yet stored in the config file"
                    )

                if "id" and "name" in configfile:
                    Setup.__conf["id"] = configfile["id"]
                    Setup.__conf["name"] = configfile["name"]
                    _LOG.debug(
                        "Loaded id and name into runtime storage from "
                        + Setup.__conf["cfg_path"]
                    )
                else:
                    _LOG.debug(
                        "Skip loading id and name as there are not yet stored in the config file"
                    )

        else:
            _LOG.info(
                Setup.__conf["cfg_path"]
                + " does not exist (yet). Please start the setup process"
            )

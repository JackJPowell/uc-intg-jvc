#!/usr/bin/env python3

"""Module that includes functions to execute pySDCP commands"""

import logging

import ucapi
from jvc_projector_remote import JVCProjector

import config
import driver

_LOG = logging.getLogger(__name__)


class Projector:
    def __init__(self, address=str, password: str | None = None) -> None:
        self._address = address
        self._client = JVCProjector(
            self._address,
            password=password,
            port=20554,
            delay_ms=600,
            connect_timeout=10,
            max_retries=10,
        )

    def get_attr_power(self):
        """Get the current power state from the projector and return the corresponding ucapi power state attribute"""
        try:
            power = self._client.command("power")
            _LOG.debug("Power State: %s", power)
            if power == "lamp_on":
                return ucapi.media_player.States.ON
            return ucapi.media_player.States.OFF
        except (Exception, ConnectionError) as e:
            raise Exception(e) from e

    def get_attr_source(self):
        """Get the current input source from the projector and return it as a string"""
        try:
            return self._client.command("input")
        except (Exception, ConnectionError) as e:
            raise Exception(e) from e

    async def send_cmd(self, entity_id: str, cmd_name: str, params=None):
        """Send a command to the projector and raise an exception if it fails"""

        mp_id = config.Setup.get("id")

        def cmd_error(msg: str = None):
            if msg is None:
                _LOG.error("Error while executing the command: " + cmd_name)
                raise Exception(msg)
            _LOG.error(msg)
            raise Exception(msg)

        match cmd_name:
            case ucapi.media_player.Commands.ON:
                try:
                    _LOG.debug("Prior to sending Power on command the assumed state is: %s", driver.api.configured_entities.get("state",""))
                    if not self._client.is_on:
                        _LOG.debug("The projector reported the state as off. Powering on.")
                        self._client.power_on()
                        _LOG.debug("Follow up debug statement after command power on send.")
                    driver.api.configured_entities.update_attributes(
                        entity_id,
                        {
                            ucapi.media_player.Attributes.STATE: ucapi.media_player.States.ON
                        },
                    )
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.OFF:
                try:
                    _LOG.debug("Prior to sending Power off command the assumed state is: %s", driver.api.configured_entities.get("state",""))
                    if self._client.is_on:
                        _LOG.debug("The projector reported the state as on. Powering off.")
                        self._client.power_off()
                        _LOG.debug("Follow up debug statement after command power off send.")
                    driver.api.configured_entities.update_attributes(
                        entity_id,
                        {
                            ucapi.media_player.Attributes.STATE: ucapi.media_player.States.OFF
                        },
                    )
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.TOGGLE:
                try:
                    _LOG.debug("Toggling Power requested.")
                    if self._client.is_on:
                        self._client.power_off()
                        driver.api.configured_entities.update_attributes(
                            entity_id,
                            {
                                ucapi.media_player.Attributes.STATE: ucapi.media_player.States.OFF
                            },
                        )
                    else:
                        self._client.power_on()
                        driver.api.configured_entities.update_attributes(
                            entity_id,
                            {
                                ucapi.media_player.Attributes.STATE: ucapi.media_player.States.ON
                            },
                        )
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case (
                ucapi.media_player.Commands.SELECT_SOURCE
                | "INPUT_HDMI_1"
                | "INPUT_HDMI_2"
            ):
                if params:
                    source = params["source"]
                else:
                    source = cmd_name.replace("INPUT_", "").replace("_", " ")

                try:
                    if source == "HDMI 1":
                        self._client.command("input-hdmi1")
                        driver.api.configured_entities.update_attributes(
                            mp_id, {ucapi.media_player.Attributes.SOURCE: source}
                        )
                    elif source == "HDMI 2":
                        self._client.command("input-hdmi2")
                        driver.api.configured_entities.update_attributes(
                            mp_id, {ucapi.media_player.Attributes.SOURCE: source}
                        )
                    else:
                        cmd_error("Unknown source: " + source)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.HOME | "HOME" | "MENU":
                try:
                    self._client.command("menu-menu")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.BACK | "BACK":
                try:
                    self._client.command("menu-back")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.CURSOR_ENTER | "BACK":
                try:
                    self._client.command("menu-ok")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.CURSOR_UP | "BACK":
                try:
                    self._client.command("menu-up")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.CURSOR_RIGHT | "BACK":
                try:
                    self._client.command("menu-right")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.CURSOR_DOWN | "BACK":
                try:
                    self._client.command("menu-down")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case ucapi.media_player.Commands.CURSOR_LEFT | "BACK":
                try:
                    self._client.command("menu-left")
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case (
                "PICTURE_MODE_FILM"
                | "PICTURE_MODE_CINEMA"
                | "PICTURE_MODE_NATURAL"
                | "PICTURE_MODE_HDR10"
                | "PICTURE_MODE_THX"
                | "PICTURE_MODE_USER1"
                | "PICTURE_MODE_USER2"
                | "PICTURE_MODE_USER3"
                | "PICTURE_MODE_USER4"
                | "PICTURE_MODE_USER5"
                | "PICTURE_MODE_USER6"
                | "PICTURE_MODE_HLG"
                | "PICTURE_MODE_FRAME_ADAPT_HDR"
                | "PICTURE_MODE_HDR10P"
                | "PICTURE_MODE_PANA_PQ"
            ):
                mode = cmd_name.replace("PICTURE_MODE_", "PICTURE_MODE-").lower()
                try:
                    self._client.command(mode)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case (
                "LENS_MEMORY_1"
                | "LENS_MEMORY_2"
                | "LENS_MEMORY_3"
                | "LENS_MEMORY_4"
                | "LENS_MEMORY_5"
                | "LENS_MEMORY_6"
                | "LENS_MEMORY_7"
                | "LENS_MEMORY_8"
                | "LENS_MEMORY_9"
                | "LENS_MEMORY_10"
            ):
                preset = cmd_name.replace("LENS_", "").lower()
                preset = preset.replace("_", "-")
                try:
                    self._client.command(preset)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case "LOW_LATENCY_ON" | "LOW_LATENCY_OFF":
                latency = cmd_name.replace("LOW_LATENCY_", "LOW_LATENCY-").lower()
                try:
                    self._client.command(latency)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case "MASK_OFF" | "MASK_CUSTOM1" | "MASK_CUSTOM2" | "MASK_CUSTOM3":
                mask = cmd_name.replace("_", "-")

                try:
                    self._client.command(mask)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case "LAMP_LOW" | "LAMP_MID" | "LAMP_HIGH":
                lamp = cmd_name.replace("_", "-").lower()
                try:
                    self._client.command(lamp)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case "LENS_APERTURE_OFF" | "LENS_APERTURE_AUTO1" | "LENS_APERTURE_AUTO2":
                lens = cmd_name.replace("LENS_", "")
                lens = lens.replace("_", "-").lower()
                try:
                    self._client.command(lens)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case (
                "LENS_ANIMORPHIC_OFF"
                | "LENS_ANIMORPHIC_A"
                | "LENS_ANIMORPHIC_B"
                | "LENS_ANIMORPHIC_C"
                | "LENS_ANIMORPHIC_D"
            ):
                lens = cmd_name.replace("LENS_", "")
                lens = lens.replace("_", "-").lower()
                try:
                    self._client.command(lens)
                except (Exception, ConnectionError) as e:
                    cmd_error(e)

            case _:
                cmd_error("Command not found or unsupported: " + cmd_name)

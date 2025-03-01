#!/usr/bin/env python3

"""Module that includes functions to add a remote entity with all available commands from the media player entity"""

import asyncio
import logging
from typing import Any
import time

import ucapi
import ucapi.ui

import driver
import config
from projector import Projector

_LOG = logging.getLogger(__name__)


async def update_rt(entity_id: str, ip: str, password: str | None = None):
    """Retrieve input source, power state and muted state from the projector, compare them with the known state on the remote and update them if necessary"""

    try:
        jvc = Projector(ip, password)
        state = jvc.get_attr_power()
    except Exception as e:
        _LOG.error(e)
        _LOG.warning("Can't get power status from projector. Set to Unavailable")
        state = {ucapi.remote.Attributes.STATE: ucapi.remote.States.UNAVAILABLE}

    try:
        api_update_attributes = driver.api.configured_entities.update_attributes(
            entity_id, state
        )
    except Exception as e:
        raise Exception(
            "Error while updating state attribute for entity id " + entity_id
        ) from e

    if not api_update_attributes:
        raise Exception(
            "Entity "
            + entity_id
            + " not found. Please make sure it's added as a configured entity on the remote"
        )
    else:
        _LOG.info(
            "Updated remote entity state attribute to "
            + str(state)
            + " for "
            + entity_id
        )


async def remote_cmd_handler(
    entity: ucapi.Remote, cmd_id: str, params: dict[str, Any] | None
) -> ucapi.StatusCodes:
    """
    Remote command handler.

    Called by the integration-API if a command is sent to a configured remote-entity.

    :param entity: remote entity
    :param cmd_id: command
    :param params: optional command parameters
    :return: status of the command
    """

    if not params:
        _LOG.info(f"Received {cmd_id} command for {entity.id}")
    else:
        _LOG.info(f"Received {cmd_id} command with parameter {params} for {entity.id}")
        repeat = params.get("repeat")
        delay = params.get("delay")
        hold = params.get("hold")

        if hold is None or hold == "":
            hold = 0
        if repeat is None:
            repeat = 1
        if delay is None:
            delay = 0
        else:
            delay = delay / 1000  # Convert milliseconds to seconds for sleep

        if repeat == 1 and delay != 0:
            _LOG.info(
                str(delay)
                + " seconds delay will be ignored as the command will not be repeated (repeat = 1)"
            )
            delay = 0

    password = None
    try:
        ip = config.Setup.get("ip")
        try:
            password = config.Setup.get("password")
        except ValueError:
            _LOG.debug("No password set")
        api = Projector(ip, password)
    except ValueError as v:
        _LOG.error(v)
        return ucapi.StatusCodes.SERVER_ERROR

    match cmd_id:
        case (
            ucapi.remote.Commands.ON
            | ucapi.remote.Commands.OFF
            | ucapi.remote.Commands.TOGGLE
        ):
            try:
                await api.send_cmd(entity.id, cmd_id)
            except Exception as e:
                if e is None:
                    return ucapi.StatusCodes.SERVER_ERROR
                return ucapi.StatusCodes.BAD_REQUEST
            return ucapi.StatusCodes.OK

        case ucapi.remote.Commands.SEND_CMD:
            command = params.get("command")

            try:
                i = 0
                r = range(repeat)
                for i in r:
                    i = i + 1
                    if repeat != 1:
                        _LOG.debug("Round " + str(i) + " for command " + command)
                    if hold != 0:
                        cmd_start = time.time() * 1000
                        while time.time() * 1000 - cmd_start < hold:
                            await api.send_cmd(entity.id, command)
                            await asyncio.sleep(0)
                    else:
                        await api.send_cmd(entity.id, command)
                        await asyncio.sleep(0)
                    await asyncio.sleep(delay)
            except Exception as e:
                if repeat != 1:
                    _LOG.warning(
                        "Execution of the command %s failed. Remaining %s repetitions will no longer be executed",
                        command,
                        str(repeat - 1),
                    )
                if e is None:
                    return ucapi.StatusCodes.SERVER_ERROR
                return ucapi.StatusCodes.BAD_REQUEST

            return ucapi.StatusCodes.OK

        case ucapi.remote.Commands.SEND_CMD_SEQUENCE:
            sequence = params.get("sequence")

            _LOG.info(f"Command sequence: {sequence}")

            for command in sequence:
                _LOG.debug("Sending command: " + command)
                try:
                    i = 0
                    r = range(repeat)
                    for i in r:
                        i = i + 1
                        if repeat != 1:
                            _LOG.debug("Round " + str(i) + " for command " + command)
                        if hold != 0:
                            cmd_start = time.time() * 1000
                            while time.time() * 1000 - cmd_start < hold:
                                await api.send_cmd(entity.id, command)
                                await asyncio.sleep(0)
                        else:
                            await api.send_cmd(entity.id, command)
                            await asyncio.sleep(0)
                        await asyncio.sleep(delay)
                except Exception as e:
                    if repeat != 1:
                        _LOG.warning(
                            "Execution of the command %s failed. Remaining %s repetitions will no longer be executed",
                            command,
                            str(repeat - 1),
                        )
                    if e is None:
                        return ucapi.StatusCodes.SERVER_ERROR
                    return ucapi.StatusCodes.BAD_REQUEST

            return ucapi.StatusCodes.OK

        case _:
            _LOG.info(f"Unsupported command: {cmd_id} for {entity.id}")
            return ucapi.StatusCodes.BAD_REQUEST


def create_button_mappings() -> list[ucapi.ui.DeviceButtonMapping | dict[str, Any]]:
    """Create the button mapping of the remote entity"""
    return [
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.DPAD_UP, "CURSOR_UP"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.DPAD_DOWN, "CURSOR_DOWN"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.DPAD_LEFT, "CURSOR_LEFT"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.DPAD_RIGHT, "CURSOR_RIGHT"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.DPAD_MIDDLE, "CURSOR_ENTER"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.GREEN, "BACK", "BACK"),
        ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.YELLOW, "MENU", "MENU"),
        ucapi.ui.create_btn_mapping(
            ucapi.ui.Buttons.RED, "LENS_MEMORY_1", "LENS_MEMORY_2"
        ),
        ucapi.ui.create_btn_mapping(
            ucapi.ui.Buttons.BLUE, "INPUT_HDMI_1", "INPUT_HDMI_2"
        ),
        ucapi.ui.create_btn_mapping(
            ucapi.ui.Buttons.POWER, ucapi.remote.Commands.TOGGLE
        ),
    ]


def create_ui_pages() -> list[ucapi.ui.UiPage | dict[str, Any]]:
    """Create a user interface with different pages that includes all commands"""

    ui_page1 = ucapi.ui.UiPage(
        "page1", "Power, Inputs & Settings", grid=ucapi.ui.Size(6, 6)
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "On", 0, 0, size=ucapi.ui.Size(2, 1), cmd=ucapi.remote.Commands.ON
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Off", 2, 0, size=ucapi.ui.Size(2, 1), cmd=ucapi.remote.Commands.OFF
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_icon(
            "uc:button",
            4,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.Commands.TOGGLE,
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_icon(
            "uc:info",
            0,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("MENU"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "HDMI 1",
            2,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("INPUT_HDMI_1"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "HDMI 2",
            4,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("INPUT_HDMI_2"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text("-- Low Latency --", 0, 2, size=ucapi.ui.Size(6, 1))
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "On",
            0,
            3,
            size=ucapi.ui.Size(3, 1),
            cmd=ucapi.remote.create_send_cmd("LOW_LATENCY_ON"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Off",
            3,
            3,
            size=ucapi.ui.Size(3, 1),
            cmd=ucapi.remote.create_send_cmd("LOW_LATENCY_OFF"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "-- Lamp Temperature --", 0, 4, size=ucapi.ui.Size(6, 1)
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Low",
            0,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LAMP_LOW"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Med",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LAMP_MID"),
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "High",
            4,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LAMP_HIGH"),
        )
    )

    ui_page2 = ucapi.ui.UiPage("page2", "Picture Modes", grid=ucapi.ui.Size(4, 8))
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Film",
            0,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_FILM"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Cinema",
            2,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_CINEMA"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Natural",
            0,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_NATURAL"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HDR10",
            2,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_HDR10"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "THX",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_THX"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 1",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER1"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 2",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER2"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 3",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER3"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 4",
            0,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER4"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 5",
            2,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER5"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 6",
            0,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_USER6"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HLG",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_HLG"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HDR10+",
            0,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_HDR10P"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "PAN PQ",
            2,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_PANA_PQ"),
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Frame Adapt HDR",
            0,
            7,
            size=ucapi.ui.Size(4, 1),
            cmd=ucapi.remote.create_send_cmd("PICTURE_MODE_FRAME_ADAPT_HDR"),
        )
    )

    ui_page3 = ucapi.ui.UiPage("page3", "Lens and Screen", grid=ucapi.ui.Size(4, 10))
    ui_page3.add(
        ucapi.ui.create_ui_text("-- Animorphic --", 0, 0, size=ucapi.ui.Size(4, 1))
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Off",
            0,
            1,
            size=ucapi.ui.Size(4, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_ANIMORPHIC_OFF"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "A",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_ANIMORPHIC_A"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "B",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_ANIMORPHIC_B"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "C",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_ANIMORPHIC_C"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "D",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_ANIMORPHIC_D"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text("-- Screen Mask --", 0, 4, size=ucapi.ui.Size(4, 1))
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Off",
            0,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("MASK_OFF"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "1",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("MASK_CUSTOM1"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "2",
            0,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("MASK_CUSTOM2"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "3",
            2,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("MASK_CUSTOM3"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text("-- Lens Aperture --", 0, 7, size=ucapi.ui.Size(4, 1))
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Off",
            0,
            8,
            size=ucapi.ui.Size(4, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_APERTURE_OFF"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Auto 1",
            0,
            9,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_APERTURE_AUTO1"),
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Auto 2",
            2,
            9,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_APERTURE_AUTO2"),
        )
    )
    ui_page4 = ucapi.ui.UiPage("page4", "Lens Memory", grid=ucapi.ui.Size(4, 5))
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 1",
            0,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_1"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 2",
            2,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_2"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 3",
            0,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_3"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 4",
            2,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_4"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 5",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_5"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 6",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_6"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 7",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_7"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 8",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_8"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 9",
            0,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_9"),
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 10",
            2,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=ucapi.remote.create_send_cmd("LENS_MEMORY_10"),
        )
    )

    return [ui_page1, ui_page2, ui_page3, ui_page4]


async def add_remote(ent_id: str, name: str):
    """Function to add a remote entity"""

    _LOG.info("Add projector remote entity with id " + ent_id + " and name " + name)

    definition = ucapi.Remote(
        ent_id,
        name,
        features=config.RemoteDef.features,
        attributes=config.RemoteDef.attributes,
        simple_commands=config.RemoteDef.simple_commands,
        button_mapping=create_button_mappings(),
        ui_pages=create_ui_pages(),
        cmd_handler=remote_cmd_handler,
    )

    _LOG.debug("Projector remote entity definition created")

    driver.api.available_entities.add(definition)

    _LOG.info("Added projector remote entity")

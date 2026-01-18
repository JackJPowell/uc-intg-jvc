"""# JVC Remote Control Integration"""

import asyncio
import logging
from typing import Any

import const
import projector
import ucapi
from const import (
    SimpleCommands,
    JVCConfig,
)
from jvcprojector import const as JvcConst
from ucapi import EntityTypes, Remote, StatusCodes, media_player
from ucapi.media_player import States as MediaStates
from ucapi.remote import Attributes, Commands, Features
from ucapi.remote import States as RemoteStates
from ucapi.ui import DeviceButtonMapping, UiPage
from ucapi_framework import create_entity_id

_LOG = logging.getLogger(__name__)

JVC_REMOTE_STATE_MAPPING = {
    MediaStates.UNKNOWN: RemoteStates.UNKNOWN,
    MediaStates.UNAVAILABLE: RemoteStates.UNAVAILABLE,
    MediaStates.OFF: RemoteStates.OFF,
    MediaStates.ON: RemoteStates.ON,
    MediaStates.STANDBY: RemoteStates.OFF,
}


class JVCRemote(Remote):
    """Representation of a JVC Remote entity."""

    def __init__(self, config_device: JVCConfig, device: projector.JVCProjector):
        """Initialize the class."""
        self._device: projector.JVCProjector = device
        _LOG.debug("JVC Remote init")
        entity_id = create_entity_id(EntityTypes.REMOTE, config_device.identifier)
        features = [Features.SEND_CMD, Features.ON_OFF, Features.TOGGLE]
        super().__init__(
            entity_id,
            f"{config_device.name} Remote",
            features,
            attributes={
                Attributes.STATE: device.state,
            },
            simple_commands=[member.value for member in SimpleCommands],
            button_mapping=JVC_REMOTE_BUTTONS_MAPPING,
            ui_pages=create_ui_pages(),
            cmd_handler=self.command_handler,  # type: ignore[arg-type]
        )

        # Register this remote entity with the device
        self._device.register_entity(entity_id, self)

    def get_int_param(self, param: str, params: dict[str, Any], default: int):
        """Get parameter in integer format."""
        try:
            value = params.get(param, default)
        except AttributeError:
            return default

        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default

    async def command_handler(
        self, entity: Remote, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        """
        Remote entity command handler.

        Called by the integration-API if a command is sent to a configured remote entity.

        :param entity: remote entity
        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command request
        """
        repeat = 1
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No JVC Projector instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE

        if params:
            repeat = self.get_int_param("repeat", params, 1)

        for _i in range(0, repeat):
            await self.handle_command(cmd_id, params)
        return StatusCodes.OK

    async def handle_command(
        self, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        """Handle command."""
        command = ""
        delay = 0

        if params:
            command = params.get("command", "")
            delay = self.get_int_param("delay", params, 0)

        if command == "":
            command = f"remote.{cmd_id}"

        _LOG.info("Got command request: %s %s", cmd_id, params if params else "")

        jvc = self._device
        res = None
        try:
            if command == "remote.on":
                _LOG.debug("Sending ON command to JVC")
                res = await jvc.send_command("powerOn")
            elif command == "remote.off":
                res = await jvc.send_command("powerOff")
            elif command == "remote.toggle":
                res = await jvc.send_command("powerToggle")
            elif cmd_id == Commands.SEND_CMD:
                match command:
                    case media_player.Commands.ON | "ON":
                        _LOG.debug("Sending ON command to JVC")
                        res = await jvc.send_command("powerOn")
                    case media_player.Commands.OFF | "OFF":
                        res = await jvc.send_command("powerOff")
                    case media_player.Commands.TOGGLE | "TOGGLE":
                        res = await jvc.send_command("powerToggle")
                    case media_player.Commands.CURSOR_UP | "CURSOR_UP":
                        res = await jvc.send_command("remote", code=JvcConst.REMOTE_UP)
                    case media_player.Commands.CURSOR_DOWN | "CURSOR_DOWN":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_DOWN
                        )
                    case media_player.Commands.CURSOR_LEFT | "CURSOR_LEFT":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_LEFT
                        )
                    case media_player.Commands.CURSOR_RIGHT | "CURSOR_RIGHT":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_RIGHT
                        )
                    case media_player.Commands.CURSOR_ENTER | "CURSOR_ENTER":
                        res = await jvc.send_command("remote", code=JvcConst.REMOTE_OK)
                    case media_player.Commands.BACK | "BACK":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_BACK
                        )
                    case media_player.Commands.INFO | "INFO":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_INFO
                        )
                    case media_player.Commands.MENU | "MENU":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_MENU
                        )
                    case media_player.Commands.SELECT_SOURCE:
                        if params:
                            await jvc.send_command(
                                "setInput",
                                source=params.get("source"),
                            )
                            asyncio.create_task(self._device.update_sensor("input"))
                    case "INPUT_HDMI_1":  # Special case for JVC HDMI 1 input
                        await jvc.send_command("setInput", source="HDMI1")
                        asyncio.create_task(self._device.update_sensor("input"))
                    case "INPUT_HDMI_2":  # Special case for JVC HDMI 2 input
                        await jvc.send_command("setInput", source="HDMI2")
                        asyncio.create_task(self._device.update_sensor("input"))
                    case SimpleCommands.REMOTE_ADVANCED_MENU | "REMOTE_ADVANCED_MENU":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_ADVANCED_MENU
                        )
                    case SimpleCommands.REMOTE_PICTURE_MODE | "REMOTE_PICTURE_MODE":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_PICTURE_MODE
                        )
                    case SimpleCommands.REMOTE_COLOR_PROFILE | "REMOTE_COLOR_PROFILE":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_COLOR_PROFILE
                        )
                    case SimpleCommands.REMOTE_LENS_CONTROL | "REMOTE_LENS_CONTROL":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_LENS_CONTROL
                        )
                    case SimpleCommands.REMOTE_SETTING_MEMORY | "REMOTE_SETTING_MEMORY":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_SETTING_MEMORY
                        )
                    case SimpleCommands.REMOTE_GAMMA_SETTINGS | "REMOTE_GAMMA_SETTINGS":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_GAMMA_SETTINGS
                        )
                    case SimpleCommands.REMOTE_CMD | "REMOTE_CMD":
                        res = await jvc.send_command("remote", code=JvcConst.REMOTE_CMD)
                    case SimpleCommands.REMOTE_MODE_1 | "REMOTE_MODE_1":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_MODE_1
                        )
                    case SimpleCommands.REMOTE_MODE_2 | "REMOTE_MODE_2":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_MODE_2
                        )
                    case SimpleCommands.REMOTE_MODE_3 | "REMOTE_MODE_3":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_MODE_3
                        )
                    case SimpleCommands.REMOTE_LENS_AP | "REMOTE_LENS_AP":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_LENS_AP
                        )
                    case SimpleCommands.REMOTE_ANAMO | "REMOTE_ANAMO":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_ANAMO
                        )
                    case SimpleCommands.REMOTE_GAMMA | "REMOTE_GAMMA":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_GAMMA
                        )
                    case SimpleCommands.REMOTE_COLOR_TEMP | "REMOTE_COLOR_TEMP":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_COLOR_TEMP
                        )
                    case SimpleCommands.REMOTE_3D_FORMAT | "REMOTE_3D_FORMAT":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_3D_FORMAT
                        )
                    case SimpleCommands.REMOTE_PIC_ADJ | "REMOTE_PIC_ADJ":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_PIC_ADJ
                        )
                    case SimpleCommands.REMOTE_NATURAL | "REMOTE_NATURAL":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_NATURAL
                        )
                    case SimpleCommands.REMOTE_CINEMA | "REMOTE_CINEMA":
                        res = await jvc.send_command(
                            "remote", code=JvcConst.REMOTE_CINEMA
                        )
                    case SimpleCommands.LENS_MEMORY_1 | "LENS_MEMORY_1":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_1)
                        )
                    case SimpleCommands.LENS_MEMORY_2 | "LENS_MEMORY_2":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_2)
                        )
                    case SimpleCommands.LENS_MEMORY_3 | "LENS_MEMORY_3":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_3)
                        )
                    case SimpleCommands.LENS_MEMORY_4 | "LENS_MEMORY_4":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_4)
                        )
                    case SimpleCommands.LENS_MEMORY_5 | "LENS_MEMORY_5":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_5)
                        )
                    case SimpleCommands.LENS_MEMORY_6 | "LENS_MEMORY_6":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_6)
                        )
                    case SimpleCommands.LENS_MEMORY_7 | "LENS_MEMORY_7":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_7)
                        )
                    case SimpleCommands.LENS_MEMORY_8 | "LENS_MEMORY_8":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_8)
                        )
                    case SimpleCommands.LENS_MEMORY_9 | "LENS_MEMORY_9":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_9)
                        )
                    case SimpleCommands.LENS_MEMORY_10 | "LENS_MEMORY_10":
                        asyncio.create_task(
                            jvc.send_command("operation", code=const.LENS_MEMORY_10)
                        )
                    case SimpleCommands.PICTURE_MODE_FILM | "PICTURE_MODE_FILM":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_FILM
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_CINEMA | "PICTURE_MODE_CINEMA":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_CINEMA
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_NATURAL | "PICTURE_MODE_NATURAL":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_NATURAL
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_HDR10 | "PICTURE_MODE_HDR10":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_HDR10
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_THX | "PICTURE_MODE_THX":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_THX
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER1 | "PICTURE_MODE_USER1":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER1
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER2 | "PICTURE_MODE_USER2":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER2
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER3 | "PICTURE_MODE_USER3":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER3
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER4 | "PICTURE_MODE_USER4":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER4
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER5 | "PICTURE_MODE_USER5":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER5
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_USER6 | "PICTURE_MODE_USER6":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_USER6
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_HLG | "PICTURE_MODE_HLG":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_HLG
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case (
                        SimpleCommands.PICTURE_MODE_FRAME_ADAPT_HDR
                        | "PICTURE_MODE_FRAME_ADAPT_HDR"
                    ):
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_FRAME_ADAPT_HDR
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_HDR10P | "PICTURE_MODE_HDR10P":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_HDR10P
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.PICTURE_MODE_PANA_PQ | "PICTURE_MODE_PANA_PQ":
                        res = await jvc.send_command(
                            "operation", code=const.PICTURE_MODE_PANA_PQ
                        )
                        asyncio.create_task(self._device.update_sensor("picture_mode"))
                    case SimpleCommands.LOW_LATENCY_ON | "LOW_LATENCY_ON":
                        res = await jvc.send_command(
                            "operation", code=const.LOW_LATENCY_ON
                        )
                        asyncio.create_task(self._device.update_sensor("low_latency"))
                    case SimpleCommands.LOW_LATENCY_OFF | "LOW_LATENCY_OFF":
                        res = await jvc.send_command(
                            "operation", code=const.LOW_LATENCY_OFF
                        )
                        asyncio.create_task(self._device.update_sensor("low_latency"))
                    case SimpleCommands.MASK_OFF | "MASK_OFF":
                        res = await jvc.send_command("operation", code=const.MASK_OFF)
                        asyncio.create_task(self._device.update_sensor("mask"))
                    case SimpleCommands.MASK_CUSTOM1 | "MASK_CUSTOM1":
                        res = await jvc.send_command(
                            "operation", code=const.MASK_CUSTOM1
                        )
                        asyncio.create_task(self._device.update_sensor("mask"))
                    case SimpleCommands.MASK_CUSTOM2 | "MASK_CUSTOM2":
                        res = await jvc.send_command(
                            "operation", code=const.MASK_CUSTOM2
                        )
                        asyncio.create_task(self._device.update_sensor("mask"))
                    case SimpleCommands.MASK_CUSTOM3 | "MASK_CUSTOM3":
                        res = await jvc.send_command(
                            "operation", code=const.MASK_CUSTOM3
                        )
                        asyncio.create_task(self._device.update_sensor("mask"))
                    case SimpleCommands.LAMP_LOW | "LAMP_LOW":
                        res = await jvc.send_command("operation", code=const.LAMP_LOW)
                        asyncio.create_task(self._device.update_sensor("lamp_power"))
                    case SimpleCommands.LAMP_MID | "LAMP_MID":
                        res = await jvc.send_command("operation", code=const.LAMP_MID)
                        asyncio.create_task(self._device.update_sensor("lamp_power"))
                    case SimpleCommands.LAMP_HIGH | "LAMP_HIGH":
                        res = await jvc.send_command("operation", code=const.LAMP_HIGH)
                        asyncio.create_task(self._device.update_sensor("lamp_power"))
                    case SimpleCommands.LENS_APERTURE_OFF | "LENS_APERTURE_OFF":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_APERTURE_OFF
                        )
                        asyncio.create_task(self._device.update_sensor("lens_aperture"))
                    case SimpleCommands.LENS_APERTURE_AUTO1 | "LENS_APERTURE_AUTO1":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_APERTURE_AUTO1
                        )
                        asyncio.create_task(self._device.update_sensor("lens_aperture"))
                    case SimpleCommands.LENS_APERTURE_AUTO2 | "LENS_APERTURE_AUTO2":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_APERTURE_AUTO2
                        )
                        asyncio.create_task(self._device.update_sensor("lens_aperture"))
                    case SimpleCommands.LENS_ANIMORPHIC_OFF | "LENS_ANIMORPHIC_OFF":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_ANIMORPHIC_OFF
                        )
                        asyncio.create_task(self._device.update_sensor("anamorphic"))
                    case SimpleCommands.LENS_ANIMORPHIC_A | "LENS_ANIMORPHIC_A":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_ANIMORPHIC_A
                        )
                        asyncio.create_task(self._device.update_sensor("anamorphic"))
                    case SimpleCommands.LENS_ANIMORPHIC_B | "LENS_ANIMORPHIC_B":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_ANIMORPHIC_B
                        )
                        asyncio.create_task(self._device.update_sensor("anamorphic"))
                    case SimpleCommands.LENS_ANIMORPHIC_C | "LENS_ANIMORPHIC_C":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_ANIMORPHIC_C
                        )
                        asyncio.create_task(self._device.update_sensor("anamorphic"))
                    case SimpleCommands.LENS_ANIMORPHIC_D | "LENS_ANIMORPHIC_D":
                        res = await jvc.send_command(
                            "operation", code=const.LENS_ANIMORPHIC_D
                        )
                        asyncio.create_task(self._device.update_sensor("anamorphic"))

            elif cmd_id == Commands.SEND_CMD_SEQUENCE:
                if params:
                    commands = params.get("sequence", [])
                else:
                    commands = []
                res = StatusCodes.OK
                for command in commands:
                    res = await self.handle_command(
                        Commands.SEND_CMD, {"command": command, "params": params}
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
            else:
                return StatusCodes.NOT_IMPLEMENTED
            if delay > 0 and cmd_id != Commands.SEND_CMD_SEQUENCE:
                await asyncio.sleep(delay)
            return res if res else StatusCodes.OK
        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing remote command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST


JVC_REMOTE_BUTTONS_MAPPING: [DeviceButtonMapping] = [  # type: ignore
    ucapi.ui.create_btn_mapping(
        ucapi.ui.Buttons.DPAD_UP, media_player.Commands.CURSOR_UP
    ),
    ucapi.ui.create_btn_mapping(
        ucapi.ui.Buttons.DPAD_DOWN, media_player.Commands.CURSOR_DOWN
    ),
    ucapi.ui.create_btn_mapping(
        ucapi.ui.Buttons.DPAD_LEFT, media_player.Commands.CURSOR_LEFT
    ),
    ucapi.ui.create_btn_mapping(
        ucapi.ui.Buttons.DPAD_RIGHT, media_player.Commands.CURSOR_RIGHT
    ),
    ucapi.ui.create_btn_mapping(
        ucapi.ui.Buttons.DPAD_MIDDLE, media_player.Commands.CURSOR_ENTER
    ),
    ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.GREEN, media_player.Commands.BACK),
    ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.YELLOW, media_player.Commands.MENU),
    ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.RED, SimpleCommands.LENS_MEMORY_1),
    ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.BLUE, "INPUT_HDMI_1"),
    ucapi.ui.create_btn_mapping(ucapi.ui.Buttons.POWER, media_player.Commands.TOGGLE),
]


def create_ui_pages() -> list[UiPage | dict[str, Any]]:
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
            cmd=media_player.Commands.MENU,
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
            cmd=SimpleCommands.LOW_LATENCY_ON,
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Off",
            3,
            3,
            size=ucapi.ui.Size(3, 1),
            cmd=SimpleCommands.LOW_LATENCY_OFF,
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
            cmd=SimpleCommands.LAMP_LOW,
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "Med",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LAMP_MID,
        )
    )
    ui_page1.add(
        ucapi.ui.create_ui_text(
            "High",
            4,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LAMP_HIGH,
        )
    )

    ui_page2 = ucapi.ui.UiPage("page2", "Picture Modes", grid=ucapi.ui.Size(4, 8))
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Film",
            0,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_FILM,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Cinema",
            2,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_CINEMA,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Natural",
            0,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_NATURAL,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HDR10",
            2,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_HDR10,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "THX",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_THX,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 1",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER1,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 2",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER2,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 3",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER3,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 4",
            0,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER4,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 5",
            2,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER5,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "User 6",
            0,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_USER6,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HLG",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_HLG,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "HDR10+",
            0,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_HDR10P,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "PAN PQ",
            2,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.PICTURE_MODE_PANA_PQ,
        )
    )
    ui_page2.add(
        ucapi.ui.create_ui_text(
            "Frame Adapt HDR",
            0,
            7,
            size=ucapi.ui.Size(4, 1),
            cmd=SimpleCommands.PICTURE_MODE_FRAME_ADAPT_HDR,
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
            cmd=SimpleCommands.LENS_ANIMORPHIC_OFF,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "A",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_ANIMORPHIC_A,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "B",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_ANIMORPHIC_B,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "C",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_ANIMORPHIC_C,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "D",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_ANIMORPHIC_D,
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
            cmd=SimpleCommands.MASK_OFF,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "1",
            2,
            5,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.MASK_CUSTOM1,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "2",
            0,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.MASK_CUSTOM2,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "3",
            2,
            6,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.MASK_CUSTOM3,
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
            cmd=SimpleCommands.LENS_APERTURE_OFF,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Auto 1",
            0,
            9,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_APERTURE_AUTO1,
        )
    )
    ui_page3.add(
        ucapi.ui.create_ui_text(
            "Auto 2",
            2,
            9,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_APERTURE_AUTO2,
        )
    )
    ui_page4 = ucapi.ui.UiPage("page4", "Lens Memory", grid=ucapi.ui.Size(4, 5))
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 1",
            0,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_1,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 2",
            2,
            0,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_2,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 3",
            0,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_3,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 4",
            2,
            1,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_4,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 5",
            0,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_5,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 6",
            2,
            2,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_6,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 7",
            0,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_7,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 8",
            2,
            3,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_8,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 9",
            0,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_9,
        )
    )
    ui_page4.add(
        ucapi.ui.create_ui_text(
            "Lens 10",
            2,
            4,
            size=ucapi.ui.Size(2, 1),
            cmd=SimpleCommands.LENS_MEMORY_10,
        )
    )

    return [ui_page1, ui_page2, ui_page3, ui_page4]

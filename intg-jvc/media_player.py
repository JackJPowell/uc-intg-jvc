"""
Media-player entity functions.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

import ucapi
import projector
from const import (
    SimpleCommands,
    JVCConfig,
)
import const
from ucapi import MediaPlayer, media_player, EntityTypes
from ucapi.media_player import DeviceClasses, Attributes
from jvcprojector import const as JvcConst
from ucapi_framework import create_entity_id, Entity as FrameworkEntity

_LOG = logging.getLogger(__name__)

features = [
    media_player.Features.ON_OFF,
    media_player.Features.TOGGLE,
    media_player.Features.DPAD,
    media_player.Features.SELECT_SOURCE,
    media_player.Features.MENU,
    media_player.Features.INFO,
    media_player.Features.SETTINGS,
]


class JVCMediaPlayer(MediaPlayer, FrameworkEntity):
    """Representation of a JVC MediaPlayer entity."""

    def __init__(self, config_device: JVCConfig, device: projector.JVCProjector):
        """Initialize the class."""
        self._device = device
        _LOG.debug("JVC Media Player init")
        entity_id = create_entity_id(EntityTypes.MEDIA_PLAYER, config_device.identifier)
        self.config = config_device

        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes={
                Attributes.STATE: device.state,
                Attributes.SOURCE: device.source if device.source else "",
                Attributes.SOURCE_LIST: device.source_list,
            },
            device_class=DeviceClasses.TV,
            options={
                media_player.Options.SIMPLE_COMMANDS: [
                    member.value for member in SimpleCommands
                ]
            },
            cmd_handler=self.media_player_cmd_handler,  # type: ignore[arg-type]
        )

        # Register this media player entity with the device
        self._device.register_entity(entity_id, self)

    # pylint: disable=too-many-statements
    async def media_player_cmd_handler(
        self, entity: MediaPlayer, cmd_id: str, params: dict[str, Any] | None
    ) -> ucapi.StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param entity: media-player entity
        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command. StatusCodes.OK if the command succeeded.
        """
        _LOG.info(
            "Got %s command request: %s %s", entity.id, cmd_id, params if params else ""
        )
        res = None
        state_changed = False  # Track if command changes device state

        try:
            jvc = self._device

            match cmd_id:
                case media_player.Commands.ON:
                    _LOG.debug("Sending ON command to AVR")
                    res = await jvc.send_command("powerOn")
                    state_changed = True
                case media_player.Commands.OFF:
                    res = await jvc.send_command("powerOff")
                    state_changed = True
                case media_player.Commands.TOGGLE:
                    res = await jvc.send_command("powerToggle")
                    state_changed = True
                case media_player.Commands.CURSOR_UP:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_UP)
                case media_player.Commands.CURSOR_DOWN:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_DOWN)
                case media_player.Commands.CURSOR_LEFT:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_LEFT)
                case media_player.Commands.CURSOR_RIGHT:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_RIGHT)
                case media_player.Commands.CURSOR_ENTER:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_OK)
                case media_player.Commands.BACK:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_BACK)
                case media_player.Commands.INFO:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_INFO)
                case media_player.Commands.MENU:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_MENU)
                case media_player.Commands.SELECT_SOURCE:
                    if params:
                        await jvc.send_command(
                            "setInput",
                            source=params.get("source"),
                        )
                        asyncio.create_task(jvc.update_sensor("input"))
                        state_changed = True
                case SimpleCommands.REMOTE_ADVANCED_MENU:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_ADVANCED_MENU
                    )
                case SimpleCommands.REMOTE_PICTURE_MODE:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_PICTURE_MODE
                    )
                case SimpleCommands.REMOTE_COLOR_PROFILE:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_COLOR_PROFILE
                    )
                case SimpleCommands.REMOTE_LENS_CONTROL:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_LENS_CONTROL
                    )
                case SimpleCommands.REMOTE_SETTING_MEMORY:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_SETTING_MEMORY
                    )
                case SimpleCommands.REMOTE_GAMMA_SETTINGS:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_GAMMA_SETTINGS
                    )
                case SimpleCommands.REMOTE_CMD:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_CMD)
                case SimpleCommands.REMOTE_MODE_1:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_MODE_1)
                case SimpleCommands.REMOTE_MODE_2:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_MODE_2)
                case SimpleCommands.REMOTE_MODE_3:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_MODE_3)
                case SimpleCommands.REMOTE_LENS_AP:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_LENS_AP)
                case SimpleCommands.REMOTE_ANAMO:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_ANAMO)
                case SimpleCommands.REMOTE_GAMMA:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_GAMMA)
                case SimpleCommands.REMOTE_COLOR_TEMP:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_COLOR_TEMP
                    )
                case SimpleCommands.REMOTE_3D_FORMAT:
                    res = await jvc.send_command(
                        "remote", code=JvcConst.REMOTE_3D_FORMAT
                    )
                case SimpleCommands.REMOTE_PIC_ADJ:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_PIC_ADJ)
                case SimpleCommands.REMOTE_NATURAL:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_NATURAL)
                case SimpleCommands.REMOTE_CINEMA:
                    res = await jvc.send_command("remote", code=JvcConst.REMOTE_CINEMA)
                case SimpleCommands.LENS_MEMORY_1:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_1)
                    )
                case SimpleCommands.LENS_MEMORY_2:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_2)
                    )
                case SimpleCommands.LENS_MEMORY_3:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_3)
                    )
                case SimpleCommands.LENS_MEMORY_4:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_4)
                    )
                case SimpleCommands.LENS_MEMORY_5:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_5)
                    )
                case SimpleCommands.LENS_MEMORY_6:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_6)
                    )
                case SimpleCommands.LENS_MEMORY_7:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_7)
                    )
                case SimpleCommands.LENS_MEMORY_8:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_8)
                    )
                case SimpleCommands.LENS_MEMORY_9:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_9)
                    )
                case SimpleCommands.LENS_MEMORY_10:
                    asyncio.create_task(
                        jvc.send_command("operation", code=const.LENS_MEMORY_10)
                    )
                case SimpleCommands.PICTURE_MODE_FILM:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_FILM
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_CINEMA:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_CINEMA
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_NATURAL:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_NATURAL
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_HDR10:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_HDR10
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_THX:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_THX
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER1:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER1
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER2:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER2
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER3:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER3
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER4:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER4
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER5:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER5
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_USER6:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_USER6
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_HLG:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_HLG
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_FRAME_ADAPT_HDR:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_FRAME_ADAPT_HDR
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_HDR10P:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_HDR10P
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.PICTURE_MODE_PANA_PQ:
                    res = await jvc.send_command(
                        "operation", code=const.PICTURE_MODE_PANA_PQ
                    )
                    asyncio.create_task(jvc.update_sensor("picture_mode"))
                case SimpleCommands.LOW_LATENCY_ON:
                    res = await jvc.send_command("operation", code=const.LOW_LATENCY_ON)
                    asyncio.create_task(jvc.update_sensor("low_latency"))
                case SimpleCommands.LOW_LATENCY_OFF:
                    res = await jvc.send_command(
                        "operation", code=const.LOW_LATENCY_OFF
                    )
                    asyncio.create_task(jvc.update_sensor("low_latency"))
                case SimpleCommands.MASK_OFF:
                    res = await jvc.send_command("operation", code=const.MASK_OFF)
                    asyncio.create_task(jvc.update_sensor("mask"))
                case SimpleCommands.MASK_CUSTOM1:
                    res = await jvc.send_command("operation", code=const.MASK_CUSTOM1)
                    asyncio.create_task(jvc.update_sensor("mask"))
                case SimpleCommands.MASK_CUSTOM2:
                    res = await jvc.send_command("operation", code=const.MASK_CUSTOM2)
                    asyncio.create_task(jvc.update_sensor("mask"))
                case SimpleCommands.MASK_CUSTOM3:
                    res = await jvc.send_command("operation", code=const.MASK_CUSTOM3)
                    asyncio.create_task(jvc.update_sensor("mask"))
                case SimpleCommands.LAMP_LOW:
                    res = await jvc.send_command("operation", code=const.LAMP_LOW)
                    asyncio.create_task(jvc.update_sensor("lamp_power"))
                case SimpleCommands.LAMP_MID:
                    res = await jvc.send_command("operation", code=const.LAMP_MID)
                    asyncio.create_task(jvc.update_sensor("lamp_power"))
                case SimpleCommands.LAMP_HIGH:
                    res = await jvc.send_command("operation", code=const.LAMP_HIGH)
                    asyncio.create_task(jvc.update_sensor("lamp_power"))
                case SimpleCommands.LENS_APERTURE_OFF:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_APERTURE_OFF
                    )
                    asyncio.create_task(jvc.update_sensor("lens_aperture"))
                case SimpleCommands.LENS_APERTURE_AUTO1:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_APERTURE_AUTO1
                    )
                    asyncio.create_task(jvc.update_sensor("lens_aperture"))
                case SimpleCommands.LENS_APERTURE_AUTO2:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_APERTURE_AUTO2
                    )
                    asyncio.create_task(jvc.update_sensor("lens_aperture"))
                case SimpleCommands.LENS_ANIMORPHIC_OFF:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_ANIMORPHIC_OFF
                    )
                    asyncio.create_task(jvc.update_sensor("anamorphic"))
                case SimpleCommands.LENS_ANIMORPHIC_A:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_ANIMORPHIC_A
                    )
                    asyncio.create_task(jvc.update_sensor("anamorphic"))
                case SimpleCommands.LENS_ANIMORPHIC_B:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_ANIMORPHIC_B
                    )
                    asyncio.create_task(jvc.update_sensor("anamorphic"))
                case SimpleCommands.LENS_ANIMORPHIC_C:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_ANIMORPHIC_C
                    )
                    asyncio.create_task(jvc.update_sensor("anamorphic"))
                case SimpleCommands.LENS_ANIMORPHIC_D:
                    res = await jvc.send_command(
                        "operation", code=const.LENS_ANIMORPHIC_D
                    )
                    asyncio.create_task(jvc.update_sensor("anamorphic"))

        except Exception as ex:  # pylint: disable=broad-except
            _LOG.error("Error executing command %s: %s", cmd_id, ex)
            return ucapi.StatusCodes.BAD_REQUEST

        # Update entity state if command changed device state
        # Framework Entity.update() calls get_device_attributes() to retrieve updated attributes
        if state_changed and isinstance(entity, FrameworkEntity):
            self.update(jvc.attributes)

        _LOG.debug("Command %s executed successfully: %s", cmd_id, res)
        return ucapi.StatusCodes.OK

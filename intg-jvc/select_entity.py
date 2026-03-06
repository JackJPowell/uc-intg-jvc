"""
Select entity functions for the JVC integration.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from const import JVCConfig, SelectConfig
from projector import JVCProjector
from ucapi import EntityTypes, StatusCodes
from ucapi.select import Attributes, Commands, States
from ucapi_framework import create_entity_id
from ucapi_framework.entities import SelectEntity

_LOG = logging.getLogger(__name__)


class JVCSelect(SelectEntity):
    """Representation of a JVC Select entity."""

    def __init__(
        self,
        config_device: JVCConfig,
        device: JVCProjector,
        select_config: SelectConfig,
    ):
        """Initialize a JVC Select entity.

        Args:
            config_device: Device configuration
            device: JVCProjector device instance
            select_config: SelectConfig dataclass with select metadata
        """
        self._device = device
        self._select_id = select_config.identifier

        # Set entity_id for FrameworkEntity mixin
        self._entity_id = create_entity_id(
            EntityTypes.SELECT, config_device.identifier, select_config.identifier
        )

        super().__init__(
            self._entity_id,
            select_config.name,
            attributes={
                Attributes.STATE: States.UNAVAILABLE,
                Attributes.CURRENT_OPTION: "",
                Attributes.OPTIONS: [],
            },
            cmd_handler=self.select_cmd_handler,
        )
        self.subscribe_to_device(device)

        _LOG.debug(
            "Created select entity: %s with %d options",
            self._entity_id,
            len(select_config.options or []),
        )

    async def select_cmd_handler(
        self,
        _entity: SelectEntity,
        cmd_id: str,
        params: dict[str, Any] | None,
        _websocket: Any = None,
    ) -> StatusCodes:
        """Handle select entity commands.

        Args:
            _entity: Select entity
            cmd_id: Command identifier
            params: Optional command parameters
            _websocket: Optional websocket connection

        Returns:
            StatusCodes: Result of command execution
        """
        _LOG.debug("[%s] Command: %s, params: %s", self._select_id, cmd_id, params)

        match cmd_id:
            case Commands.SELECT_OPTION:
                if params and "option" in params:
                    success = await self._device.select_option(
                        self._select_id, params["option"]
                    )
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_FIRST:
                options = self.attributes.get(Attributes.OPTIONS, [])
                if options:
                    success = await self._device.select_option(
                        self._select_id, options[0]
                    )
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_LAST:
                options = self.attributes.get(Attributes.OPTIONS, [])
                if options:
                    success = await self._device.select_option(
                        self._select_id, options[-1]
                    )
                    return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_NEXT:
                options = self.attributes.get(Attributes.OPTIONS, [])
                current = self.attributes.get(Attributes.CURRENT_OPTION, "")
                if options and current in options:
                    cycle = params.get("cycle", False) if params else False
                    current_idx = options.index(current)
                    if current_idx < len(options) - 1:
                        success = await self._device.select_option(
                            self._select_id, options[current_idx + 1]
                        )
                        return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                    elif cycle:
                        success = await self._device.select_option(
                            self._select_id, options[0]
                        )
                        return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_PREVIOUS:
                options = self.attributes.get(Attributes.OPTIONS, [])
                current = self.attributes.get(Attributes.CURRENT_OPTION, "")
                if options and current in options:
                    cycle = params.get("cycle", False) if params else False
                    current_idx = options.index(current)
                    if current_idx > 0:
                        success = await self._device.select_option(
                            self._select_id, options[current_idx - 1]
                        )
                        return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                    elif cycle:
                        success = await self._device.select_option(
                            self._select_id, options[-1]
                        )
                        return StatusCodes.OK if success else StatusCodes.SERVER_ERROR
                return StatusCodes.BAD_REQUEST

            case _:
                _LOG.warning("[%s] Unknown command: %s", self._select_id, cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

    async def sync_state(self) -> None:
        """Sync entity state from device attributes."""
        if self._device is None:
            self.set_unavailable()
            return
        attrs = self._device.get_select_attributes(self._select_id)
        if attrs is not None:
            self.update(attrs)
        else:
            self.set_unavailable()

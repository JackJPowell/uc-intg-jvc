"""
Select entity functions for the JVC integration.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from jvcprojector.error import JvcProjectorError

from const import JVCConfig, SelectConfig
from projector import JVCProjector
from ucapi import EntityTypes, StatusCodes
from ucapi.select import Attributes, Commands, Select, States
from ucapi_framework import create_entity_id
from ucapi_framework.entity import Entity as FrameworkEntity

_LOG = logging.getLogger(__name__)


class JVCSelect(Select, FrameworkEntity):
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
        self._command_class = select_config.command_class

        # Set entity_id for FrameworkEntity mixin
        self._entity_id = create_entity_id(
            EntityTypes.SELECT, config_device.identifier, select_config.identifier
        )

        attributes: dict[str, Any] = {
            Attributes.STATE: States.UNAVAILABLE,
            Attributes.CURRENT_OPTION: select_config.value or "",
            Attributes.OPTIONS: select_config.options or [],
        }

        super().__init__(
            self._entity_id,
            select_config.name,
            attributes=attributes,
            cmd_handler=self.select_cmd_handler,
        )

        _LOG.debug(
            "Created select entity: %s with %d options",
            self._entity_id,
            len(select_config.options or []),
        )

    async def select_cmd_handler(
        self,
        _entity: Select,
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
                    return await self.select_option(params["option"])
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_FIRST:
                options = self.attributes.get(Attributes.OPTIONS, [])
                if options:
                    return await self.select_option(options[0])
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_LAST:
                options = self.attributes.get(Attributes.OPTIONS, [])
                if options:
                    return await self.select_option(options[-1])
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_NEXT:
                options = self.attributes.get(Attributes.OPTIONS, [])
                current = self.attributes.get(Attributes.CURRENT_OPTION, "")
                if options and current in options:
                    cycle = params.get("cycle", False) if params else False
                    current_idx = options.index(current)
                    if current_idx < len(options) - 1:
                        return await self.select_option(options[current_idx + 1])
                    elif cycle:
                        return await self.select_option(options[0])
                return StatusCodes.BAD_REQUEST

            case Commands.SELECT_PREVIOUS:
                options = self.attributes.get(Attributes.OPTIONS, [])
                current = self.attributes.get(Attributes.CURRENT_OPTION, "")
                if options and current in options:
                    cycle = params.get("cycle", False) if params else False
                    current_idx = options.index(current)
                    if current_idx > 0:
                        return await self.select_option(options[current_idx - 1])
                    elif cycle:
                        return await self.select_option(options[-1])
                return StatusCodes.BAD_REQUEST

            case _:
                _LOG.warning("[%s] Unknown command: %s", self._select_id, cmd_id)
                return StatusCodes.NOT_IMPLEMENTED

    async def select_option(self, option: str) -> StatusCodes:
        """Handle option selection.

        Args:
            option: The selected option value

        Returns:
            StatusCodes: SUCCESS if command sent, ERROR otherwise
        """
        _LOG.debug("[%s] Selecting option: %s", self._select_id, option)

        try:
            # Send operation command to projector
            await self._device.send_command(
                "operation",
                cmd_class=self._command_class,
                value=option,
            )

            # Update local state
            self.attributes[Attributes.CURRENT_OPTION] = option
            self.attributes[Attributes.STATE] = States.ON

            _LOG.info("[%s] Successfully set to: %s", self._select_id, option)
            return StatusCodes.OK

        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Failed to select option %s: %s",
                self._select_id,
                option,
                err,
            )
            return StatusCodes.SERVER_ERROR

    def update_value(self, value: str) -> None:
        """Update the select value (called when sensor updates).

        Args:
            value: New value from projector
        """
        if value and value in self.attributes.get(Attributes.OPTIONS, []):
            self.attributes[Attributes.CURRENT_OPTION] = value
            self.attributes[Attributes.STATE] = States.ON
            _LOG.debug("[%s] Updated value to: %s", self._select_id, value)
        elif value:
            _LOG.warning(
                "[%s] Received unknown value '%s', not in options list",
                self._select_id,
                value,
            )

    def set_unavailable(self) -> None:
        """Mark the select as unavailable."""
        self.attributes[Attributes.STATE] = States.UNAVAILABLE
        _LOG.debug("[%s] Set to unavailable", self._select_id)

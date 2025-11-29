"""
This module implements the JVC Projector communication of the Remote Two/3 integration driver.

"""

import logging
from asyncio import AbstractEventLoop
from enum import StrEnum
from typing import Any

import aiohttp
from const import JVCDevice
from jvcprojector import const as JvcConst
from jvcprojector.projector import JvcProjector
from ucapi.media_player import Attributes as MediaAttr
from ucapi_framework import BaseDeviceManager, StatelessHTTPDevice
from ucapi_framework.device import DeviceEvents

_LOG = logging.getLogger(__name__)


class PowerState(StrEnum):
    """Playback state for companion protocol."""

    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"


class JVCProjector(StatelessHTTPDevice):
    """Representing a JVC Projector Device."""

    def __init__(
        self,
        device: JVCDevice,
        loop: AbstractEventLoop | None,
        config_manager: BaseDeviceManager | None = None,
    ) -> None:
        """Create instance with stateless device base."""
        super().__init__(device_config=device, loop=loop, config_manager=config_manager)
        self._jvc_projector = JvcProjector(
            host=device.address, password=device.password
        )
        self._source_list: list[str] = ["HDMI1", "HDMI2"]
        self._active_source: str = ""
        self._signal: str = ""

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        return self._device_config.identifier

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device_config.name

    @property
    def address(self) -> str | None:
        """Return the device address."""
        return self._device_config.address

    @property
    def source(self) -> str:
        """Return the current input source."""
        return self._active_source if self._active_source else ""

    @property
    def source_list(self) -> list[str]:
        """Return the list of available input sources."""
        return self._source_list

    @property
    def state(self) -> PowerState | None:
        """Return the current power state."""
        return self._state

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return (
            self._device_config.name
            if self._device_config.name
            else self._device_config.identifier
        )

    async def verify_connection(self) -> None:
        """
        Verify connection to the projector and emit current state.

        This method is called by the framework to check device connectivity
        and retrieve the current state. State updates are emitted via DeviceEvents.UPDATE.

        :raises: Exception if connection verification fails
        """
        _LOG.debug(
            "[%s] Verifying connection to JVC projector at IP address: %s",
            self.name,
            self.address,
        )

        try:
            await self._jvc_projector.connect()

            state_dict = await self._jvc_projector.get_state()

            self._state = PowerState(state_dict.get("power", "").upper())

            # Extract input source safely
            input_value = state_dict.get("input", "")
            if input_value:
                self._active_source = input_value.upper()

            # Extract signal source safely
            source_value = state_dict.get("source", "")
            if source_value:
                self._signal = source_value.upper()

            _LOG.debug(
                "[%s] Connection verified successfully, state: %s",
                self.name,
                self._state,
            )

            # Emit state update to the Remote
            attributes = {
                MediaAttr.STATE: self._state,
                MediaAttr.SOURCE: self._active_source if self._active_source else "",
                MediaAttr.SOURCE_LIST: self._source_list,
            }
            self.events.emit(DeviceEvents.UPDATE, self.identifier, attributes)

        except aiohttp.ClientError as err:
            _LOG.error("[%s] Connection verification failed: %s", self.name, err)
            raise
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Unexpected error during connection verification: %s",
                self.name,
                err,
            )
            raise

    async def send_command(self, command: str, *args: Any, **kwargs: Any) -> None:
        """
        Send a command to the projector and emit state updates.

        For stateless devices, emits the updated state after command execution
        via DeviceEvents.UPDATE.

        :param command: Command to send
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        """
        try:
            _LOG.debug(
                "[%s] Sending command: %s, args: %s, kwargs: %s",
                self.name,
                command,
                args,
                kwargs,
            )

            attributes = {}

            match command:
                case "powerOn":
                    power = await self._jvc_projector.get_power()
                    # Normalize power state from API to PowerState enum for comparison
                    power_state = PowerState(
                        power.upper() if isinstance(power, str) else power
                    )
                    if power_state in [PowerState.STANDBY, PowerState.OFF]:
                        await self._jvc_projector.power_on()
                    attributes[MediaAttr.STATE] = PowerState.ON

                case "powerOff":
                    power = await self._jvc_projector.get_power()
                    # Normalize power state from API to PowerState enum for comparison
                    power_state = PowerState(
                        power.upper() if isinstance(power, str) else power
                    )
                    if power_state == PowerState.ON:
                        await self._jvc_projector.power_off()
                    attributes[MediaAttr.STATE] = PowerState.STANDBY

                case "powerToggle":
                    power = await self._jvc_projector.get_power()
                    # Normalize power state from API to PowerState enum for comparison
                    power_state = PowerState(
                        power.upper() if isinstance(power, str) else power
                    )
                    if power_state == PowerState.ON:
                        await self._jvc_projector.power_off()
                        attributes[MediaAttr.STATE] = PowerState.STANDBY
                    elif power_state in [PowerState.STANDBY, PowerState.OFF]:
                        await self._jvc_projector.power_on()
                        attributes[MediaAttr.STATE] = PowerState.ON
                    else:
                        attributes[MediaAttr.STATE] = power_state

                case "setInput":
                    code = JvcConst.REMOTE_HDMI_1  # Default to HDMI1
                    source = kwargs.get("source", "")
                    if source.upper() == "HDMI2":
                        code = JvcConst.REMOTE_HDMI_2
                    await self._jvc_projector.remote(code)
                    self._active_source = kwargs["source"].upper()
                    attributes[MediaAttr.SOURCE] = self._active_source

                case "remote":
                    code = kwargs.get("code")
                    await self._jvc_projector.remote(code)
                    # Remote commands don't update attributes

                case "operation":
                    code = kwargs.get("code")
                    await self._jvc_projector.op(code)
                    # Operation commands don't update attributes

                case _:
                    _LOG.warning("[%s] Unknown command: %s", self.name, command)

            # Emit attribute updates to the Remote
            if attributes:
                self.events.emit(DeviceEvents.UPDATE, self.identifier, attributes)

        except KeyError as err:
            _LOG.error(
                "[%s] Missing parameter for command %s: %s",
                self.name,
                command,
                err,
            )
            raise
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error sending command %s: %s",
                self.name,
                command,
                err,
            )
            raise

    def simple_power(self, power: str) -> PowerState:
        """Convert power state string to PowerState enum."""
        power_lower = power.lower()
        if power_lower in ["on", "warming"]:
            return PowerState.ON
        elif power_lower in ["cooling", "standby", "off"]:
            return PowerState.OFF
        else:
            raise ValueError(f"Unknown power state: {power}")

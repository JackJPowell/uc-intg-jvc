"""
This module implements the JVC Projector communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from enum import StrEnum, IntEnum
from typing import Any, ParamSpec, TypeVar

import aiohttp

from jvcprojector.projector import JvcProjector
from jvcprojector import const as JvcConst
from config import JVCDevice
from pyee.asyncio import AsyncIOEventEmitter
from ucapi.media_player import Attributes as MediaAttr

_LOG = logging.getLogger(__name__)


class EVENTS(IntEnum):
    """Internal driver events."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    PAIRED = 3
    ERROR = 4
    UPDATE = 5


_JvcProjectorT = TypeVar("_JvcProjectorT", bound="JvcProjector")
_P = ParamSpec("_P")


class PowerState(StrEnum):
    """Playback state for companion protocol."""

    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"


class JVCProjector:
    """Representing a JVC Projector Device."""

    def __init__(
        self, device: JVCDevice, loop: AbstractEventLoop | None = None
    ) -> None:
        """Create instance."""
        self._loop: AbstractEventLoop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self._is_connected: bool = False
        self._device: JVCDevice = device
        self._jvc_projector = JvcProjector(
            host=self._device.address, password=self._device.password
        )
        self._connection_attempts: int = 0
        self._state: PowerState = PowerState.OFF
        self._source_list: list[str] = []
        self._active_source: str = ""
        self._features: dict = {}
        self._signal: str = ""

    @property
    def device_config(self) -> JVCDevice:
        """Return the device configuration."""
        return self._device

    @property
    def identifier(self) -> str:
        """Return the device identifier."""
        if not self._device.identifier:
            raise ValueError("Instance not initialized, no identifier available")
        return self._device.identifier

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return self._device.name if self._device.name else self._device.identifier

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._device.name

    @property
    def address(self) -> str | None:
        """Return the optional device address."""
        return self._device.address

    @property
    def state(self) -> PowerState | None:
        """Return the device state."""
        return self._state.upper()

    @property
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        return sorted(self._source_list)

    @property
    def source(self) -> str:
        """Return the current input source."""
        return self._active_source

    @property
    def attributes(self) -> dict[str, any]:
        """Return the device attributes."""
        updated_data = {
            MediaAttr.STATE: self.state,
        }
        if self.source_list:
            updated_data[MediaAttr.SOURCE_LIST] = self.source_list
        if self.source:
            updated_data[MediaAttr.SOURCE] = self.source
        return updated_data

    async def connect(self) -> None:
        """Establish connection to the AVR."""
        if self.state != PowerState.OFF:
            return

        _LOG.debug("[%s] Connecting to device", self.log_id)
        self.events.emit(EVENTS.CONNECTING, self._device.identifier)
        await self._connect_setup()

    async def _connect_setup(self) -> None:
        try:
            await self._connect()

            if self.state != PowerState.OFF:
                _LOG.debug("[%s] Device is alive", self.log_id)
                self.events.emit(
                    EVENTS.UPDATE, self._device.identifier, {"state": self.state}
                )
            else:
                _LOG.debug("[%s] Device is not alive", self.log_id)
                self.events.emit(
                    EVENTS.UPDATE,
                    self._device.identifier,
                    {"state": PowerState.OFF},
                )
        except asyncio.CancelledError:
            pass
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Could not connect: %s", self.log_id, err)
        finally:
            _LOG.debug("[%s] Connect setup finished", self.log_id)

        self.events.emit(EVENTS.CONNECTED, self._device.identifier)
        _LOG.debug("[%s] Connected", self.log_id)

        await self._update_attributes()

    async def _connect(self) -> None:
        """Connect to the device."""
        _LOG.debug(
            "[%s] Connecting to TVWS device at IP address: %s",
            self.log_id,
            self.address,
        )
        try:
            await self._jvc_projector.connect()
            self._state = await self._jvc_projector.get_power()
        except aiohttp.ClientError as err:
            _LOG.error("[%s] Connection error: %s", self.log_id, err)
            self._state = PowerState.OFF

    async def _update_attributes(self) -> None:
        _LOG.debug("[%s] Updating app list", self.log_id)
        update = {}

        try:
            await self._jvc_projector.connect()
            state = await self._jvc_projector.get_state()
            self._state = PowerState(state["power", ""].upper())
            self._active_source = state["input"].upper()
            self._signal = state["source"].upper()

        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Error retrieving status: %s", self.log_id, err)

        self._source_list = [
            "HDMI1",
            "HDMI2",
        ]

        try:
            update["state"] = self.state
            update["source"] = self.source.upper()
            update["source_list"] = self.source_list

        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.exception("[%s] App list: protocol error", self.log_id)

        self.events.emit(EVENTS.UPDATE, self._device.identifier, update)

    async def send_command(self, command: str, *args: Any, **kwargs: Any) -> str:
        """Send a command to the AVR."""
        update = {}
        res = ""
        try:
            _LOG.debug(
                "[%s] Sending command: %s, args: %s, kwargs: %s",
                self.log_id,
                command,
                args,
                kwargs,
            )
            match command:
                case "powerOn":
                    power = await self._jvc_projector.get_power()
                    if power.upper() in [PowerState.STANDBY, PowerState.OFF]:
                        res = await self._jvc_projector.power_on()
                    self._state = PowerState.ON
                    update["state"] = PowerState.ON
                case "powerOff":
                    power = await self._jvc_projector.get_power()
                    if power.upper() == PowerState.ON:
                        res = await self._jvc_projector.power_off()
                    self._state = PowerState.STANDBY
                    update["state"] = PowerState.STANDBY
                case "powerToggle":
                    power = await self._jvc_projector.get_power()
                    if power.upper() == PowerState.ON:
                        res = await self._jvc_projector.power_off()
                        self._state = PowerState.STANDBY
                        update["state"] = PowerState.STANDBY
                    elif power.upper() in [PowerState.STANDBY, PowerState.OFF]:
                        res = await self._jvc_projector.power_on()
                        self._state = PowerState.ON
                        update["state"] = PowerState.ON
                case "setInput":
                    code = JvcConst.REMOTE_HDMI_1  # Default to HDMI1
                    source = kwargs.get("source", "")
                    if source.upper() == "HDMI2":
                        code = JvcConst.REMOTE_HDMI_2
                    res = await self._jvc_projector.remote(code)
                    update["source"] = kwargs["source"].upper()
                case "remote":
                    code = kwargs.get("code")
                    res = await self._jvc_projector.remote(code)
                case "operation":
                    code = kwargs.get("code")
                    res = await self._jvc_projector.op(code)

            self.events.emit(EVENTS.UPDATE, self._device.identifier, update)
            return res
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error sending command %s: %s",
                self.log_id,
                command,
                err,
            )
            raise Exception(err) from err  # pylint: disable=broad-exception-raised

    def simple_power(self, power: str) -> PowerState:
        """Set the power state of the projector."""
        if power in ["on", "warming"]:
            return PowerState.ON
        elif power in ["cooling", "standby", "off"]:
            return PowerState.OFF
        else:
            raise ValueError(f"Unknown power state: {power}")

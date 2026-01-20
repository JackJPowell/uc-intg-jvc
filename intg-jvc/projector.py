"""
This module implements the JVC Projector communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from typing import Any

import aiohttp
from const import (
    JVCConfig,
    SENSORS,
    SensorConfig,
)
from jvcprojector import JvcProjector as JvcLib
from jvcprojector import command as jvc_cmd
from jvcprojector.error import JvcProjectorError
from ucapi import media_player
from ucapi.sensor import States as SensorStates
from ucapi_framework import BaseConfigManager, StatelessHTTPDevice
from ucapi_framework.helpers import MediaPlayerAttributes, SensorAttributes

_LOG = logging.getLogger(__name__)


class JVCProjector(StatelessHTTPDevice):
    """Representing a JVC Projector Device."""

    def __init__(
        self,
        device_config: JVCConfig,
        loop: AbstractEventLoop | None,
        config_manager: BaseConfigManager | None = None,
    ) -> None:
        """Create instance with stateless device base."""
        self._device_config: JVCConfig
        super().__init__(
            device_config=device_config, loop=loop, config_manager=config_manager
        )
        self._jvc_projector = JvcLib(
            host=device_config.address, password=device_config.password
        )
        self._projector_lock = asyncio.Lock()
        self._sensor_update_task: asyncio.Task | None = None
        self._source_list: list[str] = ["HDMI1", "HDMI2"]
        self._active_source: str = ""
        self._signal: str = ""

        self.sensors: dict[str, SensorConfig] = {s.identifier: s for s in SENSORS}

        self.attributes = MediaPlayerAttributes(
            STATE=None,
            SOURCE=None,
            SOURCE_LIST=self._source_list,
        )

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
    def state(self) -> media_player.States | None:
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

    def register_sensor_entity(self, sensor_id: str, entity: Any) -> None:
        """Register a sensor entity with this device.

        Args:
            sensor_id: The sensor identifier (e.g., 'picture_mode', 'low_latency')
            entity: The sensor entity instance
        """
        sensor_config = self.sensors.get(sensor_id)
        if sensor_config:
            sensor_config.entity = entity
            _LOG.debug("[%s] Registered sensor entity: %s", self.log_id, sensor_id)
        else:
            _LOG.warning(
                "[%s] Attempted to register unknown sensor: %s", self.log_id, sensor_id
            )

    async def _update_all_sensors(self) -> None:
        """Update all sensor values with delays between queries."""
        try:
            # Only update sensors if projector is on
            if self.state != media_player.States.ON:
                _LOG.debug(
                    "[%s] Skipping sensor update - projector state is %s",
                    self.name,
                    self.state,
                )
                return

            # Acquire lock to serialize access to projector
            async with self._projector_lock:
                # Query additional sensor values using get() with 100ms delays
                for sensor_id in [
                    "picture_mode",
                    "low_latency",
                    "mask",
                    "lamp_power",
                    "lens_aperture",
                ]:
                    sensor = self.sensors.get(sensor_id)
                    if sensor and sensor.query_command:
                        # Use new get() API with command classes
                        sensor.value = await self._jvc_projector.get(
                            sensor.query_command
                        )
                        await asyncio.sleep(0.1)

            # Call refresh_state on registered sensor entities (outside lock)
            for sensor_config in self.sensors.values():
                if sensor_config.entity:
                    sensor_config.entity.refresh_state()

            _LOG.debug("[%s] All sensors updated successfully", self.name)
        except JvcProjectorError as err:  # noqa: BLE001
            _LOG.error("[%s] Error updating sensors: %s", self.name, err)
        finally:
            # Clear the task reference when done
            self._sensor_update_task = None

    async def update_sensor(self, sensor_key: str) -> None:
        """Update a specific sensor value and trigger entity refresh.

        Args:
            sensor_key: The sensor identifier (e.g., 'picture_mode', 'low_latency')
        """
        try:
            # Get sensor config and query command
            sensor = self.sensors.get(sensor_key)
            if not sensor or not sensor.query_command:
                _LOG.warning(
                    "[%s] Sensor '%s' not found or has no query command",
                    self.name,
                    sensor_key,
                )
                return

            # Acquire lock to serialize access to projector
            async with self._projector_lock:
                # Query the specific sensor value and store in sensor config
                sensor.value = await self._jvc_projector.get(sensor.query_command)

            # Trigger sensor entity update if it exists (outside lock)
            if sensor.entity:
                sensor.entity.refresh_state()

            _LOG.debug("[%s] Sensor '%s' updated", self.name, sensor_key)
        except JvcProjectorError as err:  # noqa: BLE001
            _LOG.error(
                "[%s] Error updating sensor '%s': %s", self.name, sensor_key, err
            )

    def _sensor_attributes(self, sensor_id: str) -> SensorAttributes:
        """Return sensor attributes for the given sensor identifier.

        Args:
            sensor_id: Sensor identifier (e.g., 'picture_mode', 'low_latency')

        Returns:
            SensorAttributes dataclass with STATE, VALUE, and optionally UNIT
        """
        sensor_config = self.sensors.get(sensor_id)
        if not sensor_config:
            return SensorAttributes()

        # Get value directly from sensor config
        raw_value = sensor_config.value

        # Format value based on sensor type
        if sensor_config.identifier in ["input", "source"]:
            value = str(raw_value).upper() if raw_value is not None else None
        else:
            value = raw_value

        # Return SensorAttributes dataclass
        sensor_state = SensorStates.UNAVAILABLE
        if self.state == media_player.States.ON:
            sensor_state = SensorStates.ON
        elif self.state == media_player.States.STANDBY:
            sensor_state = SensorStates.UNAVAILABLE

        # Return value if projector is ON, otherwise use default
        # Use 'is not None' check to allow empty strings as valid values
        return SensorAttributes(
            STATE=sensor_state,
            VALUE=value
            if self.state == media_player.States.ON and value is not None
            else sensor_config.default,
            UNIT=sensor_config.unit,
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
            # Acquire lock to serialize access to projector
            async with self._projector_lock:
                await self._jvc_projector.connect()

                # Get power state
                power_str = await self._jvc_projector.get(jvc_cmd.Power)
                self._state = self._convert_power_state(str(power_str))

                # Get input if projector is on
                if self._state == media_player.States.ON:
                    input_value = await self._jvc_projector.get(jvc_cmd.Input)
                    if input_value:
                        self._active_source = input_value.upper()
                        # Update input sensor config
                        input_sensor = self.sensors.get("input")
                        if input_sensor:
                            input_sensor.value = input_value

            # Update sensors in background task with delays, but only if not already running
            if self._sensor_update_task is None or self._sensor_update_task.done():
                self._sensor_update_task = asyncio.create_task(
                    self._update_all_sensors()
                )
            else:
                _LOG.debug(
                    "[%s] Skipping sensor update - already in progress",
                    self.name,
                )

            _LOG.debug(
                "[%s] Connection verified successfully, state: %s",
                self.name,
                self._state,
            )

            # Update attributes dataclass for framework to retrieve via get_device_attributes
            self.attributes.STATE = self._state
            self.attributes.SOURCE = self._active_source if self._active_source else ""
            self.attributes.SOURCE_LIST = self._source_list

        except aiohttp.ClientError as err:
            _LOG.error("[%s] Connection verification failed: %s", self.name, err)
            raise
        except JvcProjectorError as err:  # pylint: disable=broad-exception-caught
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

            # Acquire lock to serialize access to projector
            async with self._projector_lock:
                match command:
                    case "powerOn":
                        power = await self._jvc_projector.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state in [
                            media_player.States.STANDBY,
                            media_player.States.OFF,
                        ]:
                            await self._jvc_projector.set(
                                jvc_cmd.Power, jvc_cmd.Power.ON
                            )
                        self._state = media_player.States.ON
                        self.attributes.STATE = media_player.States.ON

                    case "powerOff":
                        power = await self._jvc_projector.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._jvc_projector.set(
                                jvc_cmd.Power, jvc_cmd.Power.OFF
                            )
                        self._state = media_player.States.STANDBY
                        self.attributes.STATE = media_player.States.STANDBY

                    case "powerToggle":
                        power = await self._jvc_projector.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._jvc_projector.set(
                                jvc_cmd.Power, jvc_cmd.Power.OFF
                            )
                            self._state = media_player.States.STANDBY
                            self.attributes.STATE = media_player.States.STANDBY
                        elif power_state in [
                            media_player.States.STANDBY,
                            media_player.States.OFF,
                        ]:
                            await self._jvc_projector.set(
                                jvc_cmd.Power, jvc_cmd.Power.ON
                            )
                            self._state = media_player.States.ON
                            self.attributes.STATE = media_player.States.ON
                        else:
                            self._state = power_state
                            self.attributes.STATE = power_state

                    case "setInput":
                        # Use command.Remote for input selection
                        remote_cmd = jvc_cmd.Remote.HDMI1  # Default to HDMI1
                        source = kwargs.get("source", "")
                        if source.upper() == "HDMI2":
                            remote_cmd = jvc_cmd.Remote.HDMI2
                        await self._jvc_projector.remote(remote_cmd)
                        self._active_source = kwargs["source"].upper()
                        self.attributes.SOURCE = self._active_source

                    case "remote":
                        code = kwargs.get("code")
                        if code:
                            # Code is already a command.Remote value, pass directly
                            await self._jvc_projector.remote(code)
                        # Remote commands don't update attributes

                    case "operation":
                        code = kwargs.get("code")
                        if code:
                            # Operation commands use set() with appropriate command class
                            # Code should be command.CommandName.VALUE format
                            await self._jvc_projector.set(code, code)
                        # Operation commands don't update attributes

                    case _:
                        _LOG.warning("[%s] Unknown command: %s", self.name, command)

        except KeyError as err:
            _LOG.error(
                "[%s] Missing parameter for command %s: %s",
                self.name,
                command,
                err,
            )
            raise
        except JvcProjectorError as err:  # pylint: disable=broad-exception-caught
            _LOG.error(
                "[%s] Error sending command %s: %s",
                self.name,
                command,
                err,
            )
            raise

    def get_device_attributes(
        self, entity_id: str
    ) -> MediaPlayerAttributes | SensorAttributes:
        """
        Return device attributes for the given entity.

        Called by framework when refreshing entity state to retrieve current attributes.
        For sensor entities, extracts the sensor identifier from entity_id and returns sensor attributes.

        :param entity_id: Entity identifier (format: sensor.{device_id}.{sensor_id} for sensors)
        :return: MediaPlayerAttributes for media player, SensorAttributes for sensors
        """
        # Check if this is a sensor entity by looking for the pattern
        if "sensor." in entity_id:
            # Extract sensor identifier from entity_id using split
            # Format: sensor.{device_id}.{sensor_id}
            parts = entity_id.split(".", 2)
            if len(parts) >= 3:
                sensor_id = parts[2]
                return self._sensor_attributes(sensor_id)

        # Default to media player attributes
        return self.attributes

    def _convert_power_state(self, power: str) -> media_player.States:
        """Convert JVC power state string to ucapi media_player.States."""
        power_lower = power.lower()
        if power_lower in ["on", "warming"]:
            return media_player.States.ON
        elif power_lower in ["cooling", "standby", "off"]:
            return media_player.States.STANDBY
        else:
            _LOG.warning("Unknown power state: %s, defaulting to UNKNOWN", power)
            return media_player.States.UNKNOWN

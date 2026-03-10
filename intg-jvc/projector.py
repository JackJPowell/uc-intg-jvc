"""
This module implements the JVC Projector communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from copy import copy
from typing import Any

from const import SELECTS, SENSORS, JVCConfig, SelectConfig, SensorConfig
from jvcprojector import JvcProjector
from jvcprojector import command as jvc_cmd
from jvcprojector.command.base import Command as JvcCommand
from jvcprojector.command.command import SPECIFICATIONS
from jvcprojector.error import JvcProjectorError
from ucapi import media_player
from ucapi.select import States as SelectStates
from ucapi.sensor import States as SensorStates
from ucapi_framework import (
    BaseConfigManager,
    BaseIntegrationDriver,
    ExternalClientDevice,
)
from ucapi_framework.helpers import (
    MediaPlayerAttributes,
    SelectAttributes,
    SensorAttributes,
)

_LOG = logging.getLogger(__name__)


class JVCProjector(ExternalClientDevice):
    """Representing a JVC Projector Device."""

    driver: BaseIntegrationDriver | None

    def __init__(
        self,
        device_config: JVCConfig,
        loop: AbstractEventLoop | None,
        config_manager: BaseConfigManager | None = None,
        driver: BaseIntegrationDriver | None = None,
    ) -> None:
        """Create instance with external client device base."""
        self._device_config: JVCConfig
        super().__init__(
            device_config=device_config,
            loop=loop,
            enable_watchdog=True,
            watchdog_interval=30,
            reconnect_delay=10,
            max_reconnect_attempts=3,
            config_manager=config_manager,
            driver=driver,
        )
        self._projector_lock = asyncio.Lock()
        self._sensor_update_task: asyncio.Task | None = None
        self._source_list: list[str] = ["HDMI1", "HDMI2"]
        self._capabilities: dict[str, Any] = {}
        self._capabilities_retrieved = False

        # Initialize empty sensor and select config dicts (metadata only, not runtime state)
        self.sensors: dict[str, SensorConfig] = {}
        self.selects: dict[str, SelectConfig] = {}

        # Single source-of-truth state dict keyed by logical name.
        # Reserved keys: "power" (media_player.States), "input" (str).
        # All sensor/select IDs share the same namespace — one write updates all.
        self._state_values: dict[str, Any] = {
            "power": None,
            "input": "",
        }
        if device_config.capabilities:
            # Convert list to dict format (same as jp.capabilities() returns)
            self._capabilities = {cmd: None for cmd in device_config.capabilities}
            self._capabilities_retrieved = True
            # Build sensors and selects immediately from cached capabilities
            if device_config.use_sensors:
                self._build_sensors_from_capabilities()
            self._build_selects_from_capabilities()

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
        return self._state_values.get("input") or ""

    @property
    def source_list(self) -> list[str]:
        """Return the list of available input sources."""
        return self._source_list

    @property
    def state(self) -> media_player.States | None:
        """Return the current power state."""
        return self._state_values.get("power")

    @property
    def log_id(self) -> str:
        """Return a log identifier."""
        return (
            self._device_config.name
            if self._device_config.name
            else self._device_config.identifier
        )

    # ─────────────────────────────────────────────────────────────────
    # ExternalClientDevice abstract methods
    # ─────────────────────────────────────────────────────────────────

    async def create_client(self) -> Any:
        """Create the JVC projector client instance."""

        return JvcProjector(
            host=self._device_config.address,
            password=self._device_config.password,
            timeout=5.0,
        )

    async def connect_client(self) -> None:
        """Connect to the JVC projector and initialize state."""
        try:
            _LOG.debug(
                "[%s] Attempting to connect to projector at %s",
                self.name,
                self.address,
            )
            await self._client.connect()
            _LOG.debug("[%s] Connection established successfully", self.name)
        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Failed to connect to projector: %s",
                self.name,
                err,
            )
            raise

        # Get initial power state
        try:
            _LOG.debug("[%s] Querying power state", self.name)
            power_str = await self._client.get(jvc_cmd.Power)
            self._state_values["power"] = self._convert_power_state(str(power_str))
            _LOG.debug("[%s] Power state: %s", self.name, self._state_values["power"])
        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Failed to get power state: %s",
                self.name,
                err,
            )
            raise

        # Discover and store capabilities if not already loaded from config (upgrade case)
        # Only attempt discovery if projector is ON
        if (
            not self._capabilities_retrieved
            and self._state_values["power"] == media_player.States.ON
        ):
            await self.discover_capabilities()
            self._store_capabilities_and_spec_in_config()
            # Only create sensor entities if use_sensors is enabled
            if self.driver and self._device_config.use_sensors:
                # Import here to avoid circular dependency
                from sensor import JVCSensor

                # Create sensor entities and register them
                sensor_entities: list[JVCSensor] = [
                    JVCSensor(self.device_config, self, sensor_config)
                    for sensor_config in self.sensors.values()
                ]
                self.driver.add_entities(sensor_entities)  # type:ignore[arg-type]

            # Create select entities
            if self.driver and self.selects:
                # Import here to avoid circular dependency
                from select_entity import JVCSelect

                # Create select entities and register them
                select_entities: list[JVCSelect] = [
                    JVCSelect(self.device_config, self, select_config)
                    for select_config in self.selects.values()
                ]
                self.driver.add_entities(select_entities)  # type: ignore[arg-type]

        # Get input if projector is on
        if self._state_values["power"] == media_player.States.ON:
            async with self._projector_lock:
                input_value = await self._client.get(jvc_cmd.Input)
                if input_value:
                    self._state_values["input"] = input_value.upper()

        # Update sensors in background task
        if self._sensor_update_task is None or self._sensor_update_task.done():
            self._sensor_update_task = asyncio.create_task(self._update_all_sensors())

        self.push_update()

    async def disconnect_client(self) -> None:
        """Disconnect from the JVC projector."""
        # Stop sensor update task if running
        if self._sensor_update_task and not self._sensor_update_task.done():
            self._sensor_update_task.cancel()
            try:
                await self._sensor_update_task
            except asyncio.CancelledError:
                pass
            self._sensor_update_task = None

        # JvcLib doesn't have an explicit disconnect method
        # The connection is managed internally
        _LOG.debug("[%s] Disconnected from projector", self.name)

    def check_client_connected(self) -> bool:
        """Check if the JVC projector client is connected."""
        # JvcLib doesn't expose a connected property
        # Return True if client exists; watchdog will detect issues when commands fail
        return self._client is not None

    # ─────────────────────────────────────────────────────────────────
    # Device command handling
    # ─────────────────────────────────────────────────────────────────

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
                        power = await self._client.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state in [
                            media_player.States.STANDBY,
                            media_player.States.OFF,
                        ]:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.ON)
                        self._state_values["power"] = media_player.States.ON
                        self.push_update()
                        # Delay sensor updates for 60 seconds to allow projector to warm up
                        asyncio.create_task(self._delayed_sensor_update(60))
                    case "powerOff":
                        power = await self._client.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.OFF)
                        self._state_values["power"] = media_player.States.STANDBY
                        self.push_update()
                        await self._update_all_sensors()
                    case "powerToggle":
                        power = await self._client.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.OFF)
                            self._state_values["power"] = media_player.States.STANDBY
                            self.push_update()
                            await self._update_all_sensors()
                        elif power_state in [
                            media_player.States.STANDBY,
                            media_player.States.OFF,
                        ]:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.ON)
                            self._state_values["power"] = media_player.States.ON
                            self.push_update()
                            asyncio.create_task(self._delayed_sensor_update(60))
                        else:
                            self._state_values["power"] = power_state
                            self.push_update()

                    case "setInput":
                        remote_cmd = jvc_cmd.Remote.HDMI1  # Default to HDMI1
                        source = kwargs.get("source", "")
                        if source.upper() == "HDMI2":
                            remote_cmd = jvc_cmd.Remote.HDMI2
                        await self._client.set(jvc_cmd.Input, remote_cmd)
                        self._state_values["input"] = kwargs["source"].upper()
                        self.push_update()

                    case "remote":
                        code = kwargs.get("code")
                        if code:
                            # For Remote commands, just check if Remote class is supported
                            # Individual remote values don't need separate support checks
                            if not self._client.supports(jvc_cmd.Remote):
                                _LOG.warning(
                                    "[%s] Remote commands not supported",
                                    self.name,
                                )
                                return
                            await self._client.remote(code)

                    case "operation":
                        cmd_class = kwargs.get("cmd_class")
                        value = kwargs.get("value")
                        if cmd_class and value is not None:
                            # Operation commands use set() with command class and value
                            if not self._client.supports(cmd_class):
                                _LOG.warning(
                                    "[%s] Operation command %s not supported",
                                    self.name,
                                    cmd_class.__name__,
                                )
                                return

                            await self._client.set(cmd_class, value)

                            # Single write covers sensor, select, and any other entity
                            # sharing the same key in _state_values
                            for sensor_id, sensor_config in self.sensors.items():
                                if sensor_config.query_command == cmd_class:
                                    self._state_values[sensor_id] = str(value)
                                    self.push_update()
                                    break

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

    async def discover_capabilities(self) -> None:
        """Discover projector capabilities and build dynamic sensor/select lists.

        This must be called after connection is established.
        """
        try:
            async with self._projector_lock:
                # Get capabilities and projector info
                self._capabilities = self._client.capabilities()

                # Get spec and model if not already stored
                if not self._device_config.spec:
                    self._device_config.spec = self._client.spec
                    self._device_config.model = self._client.model
                    _LOG.info(
                        "[%s] Detected spec: %s, model: %s",
                        self.name,
                        self._device_config.spec,
                        self._device_config.model,
                    )

            # Build sensor list from supported queryable commands
            self._build_sensors_from_capabilities()

            # Build select list from supported operation commands
            self._build_selects_from_capabilities()

        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Error discovering capabilities: %s",
                self.name,
                err,
            )

    def _build_sensors_from_capabilities(self) -> None:
        """Filter SENSORS dict based on projector capabilities."""
        new_sensors = {}

        # Add sensors for discovered capabilities
        for cmd_name in self._capabilities:
            if cmd_name in SENSORS:
                # Create a copy to avoid sharing instances between devices
                sensor_config = copy(SENSORS[cmd_name])
                sensor_id = sensor_config.identifier
                _LOG.debug(
                    "[%s] Adding sensor: %s (command: %s)",
                    self.name,
                    sensor_id,
                    cmd_name,
                )
                new_sensors[sensor_id] = sensor_config

        self.sensors = new_sensors

    def _build_selects_from_capabilities(self) -> None:
        """Filter SELECTS dict based on projector capabilities and populate options."""
        new_selects = {}

        # Add selects for discovered capabilities
        for cmd_name in self._capabilities:
            if cmd_name in SELECTS:
                # Create a copy to avoid sharing instances between devices
                select_config = copy(SELECTS[cmd_name])
                select_id = select_config.identifier

                # Extract options from command description
                try:
                    options = self._extract_command_options(select_config.command_class)
                    if options:
                        select_config.options = options
                        _LOG.debug(
                            "[%s] Adding select: %s (command: %s, options: %d)",
                            self.name,
                            select_id,
                            cmd_name,
                            len(options),
                        )
                        new_selects[select_id] = select_config
                    else:
                        _LOG.warning(
                            "[%s] No options found for select %s, skipping",
                            self.name,
                            select_id,
                        )
                except JvcProjectorError as err:
                    _LOG.warning(
                        "[%s] Failed to get options for %s: %s",
                        self.name,
                        select_id,
                        err,
                    )

        self.selects = new_selects

    def _extract_command_options(self, command_class: Any) -> list[str]:
        """Extract valid options from a command class for the connected projector's spec.

        Resolves command parameters statically using the stored spec — no live
        client connection required.

        Args:
            command_class: The command class (e.g., command.PictureMode)

        Returns:
            List of valid option strings for this command, or empty list if
            no spec is available or the command is not supported by this model.
        """
        spec_name = self._device_config.spec
        if not spec_name:
            _LOG.debug(
                "[%s] No spec stored yet; cannot resolve options for %s",
                self.name,
                command_class.__name__,
            )
            return []

        # Strip any model suffix (spec string may be e.g. "CS20241-B8A1")
        base_spec_name = spec_name.split("-")[0]
        spec = next((s for s in SPECIFICATIONS if s.name == base_spec_name), None)
        if spec is None:
            _LOG.warning(
                "[%s] Unknown spec '%s'; cannot resolve options for %s",
                self.name,
                spec_name,
                command_class.__name__,
            )
            return []

        try:
            getattr(command_class, "_resolve")(spec)
            resolved = getattr(command_class, "_parameter", None)
            if not resolved or not resolved.supported():
                return []
            description = command_class.describe()
            param = description.get("parameter", {})
            if isinstance(param, dict) and "write" in param:
                return list(param["write"].values())
            return []
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            _LOG.warning(
                "[%s] Failed to resolve options for %s: %s",
                self.name,
                command_class.__name__,
                err,
            )
            return []
        finally:
            # Unload so the resolved _parameter doesn't bleed across device instances
            # (Command._parameter is a class-level attribute shared globally)
            JvcCommand.unload()

    async def select_option(self, select_id: str, option: str) -> bool:
        """Send a select option command to the projector and update state.

        Args:
            select_id: The select identifier (e.g., 'picture_mode')
            option: The option value to select

        Returns:
            True if the command succeeded, False otherwise.
        """
        if select_id not in self.selects:
            _LOG.warning("[%s] Unknown select '%s'", self.name, select_id)
            return False

        select_config = self.selects[select_id]
        try:
            async with self._projector_lock:
                await self._client.set(select_config.command_class, option)
            self._state_values[select_id] = option
            self.push_update()
            _LOG.info("[%s] Select '%s' set to: %s", self.name, select_id, option)
            return True
        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Failed to set select '%s' to '%s': %s",
                self.name,
                select_id,
                option,
                err,
            )
            return False

    def _store_capabilities_and_spec_in_config(self) -> None:
        """Store discovered capabilities, spec, and model in config for future use."""
        if not self._capabilities or not self._config_manager:
            return

        capabilities_list = list(self._capabilities.keys())
        self._device_config.capabilities = capabilities_list
        self.update_config()
        _LOG.info(
            "[%s] Stored %d capabilities, spec: %s, model: %s in config",
            self.name,
            len(capabilities_list),
            self._device_config.spec,
            self._device_config.model,
        )

    async def _update_all_sensors(self) -> None:
        """Update all sensor values with delays between queries."""
        try:
            # Only query sensor values if projector is on
            if self.state == media_player.States.ON:
                # Acquire lock to serialize access to projector
                async with self._projector_lock:
                    # Query all sensors that have query commands
                    # Note: sensors are only created for supported commands, so no need to check supports_command
                    for sensor_id, sensor_config in self.sensors.items():
                        if sensor_config.query_command:
                            try:
                                # Use new get() API with command classes
                                value = await self._client.get(
                                    sensor_config.query_command
                                )

                                # Single write — all entities (sensor, select, media player)
                                # that share this key will read the updated value
                                self._state_values[sensor_id] = str(value)

                                await asyncio.sleep(0.25)
                            except JvcProjectorError as err:
                                _LOG.warning(
                                    "[%s] Error querying sensor '%s': %s",
                                    self.name,
                                    sensor_id,
                                    err,
                                )
                _LOG.debug("[%s] All sensor values updated", self.name)
            else:
                _LOG.debug(
                    "[%s] Skipping sensor value queries - projector state is %s",
                    self.name,
                    self.state,
                )

            # Push a single update to notify all subscribed entities
            self.push_update()

        except JvcProjectorError as err:  # noqa: BLE001
            _LOG.error("[%s] Error updating sensors: %s", self.name, err)
        finally:
            # Clear the task reference when done
            self._sensor_update_task = None

    async def _delayed_sensor_update(self, delay: int) -> None:
        """Update sensors after a delay.

        Args:
            delay: Delay in seconds before updating sensors
        """
        _LOG.debug(
            "[%s] Delaying sensor update for %d seconds (projector warming up)",
            self.name,
            delay,
        )
        await asyncio.sleep(delay)
        _LOG.debug("[%s] Starting delayed sensor update", self.name)
        await self._update_all_sensors()

    def get_media_player_attributes(self) -> MediaPlayerAttributes:
        """Return current media player attributes built from _state_values."""
        return MediaPlayerAttributes(
            STATE=self._state_values.get("power"),
            SOURCE=self._state_values.get("input", ""),
            SOURCE_LIST=self._source_list,
        )

    def get_sensor_attributes(self, sensor_id: str) -> SensorAttributes | None:
        """Return current sensor attributes for the given sensor_id.

        Args:
            sensor_id: Sensor identifier (e.g., 'picture_mode')

        Returns:
            SensorAttributes or None if sensor_id is not known.
        """

        if sensor_id not in self.sensors:
            return None
        sensor_config = self.sensors[sensor_id]
        value = self._state_values.get(sensor_id)
        state = (
            SensorStates.ON
            if value is not None
            and self._state_values.get("power") == media_player.States.ON
            else SensorStates.UNAVAILABLE
        )
        return SensorAttributes(
            STATE=state,
            VALUE=value if value is not None else sensor_config.default,
            UNIT=sensor_config.unit,
        )

    def get_select_attributes(self, select_id: str) -> SelectAttributes | None:
        """Return current select attributes for the given select_id.

        Args:
            select_id: Select identifier (e.g., 'picture_mode')

        Returns:
            SelectAttributes or None if select_id is not known.
        """

        if select_id not in self.selects:
            return None
        state = (
            SelectStates.ON
            if self._state_values.get("power") == media_player.States.ON
            else SelectStates.UNAVAILABLE
        )
        return SelectAttributes(
            STATE=state,
            CURRENT_OPTION=self._state_values.get(select_id, ""),
            OPTIONS=self.selects[select_id].options or [],
        )

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

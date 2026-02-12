"""
This module implements the JVC Projector communication of the Remote Two/3 integration driver.

"""

import asyncio
import logging
from asyncio import AbstractEventLoop
from copy import copy
from typing import Any

from const import (
    JVCConfig,
    SENSORS,
    SELECTS,
    SensorConfig,
    SelectConfig,
)
from jvcprojector import command as jvc_cmd, JvcProjector
from jvcprojector.error import JvcProjectorError
from ucapi import media_player, EntityTypes
from ucapi.sensor import States as SensorStates
from ucapi_framework import (
    BaseConfigManager,
    ExternalClientDevice,
    EntitySource,
    BaseIntegrationDriver,
)
from ucapi_framework.helpers import MediaPlayerAttributes, SensorAttributes

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
        self._active_source: str = ""
        self._signal: str = ""
        self._capabilities: dict[str, Any] = {}
        self._capabilities_retrieved = False

        # Initialize empty sensors and selects dicts
        self.sensors: dict[str, SensorConfig] = {}
        self.selects: dict[str, SelectConfig] = {}

        # Load capabilities from config if available and build sensors immediately
        if device_config.capabilities:
            # Convert list to dict format (same as jp.capabilities() returns)
            self._capabilities = {cmd: None for cmd in device_config.capabilities}
            self._capabilities_retrieved = True
            # Build sensors and selects immediately from cached capabilities
            if device_config.use_sensors:
                self._build_sensors_from_capabilities()
            self._build_selects_from_capabilities()

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
            self._state = self._convert_power_state(str(power_str))
            _LOG.debug("[%s] Power state: %s", self.name, self._state)
        except JvcProjectorError as err:
            _LOG.error(
                "[%s] Failed to get power state: %s",
                self.name,
                err,
            )
            raise

        # Discover and store capabilities if not already loaded from config (upgrade case)
        # Only attempt discovery if projector is ON
        if not self._capabilities_retrieved and self._state == media_player.States.ON:
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
                from jvc_select import JVCSelect

                # Create select entities and register them
                select_entities: list[JVCSelect] = [
                    JVCSelect(self.device_config, self, select_config)
                    for select_config in self.selects.values()
                ]
                self.driver.add_entities(select_entities)  # type: ignore[arg-type]

        # Get input if projector is on
        if self._state == media_player.States.ON:
            async with self._projector_lock:
                input_value = await self._client.get(jvc_cmd.Input)
                if input_value:
                    self._active_source = input_value.upper()
                    # Update input sensor config
                    input_sensor = self.sensors.get("input")
                    if input_sensor:
                        input_sensor.value = input_value

        # Update sensors in background task
        if self._sensor_update_task is None or self._sensor_update_task.done():
            self._sensor_update_task = asyncio.create_task(self._update_all_sensors())

        # Update attributes dataclass
        self.attributes.STATE = self._state
        self.attributes.SOURCE = self._active_source if self._active_source else ""
        self.attributes.SOURCE_LIST = self._source_list

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
                        self._state = media_player.States.ON
                        self.attributes.STATE = media_player.States.ON
                        # Delay sensor updates for 60 seconds to allow projector to warm up
                        asyncio.create_task(self._delayed_sensor_update(60))
                    case "powerOff":
                        power = await self._client.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.OFF)
                        self._state = media_player.States.STANDBY
                        self.attributes.STATE = media_player.States.STANDBY
                        await self._update_all_sensors()
                    case "powerToggle":
                        power = await self._client.get(jvc_cmd.Power)
                        # Normalize power state from API
                        power_state = self._convert_power_state(str(power))
                        if power_state == media_player.States.ON:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.OFF)
                            self._state = media_player.States.STANDBY
                            self.attributes.STATE = media_player.States.STANDBY
                            await self._update_all_sensors()
                        elif power_state in [
                            media_player.States.STANDBY,
                            media_player.States.OFF,
                        ]:
                            await self._client.set(jvc_cmd.Power, jvc_cmd.Power.ON)
                            self._state = media_player.States.ON
                            self.attributes.STATE = media_player.States.ON
                            asyncio.create_task(self._delayed_sensor_update(60))
                        else:
                            self._state = power_state
                            self.attributes.STATE = power_state

                    case "setInput":
                        remote_cmd = jvc_cmd.Remote.HDMI1  # Default to HDMI1
                        source = kwargs.get("source", "")
                        if source.upper() == "HDMI2":
                            remote_cmd = jvc_cmd.Remote.HDMI2
                        await self._client.set(jvc_cmd.Input, remote_cmd)
                        self._active_source = kwargs["source"].upper()
                        self.attributes.SOURCE = self._active_source
                        await self.update_sensor("input", value=self._active_source)

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

                            # Find and update the corresponding sensor value if sensors are enabled
                            if self._device_config.use_sensors:
                                for sensor_id, sensor_config in self.sensors.items():
                                    if sensor_config.query_command == cmd_class:
                                        # Update sensor with the assigned value (no network call needed)
                                        await self.update_sensor(sensor_id, value=value)
                                        break

                            # Find and update the corresponding select entity
                            for select_id, select_config in self.selects.items():
                                if select_config.command_class == cmd_class:
                                    # Sync the select entity value
                                    await self._sync_sensor_from_select(
                                        select_id, value
                                    )
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
            self._build_sensors_from_capabilities()

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
        if not self._device_config.spec:
            _LOG.warning(
                "[%s] Cannot build selects: spec not available in config",
                self.name,
            )
            return

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
        """Extract valid options from a command's describe() output.

        Args:
            command_class: The command class (e.g., command.PictureMode)

        Returns:
            List of valid option strings for this command
        """
        try:
            description = self._client.describe(command_class)
            if not description or "parameter" not in description:
                return []

            param = description["parameter"]

            # MapParameter returns {"read": {...}, "write": {...}}
            if isinstance(param, dict) and "write" in param:
                # Return the human-readable values (not the hex codes)
                return list(param["write"].values())

            return []

        except JvcProjectorError:
            return []

    async def _sync_select_from_sensor(self, sensor_id: str, value: str) -> None:
        """Update select entity when sensor value changes.

        Args:
            sensor_id: Sensor identifier
            value: New value from sensor
        """
        if not self.driver or not value:
            return

        # Map sensor IDs to select IDs
        sensor_to_select_map = {
            "picture_mode": "picture_mode_select",
            "lens_aperture": "lens_aperture_select",
            "color_profile": "color_profile_select",
            "anamorphic": "anamorphic_select",
            "low_latency": "low_latency_select",
            "mask": "mask_select",
            "lamp_power": "lamp_power_select",
        }

        select_id = sensor_to_select_map.get(sensor_id)
        if not select_id:
            return

        # Find and update the corresponding select entity
        select_entities = self.driver.filter_entities_by_type(
            EntityTypes.SELECT, EntitySource.CONFIGURED
        )
        for entity in select_entities:
            if select_id in entity.id:
                entity.update_value(value)  # type:ignore[attr-defined]
                break

    async def _sync_sensor_from_select(self, select_id: str, value: str) -> None:
        """Update sensor entity when select value changes.

        Args:
            select_id: Select identifier
            value: New value from select
        """
        if not self.driver or not value:
            return

        # Map select IDs to sensor IDs
        select_to_sensor_map = {
            "picture_mode_select": "picture_mode",
            "lens_aperture_select": "lens_aperture",
            "color_profile_select": "color_profile",
            "anamorphic_select": "anamorphic",
            "low_latency_select": "low_latency",
            "mask_select": "mask",
            "lamp_power_select": "lamp_power",
        }

        sensor_id = select_to_sensor_map.get(select_id)
        if not sensor_id or sensor_id not in self.sensors:
            return

        # Update the sensor config value
        self.sensors[sensor_id].value = value

        # Find and update the corresponding sensor entity
        sensor_entities = self.driver.filter_entities_by_type(
            EntityTypes.SENSOR, EntitySource.CONFIGURED
        )
        for entity in sensor_entities:
            if sensor_id in entity.id:
                entity.update_sensor(value)  # type:ignore[attr-defined]
                break

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
                    for sensor_id, sensor in self.sensors.items():
                        if sensor.query_command:
                            try:
                                # Use new get() API with command classes
                                sensor.value = await self._client.get(
                                    sensor.query_command
                                )

                                # Update corresponding select entity if it exists
                                await self._sync_select_from_sensor(
                                    sensor_id, sensor.value
                                )

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

            # Always refresh sensor entity states (even when projector is off)
            # This updates sensor state to UNAVAILABLE when projector is off
            if self.driver:
                sensor_entities = self.driver.filter_entities_by_type(
                    EntityTypes.SENSOR, EntitySource.CONFIGURED
                )
                for entity in sensor_entities:
                    entity.refresh_state()  # type:ignore[attr-defined]

                # Also update select entities
                select_entities = self.driver.filter_entities_by_type(
                    EntityTypes.SELECT, EntitySource.CONFIGURED
                )
                for entity in select_entities:
                    if self.state != media_player.States.ON:
                        entity.set_unavailable()  # type:ignore[attr-defined]

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

    async def update_sensor(self, sensor_key: str, value: Any = None) -> None:
        """Update a specific sensor value and trigger entity refresh.

        Args:
            sensor_key: The sensor identifier (e.g., 'picture_mode', 'low_latency')
            value: Optional pre-assigned value to use instead of querying the projector
        """
        try:
            # Get sensor config
            sensor = self.sensors.get(sensor_key)
            if not sensor:
                _LOG.warning(
                    "[%s] Sensor '%s' not found",
                    self.name,
                    sensor_key,
                )
                return

            # Use provided value if available, otherwise query the projector
            if value is not None:
                # Use the assigned value directly (no network call)
                sensor.value = value
                _LOG.debug(
                    "[%s] Sensor '%s' value set to %s (assigned)",
                    self.name,
                    sensor_key,
                    value,
                )
            elif sensor.query_command and self.state == media_player.States.ON:
                # Only query value if projector is ON and no value was provided
                # Acquire lock to serialize access to projector
                async with self._projector_lock:
                    # Query the specific sensor value and store in sensor config
                    sensor.value = await self._client.get(sensor.query_command)
                _LOG.debug(
                    "[%s] Sensor '%s' value updated (queried)",
                    self.name,
                    sensor_key,
                )
            else:
                _LOG.debug(
                    "[%s] Skipping sensor '%s' value query - projector state is %s",
                    self.name,
                    sensor_key,
                    self.state,
                )

            # Always trigger sensor entity state refresh (even when projector is off)
            if self.driver:
                # Find the specific sensor entity by matching the sensor_id in the entity_id
                sensor_entities = self.driver.filter_entities_by_type(
                    EntityTypes.SENSOR, EntitySource.CONFIGURED
                )
                for entity in sensor_entities:
                    # Entity ID format: sensor.{device_id}.{sensor_id}
                    if entity.id.endswith(f".{sensor_key}"):
                        entity.refresh_state()  # ty:ignore[unresolved-attribute]
                        break

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
        sensor_state = SensorStates.UNKNOWN
        if self.state == media_player.States.ON:
            sensor_state = SensorStates.ON
        elif self.state == media_player.States.STANDBY:
            sensor_state = SensorStates.UNKNOWN

        # Return value if projector is ON, otherwise use default
        # Use 'is not None' check to allow empty strings as valid values
        return SensorAttributes(
            STATE=sensor_state,
            VALUE=value
            if self.state == media_player.States.ON and value is not None
            else sensor_config.default,
            UNIT=sensor_config.unit,
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

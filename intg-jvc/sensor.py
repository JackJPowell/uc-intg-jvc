"""
Sensor entity functions for the JVC integration.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from const import JVCConfig, SensorConfig
from projector import JVCProjector
from ucapi import EntityTypes
from ucapi.sensor import Attributes, DeviceClasses, States
from ucapi_framework import create_entity_id
from ucapi_framework.entities import SensorEntity

_LOG = logging.getLogger(__name__)


class JVCSensor(SensorEntity):
    """Representation of a JVC Sensor entity."""

    def __init__(
        self,
        config_device: JVCConfig,
        device: JVCProjector,
        sensor_config: SensorConfig,
    ):
        """Initialize a JVC Sensor entity.

        Args:
            config_device: Device configuration
            device: JVCProjector device instance
            sensor_config: SensorConfig dataclass with sensor metadata
        """
        self._device = device
        self._sensor_id = sensor_config.identifier

        # Set entity_id for FrameworkEntity mixin
        self._entity_id = create_entity_id(
            EntityTypes.SENSOR, config_device.identifier, sensor_config.identifier
        )

        attributes: dict[str, Any] = {
            Attributes.STATE: States.UNAVAILABLE,
            Attributes.VALUE: sensor_config.default,
        }

        if sensor_config.unit is not None:
            attributes[Attributes.UNIT] = sensor_config.unit

        _LOG.debug("Initializing sensor entity: %s", self._entity_id)

        super().__init__(
            identifier=self._entity_id,
            name=f"{sensor_config.name}",
            features=[],
            attributes=attributes,
            device_class=DeviceClasses.CUSTOM,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        """Sync entity state from device attributes."""
        if self._device is None:
            self.set_unavailable()
            return
        attrs = self._device.get_sensor_attributes(self._sensor_id)
        if attrs is None:
            self.set_unavailable()
        else:
            self.update(attrs)

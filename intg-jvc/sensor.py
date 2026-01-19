"""
Sensor entity functions for the JVC integration.

:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from const import JVCConfig, SensorConfig
from projector import JVCProjector
from ucapi import EntityTypes
from ucapi.sensor import Attributes, DeviceClasses, Sensor, States
from ucapi_framework import create_entity_id
from ucapi_framework.entity import Entity as FrameworkEntity

_LOG = logging.getLogger(__name__)


class JVCSensor(Sensor, FrameworkEntity):
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
            Attributes.STATE: States.UNKNOWN,
            Attributes.VALUE: sensor_config.default,
        }

        if sensor_config.unit is not None:
            attributes[Attributes.UNIT] = sensor_config.unit

        _LOG.debug("Initializing sensor entity: %s", self._entity_id)

        super().__init__(
            identifier=self._entity_id,
            name=f"{config_device.name} {sensor_config.name}",
            features=[],
            attributes=attributes,
            device_class=DeviceClasses.CUSTOM,
        )

        self._device.register_sensor_entity(sensor_config.identifier, self)

    def refresh_state(self) -> None:
        """Refresh sensor state from device and update entity.

        This method is called by the device after updating sensor values.
        It retrieves the current attributes and uses entity.update() to
        notify the framework.
        """

        self.update(self._device.get_device_attributes(self.id))

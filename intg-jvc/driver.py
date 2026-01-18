"""
This module implements a Remote Two integration driver for JVC Projector devices.

:copyright: (c) 2025 by Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os

from const import JVCConfig
from discover import JVCProjectorDiscovery
from media_player import JVCMediaPlayer
from projector import JVCProjector
from remote import JVCRemote
from sensor import JVCSensor
from setup import JVCSetupFlow
from ucapi_framework import BaseConfigManager, BaseIntegrationDriver, get_config_path
from const import SENSORS

_LOG = logging.getLogger("driver")


async def main():
    """Start the Remote Two integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("media_player").setLevel(level)
    logging.getLogger("remote").setLevel(level)
    logging.getLogger("projector").setLevel(level)
    logging.getLogger("sensor").setLevel(level)
    logging.getLogger("setup_flow").setLevel(level)

    driver = BaseIntegrationDriver(
        device_class=JVCProjector,
        entity_classes=[
            JVCMediaPlayer,
            JVCRemote,
            lambda cfg, dev: [
                JVCSensor(cfg, dev, sensor_config)
                for sensor_config in SENSORS
            ],
        ],
    )
    driver.config_manager = BaseConfigManager(
        get_config_path(driver.api.config_dir_path),
        driver.on_device_added,
        driver.on_device_removed,
        config_class=JVCConfig,
    )

    await driver.register_all_configured_devices()

    discovery = JVCProjectorDiscovery(timeout=1, search_pattern="JVC")
    setup_handler = JVCSetupFlow.create_handler(driver, discovery=discovery)
    await driver.api.init("driver.json", setup_handler)

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

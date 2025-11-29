"""
This module implements a Remote Two integration driver for JVC Projector devices.

:copyright: (c) 2025 by Jack Powell.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os

from const import JVCDevice
from discover import JVCProjectorDiscovery
from media_player import JVCMediaPlayer
from projector import JVCProjector
from remote import JVCRemote
from setup import JVCSetupFlow
from ucapi_framework import BaseDeviceManager, BaseIntegrationDriver, get_config_path


async def main():
    """Start the Remote Two integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("media_player").setLevel(level)
    logging.getLogger("remote").setLevel(level)
    logging.getLogger("projector").setLevel(level)
    logging.getLogger("setup_flow").setLevel(level)

    loop = asyncio.get_running_loop()

    driver = BaseIntegrationDriver(
        loop=loop, device_class=JVCProjector, entity_classes=[JVCMediaPlayer, JVCRemote]
    )
    driver.config = BaseDeviceManager(
        get_config_path(driver.api.config_dir_path),
        driver.on_device_added,
        driver.on_device_removed,
        device_class=JVCDevice,
    )

    for device in list(driver.config.all()):
        driver.add_configured_device(device)

    discovery = JVCProjectorDiscovery(timeout=1, search_pattern="JVC")
    setup_handler = JVCSetupFlow.create_handler(driver.config, discovery=discovery)
    await driver.api.init("driver.json", setup_handler)

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

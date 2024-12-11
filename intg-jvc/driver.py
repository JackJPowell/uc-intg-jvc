#!/usr/bin/env python3

"""Main driver file. Run this module to start the integration driver"""

import sys
import os
import asyncio
import logging
import logging.handlers

import ucapi

import config
import setup
import media_player

_LOG = logging.getLogger("driver")

loop = asyncio.get_event_loop()
api = ucapi.IntegrationAPI(loop)


async def startcheck():
    """
    Called at the start of the integration driver to load the config file into the runtime storage and add all needed entities and create attributes poller tasks
    """
    try:
        config.Setup.load()
    except OSError as o:
        _LOG.critical(o)
        _LOG.critical("Stopping integration driver")
        raise SystemExit(0) from o

    if config.Setup.get("setup_complete"):
        try:
            mp_entity_id = config.Setup.get("id")
            mp_entity_name = config.Setup.get("name")
            try:
                mp_entity_password = config.Setup.get("password")
            except ValueError:
                _LOG.debug("No password set")
        except ValueError as v:
            _LOG.error(v)

        if api.available_entities.contains(mp_entity_id):
            _LOG.debug(
                "Projector media player entity with id "
                + mp_entity_id
                + " is already in storage as available entity"
            )
        else:
            await media_player.add_mp(mp_entity_id, mp_entity_name)


@api.listens_to(ucapi.Events.CONNECT)
async def on_r2_connect() -> None:
    """
    Connect notification from Remote Two.

    Just reply with connected as there is no permanent connection to the projector that needs to be re-established
    """
    _LOG.info("Received connect event message from remote")

    await api.set_device_state(ucapi.DeviceStates.CONNECTED)

    mp_entity_password = None
    if config.Setup.get("setup_complete"):
        try:
            ip = config.Setup.get("ip")
            mp_entity_id = config.Setup.get("id")
            try:
                mp_entity_password = config.Setup.get("password")
            except ValueError:
                _LOG.debug("No password set")
        except ValueError as v:
            _LOG.error(v)

        await media_player.create_mp_poller(mp_entity_id, ip, mp_entity_password)


@api.listens_to(ucapi.Events.DISCONNECT)
async def on_r2_disconnect() -> None:
    """
    Disconnect notification from the remote Two.

    Just reply with disconnected as there is no permanent connection to the projector that needs to be closed
    """
    _LOG.info("Received disconnect event message from remote")

    if config.Setup.get("setup_complete"):
        _LOG.info("Stopping all attributes poller tasks")

        tasks = ["mp_poller"]
        for task_name in tasks:
            try:
                (poller_task,) = [
                    task for task in asyncio.all_tasks() if task.get_name() == task_name
                ]
                poller_task.cancel()
                try:
                    await poller_task
                except asyncio.CancelledError:
                    _LOG.debug("Stopped " + task_name + " task")
            except ValueError:
                _LOG.debug(task_name + " task is not running")

    await api.set_device_state(ucapi.DeviceStates.DISCONNECTED)


@api.listens_to(ucapi.Events.ENTER_STANDBY)
async def on_r2_enter_standby() -> None:
    """
    Enter standby notification from Remote Two.

    Set config.R2_IN_STANDBY to True and show a debug log message as there is no permanent connection to the projector that needs to be closed.
    """
    _LOG.info("Received enter standby event message from remote")

    _LOG.debug("Set config.R2_IN_STANDBY to True")
    config.Setup.set("standby", True)


@api.listens_to(ucapi.Events.EXIT_STANDBY)
async def on_r2_exit_standby() -> None:
    """
    Exit standby notification from Remote Two.

    Just show a debug log message as there is no permanent connection to the projector that needs to be re-established.
    """
    _LOG.info("Received exit standby event message from remote")

    _LOG.debug("Set config.R2_IN_STANDBY to False")
    config.Setup.set("standby", False)


@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]) -> None:
    """
    Subscribe to given entities.

    :param entity_ids: entity identifiers.
    """
    _LOG.info("Received subscribe entities event for entity ids: " + str(entity_ids))

    config.Setup.set("standby", False)
    ip = config.Setup.get("ip")
    mp_entity_id = config.Setup.get("id")

    for entity_id in entity_ids:
        try:
            if entity_id == mp_entity_id:
                await media_player.update_mp(entity_id, ip)
        except OSError as o:
            _LOG.critical(o)
        except Exception as e:
            _LOG.warning(e)


@api.listens_to(ucapi.Events.UNSUBSCRIBE_ENTITIES)
async def on_unsubscribe_entities(entity_ids: list[str]) -> None:
    """
    Unsubscribe to given entities.

    Just show a debug log message as there is no permanent connection to the projector or clients that needs to be closed or removed.
    """
    _LOG.info("Unsubscribe entities event for: %s", entity_ids)


def setup_logger():
    """Get logger from all modules"""

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()

    logging.getLogger("ucapi.api").setLevel(level)
    logging.getLogger("ucapi.entities").setLevel(level)
    logging.getLogger("ucapi.entity").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("config").setLevel(level)
    logging.getLogger("setup").setLevel(level)
    logging.getLogger("projector").setLevel(level)
    logging.getLogger("media_player").setLevel(level)
    logging.getLogger("remote").setLevel(level)
    logging.getLogger("sensor").setLevel(level)


async def main():
    """Main function that gets logging from all sub modules and starts the driver"""

    # Check if integration runs in a PyInstaller bundle on the remote and adjust the logging format, config file path and projector attributes poller interval
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        logging.basicConfig(format="%(name)-14s %(levelname)-8s %(message)s")
        setup_logger()

        _LOG.info(
            "This integration is running in a PyInstaller bundle. Probably on the remote hardware"
        )
        config.Setup.set("bundle_mode", True)

        cfg_path = os.environ["UC_CONFIG_HOME"] + "/config.json"
        config.Setup.set("cfg_path", cfg_path)
        _LOG.info("The configuration is stored in " + cfg_path)

        _LOG.info(
            "Deactivating projector attributes poller to reduce battery consumption when running on the remote"
        )
        config.Setup.set("mp_poller_interval", 0)
    else:
        logging.basicConfig(
            format="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-14s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        setup_logger()

    _LOG.debug("Starting driver")

    await setup.init()
    await startcheck()


if __name__ == "__main__":
    loop.run_until_complete(main())
    loop.run_forever()

#!/usr/bin/env python3

"""Module that includes all functions needed for the setup and reconfiguration process"""

import logging

from ipaddress import ip_address
import ucapi

from jvc_projector_remote import JVCProjector, JVCCannotConnectError

import config
import driver
import media_player

_LOG = logging.getLogger(__name__)


async def init():
    """Advertises the driver metadata and first setup page to the remote using driver.json"""
    await driver.api.init("driver.json", driver_setup_handler)


async def driver_setup_handler(msg: ucapi.SetupDriver) -> ucapi.SetupAction:
    """
    Dispatch driver setup requests to corresponding handlers.

    Either start the setup process or handle the provided user input data.

    :param msg: the setup driver request object, either DriverSetupRequest,
                UserDataResponse or UserConfirmationResponse
    :return: the setup action on how to continue
    """
    if isinstance(msg, ucapi.DriverSetupRequest):
        return await handle_driver_setup(msg)
    elif isinstance(msg, ucapi.AbortDriverSetup):
        _LOG.info("Setup was aborted with code: %s", msg.error)

    _LOG.error("Error during setup")
    config.Setup.set("setup_complete", False)
    return ucapi.SetupError()


async def handle_driver_setup(
    msg: ucapi.DriverSetupRequest,
) -> ucapi.SetupAction:
    """
    Start driver setup.

    Initiated by Remote Two to set up the driver.

    :param msg: value(s) of input fields in the first setup screen.
    :return: the setup action on how to continue
    """

    if msg.reconfigure and config.Setup.get("setup_complete"):
        _LOG.info("Starting reconfiguration")
        config.Setup.set("setup_reconfigure", True)

    ip = msg.setup_data["ip"]
    password = msg.setup_data["password"]
    name = msg.setup_data["name"]

    if ip != "":
        # Check if input is a valid ipv4 or ipv6 address
        try:
            ip_address(ip)
        except ValueError:
            _LOG.error("The entered ip address %s is not valid", ip)
            return ucapi.SetupError(error_type=ucapi.IntegrationSetupError.NOT_FOUND)

        _LOG.info("Entered ip address: %s", ip)

        try:
            _LOG.debug(ip)
            projector = JVCProjector(
                ip, password=password, port=20554, delay_ms=600, connect_timeout=10, max_retries=10
            )
            mac = projector.get_mac()
            config.Setup.set("ip", ip)
            config.Setup.set("id", mac)
            config.Setup.set("name", name)
        except JVCCannotConnectError as ex:
            _LOG.error("Unable to connect at IP: %s", ip)
            _LOG.info("Please check if you entered the correct ip of the projector")
            return ucapi.SetupError(
                error_type=ucapi.IntegrationSetupError.CONNECTION_REFUSED
            )
    else:
        _LOG.info("No ip address entered")
        return ucapi.SetupError()

    try:
        mp_entity_id = config.Setup.get("id")
        mp_entity_name = config.Setup.get("name")
    except ValueError as v:
        _LOG.error(v)
        return ucapi.SetupError()

    await media_player.add_mp(mp_entity_id, mp_entity_name)
    await media_player.create_mp_poller(mp_entity_id, ip)

    config.Setup.set("setup_complete", True)
    _LOG.info("Setup complete")
    return ucapi.SetupComplete()

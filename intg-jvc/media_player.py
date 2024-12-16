#!/usr/bin/env python3

"""Module that includes functions to add a projector media player entity, poll attributes and the media player command handler"""

import logging
from typing import Any

import ucapi

import config
import driver
from projector import Projector

_LOG = logging.getLogger(__name__)


async def mp_cmd_handler(
    entity: ucapi.MediaPlayer, cmd_id: str, _params: dict[str, Any] | None
) -> ucapi.StatusCodes:
    """
    Media Player command handler.

    Called by the integration-API if a command is sent to a configured media_player-entity.

    :param entity: media_player entity
    :param cmd_id: command
    :param _params: optional command parameters
    :return: status of the command
    """
    password = None
    try:
        ip = config.Setup.get("ip")
        try:
            password = config.Setup.get("password")
        except ValueError:
            _LOG.debug("No password set")
        api = Projector(ip, password)
    except ValueError as v:
        _LOG.error(v)
        return ucapi.StatusCodes.SERVER_ERROR

    try:
        if _params is None:
            _LOG.info("Received %s command for %s", cmd_id, entity.id)
            await api.send_cmd(entity.id, cmd_id)
        else:
            _LOG.info(
                "Received %s command with parameter %s for %s",
                cmd_id,
                _params,
                entity.id,
            )
            await api.send_cmd(entity.id, cmd_id, _params)
    except Exception as e:
        if e is None:
            return ucapi.StatusCodes.SERVER_ERROR
        return ucapi.StatusCodes.BAD_REQUEST
    return ucapi.StatusCodes.OK


async def add_mp(ent_id: str, name: str):
    """Function to add a media player entity with the config.MpDef class definition"""

    _LOG.info(
        "Add projector media player entity with id " + ent_id + " and name " + name
    )

    definition = ucapi.MediaPlayer(
        ent_id,
        name,
        features=config.MpDef.features,
        attributes=config.MpDef.attributes,
        device_class=config.MpDef.device_class,
        options=config.MpDef.options,
        cmd_handler=mp_cmd_handler,
    )

    _LOG.debug("Projector media player entity definition created")

    driver.api.available_entities.add(definition)

    _LOG.info("Added projector media player entity")


async def create_mp_poller(ent_id: str, ip: str, password: str | None = None):
    """Creates a task to regularly poll attributes from the projector"""

    mp_poller_interval = config.Setup.get("mp_poller_interval")

    if mp_poller_interval == 0:
        _LOG.info(
            "Projector attributes poller interval set to "
            + str(mp_poller_interval)
            + ". Task will not be started"
        )
    else:
        driver.loop.create_task(
            mp_poller(ent_id, mp_poller_interval, ip, password), name="mp_poller"
        )
        _LOG.debug(
            "Started projector attributes poller task with an interval of "
            + str(mp_poller_interval)
            + " seconds"
        )


async def mp_poller(
    entity_id: str, interval: int, ip: str, password: str | None = None
) -> None:
    """Projector attributes poller task"""
    while True:
        await driver.asyncio.sleep(interval)
        # TODO Implement check if there are too many timeouts to the projector and automatically deactivate poller and set entity status to unknown
        # TODO #WAIT Check if there are configured entities using the get_configured_entities api request once the UC Python library supports this
        if config.Setup.get("standby"):
            continue
        try:
            # TODO Add check if network and remote is reachable
            await update_mp(entity_id, ip, password)
        except Exception as e:
            _LOG.warning(e)


async def update_mp(entity_id: str, ip: str, password: str | None = None):
    """Retrieve input source, power state and muted state from the projector, compare them with the known state on the remote and update them if necessary"""

    try:
        source = None
        api = Projector(ip, password)
        state = api.get_attr_power()
        _LOG.debug(
            "Projector State: %s - UC State on: %s", state, ucapi.media_player.States.ON
        )
        if state == ucapi.media_player.States.ON:
            source = api.get_attr_source()
    except Exception as e:
        raise Exception(e) from e

    try:
        stored_states = await driver.api.available_entities.get_states()
    except Exception as e:
        raise Exception(e) from e

    if stored_states != []:
        attributes_stored = stored_states[0][
            "attributes"
        ]  # [0] = 1st entity that has been added
    else:
        raise Exception(
            "Got empty states from remote. Please make sure to add configured entities"
        )

    stored_attributes = {
        "state": attributes_stored["state"],
        "source": attributes_stored["source"],
    }
    current_attributes = {"state": state, "source": source}

    attributes_to_check = ["state"]
    if state == ucapi.media_player.States.ON:
        attributes_to_check.append("source")
    attributes_to_update = []
    attributes_to_skip = []

    for attribute in attributes_to_check:
        if current_attributes[attribute] != stored_attributes[attribute]:
            attributes_to_update.append(attribute)
        else:
            attributes_to_skip.append(attribute)

    if not attributes_to_skip:
        _LOG.debug(
            "Entity attributes for "
            + str(attributes_to_skip)
            + " have not changed since the last update"
        )

    if attributes_to_update:
        attributes_to_send = {}
        if "state" in attributes_to_update:
            attributes_to_send.update({ucapi.media_player.Attributes.STATE: state})
        if "source" in attributes_to_update:
            attributes_to_send.update({ucapi.media_player.Attributes.SOURCE: source})

        try:
            if attributes_to_send:
                api_update_attributes = driver.api.configured_entities.update_attributes(
                    entity_id, attributes_to_send
                )
            else:
                _LOG.debug("Nothing to update")
        except Exception as e:
            raise Exception(
                "Error while updating attributes for entity id " + entity_id
            ) from e

        if not api_update_attributes:
            raise Exception(
                "Entity "
                + entity_id
                + " not found. Please make sure it's added as a configured entity on the remote"
            )
        else:
            _LOG.info(
                "Updated entity attribute(s) "
                + str(attributes_to_update)
                + " for "
                + entity_id
            )

    else:
        _LOG.debug("No projector attributes to update. Skipping update process")

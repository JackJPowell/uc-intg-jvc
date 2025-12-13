"""Module that includes all functions needed for the setup and reconfiguration process"""

import logging
from ipaddress import ip_address
from typing import Any

from const import JVCConfig
from jvcprojector.projector import JvcProjector
from ucapi import IntegrationSetupError, RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

_LOG = logging.getLogger(__name__)

_MANUAL_INPUT_SCHEMA = RequestUserInput(
    {"en": "JVC Projector Setup"},
    [
        {
            "id": "info",
            "label": {
                "en": "Setup your JVC Projector",
            },
            "field": {
                "label": {
                    "value": {
                        "en": (
                            "Please supply the IP address or Hostname of your JVC Projector."
                        ),
                    }
                }
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "name",
            "label": {
                "en": "Projector Name",
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "address",
            "label": {
                "en": "IP Address",
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "password",
            "label": {
                "en": "Password",
            },
        },
    ],
)


class JVCSetupFlow(BaseSetupFlow[JVCConfig]):
    """
    Setup flow for JVC Projector integration.

    Handles JVC Projector configuration through SSDP discovery or manual entry.
    """

    def get_manual_entry_form(self) -> RequestUserInput:
        """
        Return the manual entry form for device setup.

        :return: RequestUserInput with form fields for manual configuration
        """
        return _MANUAL_INPUT_SCHEMA

    def get_additional_discovery_fields(self) -> list[dict]:
        return [
            {
                "field": {"text": {"value": ""}},
                "id": "name",
                "label": {
                    "en": "Projector Name",
                },
            },
            {
                "field": {"text": {"value": ""}},
                "id": "password",
                "label": {
                    "en": "Password",
                },
            },
        ]

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> JVCConfig | SetupError | RequestUserInput:
        """
        Create JVC device configuration from manual entry.

        :param input_values: User input containing 'address' and 'password' and 'name'
        :return: JVC device configuration or RequestUserInput to re-display form
        """
        address = input_values.get("address", "").strip()
        password = input_values.get("password", "").strip()
        name = (input_values.get("name", "")).strip()

        if not name or name == "":
            name = "JVC Projector"

        if not address:
            # Re-display the form if address is missing
            _LOG.warning("Address is required, re-displaying form")
            return _MANUAL_INPUT_SCHEMA

        _LOG.debug("Connecting to JVC Projector at %s", address)

        try:
            address = ip_address(address).compressed
        except ValueError:
            _LOG.error("Invalid IP address provided: %s", address)
            _LOG.info("Please enter a valid IP address for the projector.")
            return _MANUAL_INPUT_SCHEMA

        try:
            jvc = JvcProjector(address, password=password)
            try:
                await jvc.connect()
                info = await jvc.get_info()
            finally:
                await jvc.disconnect()
            _LOG.debug("JVC Projector info: %s", info)

            return JVCConfig(
                identifier=info.get("mac", info.get("model", "jvc")),
                name=name,
                address=address,
                password=password,
            )

        except Exception as ex:  # pylint: disable=broad-exception-caught
            _LOG.error("Unable to connect at Address: %s. Exception: %s", address, ex)
            _LOG.info(
                "Please check if you entered the correct address of the projector"
            )
            return SetupError(IntegrationSetupError.CONNECTION_REFUSED)

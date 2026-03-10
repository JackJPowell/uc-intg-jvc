"""Module that includes all functions needed for the setup and reconfiguration process"""

import logging
from ipaddress import ip_address
from typing import Any

from const import JVCConfig
from jvcprojector import JvcProjector, command
from jvcprojector.error import JvcProjectorError
from ucapi import IntegrationSetupError, RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

_LOG = logging.getLogger(__name__)


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
        return RequestUserInput(
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
                {
                    "field": {"checkbox": {"value": True}},
                    "id": "use_sensors",
                    "label": {
                        "en": "Enable Sensors",
                    },
                },
            ],
        )

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
            {
                "field": {"checkbox": {"value": True}},
                "id": "use_sensors",
                "label": {
                    "en": "Enable Sensors",
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
        use_sensors = input_values.get("use_sensors", True)

        if not name or name == "":
            name = "JVC Projector"

        if not address:
            # Re-display the form if address is missing
            _LOG.warning("Address is required, re-displaying form")
            return self.get_manual_entry_form()

        _LOG.debug("Connecting to JVC Projector at %s", address)

        try:
            address = ip_address(address).compressed
        except ValueError:
            _LOG.error("Invalid IP address provided: %s", address)
            _LOG.info("Please enter a valid IP address for the projector.")
            return self.get_manual_entry_form()

        try:
            _LOG.debug("Creating JvcProjector instance for %s (password set: %s)", address, bool(password))
            jvc = JvcProjector(address, password=password)
            try:
                _LOG.debug("Attempting jvc.connect() to %s", address)
                await jvc.connect()
                _LOG.debug("jvc.connect() succeeded")

                # Get MAC address, model, and spec from connected projector
                _LOG.debug("Requesting MAC address")
                mac = await jvc.get(command.MacAddress)
                _LOG.debug("MAC address: %s", mac)

                model = jvc.model
                _LOG.debug("Model: %s", model)

                spec = jvc.spec
                _LOG.debug("Spec: %s", spec)

                # Get capabilities to store in config
                _LOG.debug("Requesting capabilities")
                capabilities_dict = jvc.capabilities()
                capabilities_list = (
                    list(capabilities_dict.keys()) if capabilities_dict else []
                )
                _LOG.debug("Capabilities: %d commands", len(capabilities_list))
            finally:
                _LOG.debug("Disconnecting from %s", address)
                await jvc.disconnect()
                _LOG.debug("Disconnected")
            _LOG.debug("JVC Projector MAC: %s, Model: %s, Spec: %s", mac, model, spec)

            return JVCConfig(
                identifier=mac if mac else model,
                name=name,
                address=address,
                password=password,
                capabilities=capabilities_list,
                spec=spec,
                model=model,
                use_sensors=use_sensors,
            )

        except JvcProjectorError as ex:
            _LOG.error(
                "JvcProjectorError during setup for %s: %s",
                address,
                ex,
                exc_info=True,
            )
            return SetupError(IntegrationSetupError.CONNECTION_REFUSED)

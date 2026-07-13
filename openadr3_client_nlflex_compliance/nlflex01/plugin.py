# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""NL-Flex compliance plugin for OpenADR3 client."""

from typing import Any

from openadr3_client.extensions.resource_group.models.resource_group import ResourceGroup
from openadr3_client.oadr310.models.event.event import Event
from openadr3_client.oadr310.models.program.program import Program
from openadr3_client.oadr310.models.report.report import Report
from openadr3_client.oadr310.models.resource.resource import Resource
from openadr3_client.oadr310.models.ven.ven import Ven
from openadr3_client.plugin import ValidatorPlugin

from openadr3_client_nlflex_compliance.nlflex01.event_nlflex_compliant import validate_event_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex01.program_nlflex_compliant import validate_program_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex01.report_nlflex_compliant import validate_report_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex01.resource_group_nlflex_compliant import (
    validate_resource_group_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex01.resource_nlflex_compliant import validate_resource_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex01.ven_nlflex_compliant import validate_ven_nlflex_compliant


class Nlflex01ValidatorPlugin(ValidatorPlugin):
    """Plugin that validates OpenADR3 models for NL-Flex 0.1 compliance."""

    def __init__(self) -> None:
        """Initialize the NL-Flex validator plugin."""
        super().__init__()

    @staticmethod
    def setup(*_args: Any, **_kwargs: Any) -> "Nlflex01ValidatorPlugin":  # noqa: ANN401
        """
        Set up the NL-Flex validator plugin.

        Args:
            *args: Positional arguments (unused).
            **kwargs: Keyword arguments (unused).

        Returns:
            Nlflex01ValidatorPlugin: Configured plugin instance.

        """
        plugin = Nlflex01ValidatorPlugin()

        plugin.register_model_validator(Event, validate_event_nlflex_compliant)
        plugin.register_model_validator(Program, validate_program_nlflex_compliant)
        plugin.register_model_validator(Ven, validate_ven_nlflex_compliant)
        plugin.register_model_validator(Resource, validate_resource_nlflex_compliant)
        plugin.register_model_validator(ResourceGroup, validate_resource_group_nlflex_compliant)
        plugin.register_model_validator(Report, validate_report_nlflex_compliant)

        return plugin

# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""OpenADR DER profile specification v1.0.0 compliance plugin for the OpenADR3 client."""

from typing import Any, override

from openadr3_client.extensions.resource_group.models.resource_group import ResourceGroup
from openadr3_client.oadr310.models.event.event import Event
from openadr3_client.oadr310.models.program.program import Program
from openadr3_client.oadr310.models.report.report import Report
from openadr3_client.oadr310.models.resource.resource import Resource
from openadr3_client.oadr310.models.ven.ven import Ven
from openadr3_client.plugin import ValidatorPlugin

from openadr3_client_nlflex_compliance.nlflex10.event_nlflex_compliant import validate_event_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.program_nlflex_compliant import validate_program_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.report_nlflex_compliant import validate_report_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.resource_group_nlflex_compliant import (
    validate_resource_group_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex10.resource_nlflex_compliant import validate_resource_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.ven_nlflex_compliant import validate_ven_nlflex_compliant


class Nlflex10ValidatorPlugin(ValidatorPlugin):
    """Plugin that validates OpenADR3 models against the OpenADR DER profile specification v1.0.0."""

    def __init__(self) -> None:
        """Initialize the validator plugin."""
        super().__init__()

    @staticmethod
    @override
    def setup(*_args: Any, **_kwargs: Any) -> "Nlflex10ValidatorPlugin":
        """
        Set up the validator plugin.

        Args:
            *args: Positional arguments (unused).
            **kwargs: Keyword arguments (unused).

        Returns:
            Nlflex10ValidatorPlugin: Configured plugin instance.

        """
        plugin = Nlflex10ValidatorPlugin()

        plugin.register_model_validator(Event, validate_event_nlflex_compliant)
        plugin.register_model_validator(Program, validate_program_nlflex_compliant)
        plugin.register_model_validator(Ven, validate_ven_nlflex_compliant)
        plugin.register_model_validator(Resource, validate_resource_nlflex_compliant)
        plugin.register_model_validator(ResourceGroup, validate_resource_group_nlflex_compliant)
        plugin.register_model_validator(Report, validate_report_nlflex_compliant)

        return plugin

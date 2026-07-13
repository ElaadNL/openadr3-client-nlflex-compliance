# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""Module which implements NL-Flex 0.1 compliance validators for the resource group OpenADR3 extension types."""

import re

from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.extensions.resource_group.models.resource_group import ResourceGroup
from pydantic_core import InitErrorDetails, PydanticCustomError

DSO_IDENTIFIER_REGEX = r"^DSB-[A-Z]+$"
SERVICE_PROVIDER_IDENTIFIER_REGEX = r"^SP-[A-Z]+$"

# See Section 11.3.3, "Object constraints and requirements" of the NL-Flex specification.
KNOWN_MAX_DURATIONS = frozenset({"PT2H", "PT4H", "PT6H"})

DSO_ID_ATTRIBUTE = VenResourceAttributeType("DSO_ID")
SERVICE_PROVIDER_ID_ATTRIBUTE = VenResourceAttributeType("SERVICE_PROVIDER_ID")
CONGESTION_POINT_ID_ATTRIBUTE = VenResourceAttributeType("CONGESTION_POINT_ID")
MAX_DURATION_ATTRIBUTE = VenResourceAttributeType("MAX_DURATION")


def _targets_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group targets its own Group-ID."""
    validation_errors: list[InitErrorDetails] = []

    if self.resource_group_name not in self.targets:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource group targets must include the Group-ID.",
                ),
                loc=("targets",),
                input=self.targets,
                ctx={},
            )
        )

    return validation_errors


def _dso_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group has a DSO_ID attribute formatted as a DSO identifier."""
    validation_errors: list[InitErrorDetails] = []

    dso_id = self.attributes.get_by_type(DSO_ID_ATTRIBUTE) if self.attributes else None

    if dso_id is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource group must have a DSO_ID attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not dso_id.values or not all(re.fullmatch(DSO_IDENTIFIER_REGEX, value) for value in dso_id.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The DSO_ID attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA').",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _service_provider_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group has a SERVICE_PROVIDER_ID attribute formatted as a SP identifier."""
    validation_errors: list[InitErrorDetails] = []

    service_provider_id = self.attributes.get_by_type(SERVICE_PROVIDER_ID_ATTRIBUTE) if self.attributes else None

    if service_provider_id is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource group must have a SERVICE_PROVIDER_ID attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not service_provider_id.values or not all(
        re.fullmatch(SERVICE_PROVIDER_IDENTIFIER_REGEX, value) for value in service_provider_id.values
    ):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The SERVICE_PROVIDER_ID attribute must be formatted as a Service Provider identifier "
                    "(e.g. 'SP-ZON').",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _congestion_point_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group has a non-empty CONGESTION_POINT_ID attribute."""
    validation_errors: list[InitErrorDetails] = []

    congestion_point_id = self.attributes.get_by_type(CONGESTION_POINT_ID_ATTRIBUTE) if self.attributes else None

    if congestion_point_id is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource group must have a CONGESTION_POINT_ID attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not congestion_point_id.values or not all(value for value in congestion_point_id.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The CONGESTION_POINT_ID attribute value may not be empty.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _max_duration_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group has a MAX_DURATION attribute of PT2H, PT4H or PT6H."""
    validation_errors: list[InitErrorDetails] = []

    max_duration = self.attributes.get_by_type(MAX_DURATION_ATTRIBUTE) if self.attributes else None

    if max_duration is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource group must have a MAX_DURATION attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not max_duration.values or not all(value in KNOWN_MAX_DURATIONS for value in max_duration.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The MAX_DURATION attribute must be equal to one of PT2H, PT4H or PT6H.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def validate_resource_group_nlflex_compliant(resource_group: ResourceGroup) -> list[InitErrorDetails] | None:
    """
    Validates that a resource group is NL-Flex 0.1 compliant.

    Validates the object constraints and requirements of a resource group, as specified in
    Section 11.3, "Resource Group" of the NL-Flex specification.
    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_targets_compliant(resource_group))
    validation_errors.extend(_dso_id_attribute_compliant(resource_group))
    validation_errors.extend(_service_provider_id_attribute_compliant(resource_group))
    validation_errors.extend(_congestion_point_id_attribute_compliant(resource_group))
    validation_errors.extend(_max_duration_attribute_compliant(resource_group))

    return validation_errors or None

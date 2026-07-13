# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""Module which implements NL-Flex 0.1 compliance validators for the resource OpenADR3 types."""

import re

from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.oadr310.models.resource.resource import Resource
from pydantic_core import InitErrorDetails, PydanticCustomError

DSO_IDENTIFIER_REGEX = r"^DSB-[A-Z]+$"
EAN18_REGEX = r"^\d{18}$"

# See Table 3, "Flex types" of the NL-Flex specification.
KNOWN_FLEX_TYPES = frozenset({"EVSE", "HB", "HPE", "HPH", "PV"})
# See Table 1, "Registration statuses" of the NL-Flex specification.
KNOWN_REGISTRATION_STATUSES = frozenset({"ENROLLED", "REJECTED"})
# See Table 2, "Registration rejection reasons" of the NL-Flex specification.
KNOWN_REJECTION_REASONS = frozenset({"WRONG_CONGESTION_AREA", "WRONG_EAN", "GROUP_FLEXIBILITY_EXCEEDED", "OTHER"})

DSO_ID_ATTRIBUTE = VenResourceAttributeType("DSO_ID")
EAN_ATTRIBUTE = VenResourceAttributeType("EAN")
FLEX_TYPE_ATTRIBUTE = VenResourceAttributeType("FLEX_TYPE")
REGISTRATION_STATUS_ATTRIBUTE = VenResourceAttributeType("REGISTRATION_STATUS")
REJECTED_REASON_ATTRIBUTE = VenResourceAttributeType("REJECTED_REASON")


def _targets_compliant(self: Resource) -> list[InitErrorDetails]:
    """
    Validates that the resource targets its own Asset-ID, when targets are present.

    The targets MUST contain the Asset-ID (the resource name), which serves as the node handle
    through which the asset is targeted and referenced as a resource group child (see Section
    11.2, "Resource" of the NL-Flex specification). Targets can only be assigned by a BL client;
    a resource submitted by a VEN client does not carry a targets field at all, so there is
    nothing to validate until the BL populates it.
    """
    validation_errors: list[InitErrorDetails] = []

    targets = getattr(self, "targets", None)
    if targets is None:
        return validation_errors

    if self.resource_name not in targets:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource targets must include its own Asset-ID.",
                ),
                loc=("targets",),
                input=targets,
                ctx={},
            )
        )

    return validation_errors


def _dso_id_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource has a DSO_ID attribute formatted as a DSO identifier."""
    validation_errors: list[InitErrorDetails] = []

    dso_id = self.attributes.get_by_type(DSO_ID_ATTRIBUTE) if self.attributes else None

    if dso_id is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource must have a DSO_ID attribute.",
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


def _ean_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource has an EAN attribute formatted as an EAN18 value."""
    validation_errors: list[InitErrorDetails] = []

    ean = self.attributes.get_by_type(EAN_ATTRIBUTE) if self.attributes else None

    if ean is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource must have an EAN attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not ean.values or not all(re.fullmatch(EAN18_REGEX, value) for value in ean.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The EAN attribute must be the EAN18 of the PCC the asset is connected to.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _flex_type_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource has a FLEX_TYPE attribute with a known flex type."""
    validation_errors: list[InitErrorDetails] = []

    flex_type = self.attributes.get_by_type(FLEX_TYPE_ATTRIBUTE) if self.attributes else None

    if flex_type is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource must have a FLEX_TYPE attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not flex_type.values or not all(value in KNOWN_FLEX_TYPES for value in flex_type.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The FLEX_TYPE attribute must be one of the flex type IDs in Table 3, 'Flex types'.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _registration_status_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """
    Validates the (optional) REGISTRATION_STATUS and REJECTED_REASON attributes.

    REGISTRATION_STATUS is set by the BL when an asset is registered on a resource group, and
    if present MUST be one of the registration statuses in Table 1. REJECTED_REASON MUST be
    present, and be one of the rejection reasons in Table 2, whenever REGISTRATION_STATUS has a
    value of REJECTED.
    """
    validation_errors: list[InitErrorDetails] = []

    if not self.attributes:
        return validation_errors

    registration_status = self.attributes.get_by_type(REGISTRATION_STATUS_ATTRIBUTE)

    if registration_status is None:
        return validation_errors

    if not registration_status.values or not all(
        value in KNOWN_REGISTRATION_STATUSES for value in registration_status.values
    ):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The REGISTRATION_STATUS attribute must be one of the registration statuses in Table 1.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    if "REJECTED" not in registration_status.values:
        return validation_errors

    rejected_reason = self.attributes.get_by_type(REJECTED_REASON_ATTRIBUTE)

    if rejected_reason is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The resource must have a REJECTED_REASON attribute when REGISTRATION_STATUS is REJECTED.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not rejected_reason.values or not all(value in KNOWN_REJECTION_REASONS for value in rejected_reason.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The REJECTED_REASON attribute must be one of the rejection reasons in Table 2.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def validate_resource_nlflex_compliant(resource: Resource) -> list[InitErrorDetails] | None:
    """
    Validates that a resource is NL-Flex 0.1 compliant.

    Validates the object constraints and requirements of a resource, as specified in Section
    11.2, "Resource" of the NL-Flex specification.
    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_targets_compliant(resource))
    validation_errors.extend(_dso_id_attribute_compliant(resource))
    validation_errors.extend(_ean_attribute_compliant(resource))
    validation_errors.extend(_flex_type_attribute_compliant(resource))
    validation_errors.extend(_registration_status_attribute_compliant(resource))

    return validation_errors or None

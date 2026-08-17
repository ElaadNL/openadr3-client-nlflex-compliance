# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for the resource of the OpenADR DER profile specification v1.0.0.

A resource represents a single registered DER asset of a Service Provider. Its resourceName is the
Asset-ID, and it MUST NOT be registered to more than one resource group. That last rule is about the
resource groups rather than the resource, so it cannot be checked from the resource alone.

All attribute types below are defined by this profile and are not part of the OpenADR 3.1 attribute
type enumeration.
"""

from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.oadr310.models.resource.resource import Resource
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex10._common import error, is_ean13, is_ean18

# See the "Flex types" table.
KNOWN_FLEX_TYPES = frozenset({"EVSE", "HB", "HPE", "HPH", "PV"})
# See the "Registration status values" table.
KNOWN_REGISTRATION_STATUSES = frozenset({"ENROLLED", "REJECTED"})
# See the "Registration rejection reasons" table.
KNOWN_REJECTION_REASONS = frozenset({"WRONG_CONGESTION_AREA", "WRONG_EAN", "GROUP_FLEXIBILITY_EXCEEDED", "OTHER"})

DSO_ID_ATTRIBUTE = VenResourceAttributeType("DSO_ID")
EAN_ATTRIBUTE = VenResourceAttributeType("EAN")
FLEX_TYPE_ATTRIBUTE = VenResourceAttributeType("FLEX_TYPE")
REGISTRATION_STATUS_ATTRIBUTE = VenResourceAttributeType("REGISTRATION_STATUS")
REJECTED_REASON_ATTRIBUTE = VenResourceAttributeType("REJECTED_REASON")


def _targets_compliant(self: Resource) -> list[InitErrorDetails]:
    """
    Validates that the resource targets its own Asset-ID, when targets are present.

    The targets MUST contain the Asset-ID, which serves as the node handle through which the asset
    is targeted and referenced as a resource group child. Targets can only be assigned by a BL
    client; a resource submitted by a VEN client does not carry a targets field at all, so there is
    nothing to validate until the BL populates it.
    """
    targets = getattr(self, "targets", None)
    if targets is None:
        return []

    if self.resource_name not in targets:
        return [error("The resource targets must include its own Asset-ID.", "targets", targets)]

    return []


def _dso_id_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource names the DSO responsible for it, by its EAN13."""
    dso_id = self.attributes.get_by_type(DSO_ID_ATTRIBUTE) if self.attributes else None

    if dso_id is None:
        return [error("The resource must have a DSO_ID attribute.", "attributes", self.attributes)]

    if not dso_id.values or not all(is_ean13(value) for value in dso_id.values):
        return [
            error(
                "The DSO_ID attribute must be the DSO identifier of the responsible DSO, which is an EAN13 of "
                "13 digits with a valid check digit (for example '8716871000002').",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _ean_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource names the PCC the asset is connected to, by its EAN18."""
    ean = self.attributes.get_by_type(EAN_ATTRIBUTE) if self.attributes else None

    if ean is None:
        return [error("The resource must have an EAN attribute.", "attributes", self.attributes)]

    if not ean.values or not all(is_ean18(value) for value in ean.values):
        return [
            error(
                "The EAN attribute must be the EAN18 of the PCC the asset is connected to: 18 digits with a "
                "valid check digit.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _flex_type_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """Validates that the resource declares what kind of asset it is."""
    flex_type = self.attributes.get_by_type(FLEX_TYPE_ATTRIBUTE) if self.attributes else None

    if flex_type is None:
        return [error("The resource must have a FLEX_TYPE attribute.", "attributes", self.attributes)]

    if not flex_type.values or not all(value in KNOWN_FLEX_TYPES for value in flex_type.values):
        return [
            error(
                "The FLEX_TYPE attribute must be one of the flex type IDs in the flex types table.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _registration_status_attribute_compliant(self: Resource) -> list[InitErrorDetails]:
    """
    Validates the REGISTRATION_STATUS and REJECTED_REASON attributes.

    REGISTRATION_STATUS is set by the BL when an asset is registered on a resource group, and
    removed again when it is deregistered, so an absent status is not an error. REJECTED_REASON MUST
    be present whenever the status is REJECTED, and MUST be one of the rejection reasons.
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
            error(
                "The REGISTRATION_STATUS attribute must be one of the registration statuses in the "
                "registration status values table.",
                "attributes",
                self.attributes,
            )
        )

    if "REJECTED" not in registration_status.values:
        return validation_errors

    rejected_reason = self.attributes.get_by_type(REJECTED_REASON_ATTRIBUTE)

    if rejected_reason is None:
        validation_errors.append(
            error(
                "The resource must have a REJECTED_REASON attribute when REGISTRATION_STATUS is REJECTED.",
                "attributes",
                self.attributes,
            )
        )
    elif not rejected_reason.values or not all(value in KNOWN_REJECTION_REASONS for value in rejected_reason.values):
        validation_errors.append(
            error(
                "The REJECTED_REASON attribute must be one of the reasons in the registration rejection reasons table.",
                "attributes",
                self.attributes,
            )
        )

    return validation_errors


def validate_resource_nlflex_compliant(resource: Resource) -> list[InitErrorDetails] | None:
    """
    Validates that a resource is compliant with the OpenADR DER profile specification v1.0.0.

    Args:
        resource: The resource to validate.

    Returns:
        The validation errors found, or None when the resource is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_targets_compliant(resource))
    validation_errors.extend(_dso_id_attribute_compliant(resource))
    validation_errors.extend(_ean_attribute_compliant(resource))
    validation_errors.extend(_flex_type_attribute_compliant(resource))
    validation_errors.extend(_registration_status_attribute_compliant(resource))

    return validation_errors or None

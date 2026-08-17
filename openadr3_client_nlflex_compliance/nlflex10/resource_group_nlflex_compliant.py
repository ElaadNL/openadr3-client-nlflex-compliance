# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for the resource group of the OpenADR DER profile specification v1.0.0.

A resource group models the combination of a set of DERs, a Service Provider, a DSO and a congestion
point. It is the target of a baseline event and the subject of flex delta reports. Its
resourceGroupName is the Group-ID.

Besides the four attributes the BL persists when it creates the group, v1.0.0 mirrors the current
state of the group onto it as four BL-computed capacity attributes, as a workaround for OpenADR
having no native BL-to-BL channel. They are absent until the BL has published the group's first
baseline event, and are enforced here as all or nothing: the attribute table marks all four
required, the prose says they arrive together, and the specification's own examples show a created
group with none of them and an established group with all four.

The children of a group are pointers the BL keeps valid and that a VEN sees only in part, following
the OpenADR object privacy rules, so they carry nothing to validate here.
"""

from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.extensions.resource_group.models.resource_group import ResourceGroup
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex10._common import as_power_value, error, is_ean13

# The maximum availability duration of the group's assets, which caps the duration of a dispatch.
KNOWN_MAX_DURATIONS = frozenset({"PT2H", "PT4H", "PT6H"})

DSO_ID_ATTRIBUTE = VenResourceAttributeType("DSO_ID")
SERVICE_PROVIDER_ID_ATTRIBUTE = VenResourceAttributeType("SERVICE_PROVIDER_ID")
CONGESTION_POINT_ID_ATTRIBUTE = VenResourceAttributeType("CONGESTION_POINT_ID")
MAX_DURATION_ATTRIBUTE = VenResourceAttributeType("MAX_DURATION")
EVSE_BASELINE_OVERRIDE_ATTRIBUTE = VenResourceAttributeType("EVSE_BASELINE_OVERRIDE")

ACTIVE_BASELINE_ATTRIBUTE = VenResourceAttributeType("ACTIVE_BASELINE")
RESERVED_BASELINE_ATTRIBUTE = VenResourceAttributeType("RESERVED_BASELINE")
ACTIVE_AVAILABLE_FLEX_ATTRIBUTE = VenResourceAttributeType("ACTIVE_AVAILABLE_FLEX")
RESERVED_AVAILABLE_FLEX_ATTRIBUTE = VenResourceAttributeType("RESERVED_AVAILABLE_FLEX")

# The four attributes the BL computes, and the lower bound each carries. The two available flex
# attributes are the offered flexibility "as a positive magnitude"; the baselines carry no sign
# constraint, since a group that exports more than it draws has a negative one.
COMPUTED_CAPACITY_ATTRIBUTES: tuple[tuple[VenResourceAttributeType, float | None], ...] = (
    (ACTIVE_BASELINE_ATTRIBUTE, None),
    (RESERVED_BASELINE_ATTRIBUTE, None),
    (ACTIVE_AVAILABLE_FLEX_ATTRIBUTE, 0.0),
    (RESERVED_AVAILABLE_FLEX_ATTRIBUTE, 0.0),
)


def _targets_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the resource group targets its own Group-ID."""
    if self.resource_group_name not in self.targets:
        return [error("The resource group targets must include the Group-ID.", "targets", self.targets)]

    return []


def _dso_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the group names the DSO responsible for it, by its EAN13."""
    dso_id = self.attributes.get_by_type(DSO_ID_ATTRIBUTE) if self.attributes else None

    if dso_id is None:
        return [error("The resource group must have a DSO_ID attribute.", "attributes", self.attributes)]

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


def _service_provider_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the group names the Service Provider whose assets it holds, by its EAN13."""
    service_provider_id = self.attributes.get_by_type(SERVICE_PROVIDER_ID_ATTRIBUTE) if self.attributes else None

    if service_provider_id is None:
        return [error("The resource group must have a SERVICE_PROVIDER_ID attribute.", "attributes", self.attributes)]

    if not service_provider_id.values or not all(is_ean13(value) for value in service_provider_id.values):
        return [
            error(
                "The SERVICE_PROVIDER_ID attribute must be the Service Provider identifier, which is an EAN13 "
                "of 13 digits with a valid check digit (for example '8712345678906').",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _congestion_point_id_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates that the group points at the congestion point it sits behind."""
    congestion_point_id = self.attributes.get_by_type(CONGESTION_POINT_ID_ATTRIBUTE) if self.attributes else None

    if congestion_point_id is None:
        return [error("The resource group must have a CONGESTION_POINT_ID attribute.", "attributes", self.attributes)]

    if not congestion_point_id.values or not all(value for value in congestion_point_id.values):
        return [
            error(
                "The CONGESTION_POINT_ID attribute value may not be empty.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _max_duration_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """Validates the maximum availability duration of the group's assets."""
    max_duration = self.attributes.get_by_type(MAX_DURATION_ATTRIBUTE) if self.attributes else None

    if max_duration is None:
        return [error("The resource group must have a MAX_DURATION attribute.", "attributes", self.attributes)]

    if not max_duration.values or not all(value in KNOWN_MAX_DURATIONS for value in max_duration.values):
        return [
            error(
                "The MAX_DURATION attribute must be equal to one of PT2H, PT4H or PT6H.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _single_power_value(attribute: Attribute) -> float | None:  # type: ignore[type-arg]
    """Reads an attribute holding one power value, or None when it holds anything else."""
    if len(attribute.values) != 1:
        return None

    return as_power_value(attribute.values[0])


def _evse_baseline_override_attribute_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """
    Validates the per-asset EVSE baseline override, when present.

    The override is requested by the Service Provider out of band and persisted by the BL, and is
    absent when no correction was requested.
    """
    override = self.attributes.get_by_type(EVSE_BASELINE_OVERRIDE_ATTRIBUTE) if self.attributes else None

    if override is None:
        return []

    if _single_power_value(override) is None:
        return [
            error(
                "The EVSE_BASELINE_OVERRIDE attribute must contain exactly one value in KW, a double with at "
                "most two decimals.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _computed_capacity_attributes_compliant(self: ResourceGroup) -> list[InitErrorDetails]:
    """
    Validates the four capacity attributes the BL computes for the group.

    They are absent until the BL has published the group's first baseline event, and present
    together after that, so a group carrying some but not all of them has been half updated.
    """
    validation_errors: list[InitErrorDetails] = []
    present = {
        attribute_type: (self.attributes.get_by_type(attribute_type) if self.attributes else None)
        for attribute_type, _ in COMPUTED_CAPACITY_ATTRIBUTES
    }
    found = [attribute for attribute in present.values() if attribute is not None]

    if not found:
        return validation_errors

    if len(found) != len(COMPUTED_CAPACITY_ATTRIBUTES):
        validation_errors.append(
            error(
                "The computed capacity attributes ACTIVE_BASELINE, RESERVED_BASELINE, ACTIVE_AVAILABLE_FLEX "
                "and RESERVED_AVAILABLE_FLEX must all be present or all be absent. They are absent until the "
                "BL has published the group's first baseline event.",
                "attributes",
                self.attributes,
            )
        )

    for attribute_type, minimum in COMPUTED_CAPACITY_ATTRIBUTES:
        attribute = present[attribute_type]
        if attribute is None:
            continue

        value = _single_power_value(attribute)

        if value is None:
            validation_errors.append(
                error(
                    f"The {attribute_type} attribute must contain exactly one value in KW, a double with at "
                    "most two decimals.",
                    "attributes",
                    self.attributes,
                )
            )
        elif minimum is not None and value < minimum:
            validation_errors.append(
                error(
                    f"The {attribute_type} attribute is the offered flexibility as a positive magnitude, so it "
                    "must be equal to or larger than zero.",
                    "attributes",
                    self.attributes,
                )
            )

    return validation_errors


def validate_resource_group_nlflex_compliant(resource_group: ResourceGroup) -> list[InitErrorDetails] | None:
    """
    Validates that a resource group is compliant with the OpenADR DER profile specification v1.0.0.

    Args:
        resource_group: The resource group to validate.

    Returns:
        The validation errors found, or None when the resource group is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_targets_compliant(resource_group))
    validation_errors.extend(_dso_id_attribute_compliant(resource_group))
    validation_errors.extend(_service_provider_id_attribute_compliant(resource_group))
    validation_errors.extend(_congestion_point_id_attribute_compliant(resource_group))
    validation_errors.extend(_max_duration_attribute_compliant(resource_group))
    validation_errors.extend(_evse_baseline_override_attribute_compliant(resource_group))
    validation_errors.extend(_computed_capacity_attributes_compliant(resource_group))

    return validation_errors or None

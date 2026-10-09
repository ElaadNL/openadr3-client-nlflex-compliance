# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.extensions.resource_group.models.resource_group import (
    NewResourceGroup,
    ResourceGroupChild,
)

from openadr3_client_nlflex_compliance.nlflex10.resource_group_nlflex_compliant import (
    validate_resource_group_nlflex_compliant,
)

_UNSET: Any = object()

DSO_EAN13 = "8716871000002"  # Liander, from the DSO identifiers table
SERVICE_PROVIDER_EAN13 = "8712345678906"

COMPUTED_ATTRIBUTE_TYPES = (
    "ACTIVE_BASELINE",
    "RESERVED_BASELINE",
    "ACTIVE_AVAILABLE_FLEX",
    "RESERVED_AVAILABLE_FLEX",
)


def _required_attributes() -> list[Attribute]:
    """Helper function to create the four attributes a freshly created group carries."""
    return [
        Attribute(type="DSO_ID", values=(DSO_EAN13,)),
        Attribute(type="SERVICE_PROVIDER_ID", values=(SERVICE_PROVIDER_EAN13,)),
        Attribute(type="CONGESTION_POINT_ID", values=("CP-0001",)),
        Attribute(type="MAX_DURATION", values=("PT4H",)),
    ]


def _computed_attributes() -> list[Attribute]:
    """Helper function to create the four attributes the BL computes after the first baseline event."""
    return [
        Attribute(type="ACTIVE_BASELINE", values=(500,)),
        Attribute(type="RESERVED_BASELINE", values=(500,)),
        Attribute(type="ACTIVE_AVAILABLE_FLEX", values=(300,)),
        Attribute(type="RESERVED_AVAILABLE_FLEX", values=(100,)),
    ]


def _default_valid_attributes() -> list[Attribute]:
    """Helper function to create the attributes of the specification's resource group example."""
    return [*_required_attributes(), *_computed_attributes()]


def _without(attribute_type: str) -> list[Attribute]:
    """Helper function to drop one attribute from the compliant set."""
    return [a for a in _default_valid_attributes() if a.type != attribute_type]


def _replacing(attribute_type: str, values: tuple[Any, ...]) -> list[Attribute]:
    """Helper function to replace the values of one attribute in the compliant set."""
    return [
        Attribute(type=attribute_type, values=values) if a.type == attribute_type else a
        for a in _default_valid_attributes()
    ]


def _create_resource_group(
    attributes: list[Attribute] | None = _UNSET,
    targets: tuple[str, ...] = _UNSET,
) -> NewResourceGroup:
    """
    Helper function to create a resource group with the specified values.

    Any argument left unset defaults to a compliant value.
    """
    resolved_attributes = _default_valid_attributes() if attributes is _UNSET else attributes
    return NewResourceGroup(
        resource_group_name="GROUP-0001",
        targets=("GROUP-0001",) if targets is _UNSET else targets,
        attributes=None if resolved_attributes is None else ValuesMap(resolved_attributes),
        children=(ResourceGroupChild(type="ven_resource", id="a1a1a1a1-0001-4001-8001-000000000001"),),
    )


def test_resource_group_valid() -> None:
    """A resource group matching the specification's example is compliant."""
    assert validate_resource_group_nlflex_compliant(_create_resource_group()) is None


def test_targets_must_include_the_group_id() -> None:
    """The targets MUST include the Group-ID, which is the resourceGroupName."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(targets=("GROUP-0002",)))

    assert errors is not None
    assert any("must include the Group-ID" in str(error["type"]) for error in errors)


def test_dso_id_is_required() -> None:
    """The group names the DSO responsible for it."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_without("DSO_ID")))

    assert errors is not None
    assert any("must have a DSO_ID attribute" in str(error["type"]) for error in errors)


def test_the_draft_dso_id_format_is_rejected() -> None:
    """The v0.1 draft used identifiers such as 'DSB-LIA'. v1.0.0 uses an EAN13."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_replacing("DSO_ID", ("DSB-LIA",))))

    assert errors is not None
    assert any("DSO identifier" in str(error["type"]) for error in errors)


def test_service_provider_id_is_required() -> None:
    """The group names the Service Provider whose assets it holds."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_without("SERVICE_PROVIDER_ID")))

    assert errors is not None
    assert any("must have a SERVICE_PROVIDER_ID attribute" in str(error["type"]) for error in errors)


def test_the_draft_service_provider_id_format_is_rejected() -> None:
    """The v0.1 draft used identifiers such as 'SP-ZON'. v1.0.0 uses an EAN13."""
    errors = validate_resource_group_nlflex_compliant(
        _create_resource_group(_replacing("SERVICE_PROVIDER_ID", ("SP-ZON",)))
    )

    assert errors is not None
    assert any("Service Provider identifier" in str(error["type"]) for error in errors)


def test_congestion_point_id_is_required() -> None:
    """The group points at the congestion point it sits behind."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_without("CONGESTION_POINT_ID")))

    assert errors is not None
    assert any("must have a CONGESTION_POINT_ID attribute" in str(error["type"]) for error in errors)


def test_congestion_point_id_may_not_be_empty() -> None:
    """A pointer to nothing is not a pointer."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_replacing("CONGESTION_POINT_ID", ("",))))

    assert errors is not None
    assert any("may not be empty" in str(error["type"]) for error in errors)


def test_max_duration_is_required() -> None:
    """MAX_DURATION sets the ceiling on the duration of a single dispatch."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_without("MAX_DURATION")))

    assert errors is not None
    assert any("must have a MAX_DURATION attribute" in str(error["type"]) for error in errors)


@pytest.mark.parametrize("max_duration", ["PT2H", "PT4H", "PT6H"])
def test_every_allowed_max_duration_is_accepted(max_duration: str) -> None:
    """MAX_DURATION MUST be equal to one of PT2H, PT4H or PT6H."""
    group = _create_resource_group(_replacing("MAX_DURATION", (max_duration,)))

    assert validate_resource_group_nlflex_compliant(group) is None


def test_an_unsupported_max_duration_is_rejected() -> None:
    """PT1H is not one of the availability durations the profile allows."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_replacing("MAX_DURATION", ("PT1H",))))

    assert errors is not None
    assert any("PT2H, PT4H or PT6H" in str(error["type"]) for error in errors)


def test_a_group_without_computed_attributes_is_valid() -> None:
    """The four computed entries are absent until the BL publishes the group's first baseline event."""
    assert validate_resource_group_nlflex_compliant(_create_resource_group(_required_attributes())) is None


@pytest.mark.parametrize("attribute_type", COMPUTED_ATTRIBUTE_TYPES)
def test_the_computed_attributes_are_all_or_nothing(attribute_type: str) -> None:
    """A group carrying three of the four has been half updated."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_without(attribute_type)))

    assert errors is not None
    assert any("must all be present or all be absent" in str(error["type"]) for error in errors)


def test_a_computed_attribute_with_three_decimals_is_rejected() -> None:
    """The computed attributes are power values, so they carry at most two decimals."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_replacing("ACTIVE_BASELINE", (500.125,))))

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_a_negative_available_flex_is_rejected() -> None:
    """ACTIVE_AVAILABLE_FLEX is the offered flexibility as a positive magnitude."""
    errors = validate_resource_group_nlflex_compliant(
        _create_resource_group(_replacing("ACTIVE_AVAILABLE_FLEX", (-300,)))
    )

    assert errors is not None
    assert any("positive magnitude" in str(error["type"]) for error in errors)


def test_a_negative_baseline_is_accepted() -> None:
    """A baseline carries no sign constraint; a group that exports has a negative one."""
    group = _create_resource_group(_replacing("ACTIVE_BASELINE", (-200,)))

    assert validate_resource_group_nlflex_compliant(group) is None


def test_an_evse_baseline_override_is_validated_when_present() -> None:
    """The override is a per-asset baseline in KW, so it is a power value."""
    attributes = [*_default_valid_attributes(), Attribute(type="EVSE_BASELINE_OVERRIDE", values=(11.5,))]

    assert validate_resource_group_nlflex_compliant(_create_resource_group(attributes)) is None


def test_a_non_numeric_evse_baseline_override_is_rejected() -> None:
    """It is absent when the Service Provider has not requested a correction, never a string."""
    attributes = [*_default_valid_attributes(), Attribute(type="EVSE_BASELINE_OVERRIDE", values=("11.5",))]

    errors = validate_resource_group_nlflex_compliant(_create_resource_group(attributes))

    assert errors is not None
    assert any("EVSE_BASELINE_OVERRIDE" in str(error["type"]) for error in errors)


def test_a_ven_resource_child_is_valid() -> None:
    """A group's children are its member assets, which is what the profile uses."""
    group = _create_resource_group()

    assert validate_resource_group_nlflex_compliant(group) is None


def test_a_nested_resource_group_child_is_rejected() -> None:
    """The extension permits a nested resource_group; this profile does not use one."""
    group = NewResourceGroup(
        resource_group_name="GROUP-0001",
        targets=("GROUP-0001",),
        attributes=ValuesMap(_default_valid_attributes()),
        children=(ResourceGroupChild(type="resource_group", id="60000000-0000-4000-8000-000000000001"),),
    )

    errors = validate_resource_group_nlflex_compliant(group)

    assert errors is not None
    assert any("must be of type 'ven_resource'" in str(error["type"]) for error in errors)


def test_a_group_without_children_is_valid() -> None:
    """A freshly created group has no members yet, which the specification's own example shows."""
    group = NewResourceGroup(
        resource_group_name="GROUP-0001",
        targets=("GROUP-0001",),
        attributes=ValuesMap(_default_valid_attributes()),
        children=(),
    )

    assert validate_resource_group_nlflex_compliant(group) is None


def test_a_child_id_is_not_validated() -> None:
    """An id is an unvalidated string: a VEN sees only the children it may resolve."""
    group = NewResourceGroup(
        resource_group_name="GROUP-0001",
        targets=("GROUP-0001",),
        attributes=ValuesMap(_default_valid_attributes()),
        children=(ResourceGroupChild(type="ven_resource", id="not-a-uuid"),),
    )

    assert validate_resource_group_nlflex_compliant(group) is None


def test_a_group_without_attributes_is_rejected() -> None:
    """The four required attributes are missing, and all four are reported."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(attributes=None))

    assert errors is not None
    assert len(errors) == 4


def test_a_valid_ean13_that_names_no_dso_is_rejected_as_dso_id() -> None:
    """DSO_ID names the responsible DSO, and the profile fixes which codes those are."""
    errors = validate_resource_group_nlflex_compliant(_create_resource_group(_replacing("DSO_ID", ("8712345678906",))))

    assert errors is not None
    assert any("DSO identifiers table" in str(error["type"]) for error in errors)

# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.oadr310.models.resource.resource import NewResourceBlRequest

from openadr3_client_nlflex_compliance.nlflex10.resource_nlflex_compliant import (
    validate_resource_nlflex_compliant,
)

_UNSET: Any = object()

DSO_EAN13 = "8716871000002"  # Liander, from the DSO identifiers table
PCC_EAN18 = "871685900000000127"


def _default_valid_attributes() -> list[Attribute]:
    """Helper function to create the attributes of the specification's enrolled resource example."""
    return [
        Attribute(type="DSO_ID", values=(DSO_EAN13,)),
        Attribute(type="EAN", values=(PCC_EAN18,)),
        Attribute(type="FLEX_TYPE", values=("EVSE",)),
        Attribute(type="REGISTRATION_STATUS", values=("ENROLLED",)),
    ]


def _without(attribute_type: str) -> list[Attribute]:
    """Helper function to drop one attribute from the compliant set."""
    return [a for a in _default_valid_attributes() if a.type != attribute_type]


def _replacing(attribute_type: str, values: tuple[Any, ...]) -> list[Attribute]:
    """Helper function to replace the values of one attribute in the compliant set."""
    return [
        Attribute(type=attribute_type, values=values) if a.type == attribute_type else a
        for a in _default_valid_attributes()
    ]


def _create_resource(
    attributes: list[Attribute] | None = _UNSET,
    targets: tuple[str, ...] | None = _UNSET,
) -> NewResourceBlRequest:
    """
    Helper function to create a resource with the specified values.

    Any argument left unset defaults to a compliant value. Passing ``None`` for targets is
    preserved, to allow testing a resource a VEN client submitted.
    """
    resolved_attributes = _default_valid_attributes() if attributes is _UNSET else attributes
    return NewResourceBlRequest(
        resource_name="ASSET-0001",
        venID="3f2504e0-4f89-41d3-9a0c-0305e82c3301",
        clientID="elaad-client",
        targets=("ASSET-0001",) if targets is _UNSET else targets,
        attributes=None if resolved_attributes is None else ValuesMap(resolved_attributes),
    )


def test_resource_valid() -> None:
    """A resource matching the specification's example is compliant."""
    assert validate_resource_nlflex_compliant(_create_resource()) is None


def test_a_resource_not_yet_registered_is_valid() -> None:
    """REGISTRATION_STATUS is set by the BL, so a freshly submitted resource has none."""
    assert validate_resource_nlflex_compliant(_create_resource(_without("REGISTRATION_STATUS"))) is None


def test_targets_must_contain_the_asset_id() -> None:
    """The Asset-ID is the node handle the asset is targeted and referenced through."""
    errors = validate_resource_nlflex_compliant(_create_resource(targets=("ASSET-0002",)))

    assert errors is not None
    assert any("own Asset-ID" in str(error["type"]) for error in errors)


def test_absent_targets_are_not_validated() -> None:
    """A resource submitted by a VEN client carries no targets field for the BL to have filled in."""
    assert validate_resource_nlflex_compliant(_create_resource(targets=None)) is None


def test_dso_id_is_required() -> None:
    """A single VTN hosts multiple DSOs, so a resource names the one responsible for it."""
    errors = validate_resource_nlflex_compliant(_create_resource(_without("DSO_ID")))

    assert errors is not None
    assert any("must have a DSO_ID attribute" in str(error["type"]) for error in errors)


def test_the_draft_dso_id_format_is_rejected() -> None:
    """The v0.1 draft used identifiers such as 'DSB-LIA'. v1.0.0 uses an EAN13."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("DSO_ID", ("DSB-LIA",))))

    assert errors is not None
    assert any("DSO identifier" in str(error["type"]) for error in errors)


def test_ean_is_required() -> None:
    """The resource names the grid connection the asset sits behind."""
    errors = validate_resource_nlflex_compliant(_create_resource(_without("EAN")))

    assert errors is not None
    assert any("must have an EAN attribute" in str(error["type"]) for error in errors)


def test_an_ean18_with_an_invalid_check_digit_is_rejected() -> None:
    """The draft accepted any 18 digits. v1.0.0 requires a valid check digit."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("EAN", ("871685900000000128",))))

    assert errors is not None
    assert any("EAN18" in str(error["type"]) for error in errors)


def test_an_ean13_is_not_an_ean18() -> None:
    """The EAN attribute is the PCC, which is 18 digits, not a market party."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("EAN", (DSO_EAN13,))))

    assert errors is not None
    assert any("EAN18" in str(error["type"]) for error in errors)


def test_flex_type_is_required() -> None:
    """The BL calculates a baseline from the types of asset involved."""
    errors = validate_resource_nlflex_compliant(_create_resource(_without("FLEX_TYPE")))

    assert errors is not None
    assert any("must have a FLEX_TYPE attribute" in str(error["type"]) for error in errors)


@pytest.mark.parametrize("flex_type", ["EVSE", "HB", "HPE", "HPH", "PV"])
def test_every_flex_type_in_the_table_is_accepted(flex_type: str) -> None:
    """The flex types table has exactly these five entries."""
    assert validate_resource_nlflex_compliant(_create_resource(_replacing("FLEX_TYPE", (flex_type,)))) is None


def test_an_unknown_flex_type_is_rejected() -> None:
    """A flex type outside the table is not a flex type."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("FLEX_TYPE", ("WINDMILL",))))

    assert errors is not None
    assert any("flex types" in str(error["type"]) for error in errors)


def test_an_unknown_registration_status_is_rejected() -> None:
    """REGISTRATION_STATUS is one of the registration status values."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("REGISTRATION_STATUS", ("PENDING",))))

    assert errors is not None
    assert any("registration statuses" in str(error["type"]) for error in errors)


def test_a_rejected_resource_must_carry_a_reason() -> None:
    """REJECTED_REASON MUST be present when REGISTRATION_STATUS has a value of REJECTED."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("REGISTRATION_STATUS", ("REJECTED",))))

    assert errors is not None
    assert any("REJECTED_REASON attribute when" in str(error["type"]) for error in errors)


def test_a_rejected_resource_with_a_known_reason_is_valid() -> None:
    """The rejection reasons table names the reasons the BL may give."""
    attributes = [
        *_replacing("REGISTRATION_STATUS", ("REJECTED",)),
        Attribute(type="REJECTED_REASON", values=("WRONG_CONGESTION_AREA",)),
    ]

    assert validate_resource_nlflex_compliant(_create_resource(attributes)) is None


def test_an_unknown_rejection_reason_is_rejected() -> None:
    """A reason outside the table means the BL should have used OTHER."""
    attributes = [
        *_replacing("REGISTRATION_STATUS", ("REJECTED",)),
        Attribute(type="REJECTED_REASON", values=("BECAUSE",)),
    ]

    errors = validate_resource_nlflex_compliant(_create_resource(attributes))

    assert errors is not None
    assert any("rejection reasons" in str(error["type"]) for error in errors)


def test_a_resource_without_attributes_is_rejected() -> None:
    """The three required attributes are missing, and all three are reported."""
    errors = validate_resource_nlflex_compliant(_create_resource(attributes=None))

    assert errors is not None
    assert len(errors) == 3


def test_a_valid_ean13_that_names_no_dso_is_rejected_as_dso_id() -> None:
    """DSO_ID names the responsible DSO, and the profile fixes which codes those are."""
    errors = validate_resource_nlflex_compliant(_create_resource(_replacing("DSO_ID", ("8712345678906",))))

    assert errors is not None
    assert any("DSO identifiers table" in str(error["type"]) for error in errors)

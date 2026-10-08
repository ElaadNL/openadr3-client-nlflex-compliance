# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.oadr310.models.program.program import NewProgram

from openadr3_client_nlflex_compliance.nlflex10.program_nlflex_compliant import (
    validate_program_nlflex_compliant,
)

_UNSET: Any = object()


def _default_valid_attributes() -> list[Attribute]:
    """Helper function to create the attributes of the specification's program example."""
    return [
        Attribute(type="PROGRAM_TYPE", values=("DSO_SP_INTERFACE-1.0.0",)),
        Attribute(type="RETAILER_NAME", values=("8716871000002",)),
        Attribute(type="RETAILER_LONG_NAME", values=("ElaadNL",)),
        Attribute(type="COUNTRY", values=("NL",)),
        Attribute(type="BINDING_EVENTS", values=(True,)),
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


def _create_program(attributes: list[Attribute] = _UNSET) -> NewProgram:
    """Helper function to create a program with the specified attributes."""
    return NewProgram(
        program_name="DSO-SP DER interface - ElaadNL",
        attributes=ValuesMap(_default_valid_attributes() if attributes is _UNSET else attributes),
    )


def test_program_valid() -> None:
    """A program matching the specification's example is compliant."""
    assert validate_program_nlflex_compliant(_create_program()) is None


def test_program_type_is_required() -> None:
    """The program identifies the version of the specification it implements."""
    errors = validate_program_nlflex_compliant(_create_program(_without("PROGRAM_TYPE")))

    assert errors is not None
    assert any("must have a PROGRAM_TYPE attribute" in str(error["type"]) for error in errors)


def test_program_type_must_follow_the_interface_format() -> None:
    """PROGRAM_TYPE MUST equal DSO_SP_INTERFACE-x.y.z."""
    errors = validate_program_nlflex_compliant(_create_program(_replacing("PROGRAM_TYPE", ("1.0.0",))))

    assert errors is not None
    assert any("DSO_SP_INTERFACE-x.y.z" in str(error["type"]) for error in errors)


def test_retailer_name_is_required() -> None:
    """The program names the DSO issuing it."""
    errors = validate_program_nlflex_compliant(_create_program(_without("RETAILER_NAME")))

    assert errors is not None
    assert any("must have a RETAILER_NAME attribute" in str(error["type"]) for error in errors)


def test_the_draft_retailer_name_format_is_rejected() -> None:
    """The v0.1 draft used identifiers such as 'DSB-LIA'. v1.0.0 uses an EAN13."""
    errors = validate_program_nlflex_compliant(_create_program(_replacing("RETAILER_NAME", ("DSB-LIA",))))

    assert errors is not None
    assert any("DSO identifier" in str(error["type"]) for error in errors)


def test_every_dso_identifier_in_the_specification_is_accepted() -> None:
    """The DSO identifiers table lists six EAN13 codes; all six are valid RETAILER_NAMEs."""
    for identifier in (
        "8716916000004",
        "8712423014022",
        "8716871000002",
        "8716912000008",
        "8716892000005",
        "8716878999996",
    ):
        assert validate_program_nlflex_compliant(_create_program(_replacing("RETAILER_NAME", (identifier,)))) is None


def test_gopacs_is_accepted_as_retailer_name() -> None:
    """A program issued through GOPACS names GOPACS rather than a DSO."""
    assert validate_program_nlflex_compliant(_create_program(_replacing("RETAILER_NAME", ("GOPACS",)))) is None


@pytest.mark.parametrize("retailer_name", ["gopacs", "GOPACS ", "GOPACS-NL"])
def test_gopacs_must_match_exactly_as_retailer_name(retailer_name: str) -> None:
    """Only the exact string GOPACS is accepted in place of a DSO identifier."""
    errors = validate_program_nlflex_compliant(_create_program(_replacing("RETAILER_NAME", (retailer_name,))))

    assert errors is not None
    assert any("RETAILER_NAME" in str(error["type"]) for error in errors)


def test_binding_events_is_required() -> None:
    """Events in this profile are immutable, which is advertised through BINDING_EVENTS."""
    errors = validate_program_nlflex_compliant(_create_program(_without("BINDING_EVENTS")))

    assert errors is not None
    assert any("BINDING_EVENTS" in str(error["type"]) for error in errors)


def test_binding_events_must_be_true() -> None:
    """A program that says its events are not binding contradicts the profile."""
    errors = validate_program_nlflex_compliant(_create_program(_replacing("BINDING_EVENTS", (False,))))

    assert errors is not None
    assert any("BINDING_EVENTS" in str(error["type"]) for error in errors)


def test_a_program_without_attributes_is_rejected() -> None:
    """All three required attributes are missing, and all three are reported."""
    errors = validate_program_nlflex_compliant(NewProgram(program_name="DSO-SP DER interface", attributes=None))

    assert errors is not None
    assert len(errors) == 3


def test_a_valid_ean13_that_names_no_dso_is_rejected_as_retailer_name() -> None:
    """RETAILER_NAME identifies the issuing DSO, and the profile fixes which codes those are."""
    errors = validate_program_nlflex_compliant(_create_program(_replacing("RETAILER_NAME", ("8712345678906",))))

    assert errors is not None
    assert any("DSO identifiers table" in str(error["type"]) for error in errors)

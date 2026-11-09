# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.oadr310.models.program.program import NewProgram

from openadr3_client_nlflex_compliance.nlflex11.program_nlflex_compliant import (
    ProgramKind,
    program_kind,
    program_version,
    validate_program_nlflex_compliant,
    validate_programs_lock_step,
)

_UNSET: Any = object()

REGISTRATION = "DER_REGISTRATION_INTERFACE-1.1.0"
DISPATCH = "DER_DISPATCH_INTERFACE-1.1.0"
LIANDER = "8716871000002"


def _registration_attributes() -> list[Attribute]:
    """Helper function to create the attributes of the specification's registration program example."""
    return [
        Attribute(type="PROGRAM_TYPE", values=(REGISTRATION,)),
        Attribute(type="RETAILER_NAME", values=("GOPACS",)),
        Attribute(type="RETAILER_LONG_NAME", values=("GOPACS",)),
        Attribute(type="COUNTRY", values=("NL",)),
        Attribute(type="BINDING_EVENTS", values=(True,)),
    ]


def _dispatch_attributes() -> list[Attribute]:
    """Helper function to create the attributes of the specification's dispatch program example."""
    return [
        Attribute(type="PROGRAM_TYPE", values=(DISPATCH,)),
        Attribute(type="RETAILER_NAME", values=(LIANDER,)),
        Attribute(type="RETAILER_LONG_NAME", values=("Liander",)),
        Attribute(type="COUNTRY", values=("NL",)),
        Attribute(type="BINDING_EVENTS", values=(True,)),
    ]


def _replacing(attributes: list[Attribute], attribute_type: str, values: tuple[Any, ...]) -> list[Attribute]:
    """Helper function to replace the values of one attribute."""
    return [Attribute(type=attribute_type, values=values) if a.type == attribute_type else a for a in attributes]


def _without(attributes: list[Attribute], attribute_type: str) -> list[Attribute]:
    """Helper function to drop one attribute."""
    return [a for a in attributes if a.type != attribute_type]


def _create_program(attributes: list[Attribute] = _UNSET) -> NewProgram:
    """Helper function to create a program with the specified attributes (the registration example by default)."""
    return NewProgram(
        program_name="DER registration interface - GOPACS",
        attributes=ValuesMap(_registration_attributes() if attributes is _UNSET else attributes),
    )


def _typed_program(program_type: str) -> NewProgram:
    """Helper function to create a program of a given PROGRAM_TYPE, with an operator that fits its kind."""
    base = _dispatch_attributes() if program_type.startswith("DER_DISPATCH") else _registration_attributes()
    return _create_program(_replacing(base, "PROGRAM_TYPE", (program_type,)))


def _messages(program: NewProgram) -> list[str]:
    errors = validate_program_nlflex_compliant(program)
    assert errors is not None
    return [str(error["type"]) for error in errors]


def test_the_registration_program_example_is_compliant() -> None:
    """The registration program of the specification's example is compliant."""
    assert validate_program_nlflex_compliant(_create_program(_registration_attributes())) is None


def test_the_dispatch_program_example_is_compliant() -> None:
    """The dispatch program of the specification's example is compliant."""
    assert validate_program_nlflex_compliant(_create_program(_dispatch_attributes())) is None


def test_every_dso_identifier_in_the_specification_is_accepted() -> None:
    """The Operator identifiers table lists six DSO EAN13 codes; all six are valid dispatch RETAILER_NAMEs."""
    for identifier in (
        "8716916000004",
        "8712423014022",
        "8716871000002",
        "8716912000008",
        "8716892000005",
        "8716878999996",
    ):
        program = _create_program(_replacing(_dispatch_attributes(), "RETAILER_NAME", (identifier,)))
        assert validate_program_nlflex_compliant(program) is None


def test_program_type_is_required() -> None:
    """A program without PROGRAM_TYPE has no kind, and the error names both accepted formats."""
    messages = _messages(_create_program(_without(_registration_attributes(), "PROGRAM_TYPE")))

    assert any("DER_REGISTRATION_INTERFACE-x.y.z" in m and "DER_DISPATCH_INTERFACE-x.y.z" in m for m in messages)


def test_a_v1_0_0_program_type_is_rejected() -> None:
    """The single program of v1.0.0 no longer exists; the error names both v1.1.0 formats."""
    messages = _messages(_typed_program("DSO_SP_INTERFACE-1.0.0"))

    assert len(messages) == 1
    assert "DER_REGISTRATION_INTERFACE-x.y.z" in messages[0]
    assert "DER_DISPATCH_INTERFACE-x.y.z" in messages[0]


def test_a_program_type_without_a_prefix_is_rejected() -> None:
    """PROGRAM_TYPE MUST carry the kind prefix, not only a version."""
    assert any("PROGRAM_TYPE" in m for m in _messages(_typed_program("1.1.0")))


def test_a_registration_program_must_name_gopacs() -> None:
    """The registration program is owned by GOPACS, so a DSO EAN13 is not its RETAILER_NAME."""
    program = _create_program(_replacing(_registration_attributes(), "RETAILER_NAME", (LIANDER,)))

    assert any("GOPACS" in m for m in _messages(program))


def test_a_dispatch_program_must_name_a_dso() -> None:
    """A dispatch program is owned by a DSO, so GOPACS is not its RETAILER_NAME."""
    program = _create_program(_replacing(_dispatch_attributes(), "RETAILER_NAME", ("GOPACS",)))

    assert any("Operator identifiers table" in m for m in _messages(program))


def test_a_valid_ean13_that_names_no_dso_is_rejected_on_a_dispatch_program() -> None:
    """The operator identifiers are a closed set, so a well formed EAN13 outside the table is rejected."""
    program = _create_program(_replacing(_dispatch_attributes(), "RETAILER_NAME", ("8712345678906",)))

    assert any("Operator identifiers table" in m for m in _messages(program))


def test_retailer_name_is_required_on_both_kinds() -> None:
    """Both kinds name the operator that owns them."""
    for attributes in (_registration_attributes(), _dispatch_attributes()):
        messages = _messages(_create_program(_without(attributes, "RETAILER_NAME")))

        assert any("RETAILER_NAME" in m for m in messages)


def test_a_program_with_both_program_types_is_rejected() -> None:
    """Two PROGRAM_TYPE values make the kind ambiguous, so no kind is assumed."""
    program = _create_program(_replacing(_registration_attributes(), "PROGRAM_TYPE", (REGISTRATION, DISPATCH)))

    assert program_kind(program) is None
    assert any("exactly one PROGRAM_TYPE" in m for m in _messages(program))


def test_a_program_with_two_program_type_entries_is_rejected() -> None:
    """A second PROGRAM_TYPE entry counts as a second value, not as something to ignore."""
    attributes = [*_registration_attributes(), Attribute(type="PROGRAM_TYPE", values=(DISPATCH,))]

    assert program_kind(_create_program(attributes)) is None


def test_a_program_with_two_retailer_names_is_rejected() -> None:
    """RETAILER_NAME identifies one owner, so a second value is rejected."""
    program = _create_program(_replacing(_registration_attributes(), "RETAILER_NAME", ("GOPACS", "GOPACS")))

    assert any("exactly one value" in m for m in _messages(program))


def test_binding_events_is_required_on_both_kinds() -> None:
    """Events in this profile are immutable, which is advertised through BINDING_EVENTS."""
    for attributes in (_registration_attributes(), _dispatch_attributes()):
        assert any("BINDING_EVENTS" in m for m in _messages(_create_program(_without(attributes, "BINDING_EVENTS"))))


def test_binding_events_must_be_true_on_both_kinds() -> None:
    """A program that says its events are not binding contradicts the profile."""
    for attributes in (_registration_attributes(), _dispatch_attributes()):
        program = _create_program(_replacing(attributes, "BINDING_EVENTS", (False,)))

        assert any("BINDING_EVENTS" in m for m in _messages(program))


def test_binding_events_is_checked_when_the_kind_is_unknown() -> None:
    """A program of no known kind still has its BINDING_EVENTS checked, alongside the PROGRAM_TYPE error."""
    attributes = _replacing(_registration_attributes(), "PROGRAM_TYPE", ("DSO_SP_INTERFACE-1.0.0",))
    program = _create_program(_replacing(attributes, "BINDING_EVENTS", (False,)))

    messages = _messages(program)

    assert len(messages) == 2
    assert any("PROGRAM_TYPE" in m for m in messages)
    assert any("BINDING_EVENTS" in m for m in messages)


def test_a_program_without_attributes_is_rejected() -> None:
    """With no kind, only PROGRAM_TYPE and BINDING_EVENTS are reported; RETAILER_NAME needs a kind."""
    errors = validate_program_nlflex_compliant(NewProgram(program_name="DER interface", attributes=None))

    assert errors is not None
    assert len(errors) == 2


def test_program_kind_and_version_follow_program_type() -> None:
    """The kind and the x.y.z core are read from PROGRAM_TYPE; pre-release and build suffixes are not part of it."""
    assert program_kind(_typed_program(REGISTRATION)) is ProgramKind.REGISTRATION
    assert program_kind(_typed_program(DISPATCH)) is ProgramKind.DISPATCH
    assert program_version(_typed_program("DER_DISPATCH_INTERFACE-2.3.4-rc.1+build.5")) == "2.3.4"
    assert program_kind(_typed_program("DSO_SP_INTERFACE-1.0.0")) is None
    assert program_version(_typed_program("DSO_SP_INTERFACE-1.0.0")) is None


def test_programs_on_one_version_are_in_lock_step() -> None:
    """The registration program and a dispatch program on the same version are in lock step."""
    programs = [_typed_program(REGISTRATION), _typed_program(DISPATCH)]

    assert validate_programs_lock_step(programs) == []


def test_programs_on_two_versions_are_not_in_lock_step() -> None:
    """One error is reported however many programs disagree."""
    programs = [
        _typed_program(REGISTRATION),
        _typed_program(DISPATCH),
        _typed_program("DER_DISPATCH_INTERFACE-1.1.1"),
    ]

    errors = validate_programs_lock_step(programs)

    assert len(errors) == 1
    assert "same version" in str(errors[0]["type"])


def test_two_majors_each_in_lock_step_pass() -> None:
    """During a MAJOR phase-out both MAJOR versions are present, each in lock step on its own."""
    programs = [
        _typed_program(REGISTRATION),
        _typed_program(DISPATCH),
        _typed_program("DER_REGISTRATION_INTERFACE-2.0.0"),
        _typed_program("DER_DISPATCH_INTERFACE-2.0.0"),
    ]

    assert validate_programs_lock_step(programs) == []


def test_only_the_major_out_of_lock_step_is_reported() -> None:
    """A MAJOR with two versions gets an error naming only its own versions, the other MAJOR stays clean."""
    programs = [
        _typed_program(REGISTRATION),
        _typed_program("DER_DISPATCH_INTERFACE-1.1.1"),
        _typed_program("DER_REGISTRATION_INTERFACE-2.0.0"),
        _typed_program("DER_DISPATCH_INTERFACE-2.0.0"),
    ]

    errors = validate_programs_lock_step(programs)

    assert len(errors) == 1
    assert "1.1.0, 1.1.1" in str(errors[0]["type"])
    assert "2.0.0" not in str(errors[0]["type"])
    assert errors[0]["input"] == ["1.1.0", "1.1.1"]


def test_a_pre_release_counts_as_its_version_core() -> None:
    """The x.y.z core is compared, so 1.1.0 and 1.1.0-rc.1 are in lock step."""
    programs = [_typed_program(REGISTRATION), _typed_program("DER_DISPATCH_INTERFACE-1.1.0-rc.1")]

    assert validate_programs_lock_step(programs) == []


def test_lock_step_ignores_programs_of_no_known_kind() -> None:
    """A program the kind check already rejects does not count as a version of its own."""
    programs = [_typed_program(REGISTRATION), _typed_program("DSO_SP_INTERFACE-1.0.0")]

    assert validate_programs_lock_step(programs) == []

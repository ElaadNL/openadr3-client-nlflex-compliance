# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for the programs of the OpenADR DER profile specification v1.1.0.

This profile defines two kinds of program (see "Program"): the registration program, owned by GOPACS,
and one dispatch program per DSO. Both carry the version of this specification and are the parent of
the events their owner creates. The kind of a program follows from its PROGRAM_TYPE attribute, which
is also how a VEN client discovers it (see "Program discovery").

RETAILER_LONG_NAME and COUNTRY are SHOULD rather than MUST and are not enforced here. COUNTRY is
already validated by the base client against ISO 3166-1.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

from openadr3_client.oadr310.models.program.program import Program
from openadr3_client.oadr310.models.program.program_attribute import ProgramAttributeType
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex11._common import (
    GOPACS_IDENTIFIER,
    error,
    is_dso_identifier,
    is_registration_operator,
)

# The version of this specification. PROGRAM_TYPE carries it as "x.x.x", which "Profile specification
# versioning" defines as the version of this specification. A PATCH release changes no rule, so any
# 1.1.z is a program for this version of the specification; a later MINOR or MAJOR version is not. A
# pre-release or build of such a version (1.1.0-rc.1, 1.1.2+build.5) is the same version, so the
# Semantic Versioning suffixes are accepted after it.
SPECIFICATION_MAJOR_MINOR: Final = "1.1"
# The named group is the x.y.z core, which the lock step compares; the suffixes are not part of it.
_SPECIFICATION_VERSION = rf"(?P<version>{re.escape(SPECIFICATION_MAJOR_MINOR)}\.(?:0|[1-9]\d*))"

# The pre-release and build suffixes of the Semantic Versioning standard.
_SEMVER_SUFFIXES = (
    r"(?:-(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*)?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?"
)


class ProgramKind(StrEnum):
    """The two kinds of program this profile defines (see "Program")."""

    REGISTRATION = "REGISTRATION"
    DISPATCH = "DISPATCH"


# PROGRAM_TYPE MUST equal "DER_REGISTRATION_INTERFACE-x.x.x" for the registration program and
# "DER_DISPATCH_INTERFACE-x.x.x" for a dispatch program, where x.x.x is the version of this specification.
_PROGRAM_TYPE_PATTERNS = {
    ProgramKind.REGISTRATION: re.compile(rf"DER_REGISTRATION_INTERFACE-{_SPECIFICATION_VERSION}{_SEMVER_SUFFIXES}"),
    ProgramKind.DISPATCH: re.compile(rf"DER_DISPATCH_INTERFACE-{_SPECIFICATION_VERSION}{_SEMVER_SUFFIXES}"),
}

PROGRAM_TYPE_ATTRIBUTE = ProgramAttributeType.PROGRAM_TYPE
RETAILER_NAME_ATTRIBUTE = ProgramAttributeType.RETAILER_NAME
BINDING_EVENTS_ATTRIBUTE = ProgramAttributeType.BINDING_EVENTS


def _attribute_values(program: Program, attribute_type: ProgramAttributeType) -> list[object]:
    """
    Collects every value the program carries for one attribute type.

    Reads all attributes of that type rather than the first, so that a second entry for the same type
    counts as a second value instead of being silently ignored.
    """
    return [
        value
        for attribute in (program.attributes or ())
        if attribute.type == attribute_type
        for value in attribute.values
    ]


def _match_program_type(program: Program) -> tuple[ProgramKind, re.Match[str]] | None:
    """Matches the PROGRAM_TYPE of the program, which must hold exactly one value of a known format."""
    values = _attribute_values(program, PROGRAM_TYPE_ATTRIBUTE)

    # Two values would make the kind ambiguous, so they are rejected rather than resolved.
    if len(values) != 1 or not isinstance(values[0], str):
        return None

    for kind, pattern in _PROGRAM_TYPE_PATTERNS.items():
        match = pattern.fullmatch(values[0])
        if match:
            return kind, match
    return None


def program_kind(program: Program) -> ProgramKind | None:
    """
    Determines which kind of program this is.

    Returns:
        The kind, or None unless the program has exactly one PROGRAM_TYPE value naming the registration
        or the dispatch program of version 1.1.z of the specification, optionally with a pre-release
        or build suffix.

    """
    matched = _match_program_type(program)
    return matched[0] if matched else None


def program_version(program: Program) -> str | None:
    """
    Reads the version of this specification the program advertises.

    Returns:
        The x.y.z core of the PROGRAM_TYPE value, or None when the program is of no known kind.

    """
    matched = _match_program_type(program)
    return matched[1].group("version") if matched else None


def _program_type_attribute_compliant(program: Program) -> list[InitErrorDetails]:
    """Validates that the program declares which kind of program it is and the version it implements."""
    if program_kind(program) is not None:
        return []

    return [
        error(
            "The program must have exactly one PROGRAM_TYPE value: "
            f"DER_REGISTRATION_INTERFACE-{SPECIFICATION_MAJOR_MINOR}.z for the registration program or "
            f"DER_DISPATCH_INTERFACE-{SPECIFICATION_MAJOR_MINOR}.z for a dispatch program, where z is the "
            f"PATCH version, as this is version {SPECIFICATION_MAJOR_MINOR} of the profile specification.",
            "attributes",
            program.attributes,
        )
    ]


def _retailer_name_attribute_compliant(program: Program, kind: ProgramKind) -> list[InitErrorDetails]:
    """Validates that the program names the operator that owns it, as the "Operator identifiers" section defines."""
    values = _attribute_values(program, RETAILER_NAME_ATTRIBUTE)

    if kind is ProgramKind.REGISTRATION:
        is_operator = is_registration_operator
        expectation = (
            f"the identifier of GOPACS, the string {GOPACS_IDENTIFIER}, as the registration program is owned by GOPACS"
        )
    else:
        is_operator = is_dso_identifier
        expectation = (
            "the identifier of the issuing DSO: one of the six DSO EAN13 codes in the Operator identifiers table"
        )

    if len(values) != 1 or not is_operator(values[0]):
        return [
            error(
                f"The RETAILER_NAME attribute of a {kind.value.lower()} program must have exactly one value, "
                f"which must be {expectation}.",
                "attributes",
                program.attributes,
            )
        ]

    return []


def _binding_events_attribute_compliant(program: Program) -> list[InitErrorDetails]:
    """
    Validates that the program advertises its events as immutable.

    Events in this profile MUST NOT be modified once created: to change one, the BL deletes it and
    creates a new one. BINDING_EVENTS is how that is advertised to the aggregator.
    """
    values = _attribute_values(program, BINDING_EVENTS_ATTRIBUTE)

    if len(values) != 1 or values[0] is not True:
        return [
            error(
                "The program must have a BINDING_EVENTS attribute set to true. Events in this profile are immutable.",
                "attributes",
                program.attributes,
            )
        ]

    return []


def validate_program_nlflex_compliant(program: Program) -> list[InitErrorDetails] | None:
    """
    Validates that a program is compliant with the OpenADR DER profile specification v1.1.0.

    The checks that depend on the kind of program only run when PROGRAM_TYPE identifies one. Without
    a kind there is no owner to hold RETAILER_NAME against, and the PROGRAM_TYPE error already says
    why. BINDING_EVENTS applies to both kinds and is always checked.

    Args:
        program: The program to validate.

    Returns:
        The validation errors found, or None when the program is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_program_type_attribute_compliant(program))

    kind = program_kind(program)
    if kind is not None:
        validation_errors.extend(_retailer_name_attribute_compliant(program, kind))

    validation_errors.extend(_binding_events_attribute_compliant(program))

    return validation_errors or None


def validate_programs_lock_step(programs: Sequence[Program]) -> list[InitErrorDetails]:
    """
    Validates that the programs are versioned in lock step, per MAJOR version.

    "Profile specification versioning" requires the registration program and every dispatch program to
    advertise the same {MAJOR}.{MINOR}.{PATCH} version. During the phase out of an old MAJOR version
    both MAJOR versions are present and the VEN client selects the programs of the MAJOR it implements,
    so the lock step holds within each MAJOR version, not across them. This is a rule over a set of
    programs, not over one, so it is not part of the per-program validator and is exported for callers
    that hold the set. Programs of no known kind are left out: their own validator already reports them.

    Args:
        programs: The registration and dispatch programs to compare. The registration program and the
            dispatch programs are currently hosted on separate VTN deployments, so the caller merges the
            programs read from both.

    Returns:
        One error for each MAJOR version whose programs advertise more than one version, otherwise an
        empty list.

    """
    versions_by_major: dict[int, set[str]] = defaultdict(set)
    for program in programs:
        version = program_version(program)
        if version is not None:
            versions_by_major[_version_key(version)[0]].add(version)

    return [
        _lock_step_error(sorted(versions, key=_version_key))
        for _, versions in sorted(versions_by_major.items())
        if len(versions) > 1
    ]


def _version_key(version: str) -> tuple[int, ...]:
    """Orders x.y.z versions numerically, so 1.10.0 sorts after 1.9.0."""
    return tuple(int(part) for part in version.split("."))


def _lock_step_error(versions: list[str]) -> InitErrorDetails:
    """Reports the versions advertised within one MAJOR version that are not in lock step."""
    return error(
        "The registration program and every dispatch program of one MAJOR version must advertise the same "
        f"version of the profile specification, but these versions were found: {', '.join(versions)}.",
        "attributes",
        versions,
    )

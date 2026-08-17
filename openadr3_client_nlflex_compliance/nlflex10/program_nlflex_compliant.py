# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for the program of the OpenADR DER profile specification v1.0.0.

In this profile the program identifies the DSO to Service Provider interface and the version of the
specification it implements, and is the parent of the events.

RETAILER_LONG_NAME and COUNTRY are SHOULD rather than MUST and are not enforced here. COUNTRY is
already validated by the base client against ISO 3166-1.
"""

import re

from openadr3_client.oadr310.models.program.program import Program
from openadr3_client.oadr310.models.program.program_attribute import ProgramAttributeType
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex10._common import error, is_dso_identifier

# PROGRAM_TYPE MUST equal "DSO_SP_INTERFACE-x.x.x", where x.x.x is the version of this
# specification, which follows the Semantic Versioning standard.
PROGRAM_TYPE_REGEX = (
    r"^DSO_SP_INTERFACE-"
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))"
    r"?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"$"
)

PROGRAM_TYPE_ATTRIBUTE = ProgramAttributeType.PROGRAM_TYPE
RETAILER_NAME_ATTRIBUTE = ProgramAttributeType.RETAILER_NAME
BINDING_EVENTS_ATTRIBUTE = ProgramAttributeType.BINDING_EVENTS


def _program_type_attribute_compliant(self: Program) -> list[InitErrorDetails]:
    """Validates that the program declares the version of this specification it implements."""
    program_type = self.attributes.get_by_type(PROGRAM_TYPE_ATTRIBUTE) if self.attributes else None

    if program_type is None:
        return [
            error("The program must have a PROGRAM_TYPE attribute.", "attributes", self.attributes),
        ]

    if not program_type.values or not all(
        isinstance(value, str) and re.fullmatch(PROGRAM_TYPE_REGEX, value) for value in program_type.values
    ):
        return [
            error(
                "The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z, where x.y.z is the "
                "version of the profile specification the program implements.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _retailer_name_attribute_compliant(self: Program) -> list[InitErrorDetails]:
    """Validates that the program names the DSO issuing it, by its EAN13."""
    retailer_name = self.attributes.get_by_type(RETAILER_NAME_ATTRIBUTE) if self.attributes else None

    if retailer_name is None:
        return [
            error("The program must have a RETAILER_NAME attribute.", "attributes", self.attributes),
        ]

    if not retailer_name.values or not all(is_dso_identifier(value) for value in retailer_name.values):
        return [
            error(
                "The RETAILER_NAME attribute must be the identifier of the issuing DSO. The profile fixes these: the "
                "value must be one of the six EAN13 codes in the DSO identifiers table.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def _binding_events_attribute_compliant(self: Program) -> list[InitErrorDetails]:
    """
    Validates that the program advertises its events as immutable.

    Events in this profile MUST NOT be modified once created: to change one, the BL deletes it and
    creates a new one. BINDING_EVENTS is how that is advertised to the Service Provider.
    """
    binding_events = self.attributes.get_by_type(BINDING_EVENTS_ATTRIBUTE) if self.attributes else None

    if binding_events is None or len(binding_events.values) != 1 or binding_events.values[0] is not True:
        return [
            error(
                "The program must have a BINDING_EVENTS attribute set to true. Events in this profile are immutable.",
                "attributes",
                self.attributes,
            )
        ]

    return []


def validate_program_nlflex_compliant(program: Program) -> list[InitErrorDetails] | None:
    """
    Validates that a program is compliant with the OpenADR DER profile specification v1.0.0.

    Args:
        program: The program to validate.

    Returns:
        The validation errors found, or None when the program is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_program_type_attribute_compliant(program))
    validation_errors.extend(_retailer_name_attribute_compliant(program))
    validation_errors.extend(_binding_events_attribute_compliant(program))

    return validation_errors or None

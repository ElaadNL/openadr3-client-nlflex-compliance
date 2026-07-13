# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""Module which implements NL-Flex 0.1 compliance validators for the program OpenADR3 types."""

import re

from openadr3_client.oadr310.models.program.program import Program
from openadr3_client.oadr310.models.program.program_attribute import ProgramAttributeType
from pydantic_core import InitErrorDetails, PydanticCustomError

DSO_IDENTIFIER_REGEX = r"^DSB-[A-Z]+$"

# PROGRAM_TYPE MUST be formatted as "DSO_SP_INTERFACE-{MAJOR}.{MINOR}.{PATCH}",
# where the version follows the Semantic Versioning standard (see Section 11.9,
# "Profile specification versioning" of the NL-Flex specification).
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


def _program_type_attribute_compliant(self: Program) -> list[InitErrorDetails]:
    """Validates that the program has a PROGRAM_TYPE attribute formatted as DSO_SP_INTERFACE-x.y.z."""
    validation_errors: list[InitErrorDetails] = []

    program_type = self.attributes.get_by_type(PROGRAM_TYPE_ATTRIBUTE) if self.attributes else None

    if program_type is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The program must have a PROGRAM_TYPE attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not program_type.values or not all(re.fullmatch(PROGRAM_TYPE_REGEX, value) for value in program_type.values):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def _retailer_name_attribute_compliant(self: Program) -> list[InitErrorDetails]:
    """Validates that the program has a RETAILER_NAME attribute formatted as a DSO identifier."""
    validation_errors: list[InitErrorDetails] = []

    retailer_name = self.attributes.get_by_type(RETAILER_NAME_ATTRIBUTE) if self.attributes else None

    if retailer_name is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The program must have a RETAILER_NAME attribute.",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )
    elif not retailer_name.values or not all(
        re.fullmatch(DSO_IDENTIFIER_REGEX, value) for value in retailer_name.values
    ):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The RETAILER_NAME attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA').",
                ),
                loc=("attributes",),
                input=self.attributes,
                ctx={},
            )
        )

    return validation_errors


def validate_program_nlflex_compliant(program: Program) -> list[InitErrorDetails] | None:
    """
    Validates that the program is NL-Flex 0.1 compliant.

    The following constraints are enforced for programs, as specified in Section 11.4, "Program"
    of the NL-Flex specification:

    - The program MUST have a PROGRAM_TYPE attribute, formatted as "DSO_SP_INTERFACE-x.y.z",
      where x.y.z is the version of the NL-Flex specification implemented by the program.
    - The program MUST have a RETAILER_NAME attribute, being the identifier of the issuing DSO
      as specified in Section 14.1, "DSO identifiers".
    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_program_type_attribute_compliant(program))
    validation_errors.extend(_retailer_name_attribute_compliant(program))

    return validation_errors or None

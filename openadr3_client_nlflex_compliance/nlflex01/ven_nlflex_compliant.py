# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""Module which implements NL-Flex 0.1 compliance validators for the ven OpenADR3 types."""

import re

from openadr3_client.oadr310.models.ven.ven import Ven
from pydantic_core import InitErrorDetails, PydanticCustomError

SERVICE_PROVIDER_IDENTIFIER_REGEX = r"^SP-[A-Z]+$"


def validate_ven_nlflex_compliant(ven: Ven) -> list[InitErrorDetails] | None:
    """
    Validates that the VEN is NL-Flex 0.1 compliant.

    The following constraint is enforced for VENs:

    - The VEN name MUST be the Service Provider identifier, as specified in Section 14.2,
      "Service Provider identifiers" of the NL-Flex specification.
    """
    validation_errors: list[InitErrorDetails] = []

    if not re.fullmatch(SERVICE_PROVIDER_IDENTIFIER_REGEX, ven.ven_name):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The VEN name must be formatted as a Service Provider identifier (e.g. 'SP-ZON').",
                ),
                loc=("ven_name",),
                input=ven.ven_name,
                ctx={},
            )
        )

    return validation_errors or None

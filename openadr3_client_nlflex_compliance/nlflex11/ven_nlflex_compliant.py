# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for the VEN of the OpenADR DER profile specification v1.1.0.

In OpenADR a VEN is an actor that can receive objects from the VTN. In this profile the VEN is an
aggregator, and its venName is that aggregator's identifier: an EAN13, obtained by
registering with the market.

The targets of a VEN are set by the BL and hold the Group-ID of every resource group the
aggregator is allowed to see before it has registered an asset into that group. They are optional and
carry no format the profile constrains, so nothing is enforced for them.
"""

from openadr3_client.oadr310.models.ven.ven import Ven
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex11._common import error, is_ean13


def validate_ven_nlflex_compliant(ven: Ven) -> list[InitErrorDetails] | None:
    """
    Validates that a VEN is compliant with the OpenADR DER profile specification v1.1.0.

    Args:
        ven: The VEN to validate.

    Returns:
        The validation errors found, or None when the VEN is compliant.

    """
    if not is_ean13(ven.ven_name):
        return [
            error(
                "The VEN name must be the aggregator identifier, which is an EAN13 of 13 digits with a "
                "valid check digit (for example '8712345678906').",
                "ven_name",
                ven.ven_name,
            )
        ]

    return None

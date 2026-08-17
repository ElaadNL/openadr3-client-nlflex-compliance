# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""Shared building blocks for the OpenADR DER profile specification v1.0.0 compliance validators."""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic_core import InitErrorDetails, PydanticCustomError

# --------------------------------------------------------------------------------------------------------------
# Validation errors: construction of the validation errors every validator in this package returns.
# --------------------------------------------------------------------------------------------------------------


def error(message: str, loc: str, value: object) -> InitErrorDetails:
    """
    Builds a single validation error.

    Keeps the noise of the pydantic constructor in one place, so that a validator reads as the list
    of rules it enforces.

    Args:
        message: The rule that was violated, in prose.
        value: The value that violated it, reported back to the caller as the error's input.
        loc: The name of the field the rule applies to.

    Returns:
        The validation error, ready to be collected into a list.

    """
    return InitErrorDetails(
        # PydanticCustomError wants a LiteralString, but every message here is built at runtime
        # from the rule that was violated. Both checkers need their own suppression comment.
        type=PydanticCustomError(
            "value_error",
            message,  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        ),
        loc=(loc,),
        input=value,
        ctx={},
    )


# --------------------------------------------------------------------------------------------------------------
# Identifiers: the standardized identifiers of the OpenADR DER profile specification v1.0.0.
#
# The Dutch energy market uses two EAN lengths and this profile keeps them apart. An EAN18 identifies
# a PCC, the grid connection an asset sits behind, and is carried on a resource. An EAN13 identifies a
# market party, a DSO or a Service Provider. Both are written as a numeric string, without separators
# and without an 'EAN' prefix, and the check digit MUST be valid.
#
# Group-IDs and Asset-IDs are neither EANs nor UUIDs. They are assigned by the BL and by the Service
# Provider respectively and have no format this profile constrains, so they have no validator here.
#
# The DSO identifiers are a closed set (see "DSO identifiers"): "Each DSO MUST be identified by its
# EAN13 code. The following codes MUST be used", followed by six entries. Membership is therefore
# enforced, not just the EAN13 shape - a well formed EAN13 that names no Dutch DSO is not a DSO_ID.
# Service Provider identifiers are the opposite case: that section names no table, since a Service
# Provider obtains its EAN13 by registering as a Congestion Service Provider, so those are validated
# on shape alone.
# --------------------------------------------------------------------------------------------------------------

EAN13_LENGTH = 13
EAN18_LENGTH = 18


def _has_valid_check_digit(value: str) -> bool:
    """
    Validates the trailing check digit of an EAN.

    One routine covers both lengths. Reading right to left from the digit before the check digit,
    digits are weighted 3, 1, 3, 1 and summed; the check digit is that sum's complement to the next
    multiple of ten.
    """
    digits = [int(digit) for digit in value]
    *body, check_digit = digits
    weighted = sum(digit * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body)))
    return (10 - weighted % 10) % 10 == check_digit


def _is_ean(value: object, length: int) -> bool:
    """Validates that the value is an EAN of the given length, with a valid check digit."""
    return (
        isinstance(value, str)
        and len(value) == length
        # str.isdigit accepts unicode decimal digits, which are not an EAN.
        and value.isascii()
        and value.isdigit()
        and _has_valid_check_digit(value)
    )


def is_ean13(value: object) -> bool:
    """Validates that the value is the EAN13 code of a market party, such as a DSO or a Service Provider."""
    return _is_ean(value, EAN13_LENGTH)


# See the "DSO identifiers" table. A seventh DSO joining a future edition of the profile needs this
# set extended, which is the intended coupling: the table is normative.
KNOWN_DSO_IDENTIFIERS = frozenset(
    {
        "8716916000004",  # Coteq
        "8712423014022",  # Enexis
        "8716871000002",  # Liander
        "8716912000008",  # Rendo
        "8716892000005",  # Stedin
        "8716878999996",  # Westland Infra
    }
)


def is_dso_identifier(value: object) -> bool:
    """
    Validates that the value is one of the DSO identifiers the specification names.

    The profile fixes the identifier of every Dutch DSO, so an EAN13 outside that table identifies
    no DSO this profile knows, however well formed it is.
    """
    return value in KNOWN_DSO_IDENTIFIERS


def is_ean18(value: object) -> bool:
    """Validates that the value is the EAN18 code of a PCC, the grid connection an asset is connected to."""
    return _is_ean(value, EAN18_LENGTH)


def is_uuid(value: object) -> bool:
    """
    Validates that the value is a UUID.

    All IDs in this profile are UUIDs, except the Group-ID, the Asset-ID and the EAN-based party and
    connection identifiers.
    """
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------------------------------------------
# Power values: the power values of the OpenADR DER profile specification v1.0.0.
#
# Every power value in the profile is a double in KW carrying at most two decimal places: the payloads
# of the baseline event, the flexibility dispatch event, the flex delta override event, the flex delta
# report and the flex delivery report, and the EVSE_BASELINE_OVERRIDE and computed capacity attributes
# of a resource group.
#
# Whether a value may be negative follows from the payload type that carries it, so no sign is
# enforced here. Each caller applies its own bound.
# --------------------------------------------------------------------------------------------------------------

MAX_DECIMAL_PLACES = 2


def as_power_value(value: object) -> float | None:
    """
    Reads a payload or attribute value as a power value.

    Args:
        value: The value to read. Payload values are typed as int, float, str, bool or Point, so
            most of the work is rejecting the ones that are not a number.

    Returns:
        The value as a float, or None when it is not a double in KW with at most two decimals.

    """
    # bool is a subclass of int in Python, and True is not 1 kW.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    try:
        exponent = Decimal(str(value)).as_tuple().exponent
    except InvalidOperation:  # pragma: no cover - str() of a float is always parseable
        return None

    # Infinity and NaN carry a string exponent rather than an integer one.
    if not isinstance(exponent, int) or exponent < -MAX_DECIMAL_PLACES:
        return None

    return float(value)


def is_power_value(value: object) -> bool:
    """Validates that the value is a double in KW with at most two decimal places."""
    return as_power_value(value) is not None

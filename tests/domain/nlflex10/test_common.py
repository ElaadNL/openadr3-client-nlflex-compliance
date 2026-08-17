# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import pytest

from openadr3_client_nlflex_compliance.nlflex10._common import (
    KNOWN_DSO_IDENTIFIERS,
    as_power_value,
    is_dso_identifier,
    is_ean13,
    is_ean18,
    is_power_value,
    is_uuid,
)

# --- Identifiers (EAN13, EAN18, UUID) ---------------------------------------------------------

# The six DSO identifiers of the "DSO identifiers" table, plus the two fictional EAN13 codes the
# specification's examples use for a DSO and a Service Provider.
SPEC_EAN13_IDENTIFIERS = (
    "8716916000004",
    "8712423014022",
    "8716871000002",
    "8716912000008",
    "8716892000005",
    "8716878999996",
    "8719876543215",
    "8712345678906",
)


@pytest.mark.parametrize("identifier", SPEC_EAN13_IDENTIFIERS)
def test_ean13_accepts_every_identifier_in_the_specification(identifier: str) -> None:
    """Every EAN13 the specification names is accepted, check digit included."""
    assert is_ean13(identifier)


def test_ean18_accepts_the_specification_example() -> None:
    """The EAN18 of the PCC used throughout the specification's examples is accepted."""
    assert is_ean18("871685900000000127")


def test_ean13_rejects_an_invalid_check_digit() -> None:
    """A mistyped final digit is rejected: the check digit MUST be valid."""
    assert not is_ean13("8719876543216")


def test_ean18_rejects_an_invalid_check_digit() -> None:
    """A mistyped final digit is rejected for the 18 digit form too."""
    assert not is_ean18("871685900000000128")


def test_ean13_rejects_the_draft_identifier_format() -> None:
    """The v0.1 draft used identifiers such as 'DSB-LIA'. v1.0.0 uses EAN13 codes."""
    assert not is_ean13("DSB-LIA")


def test_ean13_rejects_the_wrong_length() -> None:
    """An EAN18 is not an EAN13, even though both are numeric strings."""
    assert not is_ean13("871685900000000127")


def test_ean18_rejects_the_wrong_length() -> None:
    """An EAN13 is not an EAN18."""
    assert not is_ean18("8719876543215")


def test_ean13_rejects_separators() -> None:
    """An EAN MUST be written without separators and without an 'EAN' prefix."""
    assert not is_ean13("871-987-654-3215")


def test_ean13_rejects_non_ascii_digits() -> None:
    """Unicode decimal digits are digits to str.isdigit, but are not an EAN."""
    assert not is_ean13("٨٧١٩٨٧٦٥٤٣٢١٥")


def test_ean13_rejects_a_non_string() -> None:
    """A numeric value is not an EAN: the profile requires a numeric string."""
    assert not is_ean13(8719876543215)


def test_uuid_accepts_a_resource_id() -> None:
    """Resource IDs in a registration report are UUIDs."""
    assert is_uuid("a1a1a1a1-0001-4001-8001-000000000001")


def test_uuid_rejects_an_asset_id() -> None:
    """An Asset-ID is not a UUID; the registration report carries object IDs, not names."""
    assert not is_uuid("ASSET-0001")


# --- Power values -------------------------------------------------------------------------------


def test_a_whole_number_is_a_valid_double() -> None:
    """The specification says so explicitly: a whole number such as 500 is a valid double."""
    assert as_power_value(500) == 500.0


def test_two_decimals_are_allowed() -> None:
    """A double MUST NOT carry more than two decimal places; two is the limit, not a rejection."""
    assert as_power_value(1.25) == 1.25


def test_three_decimals_are_rejected() -> None:
    """A double MUST NOT carry more than two decimal places."""
    assert as_power_value(1.234) is None


def test_a_negative_value_is_a_power_value() -> None:
    """Whether a value may be negative follows from the payload type, not from the number itself."""
    assert as_power_value(-300) == -300.0


def test_zero_is_a_power_value() -> None:
    """Zero is a valid double, and several payload types use it."""
    assert as_power_value(0) == 0.0


def test_a_string_is_not_a_power_value() -> None:
    """A payload value may be a string; a power value may not."""
    assert as_power_value("500") is None


def test_a_boolean_is_not_a_power_value() -> None:
    """True is not 1 kW, even though bool is a subclass of int in Python."""
    assert as_power_value(True) is None


def test_not_a_number_is_not_a_power_value() -> None:
    """NaN has no decimal exponent and is not a power value."""
    assert as_power_value(float("nan")) is None


def test_infinity_is_not_a_power_value() -> None:
    """Infinity has no decimal exponent and is not a power value."""
    assert as_power_value(float("inf")) is None


def test_is_power_value_mirrors_as_power_value() -> None:
    """The predicate is the conversion, read as a question."""
    assert is_power_value(500)
    assert not is_power_value(1.234)


@pytest.mark.parametrize("identifier", sorted(KNOWN_DSO_IDENTIFIERS))
def test_every_dso_in_the_table_is_a_dso_identifier(identifier: str) -> None:
    """The specification names six DSOs and fixes the EAN13 of each."""
    assert is_dso_identifier(identifier)


def test_the_table_holds_exactly_the_six_dsos_named() -> None:
    """A seventh entry means the specification changed and this set must change with it."""
    assert len(KNOWN_DSO_IDENTIFIERS) == 6


def test_a_valid_ean13_that_names_no_dso_is_not_a_dso_identifier() -> None:
    """The specification says the listed codes must be used, so an EAN13 outside the table names no DSO."""
    assert is_ean13("8712345678906")
    assert not is_dso_identifier("8712345678906")


def test_the_specifications_fictional_dso_code_is_not_a_dso_identifier() -> None:
    """The worked examples use a fictional EAN13 as a placeholder; it names no real DSO."""
    assert is_ean13("8719876543215")
    assert not is_dso_identifier("8719876543215")

# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime, timedelta

import pytest

from openadr3_client_nlflex_compliance.nlflex11._common import (
    KNOWN_DSO_IDENTIFIERS,
    as_power_value,
    is_dso_identifier,
    is_ean13,
    is_ean18,
    is_power_value,
    is_registration_operator,
    is_uuid,
    local_day_length,
)

# --- Operator identifiers -----------------------------------------------------------------------


def test_gopacs_is_the_registration_operator() -> None:
    """GOPACS has no EAN13 and is identified by the string GOPACS (see "Operator identifiers")."""
    assert is_registration_operator("GOPACS")


def test_gopacs_is_not_a_dso() -> None:
    """The registration operator is not one of the DSOs in the operator identifiers table."""
    assert not is_dso_identifier("GOPACS")


def test_a_dso_is_not_the_registration_operator() -> None:
    """The match is exact: a DSO EAN13 and a differently cased name are not GOPACS."""
    assert not is_registration_operator("8716871000002")
    assert not is_registration_operator("gopacs")


# --- Identifiers (EAN13, EAN18, UUID) ---------------------------------------------------------

# The six DSO identifiers of the "Operator identifiers" table, plus the two fictional EAN13 codes the
# specification's examples use for a DSO and an aggregator.
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
    """The v0.1 draft used identifiers such as 'DSB-LIA'. v1.1.0 uses EAN13 codes."""
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


# --- Local calendar days ------------------------------------------------------------------------


def test_an_ordinary_day_is_24_hours() -> None:
    """2026-01-02 has no DST transition, so local midnight to local midnight is PT24H."""
    assert local_day_length(datetime(2026, 1, 1, 23, 0, 0, tzinfo=UTC)) == timedelta(hours=24)


def test_the_spring_dst_day_is_23_hours() -> None:
    """DST starts on 2026-03-29, which loses the hour from 02:00 to 03:00 local time."""
    assert local_day_length(datetime(2026, 3, 28, 23, 0, 0, tzinfo=UTC)) == timedelta(hours=23)


def test_the_autumn_dst_day_is_25_hours() -> None:
    """DST ends on 2026-10-25, which repeats the hour from 02:00 to 03:00 local time."""
    assert local_day_length(datetime(2026, 10, 24, 22, 0, 0, tzinfo=UTC)) == timedelta(hours=25)


def test_a_non_midnight_start_has_no_day_length() -> None:
    """08:00 local time is the publication deadline, not the start of a day."""
    assert local_day_length(datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)) is None

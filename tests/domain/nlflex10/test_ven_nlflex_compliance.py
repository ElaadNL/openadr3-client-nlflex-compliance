# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from openadr3_client.oadr310.models.ven.ven import NewVenBlRequest

from openadr3_client_nlflex_compliance.nlflex10.ven_nlflex_compliant import validate_ven_nlflex_compliant


def _create_ven(ven_name: str, targets: tuple[str, ...] | None = None) -> NewVenBlRequest:
    """Helper function to create a VEN with the specified name."""
    return NewVenBlRequest(ven_name=ven_name, clientID="elaad-client", targets=targets)


def test_ven_valid() -> None:
    """A VEN matching the specification's example is compliant."""
    assert validate_ven_nlflex_compliant(_create_ven("8712345678906", ("GROUP-0001",))) is None


def test_a_ven_without_targets_is_valid() -> None:
    """Targets are set by the BL, so a VEN that has registered assets need not carry any."""
    assert validate_ven_nlflex_compliant(_create_ven("8712345678906")) is None


def test_the_draft_identifier_format_is_rejected() -> None:
    """The v0.1 draft used identifiers such as 'SP-ZON'. v1.0.0 uses an EAN13."""
    errors = validate_ven_nlflex_compliant(_create_ven("SP-ZON"))

    assert errors is not None
    assert any("Service Provider identifier" in str(error["type"]) for error in errors)


def test_an_invalid_check_digit_is_rejected() -> None:
    """The check digit MUST be valid, so a mistyped EAN13 does not pass."""
    errors = validate_ven_nlflex_compliant(_create_ven("8712345678900"))

    assert errors is not None
    assert any("Service Provider identifier" in str(error["type"]) for error in errors)

# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re

import pytest
from openadr3_client.oadr310.models.ven.ven import NewVen
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin


def _create_ven(ven_name: str) -> NewVen:
    """
    Helper function to create a VEN with the specified values.

    Args:
        ven_name: The name of the VEN.

    """
    return NewVen(ven_name=ven_name)


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the NL-Flex plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


def test_ven_nlflex_compliant_valid() -> None:
    """Test that a VEN with a Service Provider identifier as VEN name is accepted."""
    ven = _create_ven("SP-ZON")

    assert ven.ven_name == "SP-ZON"


def test_ven_nlflex_compliant_invalid_format() -> None:
    """Test that a VEN with a VEN name that does not follow the Service Provider identifier format is rejected."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The VEN name must be formatted as a Service Provider identifier (e.g. 'SP-ZON')."),
    ):
        _ = _create_ven("ZON")


def test_ven_nlflex_compliant_lowercase_rejected() -> None:
    """Test that a VEN name with lowercase characters is rejected."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The VEN name must be formatted as a Service Provider identifier (e.g. 'SP-ZON')."),
    ):
        _ = _create_ven("SP-zon")


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the VEN validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewVen)
    assert len(validators) == 1

    valid_ven = _create_ven("SP-ELAAD")
    assert valid_ven.ven_name == "SP-ELAAD"

    with pytest.raises(ValidationError) as exc_info:
        _create_ven("INVALID")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert (
        errors[0].get("msg", None) == "The VEN name must be formatted as a Service Provider identifier (e.g. 'SP-ZON')."
    )


def test_plugin_error_details() -> None:
    """Test that plugin errors contain correct location and input information."""
    with pytest.raises(ValidationError) as exc_info:
        _create_ven("not-valid")

    errors = exc_info.value.errors()
    assert len(errors) == 1

    assert errors[0].get("loc", None) == ("ven_name",)
    assert errors[0].get("input", None) == "not-valid"
    assert errors[0].get("type", None) == "value_error"


def test_plugin_with_edge_cases() -> None:
    """Test plugin validation with various edge cases."""
    test_cases = [
        ("SP-ZON", 0),  # Valid
        ("SP-ESS", 0),  # Valid
        ("SP-", 1),  # Missing identifier suffix
        ("SP_ZON", 1),  # Wrong separator
        ("sp-zon", 1),  # Lowercase
    ]

    for ven_name, expected_error_count in test_cases:
        if expected_error_count == 0:
            _ = _create_ven(ven_name)
            continue

        with pytest.raises(ValidationError) as exc_info:
            _create_ven(ven_name)

        errors = exc_info.value.errors()
        assert len(errors) == expected_error_count, f"Expected {expected_error_count} errors for '{ven_name}'"

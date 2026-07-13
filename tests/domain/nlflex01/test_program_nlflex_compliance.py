# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.oadr310.models.program.program import NewProgram
from openadr3_client.oadr310.models.program.program_attribute import ProgramAttributeType
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin


def _create_program(
    retailer_name: str | None = "DSB-LIA",
    program_type: str | None = "DSO_SP_INTERFACE-1.0.0",
) -> NewProgram:
    """
    Helper function to create a program with the specified values.

    Args:
        retailer_name: The RETAILER_NAME attribute value of the program, omitted if None.
        program_type: The PROGRAM_TYPE attribute value of the program, omitted if None.

    """
    attributes: list[Attribute[Any]] = []
    if program_type is not None:
        attributes.append(Attribute(type=ProgramAttributeType.PROGRAM_TYPE, values=(program_type,)))
    if retailer_name is not None:
        attributes.append(Attribute(type=ProgramAttributeType.RETAILER_NAME, values=(retailer_name,)))

    return NewProgram(
        program_name="test-program",
        attributes=ValuesMap[ProgramAttributeType, Attribute](attributes) if attributes else None,
    )


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the NL-Flex plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


def test_program_nlflex_compliant_valid() -> None:
    """Test that a fully compliant program is accepted."""
    program = _create_program()

    assert program.program_name == "test-program"
    assert program.attributes is not None
    retailer_name = program.attributes.get_by_type(ProgramAttributeType.RETAILER_NAME)
    program_type = program.attributes.get_by_type(ProgramAttributeType.PROGRAM_TYPE)
    assert retailer_name is not None
    assert program_type is not None
    assert retailer_name.values == ("DSB-LIA",)
    assert program_type.values == ("DSO_SP_INTERFACE-1.0.0",)


def test_missing_retailer_name() -> None:
    """Test that a program without a RETAILER_NAME attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The program must have a RETAILER_NAME attribute.")):
        _ = _create_program(retailer_name=None)


def test_invalid_retailer_name_format() -> None:
    """Test that a program with a RETAILER_NAME attribute that is not a DSO identifier raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The RETAILER_NAME attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA')."),
    ):
        _ = _create_program(retailer_name="ElaadNL")


def test_missing_program_type() -> None:
    """Test that a program without a PROGRAM_TYPE attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The program must have a PROGRAM_TYPE attribute.")):
        _ = _create_program(program_type=None)


def test_invalid_program_type_format() -> None:
    """Test that a program with an invalid PROGRAM_TYPE attribute format raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z."),
    ):
        _ = _create_program(program_type="INVALID_FORMAT")


def test_invalid_program_type_version() -> None:
    """Test that a program with an invalid PROGRAM_TYPE attribute version raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z."),
    ):
        _ = _create_program(program_type="DSO_SP_INTERFACE-invalid")


def test_program_multiple_errors_grouped() -> None:
    """Test that multiple errors are grouped together and returned as a single error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("2 validation errors for NewProgram"),
    ) as exc_info:
        _ = _create_program(program_type="DSO_SP_INTERFACE-invalid", retailer_name="ElaadNL")

    grouped_errors = exc_info.value.errors()

    assert len(grouped_errors) == 2
    assert grouped_errors[0].get("type", None) == "value_error"
    assert grouped_errors[1].get("type", None) == "value_error"
    assert (
        grouped_errors[0].get("msg", None)
        == "The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z."
    )
    assert (
        grouped_errors[1].get("msg", None)
        == "The RETAILER_NAME attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA')."
    )


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the Program validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewProgram)
    assert len(validators) == 1

    valid_program = _create_program()
    assert valid_program.program_name == "test-program"

    with pytest.raises(ValidationError) as exc_info:
        _create_program(retailer_name=None, program_type="INVALID")

    errors = exc_info.value.errors()
    assert len(errors) == 2  # PROGRAM_TYPE, RETAILER_NAME

    assert errors[0].get("msg", None) == "The PROGRAM_TYPE attribute must follow the format DSO_SP_INTERFACE-x.y.z."
    assert errors[1].get("msg", None) == "The program must have a RETAILER_NAME attribute."


def test_plugin_error_details() -> None:
    """Test that plugin errors contain correct location and input information."""
    with pytest.raises(ValidationError) as exc_info:
        _create_program(retailer_name="ElaadNL", program_type="BAD")

    errors = exc_info.value.errors()
    assert len(errors) == 2

    assert errors[0].get("loc", None) == ("attributes",)
    assert errors[1].get("loc", None) == ("attributes",)


def test_plugin_with_edge_cases() -> None:
    """Test plugin validation with various edge cases."""
    test_cases = [
        (None, None, 2),  # Both validations fail
        ("DSB-LIA", None, 1),  # Only program_type fails
        (None, "DSO_SP_INTERFACE-1.0.0", 1),  # Only retailer_name fails
        ("ElaadNL", "DSO_SP_INTERFACE-1.0.0", 1),  # Only retailer_name format fails
        ("DSB-LIA", "INVALID", 1),  # Only program_type format fails
    ]

    for retailer_name, program_type, expected_error_count in test_cases:
        with pytest.raises(ValidationError) as exc_info:
            _create_program(retailer_name=retailer_name, program_type=program_type)

        errors = exc_info.value.errors()
        assert len(errors) == expected_error_count, (
            f"Expected {expected_error_count} errors for "
            f"retailer_name='{retailer_name}', program_type='{program_type}', got {len(errors)}"
        )

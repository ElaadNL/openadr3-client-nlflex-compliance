# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.extensions.resource_group.models.resource_group import NewResourceGroup
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

_UNSET: Any = object()


def _default_valid_targets(resource_group_name: str = "GROUP-0001") -> tuple[str, ...]:
    """Helper function to create default targets that are NL-Flex compliant."""
    return (resource_group_name,)


def _default_valid_attributes() -> tuple[Attribute, ...]:
    """Helper function to create default attributes that are NL-Flex compliant."""
    return (
        Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
        Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
        Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
        Attribute(type="MAX_DURATION", values=("PT4H",)),
    )


def _create_resource_group(
    resource_group_name: str = "GROUP-0001",
    targets: tuple[str, ...] = _UNSET,
    attributes: tuple[Attribute, ...] | None = _UNSET,
) -> NewResourceGroup:
    """
    Helper function to create a resource group with the specified values.

    Any argument left unset defaults to a NL-Flex compliant value. Passing ``None`` or ``()``
    explicitly is preserved, to allow testing the absence of a field.
    """
    resolved_attributes = _default_valid_attributes() if attributes is _UNSET else attributes
    return NewResourceGroup(
        resource_group_name=resource_group_name,
        targets=_default_valid_targets(resource_group_name) if targets is _UNSET else targets,
        attributes=(
            ValuesMap[VenResourceAttributeType, Attribute](resolved_attributes)
            if resolved_attributes is not None
            else None
        ),
    )


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the NL-Flex plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


def test_resource_group_nlflex_compliant_valid() -> None:
    """Test that a fully NL-Flex compliant resource group is accepted."""
    resource_group = _create_resource_group()

    assert resource_group.resource_group_name == "GROUP-0001"


def test_missing_group_id_target() -> None:
    """Test that a resource group without its own Group-ID in targets raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource group targets must include the Group-ID."),
    ):
        _ = _create_resource_group(targets=())


def test_group_id_target_mismatch() -> None:
    """Test that targets not containing the resource group's own Group-ID raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource group targets must include the Group-ID."),
    ):
        _ = _create_resource_group(targets=("OTHER-GROUP",))


def test_missing_dso_id_attribute() -> None:
    """Test that a resource group without a DSO_ID attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The resource group must have a DSO_ID attribute.")):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_invalid_dso_id_attribute_format() -> None:
    """Test that a DSO_ID attribute that is not a DSO identifier raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The DSO_ID attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA')."),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("ElaadNL",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_missing_service_provider_id_attribute() -> None:
    """Test that a resource group without a SERVICE_PROVIDER_ID attribute raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource group must have a SERVICE_PROVIDER_ID attribute."),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_invalid_service_provider_id_attribute_format() -> None:
    """Test that a SERVICE_PROVIDER_ID attribute that is not a SP identifier raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "The SERVICE_PROVIDER_ID attribute must be formatted as a Service Provider identifier (e.g. 'SP-ZON').",
        ),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("ElaadNL",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_missing_congestion_point_id_attribute() -> None:
    """Test that a resource group without a CONGESTION_POINT_ID attribute raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource group must have a CONGESTION_POINT_ID attribute."),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_empty_congestion_point_id_attribute_value() -> None:
    """Test that an empty CONGESTION_POINT_ID attribute value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The CONGESTION_POINT_ID attribute value may not be empty."),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("",)),
                Attribute(type="MAX_DURATION", values=("PT4H",)),
            ),
        )


def test_missing_max_duration_attribute() -> None:
    """Test that a resource group without a MAX_DURATION attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The resource group must have a MAX_DURATION attribute.")):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
            ),
        )


def test_invalid_max_duration_attribute_value() -> None:
    """Test that a MAX_DURATION attribute value outside of PT2H, PT4H, PT6H raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The MAX_DURATION attribute must be equal to one of PT2H, PT4H or PT6H."),
    ):
        _ = _create_resource_group(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="SERVICE_PROVIDER_ID", values=("SP-ELAAD",)),
                Attribute(type="CONGESTION_POINT_ID", values=("CA-0001",)),
                Attribute(type="MAX_DURATION", values=("PT8H",)),
            ),
        )


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the ResourceGroup validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewResourceGroup)
    assert len(validators) == 1

    valid_group = _create_resource_group()
    assert valid_group.resource_group_name == "GROUP-0001"

    with pytest.raises(ValidationError) as exc_info:
        _create_resource_group(targets=(), attributes=())

    errors = exc_info.value.errors()
    assert len(errors) == 5  # targets, DSO_ID, SERVICE_PROVIDER_ID, CONGESTION_POINT_ID, MAX_DURATION

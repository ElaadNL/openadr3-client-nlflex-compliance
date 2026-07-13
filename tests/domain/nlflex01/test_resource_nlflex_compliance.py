# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re
from typing import Any

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client._models.common.ven_resource_attribute_type import VenResourceAttributeType
from openadr3_client.oadr310.models.resource.resource import NewResource, NewResourceBlRequest, NewResourceVenRequest
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

_UNSET: Any = object()


def _default_valid_targets(resource_name: str = "ASSET-0001") -> tuple[str, ...]:
    """Helper function to create default targets that are NL-Flex compliant."""
    return (resource_name,)


def _default_valid_attributes() -> tuple[Attribute, ...]:
    """Helper function to create default attributes that are NL-Flex compliant."""
    return (
        Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
        Attribute(type="EAN", values=("871685900000000123",)),
        Attribute(type="FLEX_TYPE", values=("EVSE",)),
    )


def _create_resource(
    resource_name: str = "ASSET-0001",
    ven_id: str = "ven-1",
    targets: tuple[str, ...] | None = _UNSET,
    attributes: tuple[Attribute, ...] | None = _UNSET,
) -> NewResourceBlRequest:
    """
    Helper function to create a BL-submitted resource with the specified values.

    A BL-submitted resource is used by default since only the BL variant carries a targets
    field (see Section 11.2, "Resource" of the NL-Flex specification: targets are assigned by
    the BL, not the registering VEN). Any argument left unset defaults to a NL-Flex compliant
    value. Passing ``None`` explicitly is preserved, to allow testing the absence of a field.
    """
    resolved_targets = _default_valid_targets(resource_name) if targets is _UNSET else targets
    resolved_attributes = _default_valid_attributes() if attributes is _UNSET else attributes
    return NewResourceBlRequest(
        resource_name=resource_name,
        venID=ven_id,
        clientID="client-1",
        targets=resolved_targets,
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


def test_resource_nlflex_compliant_valid() -> None:
    """Test that a fully NL-Flex compliant resource is accepted."""
    resource = _create_resource()

    assert resource.resource_name == "ASSET-0001"


def test_missing_resource_name_target() -> None:
    """Test that a resource without its own Asset-ID in targets raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource targets must include its own Asset-ID."),
    ):
        _ = _create_resource(targets=())


def test_resource_name_target_mismatch() -> None:
    """Test that targets not containing the resource's own name raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The resource targets must include its own Asset-ID."),
    ):
        _ = _create_resource(targets=("OTHER-ASSET",))


def test_ven_submitted_resource_has_no_targets_field() -> None:
    """
    Test that a VEN-submitted resource, which has no targets field at all, is valid.

    Targets can only be assigned by a BL client (see Section 11.2, "Resource" of the NL-Flex
    specification), so there is nothing to validate on a VEN-submitted resource.
    """
    resource = NewResourceVenRequest(
        resource_name="ASSET-0001",
        venID="ven-1",
        attributes=ValuesMap[VenResourceAttributeType, Attribute](_default_valid_attributes()),
    )

    assert not hasattr(resource, "targets")


def test_missing_dso_id_attribute() -> None:
    """Test that a resource without a DSO_ID attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The resource must have a DSO_ID attribute.")):
        _ = _create_resource(
            attributes=(
                Attribute(type="EAN", values=("871685900000000123",)),
                Attribute(type="FLEX_TYPE", values=("EVSE",)),
            ),
        )


def test_invalid_dso_id_attribute_format() -> None:
    """Test that a DSO_ID attribute that is not a DSO identifier raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The DSO_ID attribute must be formatted as a DSO identifier (e.g. 'DSB-LIA')."),
    ):
        _ = _create_resource(
            attributes=(
                Attribute(type="DSO_ID", values=("ElaadNL",)),
                Attribute(type="EAN", values=("871685900000000123",)),
                Attribute(type="FLEX_TYPE", values=("EVSE",)),
            ),
        )


def test_missing_ean_attribute() -> None:
    """Test that a resource without an EAN attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The resource must have an EAN attribute.")):
        _ = _create_resource(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="FLEX_TYPE", values=("EVSE",)),
            ),
        )


def test_invalid_ean_attribute_format() -> None:
    """Test that an EAN attribute that is not an EAN18 value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The EAN attribute must be the EAN18 of the PCC the asset is connected to."),
    ):
        _ = _create_resource(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="EAN", values=("not-an-ean",)),
                Attribute(type="FLEX_TYPE", values=("EVSE",)),
            ),
        )


def test_missing_flex_type_attribute() -> None:
    """Test that a resource without a FLEX_TYPE attribute raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The resource must have a FLEX_TYPE attribute.")):
        _ = _create_resource(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="EAN", values=("871685900000000123",)),
            ),
        )


def test_invalid_flex_type_attribute_value() -> None:
    """Test that a FLEX_TYPE attribute with an unknown flex type raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The FLEX_TYPE attribute must be one of the flex type IDs in Table 3, 'Flex types'."),
    ):
        _ = _create_resource(
            attributes=(
                Attribute(type="DSO_ID", values=("DSB-ELAAD",)),
                Attribute(type="EAN", values=("871685900000000123",)),
                Attribute(type="FLEX_TYPE", values=("UNKNOWN",)),
            ),
        )


def test_registration_status_not_required() -> None:
    """Test that a resource without a REGISTRATION_STATUS attribute is valid (it is set later by the BL)."""
    _ = _create_resource()


def test_invalid_registration_status_value() -> None:
    """Test that an invalid REGISTRATION_STATUS attribute value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The REGISTRATION_STATUS attribute must be one of the registration statuses in Table 1."),
    ):
        _ = _create_resource(
            attributes=(
                *_default_valid_attributes(),
                Attribute(type="REGISTRATION_STATUS", values=("UNKNOWN",)),
            ),
        )


def test_registration_status_enrolled_valid() -> None:
    """Test that a REGISTRATION_STATUS of ENROLLED without a REJECTED_REASON is valid."""
    _ = _create_resource(
        attributes=(
            *_default_valid_attributes(),
            Attribute(type="REGISTRATION_STATUS", values=("ENROLLED",)),
        ),
    )


def test_registration_status_rejected_missing_reason() -> None:
    """Test that a REGISTRATION_STATUS of REJECTED without a REJECTED_REASON raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "The resource must have a REJECTED_REASON attribute when REGISTRATION_STATUS is REJECTED.",
        ),
    ):
        _ = _create_resource(
            attributes=(
                *_default_valid_attributes(),
                Attribute(type="REGISTRATION_STATUS", values=("REJECTED",)),
            ),
        )


def test_registration_status_rejected_invalid_reason() -> None:
    """Test that an invalid REJECTED_REASON value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The REJECTED_REASON attribute must be one of the rejection reasons in Table 2."),
    ):
        _ = _create_resource(
            attributes=(
                *_default_valid_attributes(),
                Attribute(type="REGISTRATION_STATUS", values=("REJECTED",)),
                Attribute(type="REJECTED_REASON", values=("UNKNOWN",)),
            ),
        )


def test_registration_status_rejected_valid_reason() -> None:
    """Test that a valid REJECTED_REASON alongside a REJECTED status is accepted."""
    _ = _create_resource(
        attributes=(
            *_default_valid_attributes(),
            Attribute(type="REGISTRATION_STATUS", values=("REJECTED",)),
            Attribute(type="REJECTED_REASON", values=("WRONG_EAN",)),
        ),
    )


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the Resource validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewResource)
    assert len(validators) == 1

    valid_resource = _create_resource()
    assert valid_resource.resource_name == "ASSET-0001"

    with pytest.raises(ValidationError) as exc_info:
        _create_resource(targets=(), attributes=())

    errors = exc_info.value.errors()
    assert len(errors) == 4  # targets, DSO_ID, EAN, FLEX_TYPE

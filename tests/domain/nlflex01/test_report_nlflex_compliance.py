# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re
from datetime import UTC, datetime
from typing import Any

import pytest
from openadr3_client._models.common.interval import Interval
from openadr3_client.oadr310.models.report.report import ExistingReport, NewReport, ReportResource
from openadr3_client.oadr310.models.report.report_payload import ReportPayload, ReportPayloadType
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

_UNSET: Any = object()

RESOURCE_GROUP_TARGET = ReportPayloadType("RESOURCE_GROUP_TARGET")
REGISTRATION_REQUEST = ReportPayloadType("REGISTRATION_REQUEST")
DE_REGISTRATION_REQUEST = ReportPayloadType("DE_REGISTRATION_REQUEST")
OPERATIONAL_STATUS = ReportPayloadType("OPERATIONAL_STATUS")
FLEX_DELTA = ReportPayloadType("FLEX_DELTA")


def _registration_resources(
    group_id: str = "GROUP-0001",
    asset_ids: tuple[str, ...] = ("a1a1a1a1-0001-4001-8001-000000000001",),
    registration_payload_type: ReportPayloadType = REGISTRATION_REQUEST,
) -> tuple[ReportResource, ...]:
    """Helper function to create a default AGGREGATED_REPORT resource for a registration report."""
    return (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(
                        ReportPayload(type=RESOURCE_GROUP_TARGET, values=(group_id,)),
                        ReportPayload(type=registration_payload_type, values=asset_ids),
                    ),
                ),
            ),
        ),
    )


def _create_registration_report(
    resources: tuple[ReportResource, ...] = _UNSET,
) -> NewReport:
    """Helper function to create a RESOURCE_REGISTRATION report with the specified resources."""
    return NewReport(
        eventID="test-event",
        client_name="SP-ELAAD",
        report_name="RESOURCE_REGISTRATION",
        resources=_registration_resources() if resources is _UNSET else resources,
    )


def _flexibility_resources(
    values: tuple[float, ...] = (-12.5,),
    payload_type: ReportPayloadType = FLEX_DELTA,
    interval_count: int = 1,
) -> tuple[ReportResource, ...]:
    """Helper function to create a default AGGREGATED_REPORT resource for a flexibility report."""
    return (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=tuple(
                Interval(
                    id=i,
                    interval_period=None,
                    payloads=(ReportPayload(type=payload_type, values=values),),
                )
                for i in range(interval_count)
            ),
        ),
    )


def _create_flexibility_report(
    resources: tuple[ReportResource, ...] = _UNSET,
) -> NewReport:
    """Helper function to create a flexibility (FLEX_DELTA) report with the specified resources."""
    return NewReport(
        eventID="test-event",
        client_name="SP-ELAAD",
        resources=_flexibility_resources() if resources is _UNSET else resources,
    )


def _operational_status_resources(
    resource_name: str = "a1a1a1a1-0001-4001-8001-000000000001",
    values: tuple[str, ...] = ("NORMAL",),
) -> tuple[ReportResource, ...]:
    """Helper function to create a default resource entry for an operational status report."""
    return (
        ReportResource(
            resource_name=resource_name,
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=values),),
                ),
            ),
        ),
    )


def _create_operational_status_report(
    resources: tuple[ReportResource, ...] = _UNSET,
) -> NewReport:
    """Helper function to create an OPERATIONAL_STATUS report with the specified resources."""
    return NewReport(
        eventID="test-event",
        client_name="SP-ELAAD",
        report_name="OPERATIONAL_STATUS",
        resources=_operational_status_resources() if resources is _UNSET else resources,
    )


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the NL-Flex plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


# --- Resource group registration/deregistration reports (Section 11.6.1) ---


def test_registration_report_valid() -> None:
    """Test that a fully NL-Flex compliant registration report is accepted."""
    report = _create_registration_report()

    assert report.report_name == "RESOURCE_REGISTRATION"


def test_deregistration_report_valid() -> None:
    """Test that a fully NL-Flex compliant deregistration report is accepted."""
    _ = _create_registration_report(
        resources=_registration_resources(registration_payload_type=DE_REGISTRATION_REQUEST),
    )


def test_registration_report_wrong_resource_name() -> None:
    """Test that a registration report resource without resourceName AGGREGATED_REPORT raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The report must contain exactly one resource entry with resourceName AGGREGATED_REPORT."),
    ):
        _ = _create_registration_report(
            resources=(
                ReportResource(
                    resource_name="OTHER",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001",)),),
                        ),
                    ),
                ),
            ),
        )


def test_registration_report_multiple_resources() -> None:
    """Test that a registration report with more than one resource entry raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The report must contain exactly one resource entry with resourceName AGGREGATED_REPORT."),
    ):
        _ = _create_registration_report(resources=_registration_resources() + _registration_resources())


def test_registration_report_multiple_intervals() -> None:
    """Test that a registration report with more than one interval raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The report resource must contain exactly one interval with id 0."),
    ):
        _ = _create_registration_report(
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001",)),),
                        ),
                        Interval(
                            id=1,
                            interval_period=None,
                            payloads=(ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001",)),),
                        ),
                    ),
                ),
            ),
        )


def test_registration_report_missing_registration_payload() -> None:
    """Test that a registration report interval missing the registration payload raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "The report interval must contain exactly two payloads: one RESOURCE_GROUP_TARGET and one "
            "REGISTRATION_REQUEST or DE_REGISTRATION_REQUEST.",
        ),
    ):
        _ = _create_registration_report(
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001",)),),
                        ),
                    ),
                ),
            ),
        )


def test_registration_report_extra_payload() -> None:
    """Test that a registration report interval with an unexpected extra payload raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "The report interval must contain exactly two payloads: one RESOURCE_GROUP_TARGET and one "
            "REGISTRATION_REQUEST or DE_REGISTRATION_REQUEST.",
        ),
    ):
        _ = _create_registration_report(
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(
                                ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001",)),
                                ReportPayload(type=REGISTRATION_REQUEST, values=("asset-1",)),
                                ReportPayload(type=REGISTRATION_REQUEST, values=("asset-2",)),
                            ),
                        ),
                    ),
                ),
            ),
        )


def test_registration_report_resource_group_target_multiple_values() -> None:
    """Test that a RESOURCE_GROUP_TARGET payload with more than one value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The RESOURCE_GROUP_TARGET payload must contain exactly one value, the Group-ID."),
    ):
        _ = _create_registration_report(
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(
                                ReportPayload(type=RESOURCE_GROUP_TARGET, values=("GROUP-0001", "GROUP-0002")),
                                ReportPayload(type=REGISTRATION_REQUEST, values=("asset-1",)),
                            ),
                        ),
                    ),
                ),
            ),
        )


def test_registration_report_multiple_resource_ids_valid() -> None:
    """Test that a REGISTRATION_REQUEST payload listing multiple resource IDs is accepted."""
    _ = _create_registration_report(
        resources=_registration_resources(asset_ids=("asset-1", "asset-2", "asset-3")),
    )


# --- Flexibility reports (Section 11.6.2) ---


def test_flexibility_report_valid() -> None:
    """Test that a fully NL-Flex compliant flexibility report is accepted."""
    report = _create_flexibility_report()

    assert report.report_name is None


def test_flexibility_report_wrong_resource_name() -> None:
    """Test that a flexibility report resource without resourceName AGGREGATED_REPORT raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The report must contain exactly one resource entry with resourceName AGGREGATED_REPORT."),
    ):
        _ = _create_flexibility_report(
            resources=(
                ReportResource(
                    resource_name="OTHER",
                    intervals=(
                        Interval(
                            id=0, interval_period=None, payloads=(ReportPayload(type=FLEX_DELTA, values=(-1.0,)),)
                        ),
                    ),
                ),
            ),
        )


def test_flexibility_report_no_intervals() -> None:
    """Test that a flexibility report resource with no intervals raises an error."""
    with pytest.raises(ValueError, match=re.escape("ReportResource must contain at least one interval.")):
        _ = _create_flexibility_report(
            resources=(ReportResource(resource_name="AGGREGATED_REPORT", intervals=()),),
        )


def test_flexibility_report_multiple_intervals_valid() -> None:
    """Test that a flexibility report with multiple reporting intervals is accepted."""
    _ = _create_flexibility_report(resources=_flexibility_resources(interval_count=3))


def test_flexibility_report_wrong_payload_type() -> None:
    """Test that a flexibility report interval without a FLEX_DELTA payload raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("Each report interval must carry exactly one FLEX_DELTA payload."),
    ):
        _ = _create_flexibility_report(
            resources=_flexibility_resources(payload_type=ReportPayloadType("BASELINE")),
        )


def test_flexibility_report_multiple_payloads() -> None:
    """Test that a flexibility report interval with more than one payload raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("Each report interval must carry exactly one FLEX_DELTA payload."),
    ):
        _ = _create_flexibility_report(
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(
                                ReportPayload(type=FLEX_DELTA, values=(-1.0,)),
                                ReportPayload(type=FLEX_DELTA, values=(-2.0,)),
                            ),
                        ),
                    ),
                ),
            ),
        )


def test_flexibility_report_positive_value_rejected() -> None:
    """Test that a positive FLEX_DELTA value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The FLEX_DELTA payload values must be zero or negative."),
    ):
        _ = _create_flexibility_report(resources=_flexibility_resources(values=(12.5,)))


def test_flexibility_report_zero_value_valid() -> None:
    """Test that a FLEX_DELTA value of exactly zero is accepted."""
    _ = _create_flexibility_report(resources=_flexibility_resources(values=(0.0,)))


# --- Operational status reports (Section 11.6.3) ---


def test_operational_status_report_valid() -> None:
    """Test that a fully NL-Flex compliant operational status report is accepted."""
    report = _create_operational_status_report()

    assert report.report_name == "OPERATIONAL_STATUS"


def test_operational_status_report_no_resources() -> None:
    """Test that a new operational status report with no resources raises an error."""
    with pytest.raises(ValueError, match=re.escape("NewReport must contain at least one resource.")):
        _ = _create_operational_status_report(resources=())


def test_existing_operational_status_report_no_resources() -> None:
    """
    Test that our own empty-resources check is exercised for report types other than NewReport.

    Unlike NewReport, ExistingReport does not itself enforce a minimum of one resource, so this
    is where our plugin's own check (rather than the library's field validator) is exercised.
    """
    with pytest.raises(
        ValidationError,
        match=re.escape("The report must contain one resource entry per resource being reported on."),
    ):
        _ = ExistingReport(
            id="report-1",
            created_date_time=datetime(2026, 1, 1, tzinfo=UTC),
            modification_date_time=datetime(2026, 1, 1, tzinfo=UTC),
            eventID="test-event",
            clientID="test-client",
            client_name="SP-ELAAD",
            report_name="OPERATIONAL_STATUS",
            resources=(),
        )


def test_operational_status_report_interval_not_starting_at_zero() -> None:
    """Test that an operational status report resource whose first interval id is not 0 raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The report resource must contain at least one interval, with ids starting at 0."),
    ):
        _ = _create_operational_status_report(
            resources=(
                ReportResource(
                    resource_name="a1a1a1a1-0001-4001-8001-000000000001",
                    intervals=(
                        Interval(
                            id=1,
                            interval_period=None,
                            payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=("NORMAL",)),),
                        ),
                    ),
                ),
            ),
        )


def test_operational_status_report_wrong_payload_type() -> None:
    """Test that an operational status report interval without an OPERATIONAL_STATUS payload raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("Each report interval must carry exactly one OPERATIONAL_STATUS payload."),
    ):
        _ = _create_operational_status_report(
            resources=(
                ReportResource(
                    resource_name="a1a1a1a1-0001-4001-8001-000000000001",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(ReportPayload(type=ReportPayloadType("BASELINE"), values=("NORMAL",)),),
                        ),
                    ),
                ),
            ),
        )


def test_operational_status_report_invalid_value() -> None:
    """Test that an operational status report with an unknown status value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The OPERATIONAL_STATUS payload must contain exactly one value from Table 7"),
    ):
        _ = _create_operational_status_report(resources=_operational_status_resources(values=("UNKNOWN",)))


def test_operational_status_report_multiple_values() -> None:
    """Test that an operational status report with more than one value raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The OPERATIONAL_STATUS payload must contain exactly one value from Table 7"),
    ):
        _ = _create_operational_status_report(resources=_operational_status_resources(values=("NORMAL", "ERROR")))


def test_operational_status_report_multiple_resources_valid() -> None:
    """Test that an operational status report with multiple resource entries is accepted."""
    _ = _create_operational_status_report(
        resources=_operational_status_resources(resource_name="asset-1")
        + _operational_status_resources(resource_name="asset-2"),
    )


# --- Plugin integration ---


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the Report validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewReport)
    assert len(validators) == 1

    valid_report = _create_flexibility_report()
    assert valid_report.event_id == "test-event"

    with pytest.raises(ValidationError) as exc_info:
        _create_flexibility_report(resources=_flexibility_resources(values=(12.5,)))

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0].get("msg") == "The FLEX_DELTA payload values must be zero or negative."

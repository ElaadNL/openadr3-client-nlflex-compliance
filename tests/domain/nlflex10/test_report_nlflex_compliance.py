# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from openadr3_client._models.common.interval import Interval
from openadr3_client._models.common.interval_period import IntervalPeriod
from openadr3_client.oadr310.models.event.event_payload import EventPayload, EventPayloadType
from openadr3_client.oadr310.models.report.report import NewReport, ReportResource
from openadr3_client.oadr310.models.report.report_payload import ReportPayload, ReportPayloadType

from openadr3_client_nlflex_compliance.nlflex10.report_nlflex_compliant import (
    ReportKind,
    report_kind,
    single_aggregated_report_resource,
    validate_flex_acknowledgment_report_compliant,
    validate_flex_delivery_report_compliant,
    validate_flex_delta_report_compliant,
    validate_operational_status_report_compliant,
    validate_registration_report_compliant,
    validate_report_nlflex_compliant,
)

_UNSET: Any = object()

SERVICE_PROVIDER_EAN13 = "8712345678906"
GROUP_OBJECT_ID = "60000000-0000-4000-8000-000000000000"
ASSET_OBJECT_ID = "a1a1a1a1-0001-4001-8001-000000000001"


def _report(*, report_name: str | None, resources: tuple[ReportResource, ...]) -> NewReport:
    """Helper function to create a report with a compliant clientName."""
    return NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name=SERVICE_PROVIDER_EAN13,
        report_name=report_name,
        resources=resources,
    )


def _aggregated(*payloads: ReportPayload) -> tuple[ReportResource, ...]:
    """Helper function to wrap payloads in a single aggregated resource with one interval."""
    return (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(Interval(id=0, interval_period=None, payloads=payloads),),
        ),
    )


def _registration_report() -> NewReport:
    """Helper function to create the compliant registration report of the specification."""
    return _report(
        report_name="RESOURCE_REGISTRATION",
        resources=_aggregated(
            ReportPayload(type=ReportPayloadType("RESOURCE_GROUP_ID"), values=(GROUP_OBJECT_ID,)),
            ReportPayload(type=ReportPayloadType("REGISTRATION_REQUEST"), values=(ASSET_OBJECT_ID,)),
        ),
    )


def _flex_delta_report() -> NewReport:
    """Helper function to create the compliant flex delta report of the specification."""
    return _report(
        report_name=None,
        resources=_aggregated(
            ReportPayload(type=ReportPayloadType("ACTIVE_FLEX_DELTA"), values=(-300,)),
            ReportPayload(type=ReportPayloadType("RESERVED_FLEX_DELTA"), values=(-100,)),
        ),
    )


def _acknowledgment_report() -> NewReport:
    """Helper function to create the compliant acknowledgment report of the specification."""
    return _report(
        report_name=None,
        resources=_aggregated(ReportPayload(type=ReportPayloadType("ACK"), values=(True,))),
    )


def _delivery_report() -> NewReport:
    """Helper function to create a compliant delivery report for one PT1H interval."""
    return _report(
        report_name=None,
        resources=(
            ReportResource(
                resource_name="AGGREGATED_REPORT",
                intervals=(
                    Interval(
                        id=0,
                        interval_period=IntervalPeriod(
                            start=datetime(2026, 1, 2, 16, 0, 0, tzinfo=UTC), duration=timedelta(hours=1)
                        ),
                        payloads=(ReportPayload(type=ReportPayloadType("DELIVERED_FLEX"), values=(0, 0, 0, 0)),),
                    ),
                ),
            ),
        ),
    )


def _operational_status_report() -> NewReport:
    """Helper function to create the compliant operational status report of the specification."""
    return _report(
        report_name="OPERATIONAL_STATUS",
        resources=(
            ReportResource(
                resource_name="ASSET-0001",
                intervals=(
                    Interval(
                        id=0,
                        interval_period=None,
                        payloads=(ReportPayload(type=ReportPayloadType("OPERATIONAL_STATUS"), values=("PENDING",)),),
                    ),
                ),
            ),
        ),
    )


def test_the_registration_report_is_recognised() -> None:
    """Discriminated by payload type."""
    assert report_kind(_registration_report()) is ReportKind.RESOURCE_REGISTRATION


def test_the_operational_status_report_is_recognised() -> None:
    """Discriminated by payload type."""
    assert report_kind(_operational_status_report()) is ReportKind.OPERATIONAL_STATUS


def test_the_flex_delta_report_is_recognised() -> None:
    """Discriminated by payload type."""
    assert report_kind(_flex_delta_report()) is ReportKind.FLEX_DELTA


def test_the_acknowledgment_report_is_recognised() -> None:
    """Discriminated by payload type."""
    assert report_kind(_acknowledgment_report()) is ReportKind.FLEX_ACKNOWLEDGMENT


def test_the_delivery_report_is_recognised() -> None:
    """Discriminated by payload type."""
    assert report_kind(_delivery_report()) is ReportKind.FLEX_DELIVERY


def test_every_compliant_report_shape_validates_clean() -> None:
    """Each of the five shapes routes to its own validator and passes it."""
    for report in (
        _registration_report(),
        _flex_delta_report(),
        _acknowledgment_report(),
        _delivery_report(),
        _operational_status_report(),
    ):
        assert validate_report_nlflex_compliant(report) is None


def test_an_acknowledgment_is_not_validated_as_a_flex_delta_report() -> None:
    """The defect this discriminator closes: the draft routed anything unnamed into flex delta."""
    errors = validate_report_nlflex_compliant(_acknowledgment_report())

    assert errors is None


def test_a_broken_acknowledgment_is_told_about_acknowledgment_rules() -> None:
    """An ACK payload that is not true is an ACK error, not a flex delta error."""
    report = _report(
        report_name=None,
        resources=_aggregated(ReportPayload(type=ReportPayloadType("ACK"), values=(False,))),
    )

    errors = validate_report_nlflex_compliant(report)

    assert errors is not None
    assert any("must be true" in str(error["type"]) for error in errors)
    assert not any("FLEX_DELTA" in str(error["type"]) for error in errors)


def test_an_unrecognised_report_shape_is_reported_as_such() -> None:
    """A report carrying a foreign payload type is not silently validated as some other shape."""
    report = _report(
        report_name=None,
        resources=_aggregated(ReportPayload(type=ReportPayloadType.READING, values=(10,))),
    )

    assert report_kind(report) is None

    errors = validate_report_nlflex_compliant(report)
    assert errors is not None
    assert any("does not match any report shape" in str(error["type"]) for error in errors)


def test_client_name_must_be_the_service_provider_ean13() -> None:
    """The clientName MUST be the VEN's venName, which MUST be the Service Provider EAN13."""
    report = NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name="elaad-client",
        report_name=None,
        resources=_aggregated(ReportPayload(type=ReportPayloadType("ACK"), values=(True,))),
    )

    errors = validate_report_nlflex_compliant(report)

    assert errors is not None
    assert any("clientName" in str(error["type"]) for error in errors)


def test_the_client_name_is_checked_on_every_shape() -> None:
    """It is a rule of the VEN, so it holds regardless of which report is being sent."""
    report = NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name="8712345678900",
        report_name="OPERATIONAL_STATUS",
        resources=_operational_status_report().resources,
    )

    errors = validate_report_nlflex_compliant(report)

    assert errors is not None
    assert any("clientName" in str(error["type"]) for error in errors)


def test_an_unrecognised_shape_still_reports_a_bad_client_name() -> None:
    """Both errors are collected: the shape is unknown and the clientName is wrong."""
    report = NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name="elaad-client",
        report_name=None,
        resources=_aggregated(ReportPayload(type=ReportPayloadType.READING, values=(10,))),
    )

    errors = validate_report_nlflex_compliant(report)

    assert errors is not None
    assert len(errors) == 2


# --- Aggregated report resource helper -----------------------------------------------------------

ACK = ReportPayloadType("ACK")


def _aggregated_resource(resource_name: str) -> ReportResource:
    """Helper function to create a report resource carrying one arbitrary payload."""
    return ReportResource(
        resource_name=resource_name,
        intervals=(Interval(id=0, interval_period=None, payloads=(ReportPayload(type=ACK, values=(True,)),)),),
    )


def _aggregated_report(*resources: ReportResource) -> NewReport:
    """Helper function to create a report with the given resources."""
    return NewReport(eventID="f0000000-0000-4000-8000-000000000000", client_name="8712345678906", resources=resources)


def test_a_single_aggregated_resource_is_returned() -> None:
    """The happy path hands the resource back so the caller can go on validating its intervals."""
    errors, resource = single_aggregated_report_resource(
        _aggregated_report(_aggregated_resource("AGGREGATED_REPORT")), "boom"
    )

    assert errors == []
    assert resource is not None
    assert resource.resource_name == "AGGREGATED_REPORT"


def test_a_differently_named_resource_is_rejected() -> None:
    """A report on the group as a whole is never reported per asset."""
    errors, resource = single_aggregated_report_resource(_aggregated_report(_aggregated_resource("ASSET-0001")), "boom")

    assert resource is None
    assert len(errors) == 1
    assert "boom" in str(errors[0]["type"])


def test_more_than_one_resource_is_rejected() -> None:
    """Exactly one entry, so two aggregated entries are as wrong as a per-asset one."""
    errors, resource = single_aggregated_report_resource(
        _aggregated_report(_aggregated_resource("AGGREGATED_REPORT"), _aggregated_resource("AGGREGATED_REPORT")), "boom"
    )

    assert resource is None
    assert len(errors) == 1


# --- Registration report -------------------------------------------------------------------------

RESOURCE_GROUP_ID = ReportPayloadType("RESOURCE_GROUP_ID")
REGISTRATION_REQUEST = ReportPayloadType("REGISTRATION_REQUEST")
DE_REGISTRATION_REQUEST = ReportPayloadType("DE_REGISTRATION_REQUEST")

FIRST_ASSET_ID = "a1a1a1a1-0001-4001-8001-000000000001"
SECOND_ASSET_ID = "a1a1a1a1-0002-4002-8002-000000000002"


def _default_valid_registration_payloads() -> tuple[ReportPayload, ...]:
    """Helper function to create the payloads of the specification's registration example."""
    return (
        ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID,)),
        ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID, SECOND_ASSET_ID)),
    )


def _create_registration_report(
    report_name: str | None = _UNSET,
    resources: tuple[ReportResource, ...] = _UNSET,
    payloads: tuple[ReportPayload, ...] = _UNSET,
) -> NewReport:
    """
    Helper function to create a report with the specified values.

    Any argument left unset defaults to a compliant registration report value. Passing ``payloads``
    rebuilds the single aggregated resource around them; passing ``resources`` overrides that.
    """
    carried = _default_valid_registration_payloads() if payloads is _UNSET else payloads
    return NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        report_name="RESOURCE_REGISTRATION" if report_name is _UNSET else report_name,
        resources=(
            (
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(Interval(id=0, interval_period=None, payloads=carried),),
                ),
            )
            if resources is _UNSET
            else resources
        ),
    )


def test_registration_report_valid() -> None:
    """A registration report matching the specification's example is compliant."""
    assert validate_registration_report_compliant(_create_registration_report()) is None


def test_deregistration_report_valid() -> None:
    """Deregistration uses the same structure, with the other request payload."""
    payloads = (
        ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID,)),
        ReportPayload(type=DE_REGISTRATION_REQUEST, values=(FIRST_ASSET_ID, SECOND_ASSET_ID)),
    )

    assert validate_registration_report_compliant(_create_registration_report(payloads=payloads)) is None


def test_registration_report_name_is_optional() -> None:
    """The reportName is optional: any value, or none at all, is accepted and plays no part in routing."""
    for report_name in (None, "REGISTRATION"):
        report = _create_registration_report(report_name=report_name)

        assert report_kind(report) is ReportKind.RESOURCE_REGISTRATION
        assert validate_report_nlflex_compliant(report) is None


def test_registration_a_per_asset_resource_entry_is_rejected() -> None:
    """The registration report is aggregated over the group, not reported per asset."""
    report = _create_registration_report(
        resources=(
            ReportResource(
                resource_name="ASSET-0001",
                intervals=(Interval(id=0, interval_period=None, payloads=_default_valid_registration_payloads()),),
            ),
        )
    )

    errors = validate_registration_report_compliant(report)

    assert errors is not None
    assert any("'AGGREGATED_REPORT'" in str(error["type"]) for error in errors)


def test_registration_exactly_one_interval_with_id_zero() -> None:
    """The report carries one interval, identified as 0."""
    report = _create_registration_report(
        resources=(
            ReportResource(
                resource_name="AGGREGATED_REPORT",
                intervals=(Interval(id=1, interval_period=None, payloads=_default_valid_registration_payloads()),),
            ),
        )
    )

    errors = validate_registration_report_compliant(report)

    assert errors is not None
    assert any("exactly one interval with an id of 0" in str(error["type"]) for error in errors)


def test_the_group_payload_is_required() -> None:
    """Without it the BL does not know which group the assets are being registered into."""
    payloads = (ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID,)),)

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_the_draft_group_payload_type_is_rejected() -> None:
    """The v0.1 draft named this payload RESOURCE_GROUP_TARGET. v1.0.0 renamed it."""
    payloads = (
        ReportPayload(type=ReportPayloadType("RESOURCE_GROUP_TARGET"), values=(GROUP_OBJECT_ID,)),
        ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID,)),
    )

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_a_request_payload_is_required() -> None:
    """A report that names a group but asks for nothing does nothing."""
    payloads = (ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID,)),)

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_both_request_payloads_at_once_are_rejected() -> None:
    """One operation per report: register or deregister, not both."""
    payloads = (
        ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID,)),
        ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID,)),
        ReportPayload(type=DE_REGISTRATION_REQUEST, values=(SECOND_ASSET_ID,)),
    )

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_the_group_payload_carries_exactly_one_value() -> None:
    """A report registers into one resource group."""
    payloads = (
        ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID, "60000000-0000-4000-8000-000000000001")),
        ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID,)),
    )

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("exactly one value" in str(error["type"]) for error in errors)


def test_the_group_payload_value_is_an_object_id() -> None:
    """RESOURCE_GROUP_ID carries the group's object ID, not its Group-ID."""
    payloads = (
        ReportPayload(type=RESOURCE_GROUP_ID, values=("GROUP-0001",)),
        ReportPayload(type=REGISTRATION_REQUEST, values=(FIRST_ASSET_ID,)),
    )

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("object ID of the resource group" in str(error["type"]) for error in errors)


def test_request_values_are_resource_ids() -> None:
    """The request lists resource IDs, not Asset-IDs."""
    payloads = (
        ReportPayload(type=RESOURCE_GROUP_ID, values=(GROUP_OBJECT_ID,)),
        ReportPayload(type=REGISTRATION_REQUEST, values=("ASSET-0001",)),
    )

    errors = validate_registration_report_compliant(_create_registration_report(payloads=payloads))

    assert errors is not None
    assert any("resource IDs" in str(error["type"]) for error in errors)


def test_an_interval_period_on_the_interval_is_ignored() -> None:
    """The profile places no intervalPeriod rule on this report, so one is not an error."""
    report = _create_registration_report(
        resources=(
            ReportResource(
                resource_name="AGGREGATED_REPORT",
                intervals=(
                    Interval(
                        id=0,
                        interval_period=IntervalPeriod(
                            start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1)
                        ),
                        payloads=_default_valid_registration_payloads(),
                    ),
                ),
            ),
        )
    )

    assert validate_registration_report_compliant(report) is None


# --- Flex delta report ----------------------------------------------------------------------

ACTIVE_FLEX_DELTA = ReportPayloadType("ACTIVE_FLEX_DELTA")
RESERVED_FLEX_DELTA = ReportPayloadType("RESERVED_FLEX_DELTA")


def _default_valid_flex_delta_payloads() -> tuple[ReportPayload, ...]:
    """Helper function to create the payloads of the specification's flex delta example."""
    return (
        ReportPayload(type=ACTIVE_FLEX_DELTA, values=(-300,)),
        ReportPayload(type=RESERVED_FLEX_DELTA, values=(-100,)),
    )


def _create_flex_delta_report(
    resources: tuple[ReportResource, ...] = _UNSET,
    payloads: tuple[ReportPayload, ...] = _UNSET,
) -> NewReport:
    """
    Helper function to create a report with the specified values.

    Any argument left unset defaults to a compliant flex delta report value.
    """
    carried = _default_valid_flex_delta_payloads() if payloads is _UNSET else payloads
    return NewReport(
        eventID="e0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        resources=(
            (
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(Interval(id=0, interval_period=None, payloads=carried),),
                ),
            )
            if resources is _UNSET
            else resources
        ),
    )


def test_flex_delta_report_valid() -> None:
    """A flex delta report matching the specification's example is compliant."""
    assert validate_flex_delta_report_compliant(_create_flex_delta_report()) is None


def test_offering_no_flexibility_is_valid() -> None:
    """An ACTIVE_FLEX_DELTA of 0 means no flexibility is offered, which is a legitimate answer."""
    payloads = (
        ReportPayload(type=ACTIVE_FLEX_DELTA, values=(0,)),
        ReportPayload(type=RESERVED_FLEX_DELTA, values=(0,)),
    )

    assert validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads)) is None


def test_flex_delta_a_per_asset_resource_entry_is_rejected() -> None:
    """Each reported value is a sum across the DER assets in the group."""
    report = _create_flex_delta_report(
        resources=(
            ReportResource(
                resource_name="ASSET-0001",
                intervals=(Interval(id=0, interval_period=None, payloads=_default_valid_flex_delta_payloads()),),
            ),
        )
    )

    errors = validate_flex_delta_report_compliant(report)

    assert errors is not None
    assert any("'AGGREGATED_REPORT'" in str(error["type"]) for error in errors)


def test_flex_delta_exactly_one_interval_with_id_zero() -> None:
    """The offer is one value pair, carried in one interval."""
    report = _create_flex_delta_report(
        resources=(
            ReportResource(
                resource_name="AGGREGATED_REPORT",
                intervals=(
                    Interval(id=0, interval_period=None, payloads=_default_valid_flex_delta_payloads()),
                    Interval(id=1, interval_period=None, payloads=_default_valid_flex_delta_payloads()),
                ),
            ),
        )
    )

    errors = validate_flex_delta_report_compliant(report)

    assert errors is not None
    assert any("exactly one interval with an id of 0" in str(error["type"]) for error in errors)


def test_the_draft_payload_type_is_rejected() -> None:
    """The v0.1 draft carried one FLEX_DELTA payload. v1.0.0 splits it in two."""
    payloads = (ReportPayload(type=ReportPayloadType("FLEX_DELTA"), values=(-300,)),)

    errors = validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_both_payloads_are_required_even_when_one_is_zero() -> None:
    """Both MUST be present even when one of them is zero."""
    payloads = (ReportPayload(type=ACTIVE_FLEX_DELTA, values=(-300,)),)

    errors = validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads))

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_a_positive_flex_delta_is_rejected() -> None:
    """A flex delta MUST be a double equal to or smaller than zero."""
    payloads = (
        ReportPayload(type=ACTIVE_FLEX_DELTA, values=(300,)),
        ReportPayload(type=RESERVED_FLEX_DELTA, values=(-100,)),
    )

    errors = validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads))

    assert errors is not None
    assert any("equal to or smaller than zero" in str(error["type"]) for error in errors)


def test_a_flex_delta_with_three_decimals_is_rejected() -> None:
    """A power value is a double with at most two decimal places."""
    payloads = (
        ReportPayload(type=ACTIVE_FLEX_DELTA, values=(-300.125,)),
        ReportPayload(type=RESERVED_FLEX_DELTA, values=(-100,)),
    )

    errors = validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads))

    assert errors is not None
    assert any("equal to or smaller than zero" in str(error["type"]) for error in errors)


def test_a_flex_delta_payload_carries_a_single_value() -> None:
    """The offer is a single current value, not a schedule."""
    payloads = (
        ReportPayload(type=ACTIVE_FLEX_DELTA, values=(-300, -200)),
        ReportPayload(type=RESERVED_FLEX_DELTA, values=(-100,)),
    )

    errors = validate_flex_delta_report_compliant(_create_flex_delta_report(payloads=payloads))

    assert errors is not None
    assert any("exactly one value" in str(error["type"]) for error in errors)


# --- Flexibility dispatch report: acknowledgment and delivery -----------------------------------

DELIVERED_FLEX = ReportPayloadType("DELIVERED_FLEX")
FLEX = EventPayloadType("FLEX")

PRE_DISPATCH_START = datetime(2026, 1, 2, 16, 0, 0, tzinfo=UTC)
DISPATCH_START = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)


def _acknowledgment_resources() -> tuple[ReportResource, ...]:
    """Helper function to create the single interval an acknowledgment report carries."""
    return (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(Interval(id=0, interval_period=None, payloads=(ReportPayload(type=ACK, values=(True,)),)),),
        ),
    )


def _create_acknowledgment_report(resources: tuple[ReportResource, ...] = _UNSET) -> NewReport:
    """Helper function to create an acknowledgment report with the specified resources."""
    return NewReport(
        eventID="f0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        resources=_acknowledgment_resources() if resources is _UNSET else resources,
    )


def _delivery_interval(
    interval_id: int,
    start: datetime,
    duration: timedelta,
    delivered_kw: float,
) -> Interval:
    """Helper function to create a delivery report interval with one value per 15 minutes."""
    quarters = duration // timedelta(minutes=15)
    return Interval(
        id=interval_id,
        interval_period=IntervalPeriod(start=start, duration=duration),
        payloads=(ReportPayload(type=DELIVERED_FLEX, values=tuple([delivered_kw] * quarters)),),
    )


def _delivery_resources(intervals: tuple[Interval, ...] = _UNSET) -> tuple[ReportResource, ...]:
    """Helper function to create the AGGREGATED_REPORT resource of a delivery report."""
    return (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(
                (
                    _delivery_interval(0, PRE_DISPATCH_START, timedelta(hours=1), 0),
                    _delivery_interval(1, DISPATCH_START, timedelta(hours=4), 200),
                )
                if intervals is _UNSET
                else intervals
            ),
        ),
    )


def _create_delivery_report(resources: tuple[ReportResource, ...] = _UNSET) -> NewReport:
    """Helper function to create a delivery report with the specified resources."""
    return NewReport(
        eventID="f0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        resources=_delivery_resources() if resources is _UNSET else resources,
    )


def _event_intervals() -> tuple[Interval[EventPayload], ...]:
    """Helper function to create the FLEX event intervals a delivery report must mirror."""
    return (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(EventPayload(type=FLEX, values=(0,)),),
        ),
        Interval(
            id=1,
            interval_period=IntervalPeriod(start=DISPATCH_START, duration=timedelta(hours=4)),
            payloads=(EventPayload(type=FLEX, values=(200,)),),
        ),
    )


def test_acknowledgment_report_valid() -> None:
    """An acknowledgment matching the specification's example is compliant."""
    assert validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report()) is None


def test_acknowledgment_report_needs_one_aggregated_resource() -> None:
    """The acknowledgment applies to the group as a whole and is not reported per asset."""
    resources = (
        ReportResource(
            resource_name="ASSET-0001",
            intervals=(Interval(id=0, interval_period=None, payloads=(ReportPayload(type=ACK, values=(True,)),)),),
        ),
    )

    errors = validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report(resources=resources))

    assert errors is not None
    assert any("'AGGREGATED_REPORT'" in str(error["type"]) for error in errors)


def test_acknowledgment_report_has_exactly_one_interval() -> None:
    """The acknowledgment carries one interval, with an id of 0."""
    resources = (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(Interval(id=1, interval_period=None, payloads=(ReportPayload(type=ACK, values=(True,)),)),),
        ),
    )

    errors = validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report(resources=resources))

    assert errors is not None
    assert any("exactly one interval, with an id of 0" in str(error["type"]) for error in errors)


def test_acknowledgment_report_interval_defines_no_interval_period() -> None:
    """The acknowledgment confirms receipt and carries no measured data, so it has no period."""
    resources = (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(
                Interval(
                    id=0,
                    interval_period=IntervalPeriod(start=DISPATCH_START, duration=timedelta(hours=1)),
                    payloads=(ReportPayload(type=ACK, values=(True,)),),
                ),
            ),
        ),
    )

    errors = validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report(resources=resources))

    assert errors is not None
    assert any("must not define its own intervalPeriod" in str(error["type"]) for error in errors)


def test_acknowledgment_payload_must_be_true() -> None:
    """An ACK payload states that the message arrived; its value must be true."""
    resources = (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(Interval(id=0, interval_period=None, payloads=(ReportPayload(type=ACK, values=(False,)),)),),
        ),
    )

    errors = validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report(resources=resources))

    assert errors is not None
    assert any("must be true" in str(error["type"]) for error in errors)


def test_acknowledgment_payload_type_must_be_ack() -> None:
    """The acknowledgment interval carries exactly one ACK payload."""
    resources = (
        ReportResource(
            resource_name="AGGREGATED_REPORT",
            intervals=(
                Interval(id=0, interval_period=None, payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0,)),)),
            ),
        ),
    )

    errors = validate_flex_acknowledgment_report_compliant(_create_acknowledgment_report(resources=resources))

    assert errors is not None
    assert any("payload of type 'ACK'" in str(error["type"]) for error in errors)


def test_delivery_report_valid() -> None:
    """A delivery report matching the specification's example is compliant."""
    assert validate_flex_delivery_report_compliant(_create_delivery_report()) is None


def test_delivery_report_value_count_follows_interval_duration() -> None:
    """A DELIVERED_FLEX payload carries one value per 15 minutes: 4 for PT1H, 16 for PT4H."""
    intervals = (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0, 0)),),
        ),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is not None
    assert any("one value per 15 minutes" in str(error["type"]) for error in errors)


def test_delivery_report_values_are_not_negative() -> None:
    """Delivered flexibility is measured against the ACTIVE_BASELINE and never goes below zero."""
    intervals = (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0, 0, -5, 0)),),
        ),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is not None
    assert any("larger than zero" in str(error["type"]) for error in errors)


def test_delivery_report_interval_defines_an_interval_period() -> None:
    """Each delivery interval states the window it reports on."""
    intervals = (Interval(id=0, interval_period=None, payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0,)),)),)

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is not None
    assert any("must define an intervalPeriod" in str(error["type"]) for error in errors)


def test_delivery_report_payload_type_must_be_delivered_flex() -> None:
    """Each delivery interval carries exactly one DELIVERED_FLEX payload."""
    intervals = (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(ReportPayload(type=ACK, values=(True,)),),
        ),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is not None
    assert any("payload of type 'DELIVERED_FLEX'" in str(error["type"]) for error in errors)


def test_delivery_report_mirrors_every_event_interval() -> None:
    """One report interval per event interval."""
    intervals = (_delivery_interval(1, DISPATCH_START, timedelta(hours=4), 200),)

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals)),
        event_intervals=_event_intervals(),
    )

    assert errors is not None
    assert any("one interval per interval of the FLEX event" in str(error["type"]) for error in errors)


def test_delivery_report_reuses_event_interval_periods() -> None:
    """Each report interval repeats the intervalPeriod of the event interval it reports on."""
    intervals = (
        _delivery_interval(0, PRE_DISPATCH_START, timedelta(hours=1), 0),
        _delivery_interval(1, DISPATCH_START + timedelta(hours=1), timedelta(hours=4), 200),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals)),
        event_intervals=_event_intervals(),
    )

    assert errors is not None
    assert any("equal to that of the event interval" in str(error["type"]) for error in errors)


def test_delivery_report_matching_the_event_is_valid() -> None:
    """The cross-object rules pass for a report built from the event it answers."""
    assert (
        validate_flex_delivery_report_compliant(_create_delivery_report(), event_intervals=_event_intervals()) is None
    )


def test_a_delivered_value_with_three_decimals_is_rejected() -> None:
    """Every power value in the profile is a double with at most two decimal places."""
    intervals = (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0, 0, 0, 0.125)),),
        ),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_a_delivered_value_with_two_decimals_is_accepted() -> None:
    """Two decimals is the limit, not a rejection."""
    intervals = (
        Interval(
            id=0,
            interval_period=IntervalPeriod(start=PRE_DISPATCH_START, duration=timedelta(hours=1)),
            payloads=(ReportPayload(type=DELIVERED_FLEX, values=(0, 0, 0, 0.25)),),
        ),
    )

    errors = validate_flex_delivery_report_compliant(
        _create_delivery_report(resources=_delivery_resources(intervals=intervals))
    )

    assert errors is None


# --- Operational status report --------------------------------------------------------------

OPERATIONAL_STATUS = ReportPayloadType("OPERATIONAL_STATUS")


def _operational_status_resource(resource_name: str, status: str) -> ReportResource:
    """Helper function to create one reported resource carrying its operational status."""
    return ReportResource(
        resource_name=resource_name,
        intervals=(
            Interval(id=0, interval_period=None, payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=(status,)),)),
        ),
    )


def _create_operational_status_report(
    report_name: str | None = _UNSET,
    resources: tuple[ReportResource, ...] = _UNSET,
) -> NewReport:
    """
    Helper function to create a report with the specified values.

    Any argument left unset defaults to a compliant operational status report value.
    """
    return NewReport(
        eventID="a0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        report_name="OPERATIONAL_STATUS" if report_name is _UNSET else report_name,
        resources=(_operational_status_resource("ASSET-0001", "PENDING"),) if resources is _UNSET else resources,
    )


def test_operational_status_report_valid() -> None:
    """A report matching the specification's example is compliant."""
    assert validate_operational_status_report_compliant(_create_operational_status_report()) is None


@pytest.mark.parametrize("status", ["NORMAL", "ERROR", "PENDING"])
def test_every_status_in_the_table_is_accepted(status: str) -> None:
    """The operational status values table has exactly these three entries."""
    report = _create_operational_status_report(resources=(_operational_status_resource("ASSET-0001", status),))

    assert validate_operational_status_report_compliant(report) is None


def test_one_entry_per_resource_being_reported_on() -> None:
    """Unlike the other reports, this one is per resource rather than aggregated."""
    report = _create_operational_status_report(
        resources=(
            _operational_status_resource("ASSET-0001", "PENDING"),
            _operational_status_resource("ASSET-0002", "ERROR"),
        )
    )

    assert validate_operational_status_report_compliant(report) is None


def test_operational_status_report_name_is_optional() -> None:
    """The reportName is optional: any value, or none at all, is accepted and plays no part in routing."""
    for report_name in (None, "STATUS"):
        report = _create_operational_status_report(report_name=report_name)

        assert report_kind(report) is ReportKind.OPERATIONAL_STATUS
        assert validate_report_nlflex_compliant(report) is None


def test_operational_status_exactly_one_interval_with_id_zero() -> None:
    """The reported status applies from the moment the BL processes the report."""
    resource = ReportResource(
        resource_name="ASSET-0001",
        intervals=(
            Interval(
                id=0, interval_period=None, payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=("NORMAL",)),)
            ),
            Interval(id=1, interval_period=None, payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=("ERROR",)),)),
        ),
    )

    errors = validate_operational_status_report_compliant(_create_operational_status_report(resources=(resource,)))

    assert errors is not None
    assert any("exactly one interval with an id of 0" in str(error["type"]) for error in errors)


def test_the_interval_must_not_define_its_own_interval_period() -> None:
    """The status applies from processing, not over a window the VEN chooses."""
    resource = ReportResource(
        resource_name="ASSET-0001",
        intervals=(
            Interval(
                id=0,
                interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1)),
                payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=("PENDING",)),),
            ),
        ),
    )

    errors = validate_operational_status_report_compliant(_create_operational_status_report(resources=(resource,)))

    assert errors is not None
    assert any("must not define its own intervalPeriod" in str(error["type"]) for error in errors)


def test_exactly_one_operational_status_payload() -> None:
    """Each resource carries one OPERATIONAL_STATUS payload and nothing else."""
    resource = ReportResource(
        resource_name="ASSET-0001",
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(
                    ReportPayload(type=OPERATIONAL_STATUS, values=("PENDING",)),
                    ReportPayload(type=ReportPayloadType("READING"), values=(10,)),
                ),
            ),
        ),
    )

    errors = validate_operational_status_report_compliant(_create_operational_status_report(resources=(resource,)))

    assert errors is not None
    assert any("exactly one payload of type 'OPERATIONAL_STATUS'" in str(error["type"]) for error in errors)


def test_an_unknown_status_value_is_rejected() -> None:
    """A value outside the operational status values table is not a status."""
    errors = validate_operational_status_report_compliant(
        _create_operational_status_report(resources=(_operational_status_resource("ASSET-0001", "OFFLINE"),))
    )

    assert errors is not None
    assert any("operational status values" in str(error["type"]) for error in errors)


def test_exactly_one_status_value() -> None:
    """A resource has one status at a time."""
    resource = ReportResource(
        resource_name="ASSET-0001",
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(ReportPayload(type=OPERATIONAL_STATUS, values=("NORMAL", "ERROR")),),
            ),
        ),
    )

    errors = validate_operational_status_report_compliant(_create_operational_status_report(resources=(resource,)))

    assert errors is not None
    assert any("operational status values" in str(error["type"]) for error in errors)


def test_a_report_on_no_resources_is_rejected() -> None:
    """A report with no resource entries reports nothing."""
    report = NewReport.model_construct(
        event_id="a0000000-0000-4000-8000-000000000000",
        client_name="8712345678906",
        report_name="OPERATIONAL_STATUS",
        resources=(),
    )

    errors = validate_operational_status_report_compliant(report)

    assert errors is not None
    assert any("one entry per resource" in str(error["type"]) for error in errors)

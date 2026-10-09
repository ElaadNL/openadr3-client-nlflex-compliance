# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for reports of the OpenADR DER profile specification v1.0.0.

The profile defines five report shapes that all use the same underlying OpenADR3 Report object:

- The registration and deregistration report, which registers assets into a resource group.
- The flex delta report, the VEN's answer to a baseline event.
- The flexibility dispatch acknowledgment, confirming that a FLEX event arrived.
- The flex delivery report, stating what the group delivered against that FLEX event.
- The operational status report, stating whether a resource can deliver flexibility.

Two of them carry a fixed reportName and three do not, so this module reads the reportName first and
falls back to the payload types the report carries. A report that matches no shape is reported as
such. That matters: the v0.1 draft's dispatcher routed every report whose reportName it did not
recognise into the flex delta branch, so an acknowledgment or a delivery report failed on a rule it
was never subject to, which reads as a real non-conformance.

The clientName rule holds for every shape, so it is checked here rather than five times over.
"""

from collections.abc import Sequence
from datetime import timedelta
from enum import StrEnum

from openadr3_client._models.common.interval import Interval
from openadr3_client._models.common.payload import AllowedPayloadInputs
from openadr3_client.oadr310.models.event.event_payload import EventPayload
from openadr3_client.oadr310.models.report.report import Report, ReportResource
from openadr3_client.oadr310.models.report.report_payload import ReportPayloadType
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex10._common import as_power_value, error, is_ean13, is_uuid
from openadr3_client_nlflex_compliance.nlflex10.event_nlflex_compliant import (
    ACTIVE_FLEX_DELTA_PAYLOAD_TYPE,
    DE_REGISTRATION_REQUEST_PAYLOAD_TYPE,
    OPERATIONAL_STATUS_PAYLOAD_TYPE,
    REGISTRATION_REQUEST_PAYLOAD_TYPE,
    RESERVED_FLEX_DELTA_PAYLOAD_TYPE,
)

# --------------------------------------------------------------------------------------------------------------
# Aggregated report resource, shared by the reports below.
#
# The registration report, the flex delta report, the flexibility dispatch acknowledgment and the flex
# delivery report all describe a resource group as a whole rather than one asset at a time, so all four
# carry exactly one resource entry named AGGREGATED_REPORT (see [OADR3-UG] section 7.7, Aggregated
# Report). The operational status report is the exception: it carries one entry per resource being
# reported on and does not use this helper.
# --------------------------------------------------------------------------------------------------------------

AGGREGATED_REPORT_RESOURCE_NAME = "AGGREGATED_REPORT"


def single_aggregated_report_resource(
    report: Report,
    error_message: str,
) -> tuple[list[InitErrorDetails], ReportResource | None]:
    """
    Validates that the report contains exactly one AGGREGATED_REPORT resource entry.

    Args:
        report: The report to validate.
        error_message: The message to report when it does not, phrased for the report shape being
            validated so that the caller is told which report it got wrong.

    Returns:
        The validation errors found, and the aggregated resource. The resource is None exactly when
        the error list is non-empty, so a caller can return early without validating intervals that
        belong to a resource that should not be there.

    """
    if len(report.resources) != 1 or report.resources[0].resource_name != AGGREGATED_REPORT_RESOURCE_NAME:
        return [error(error_message, "resources", report.resources)], None

    return [], report.resources[0]


# --------------------------------------------------------------------------------------------------------------
# Registration and deregistration report.
#
# Registration is the process by which a Service Provider's assets become members of a resource group,
# and deregistration is the reverse, as specified in "Resource group registration and deregistration"
# of the OpenADR DER profile specification v1.0.0.
#
# Both operations use the same report structure: the report identifies the target group through a
# RESOURCE_GROUP_ID payload and lists the resources to register or deregister in the values array of
# the operation-specific payload, so many assets are processed with one report. Note that the
# unreleased v0.1 draft named the group payload RESOURCE_GROUP_TARGET.
#
# The report has no originating event, so it references the program's reporting anchor event through
# its eventID. That the referenced event is in fact the anchor event cannot be checked from the report.
# --------------------------------------------------------------------------------------------------------------

REGISTRATION_REPORT_NAME = "RESOURCE_REGISTRATION"

RESOURCE_GROUP_ID_PAYLOAD_TYPE = ReportPayloadType("RESOURCE_GROUP_ID")

REQUEST_PAYLOAD_TYPES = (REGISTRATION_REQUEST_PAYLOAD_TYPE, DE_REGISTRATION_REQUEST_PAYLOAD_TYPE)

# One RESOURCE_GROUP_ID, and one REGISTRATION_REQUEST or DE_REGISTRATION_REQUEST.
REGISTRATION_REPORT_INTERVAL_PAYLOAD_COUNT = 2


def _registration_report_name_compliant(self: Report) -> list[InitErrorDetails]:
    """Validates the reportName, which both operations share."""
    if self.report_name != REGISTRATION_REPORT_NAME:
        return [
            error(
                "The registration report must have a reportName of 'RESOURCE_REGISTRATION'.",
                "report_name",
                self.report_name,
            )
        ]

    return []


def validate_registration_report_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that a report is a compliant registration or deregistration report.

    Args:
        report: The report to validate.

    Returns:
        The validation errors found, or None when the report is compliant.

    """
    validation_errors = _registration_report_name_compliant(report)

    resource_errors, resource = single_aggregated_report_resource(
        report,
        "The registration report must contain exactly one resource entry, named 'AGGREGATED_REPORT'.",
    )
    validation_errors.extend(resource_errors)

    if resource is None:
        return validation_errors or None

    if len(resource.intervals) != 1 or resource.intervals[0].id != 0:
        validation_errors.append(
            error(
                "The registration report must contain exactly one interval with an id of 0.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    payloads = resource.intervals[0].payloads
    group_payloads = [p for p in payloads if p.type == RESOURCE_GROUP_ID_PAYLOAD_TYPE]
    request_payloads = [p for p in payloads if p.type in REQUEST_PAYLOAD_TYPES]

    if (
        len(payloads) != REGISTRATION_REPORT_INTERVAL_PAYLOAD_COUNT
        or len(group_payloads) != 1
        or len(request_payloads) != 1
    ):
        validation_errors.append(
            error(
                "The registration report interval must contain exactly two payloads: one 'RESOURCE_GROUP_ID' "
                "and one 'REGISTRATION_REQUEST' or 'DE_REGISTRATION_REQUEST'.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    validation_errors.extend(_group_payload_compliant(report, group_payloads[0].values))
    validation_errors.extend(_request_payload_compliant(report, request_payloads[0]))

    return validation_errors or None


def _group_payload_compliant(self: Report, values: tuple[object, ...]) -> list[InitErrorDetails]:
    """Validates that the report names exactly one resource group, by its object ID."""
    if len(values) != 1:
        return [
            error(
                "The 'RESOURCE_GROUP_ID' payload must contain exactly one value: the ID of the resource group "
                "to register into or deregister from.",
                "resources",
                self.resources,
            )
        ]

    if not is_uuid(values[0]):
        return [
            error(
                "The 'RESOURCE_GROUP_ID' payload value must be the object ID of the resource group, which is a "
                "UUID. It is not the Group-ID.",
                "resources",
                self.resources,
            )
        ]

    return []


def _request_payload_compliant(self: Report, payload: object) -> list[InitErrorDetails]:
    """
    Validates the assets a registration or deregistration request lists.

    The values MUST be the resource IDs, that is the object IDs, of the assets to register or
    deregister. They are never Asset-IDs.

    The payload is known to carry at least one value: the OpenADR payload model rejects an empty
    values tuple before this validator ever runs.
    """
    values = getattr(payload, "values", ())
    payload_type = getattr(payload, "type", "")

    if not all(is_uuid(value) for value in values):
        return [
            error(
                f"The '{payload_type}' payload values must be the resource IDs (UUIDs) of the assets to "
                "register or deregister.",
                "resources",
                self.resources,
            )
        ]

    return []


# --------------------------------------------------------------------------------------------------------------
# Flex delta report.
#
# The VEN reports the aggregate flexibility of a resource group relative to the baseline the BL
# calculated for it, as specified in "Flexibility reporting" of the OpenADR DER profile specification
# v1.0.0. The value is split in two, following the group's active and reserved capacity: an
# ACTIVE_FLEX_DELTA over the NORMAL and ERROR children, and a RESERVED_FLEX_DELTA over the PENDING
# children. The unreleased v0.1 draft carried a single FLEX_DELTA payload instead.
#
# Both are at most zero. Zero means no flexibility is offered, so the dispatch limit equals the
# ACTIVE_BASELINE; the more negative the value, the more the group offers.
#
# The report has no fixed reportName. Two rules of the chapter are about sequence rather than shape
# and cannot be checked from a single object: the report references the baseline event that requested
# it, and the most recent report for a group is the group's offer.
# --------------------------------------------------------------------------------------------------------------

FLEX_DELTA_PAYLOAD_TYPES = (ACTIVE_FLEX_DELTA_PAYLOAD_TYPE, RESERVED_FLEX_DELTA_PAYLOAD_TYPE)
FLEX_DELTA_REPORT_PAYLOAD_TYPES = frozenset(FLEX_DELTA_PAYLOAD_TYPES)

FLEX_DELTA_REPORT_PAYLOAD_COUNT = len(FLEX_DELTA_PAYLOAD_TYPES)


def _flex_delta_value_compliant(value: AllowedPayloadInputs) -> bool:
    """Validates one flex delta value: a double in KW, at most two decimals, at most zero."""
    power_value = as_power_value(value)
    return power_value is not None and power_value <= 0


def validate_flex_delta_report_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that a report is a compliant flex delta report.

    Args:
        report: The report to validate.

    Returns:
        The validation errors found, or None when the report is compliant.

    """
    validation_errors, resource = single_aggregated_report_resource(
        report,
        "The flex delta report must contain exactly one resource entry, named 'AGGREGATED_REPORT'.",
    )

    if resource is None:
        return validation_errors or None

    if len(resource.intervals) != 1 or resource.intervals[0].id != 0:
        validation_errors.append(
            error(
                "The flex delta report must contain exactly one interval with an id of 0.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    payloads = resource.intervals[0].payloads
    carried = [payload.type for payload in payloads]

    if len(payloads) != FLEX_DELTA_REPORT_PAYLOAD_COUNT or any(
        carried.count(payload_type) != 1 for payload_type in FLEX_DELTA_PAYLOAD_TYPES
    ):
        validation_errors.append(
            error(
                "The flex delta report interval must contain exactly two payloads in KW, one "
                "'ACTIVE_FLEX_DELTA' and one 'RESERVED_FLEX_DELTA'. Both must be present even when one of them "
                "is zero.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    for payload in payloads:
        if len(payload.values) != 1:
            validation_errors.append(
                error(
                    f"The '{payload.type}' payload must contain exactly one value, the offer in KW.",
                    "resources",
                    report.resources,
                )
            )
        elif not _flex_delta_value_compliant(payload.values[0]):
            validation_errors.append(
                error(
                    f"The '{payload.type}' payload value must be a double in KW with at most two decimals, "
                    "equal to or smaller than zero.",
                    "resources",
                    report.resources,
                )
            )

    return validation_errors or None


# --------------------------------------------------------------------------------------------------------------
# Flexibility dispatch acknowledgment and flex delivery report.
#
# These are the two reports a Service Provider answers a flexibility dispatch with:
#
# - The acknowledgment report ("Flexibility dispatch acknowledgment") confirms that the `FLEX` event
#   arrived, and nothing beyond that.
# - The delivery report ("Flexibility delivery reporting") states what the resource group actually
#   delivered, per 15 minutes, once every interval of the event has transpired.
#
# Both are specified in the OpenADR DER profile specification v1.0.0. Neither exists in the v0.1
# draft, and `nlflex01` actively mis-validates them: its report dispatcher routes any report whose
# reportName is not RESOURCE_REGISTRATION or OPERATIONAL_STATUS into the flex delta validator, which
# demands exactly one FLEX_DELTA payload per interval. That produces errors naming a rule the report
# was never subject to.
#
# Neither report has a fixed reportName, so the two validators are exported separately rather than
# behind a dispatcher: the caller knows which report it asked for. One rule is not checkable from the
# report alone — a delivery report MUST carry one interval per interval of the `FLEX` event it
# references, reusing that interval's id and intervalPeriod. The value count per interval follows from
# the interval's own duration and is checked here; matching against the event needs the event, so
# `validate_flex_delivery_report_compliant` accepts the event's intervals optionally.
# --------------------------------------------------------------------------------------------------------------

ACK_PAYLOAD_TYPE = ReportPayloadType("ACK")
DELIVERED_FLEX_PAYLOAD_TYPE = ReportPayloadType("DELIVERED_FLEX")

# A DELIVERED_FLEX payload carries one value per 15 minutes of the interval it belongs to: 4 values
# for PT1H, 8 for PT2H, 16 for PT4H and 24 for PT6H.
FIFTEEN_MINUTES = timedelta(minutes=15)


# `eventID` is not validated here: the OpenADR Report model already requires it, so a report that
# does not reference an event cannot be constructed in the first place.


def validate_flex_acknowledgment_report_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that an acknowledgment report is compliant.

    The report MUST contain exactly one AGGREGATED_REPORT resource entry, and that entry MUST
    contain exactly one interval with id 0 that does not define its own intervalPeriod, carrying
    exactly one ACK payload whose single value is true. The report carries no measured data: it
    exists solely to confirm receipt.

    Args:
        report: The report to validate.

    Returns:
        The validation errors found, or None when the acknowledgment is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    resource_errors, resource = single_aggregated_report_resource(
        report,
        "The acknowledgment report must contain exactly one resource entry, named 'AGGREGATED_REPORT'.",
    )
    validation_errors.extend(resource_errors)

    if resource is None:
        return validation_errors or None

    if len(resource.intervals) != 1 or resource.intervals[0].id != 0:
        validation_errors.append(
            error(
                "The acknowledgment report must contain exactly one interval, with an id of 0.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    interval = resource.intervals[0]

    if interval.interval_period is not None:
        validation_errors.append(
            error(
                "The acknowledgment report interval must not define its own intervalPeriod.",
                "resources",
                report.resources,
            )
        )

    if len(interval.payloads) != 1 or interval.payloads[0].type != ACK_PAYLOAD_TYPE:
        validation_errors.append(
            error(
                "The acknowledgment report interval must carry exactly one payload of type 'ACK'.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    values = interval.payloads[0].values
    if len(values) != 1 or values[0] is not True:
        validation_errors.append(
            error("The ACK payload must contain exactly one value, which must be true.", "resources", report.resources)
        )

    return validation_errors or None


def validate_flex_delivery_report_compliant(
    report: Report,
    *,
    event_intervals: Sequence[Interval[EventPayload]] | None = None,
) -> list[InitErrorDetails] | None:
    """
    Validates that a delivery report is compliant.

    The report MUST contain exactly one AGGREGATED_REPORT resource entry. Each interval MUST define
    an intervalPeriod equal to that of the event interval it reports on, carry exactly one
    DELIVERED_FLEX payload, and hold one value per 15 minutes of that interval, every value a double
    equal to or larger than zero.

    Args:
        report: The report to validate.
        event_intervals: The intervals of the FLEX event being reported on, when known. Supplying
            them adds the cross-object rules: one report interval per event interval, each reusing the
            event interval's id and intervalPeriod.

    Returns:
        The validation errors found, or None when the delivery report is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    resource_errors, resource = single_aggregated_report_resource(
        report,
        "The delivery report must contain exactly one resource entry, named 'AGGREGATED_REPORT'.",
    )
    validation_errors.extend(resource_errors)

    if resource is None:
        return validation_errors or None

    for interval in resource.intervals:
        if interval.interval_period is None:
            validation_errors.append(
                error(
                    "Every delivery report interval must define an intervalPeriod equal to that of the event "
                    "interval it reports on.",
                    "resources",
                    report.resources,
                )
            )
            continue

        if len(interval.payloads) != 1 or interval.payloads[0].type != DELIVERED_FLEX_PAYLOAD_TYPE:
            validation_errors.append(
                error(
                    "Every delivery report interval must carry exactly one payload of type 'DELIVERED_FLEX'.",
                    "resources",
                    report.resources,
                )
            )
            continue

        validation_errors.extend(_delivered_values_compliant(report, interval))

    validation_errors.extend(_mirrors_event_intervals(report, resource, event_intervals))

    return validation_errors or None


def _delivered_values_compliant(self: Report, interval: Interval) -> list[InitErrorDetails]:
    """
    Validates the values of a DELIVERED_FLEX payload.

    The number of values MUST equal the interval's duration divided by 15 minutes, and every value
    MUST be a double in KW with at most two decimals, equal to or larger than zero — which holds
    because the group must not exceed the interval's ceiling, and that ceiling is at most the
    ACTIVE_BASELINE.
    """
    validation_errors: list[InitErrorDetails] = []
    values = interval.payloads[0].values

    if interval.interval_period is None:
        return validation_errors

    expected_values, remainder = divmod(interval.interval_period.duration, FIFTEEN_MINUTES)

    if remainder or len(values) != expected_values:
        validation_errors.append(
            error(
                "A DELIVERED_FLEX payload must carry one value per 15 minutes of the interval it belongs to.",
                "resources",
                self.resources,
            )
        )
        return validation_errors

    delivered = [as_power_value(value) for value in values]
    if any(value is None or value < 0 for value in delivered):
        validation_errors.append(
            error(
                "Every DELIVERED_FLEX value must be a double in KW with at most two decimals, equal to or "
                "larger than zero.",
                "resources",
                self.resources,
            )
        )

    return validation_errors


def _mirrors_event_intervals(
    self: Report,
    resource: ReportResource,
    event_intervals: Sequence[Interval[EventPayload]] | None,
) -> list[InitErrorDetails]:
    """
    Validates the delivery report against the event it reports on.

    One report interval per event interval, each reusing the id and the intervalPeriod of the event
    interval it reports on.
    """
    if event_intervals is None:
        return []

    reported = {interval.id: interval for interval in resource.intervals}
    expected = {interval.id: interval for interval in event_intervals}

    if reported.keys() != expected.keys():
        return [
            error(
                "The delivery report must contain exactly one interval per interval of the FLEX event, reusing "
                "the id of the event interval it reports on.",
                "resources",
                self.resources,
            )
        ]

    if any(reported[interval_id].interval_period != expected[interval_id].interval_period for interval_id in expected):
        return [
            error(
                "Every delivery report interval must define an intervalPeriod equal to that of the event interval "
                "it reports on.",
                "resources",
                self.resources,
            )
        ]

    return []


# --------------------------------------------------------------------------------------------------------------
# Operational status report.
#
# The operational status of a resource tells the BL whether that resource is able to deliver
# flexibility, and which part of its resource group's baseline it counts towards, as specified in
# "Operational status reporting" of the OpenADR DER profile specification v1.0.0.
#
# This is the one report shape of the profile that is not aggregated over the resource group: it
# carries one entry per resource being reported on, named for that resource's Asset-ID.
#
# Reporting is reserved for the exceptions. The BL MUST treat a resource's operational status as
# NORMAL if it has processed no report setting a different status for it, which is a change from the
# unreleased v0.1 draft, where a resource started out PENDING. That default is BL behaviour rather
# than an object constraint, so nothing here enforces it; the three status values themselves are
# unchanged.
# --------------------------------------------------------------------------------------------------------------

OPERATIONAL_STATUS_REPORT_NAME = "OPERATIONAL_STATUS"

# See the "Operational status values" table. NORMAL and ERROR are taken from the OpenADR 3.1
# operating state enumeration; PENDING is defined by this profile.
KNOWN_OPERATIONAL_STATUS_VALUES = frozenset({"NORMAL", "ERROR", "PENDING"})


def _operational_status_report_name_compliant(self: Report) -> list[InitErrorDetails]:
    """Validates the reportName the operational status report is discriminated by."""
    if self.report_name != OPERATIONAL_STATUS_REPORT_NAME:
        return [
            error(
                "The operational status report must have a reportName of 'OPERATIONAL_STATUS'.",
                "report_name",
                self.report_name,
            )
        ]

    return []


def _operational_status_resource_compliant(self: Report, resource: ReportResource) -> list[InitErrorDetails]:
    """
    Validates one reported resource.

    The resource MUST contain exactly one interval with id 0, which MUST NOT define its own
    intervalPeriod, carrying exactly one OPERATIONAL_STATUS payload with exactly one value from the
    operational status values table.
    """
    validation_errors: list[InitErrorDetails] = []

    if len(resource.intervals) != 1 or resource.intervals[0].id != 0:
        return [
            error(
                f"The operational status report resource '{resource.resource_name}' must contain exactly one "
                "interval with an id of 0.",
                "resources",
                self.resources,
            )
        ]

    interval = resource.intervals[0]

    if interval.interval_period is not None:
        validation_errors.append(
            error(
                f"The operational status report interval of '{resource.resource_name}' must not define its own "
                "intervalPeriod. The reported status applies from the moment the BL processes the report.",
                "resources",
                self.resources,
            )
        )

    if len(interval.payloads) != 1 or interval.payloads[0].type != OPERATIONAL_STATUS_PAYLOAD_TYPE:
        validation_errors.append(
            error(
                f"The operational status report interval of '{resource.resource_name}' must contain exactly one "
                "payload of type 'OPERATIONAL_STATUS'.",
                "resources",
                self.resources,
            )
        )
        return validation_errors

    values = interval.payloads[0].values
    if len(values) != 1 or values[0] not in KNOWN_OPERATIONAL_STATUS_VALUES:
        validation_errors.append(
            error(
                f"The 'OPERATIONAL_STATUS' payload of '{resource.resource_name}' must contain exactly one value "
                "from the operational status values table: 'NORMAL', 'ERROR' or 'PENDING'.",
                "resources",
                self.resources,
            )
        )

    return validation_errors


def validate_operational_status_report_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that a report is a compliant operational status report.

    Args:
        report: The report to validate.

    Returns:
        The validation errors found, or None when the report is compliant.

    """
    validation_errors = _operational_status_report_name_compliant(report)

    if not report.resources:
        validation_errors.append(
            error(
                "The operational status report must contain one entry per resource being reported on.",
                "resources",
                report.resources,
            )
        )
        return validation_errors or None

    for resource in report.resources:
        validation_errors.extend(_operational_status_resource_compliant(report, resource))

    return validation_errors or None


# --------------------------------------------------------------------------------------------------------------
# Discriminator: routes a Report to the shape-specific validator above, based on its reportName and the
# payload types it carries.
# --------------------------------------------------------------------------------------------------------------


class ReportKind(StrEnum):
    """The report shapes the OpenADR DER profile specification v1.0.0 defines."""

    RESOURCE_REGISTRATION = "RESOURCE_REGISTRATION"
    """Registering assets into a resource group, or deregistering them from it."""

    FLEX_DELTA = "FLEX_DELTA"
    """The flexibility a resource group offers against its baseline."""

    FLEX_ACKNOWLEDGMENT = "FLEX_ACKNOWLEDGMENT"
    """Confirmation that a FLEX event arrived."""

    FLEX_DELIVERY = "FLEX_DELIVERY"
    """The flexibility a resource group delivered against a FLEX event."""

    OPERATIONAL_STATUS = "OPERATIONAL_STATUS"
    """Whether a resource is able to deliver flexibility."""


def _carried_payload_types(report: Report) -> frozenset[ReportPayloadType]:
    """Collects every payload type the report carries, across all of its resources and intervals."""
    return frozenset(
        payload.type
        for resource in report.resources
        for interval in resource.intervals
        for payload in interval.payloads
    )


def report_kind(report: Report) -> ReportKind | None:
    """
    Determines which report shape this is.

    The registration report and the operational status report are identified by their reportName.
    The other three have no fixed reportName and are identified by the payload types they carry.

    Args:
        report: The report to classify.

    Returns:
        The report shape, or None when the report matches no shape the profile defines.

    """
    if report.report_name == REGISTRATION_REPORT_NAME:
        return ReportKind.RESOURCE_REGISTRATION

    if report.report_name == OPERATIONAL_STATUS_REPORT_NAME:
        return ReportKind.OPERATIONAL_STATUS

    payload_types = _carried_payload_types(report)

    if ACK_PAYLOAD_TYPE in payload_types:
        return ReportKind.FLEX_ACKNOWLEDGMENT

    if DELIVERED_FLEX_PAYLOAD_TYPE in payload_types:
        return ReportKind.FLEX_DELIVERY

    if payload_types & FLEX_DELTA_REPORT_PAYLOAD_TYPES:
        return ReportKind.FLEX_DELTA

    return None


def _client_name_compliant(report: Report) -> list[InitErrorDetails]:
    """
    Validates the clientName, which every report shape shares.

    The clientName MUST be the venName of the VEN submitting the report, and a venName MUST be the
    Service Provider identifier, which is an EAN13.
    """
    if not is_ean13(report.client_name):
        return [
            error(
                "The report clientName must be the venName of the VEN submitting it, which is the Service "
                "Provider identifier: an EAN13 of 13 digits with a valid check digit.",
                "client_name",
                report.client_name,
            )
        ]

    return []


def validate_report_nlflex_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that a report is compliant with the OpenADR DER profile specification v1.0.0.

    Dispatches to the applicable object constraints and requirements based on the report's
    reportName and the payload types it carries.

    Args:
        report: The report to validate.

    Returns:
        The validation errors found, or None when the report is compliant.

    """
    validation_errors = _client_name_compliant(report)
    kind = report_kind(report)

    if kind is ReportKind.RESOURCE_REGISTRATION:
        shape_errors = validate_registration_report_compliant(report)
    elif kind is ReportKind.OPERATIONAL_STATUS:
        shape_errors = validate_operational_status_report_compliant(report)
    elif kind is ReportKind.FLEX_ACKNOWLEDGMENT:
        shape_errors = validate_flex_acknowledgment_report_compliant(report)
    elif kind is ReportKind.FLEX_DELIVERY:
        shape_errors = validate_flex_delivery_report_compliant(report)
    elif kind is ReportKind.FLEX_DELTA:
        shape_errors = validate_flex_delta_report_compliant(report)
    else:
        shape_errors = [
            error(
                "The report does not match any report shape defined by the profile. A report is identified by "
                "its reportName, 'RESOURCE_REGISTRATION' or 'OPERATIONAL_STATUS', or by the payload types it "
                "carries: 'ACK' for a dispatch acknowledgment, 'DELIVERED_FLEX' for a delivery report, and "
                "'ACTIVE_FLEX_DELTA' or 'RESERVED_FLEX_DELTA' for a flex delta report.",
                "resources",
                report.resources,
            )
        ]

    validation_errors.extend(shape_errors or [])

    return validation_errors or None

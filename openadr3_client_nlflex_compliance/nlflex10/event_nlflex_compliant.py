# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validator for events of the OpenADR DER profile specification v1.0.0.

The profile defines four kinds of event, "each identified by the payload types it carries":

- The reporting anchor event carries no signal at all. It exists so that reports which have no
  originating event still have an eventID to reference.
- The baseline event communicates the calculated baseline of a resource group.
- The flex delta override event corrects the flexibility a Service Provider reported.
- The FLEX event calls flexibility from a resource group.

A validator plugin registers exactly one validator per model class, so this module is the single
entry point for Event and dispatches to the kind modules. An event whose payload types match no kind
is reported as such rather than validated against the rules of a kind it is not, which would name
rules the object was never subject to.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

from openadr3_client._models.common.payload import AllowedPayloadInputs
from openadr3_client.oadr310.models.event.event import Event
from openadr3_client.oadr310.models.event.event_payload import EventPayload, EventPayloadType
from openadr3_client.oadr310.models.report.report_payload import ReportIntervals, ReportPayloadType
from openadr3_client.oadr310.models.unit import Unit
from pydantic_core import InitErrorDetails

from openadr3_client_nlflex_compliance.nlflex10._common import as_power_value, error, is_power_value, is_uuid

# --------------------------------------------------------------------------------------------------------------
# Reporting anchor event.
#
# OpenADR only accepts a report that references an event through its eventID, and three of this
# profile's reports are not a response to a signal from the BL: the registration report, the
# deregistration report and the operational status report. The BL therefore creates exactly one
# reporting anchor event per program for them to reference, as specified in "Reporting anchor event"
# of the OpenADR DER profile specification v1.0.0.
#
# The anchor event carries no DR signals. It is the "report-only event with VEN-determined intervals"
# of [OADR3-UG] section 7.5: an event with no intervals of its own, whose reportDescriptors request a
# stream of reports the VEN sends at moments of its own choosing.
# --------------------------------------------------------------------------------------------------------------

REGISTRATION_REQUEST_PAYLOAD_TYPE = ReportPayloadType("REGISTRATION_REQUEST")
DE_REGISTRATION_REQUEST_PAYLOAD_TYPE = ReportPayloadType("DE_REGISTRATION_REQUEST")
OPERATIONAL_STATUS_PAYLOAD_TYPE = ReportPayloadType("OPERATIONAL_STATUS")

# The three report streams the anchor event opens, in the order the specification lists them.
ANCHOR_REPORT_PAYLOAD_TYPES = (
    REGISTRATION_REQUEST_PAYLOAD_TYPE,
    DE_REGISTRATION_REQUEST_PAYLOAD_TYPE,
    OPERATIONAL_STATUS_PAYLOAD_TYPE,
)
ANCHOR_REPORT_DESCRIPTOR_COUNT = len(ANCHOR_REPORT_PAYLOAD_TYPES)

# Ad hoc, for the whole time the program is in use.
ANCHOR_DESCRIPTOR_FREQUENCY = 0
ANCHOR_DESCRIPTOR_REPEAT = -1


def _anchor_targets_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the anchor event is public, by carrying no targets."""
    if self.targets:
        return [
            error(
                "The reporting anchor event must not define any targets. It is public, so every VEN in the "
                "program can see it and report against it.",
                "targets",
                self.targets,
            )
        ]

    return []


def _anchor_interval_period_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the anchor event has no temporal span of its own."""
    if self.interval_period is not None:
        return [
            error(
                "The reporting anchor event must not define an intervalPeriod. It has no temporal span of its "
                "own and never expires.",
                "interval_period",
                self.interval_period,
            )
        ]

    return []


def _anchor_intervals_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the anchor event carries no signal."""
    if self.intervals:
        return [
            error(
                "The reporting anchor event must not define any intervals. A report-only event carries no signal.",
                "intervals",
                self.intervals,
            )
        ]

    return []


def _anchor_report_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the report streams the anchor event opens.

    The event MUST declare one descriptor for each of REGISTRATION_REQUEST, DE_REGISTRATION_REQUEST
    and OPERATIONAL_STATUS, each setting frequency to 0 and repeat to -1, so that the VEN reports at
    moments of its own choosing, for the whole time the program is in use.
    """
    validation_errors: list[InitErrorDetails] = []
    report_descriptors = self.report_descriptors or ()

    if len(report_descriptors) != ANCHOR_REPORT_DESCRIPTOR_COUNT:
        validation_errors.append(
            error(
                "The reporting anchor event must declare exactly three report descriptors, one for each of "
                "'REGISTRATION_REQUEST', 'DE_REGISTRATION_REQUEST' and 'OPERATIONAL_STATUS'.",
                "report_descriptors",
                self.report_descriptors,
            )
        )

    for payload_type in ANCHOR_REPORT_PAYLOAD_TYPES:
        matching = [d for d in report_descriptors if d.payload_type == payload_type]

        if len(matching) != 1:
            validation_errors.append(
                error(
                    f"The reporting anchor event must declare exactly one report descriptor for '{payload_type}'.",
                    "report_descriptors",
                    self.report_descriptors,
                )
            )
            continue

        descriptor = matching[0]
        if descriptor.frequency != ANCHOR_DESCRIPTOR_FREQUENCY or descriptor.repeat != ANCHOR_DESCRIPTOR_REPEAT:
            validation_errors.append(
                error(
                    f"The '{payload_type}' report descriptor must set frequency to 0 and repeat to -1, so that "
                    "the VEN reports at moments of its own choosing for the whole time the program is in use.",
                    "report_descriptors",
                    self.report_descriptors,
                )
            )

    return validation_errors


def validate_reporting_anchor_event_compliant(event: Event) -> list[InitErrorDetails] | None:
    """
    Validates that an event is a compliant reporting anchor event.

    Args:
        event: The event to validate.

    Returns:
        The validation errors found, or None when the anchor event is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_anchor_targets_compliant(event))
    validation_errors.extend(_anchor_interval_period_compliant(event))
    validation_errors.extend(_anchor_intervals_compliant(event))
    validation_errors.extend(_anchor_report_descriptors_compliant(event))

    return validation_errors or None


# --------------------------------------------------------------------------------------------------------------
# Baseline event.
#
# A baseline event communicates the calculated aggregated baseline of a resource group to the Service
# Provider, as specified in "Baseline event" of the OpenADR DER profile specification v1.0.0. The
# baseline is split in two: the active part covers the group's NORMAL and ERROR children, the reserved
# part its PENDING children. Only the active part can be dispatched.
#
# The event is open ended. It applies from the moment it is published, through its createdDateTime,
# until a new baseline event supersedes it, which is why it carries no intervalPeriod at any level.
# Note that this contradicts the unreleased v0.1 draft, which required an event-level intervalPeriod
# with a duration of P9999Y.
#
# The Service Provider answers with a flex delta report (see the flex delta report section of
# report_nlflex_compliant), which the event asks for through its report descriptors.
# --------------------------------------------------------------------------------------------------------------

ACTIVE_BASELINE_PAYLOAD_TYPE = EventPayloadType("ACTIVE_BASELINE")
RESERVED_BASELINE_PAYLOAD_TYPE = EventPayloadType("RESERVED_BASELINE")

ACTIVE_FLEX_DELTA_PAYLOAD_TYPE = ReportPayloadType("ACTIVE_FLEX_DELTA")
RESERVED_FLEX_DELTA_PAYLOAD_TYPE = ReportPayloadType("RESERVED_FLEX_DELTA")

BASELINE_PAYLOAD_TYPES = (ACTIVE_BASELINE_PAYLOAD_TYPE, RESERVED_BASELINE_PAYLOAD_TYPE)
FLEX_DELTA_PAYLOAD_TYPES = (ACTIVE_FLEX_DELTA_PAYLOAD_TYPE, RESERVED_FLEX_DELTA_PAYLOAD_TYPE)

BASELINE_PAYLOAD_DESCRIPTOR_COUNT = len(BASELINE_PAYLOAD_TYPES)
BASELINE_INTERVAL_PAYLOAD_COUNT = len(BASELINE_PAYLOAD_TYPES)

# Ad hoc and repeated indefinitely: the VEN chooses when to report and may report more than once
# against the same baseline event.
FLEX_DELTA_DESCRIPTOR_FREQUENCY = 0
FLEX_DELTA_DESCRIPTOR_REPEAT = -1


def _baseline_targets_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the event targets the resource group the baseline applies to."""
    if not self.targets:
        return [
            error(
                "The baseline event must target the resource group the limits apply to.",
                "targets",
                self.targets,
            )
        ]

    return []


def _baseline_interval_period_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the baseline event is open ended."""
    if self.interval_period is not None:
        return [
            error(
                "The baseline event must not define an intervalPeriod at the event level. Its validity starts "
                "at createdDateTime and has no end.",
                "interval_period",
                self.interval_period,
            )
        ]

    return []


def _baseline_payload_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the payload descriptors of the baseline event.

    The event MUST declare exactly two descriptors, one ACTIVE_BASELINE and one RESERVED_BASELINE,
    with a units field of KW on both.
    """
    payload_descriptors = self.payload_descriptors or ()
    declared = [descriptor.payload_type for descriptor in payload_descriptors]

    if len(payload_descriptors) != BASELINE_PAYLOAD_DESCRIPTOR_COUNT or any(
        declared.count(payload_type) != 1 for payload_type in BASELINE_PAYLOAD_TYPES
    ):
        return [
            error(
                "The baseline event must declare exactly two payload descriptors, one 'ACTIVE_BASELINE' and "
                "one 'RESERVED_BASELINE'.",
                "payload_descriptors",
                self.payload_descriptors,
            )
        ]

    if any(descriptor.units != Unit.KW for descriptor in payload_descriptors):
        return [
            error(
                "Both baseline payload descriptors must have a units field of 'KW' (note the uppercase KW).",
                "payload_descriptors",
                self.payload_descriptors,
            )
        ]

    return []


def _baseline_report_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates that the baseline event asks the VEN for both halves of its flex delta.

    The event MUST include one reportDescriptor for ACTIVE_FLEX_DELTA and one for
    RESERVED_FLEX_DELTA. Both set reportIntervals to OPEN_INTERVALS, frequency to 0 and repeat to
    -1, which together express that the VEN reports at moments of its own choosing and MAY report
    more than once against the same baseline event.

    Descriptors beyond these two are not rejected: the specification says the event MUST include
    them, not that it carries nothing else.
    """
    validation_errors: list[InitErrorDetails] = []
    report_descriptors = self.report_descriptors or ()

    for payload_type in FLEX_DELTA_PAYLOAD_TYPES:
        matching = [d for d in report_descriptors if d.payload_type == payload_type]

        if len(matching) != 1:
            validation_errors.append(
                error(
                    f"The baseline event must include exactly one report descriptor for '{payload_type}', "
                    "instructing the VEN to submit a flex delta report in response to this event.",
                    "report_descriptors",
                    self.report_descriptors,
                )
            )
            continue

        descriptor = matching[0]
        if (
            descriptor.report_intervals != ReportIntervals.OPEN_INTERVALS
            or descriptor.frequency != FLEX_DELTA_DESCRIPTOR_FREQUENCY
            or descriptor.repeat != FLEX_DELTA_DESCRIPTOR_REPEAT
        ):
            validation_errors.append(
                error(
                    f"The '{payload_type}' report descriptor must set reportIntervals to 'OPEN_INTERVALS', "
                    "frequency to 0 and repeat to -1.",
                    "report_descriptors",
                    self.report_descriptors,
                )
            )

    return validation_errors


def _baseline_intervals_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the single interval of the baseline event.

    The event MUST contain exactly one interval with id 0, which MUST NOT define its own
    intervalPeriod. Its payloads MUST carry exactly two entries, one ACTIVE_BASELINE and one
    RESERVED_BASELINE, both present even when one of them is zero.
    """
    validation_errors: list[InitErrorDetails] = []
    intervals = self.intervals or ()

    if len(intervals) != 1:
        return [error("The baseline event must contain exactly one interval.", "intervals", self.intervals)]

    interval = intervals[0]

    if interval.id != 0:
        validation_errors.append(
            error("The baseline event interval must have an id of 0.", "intervals", self.intervals)
        )

    if interval.interval_period is not None:
        validation_errors.append(
            error(
                "The baseline event interval must not define its own intervalPeriod.",
                "intervals",
                self.intervals,
            )
        )

    carried = [payload.type for payload in interval.payloads]

    if len(interval.payloads) != BASELINE_INTERVAL_PAYLOAD_COUNT or any(
        carried.count(payload_type) != 1 for payload_type in BASELINE_PAYLOAD_TYPES
    ):
        validation_errors.append(
            error(
                "The baseline event interval must carry exactly two payloads, one 'ACTIVE_BASELINE' and one "
                "'RESERVED_BASELINE'. Both must be present even when one of them is zero.",
                "intervals",
                self.intervals,
            )
        )
        return validation_errors

    for payload in interval.payloads:
        if len(payload.values) != 1:
            validation_errors.append(
                error(
                    f"The '{payload.type}' payload must carry exactly one value, the baseline in KW.",
                    "intervals",
                    self.intervals,
                )
            )
        elif not is_power_value(payload.values[0]):
            validation_errors.append(
                error(
                    f"The '{payload.type}' payload value must be a double in KW with at most two decimals.",
                    "intervals",
                    self.intervals,
                )
            )

    return validation_errors


def validate_baseline_event_compliant(event: Event) -> list[InitErrorDetails] | None:
    """
    Validates that an event is a compliant baseline event.

    Args:
        event: The event to validate.

    Returns:
        The validation errors found, or None when the baseline event is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_baseline_targets_compliant(event))
    validation_errors.extend(_baseline_interval_period_compliant(event))
    validation_errors.extend(_baseline_payload_descriptors_compliant(event))
    validation_errors.extend(_baseline_report_descriptors_compliant(event))
    validation_errors.extend(_baseline_intervals_compliant(event))

    return validation_errors or None


# --------------------------------------------------------------------------------------------------------------
# Flex delta override event.
#
# A flex delta override is the BL setting the flexibility of a resource group to a value other than
# the one the Service Provider reported for it, as specified in "Flex delta override event" of the
# OpenADR DER profile specification v1.0.0. It carries the corrected values, the identifier of the
# report it corrects, and a reason per corrected value.
#
# The active and the reserved flex delta are evaluated separately, so the BL MAY override one of them
# and leave the other as reported. What it does override, it MUST give a reason for; what it does not,
# it MUST NOT give a reason for.
#
# One rule of that chapter is about the lifetime of the event rather than its shape and cannot be
# checked from a single object: an override applies until a later flex delta report or override for
# that resource group supersedes it, at which point the BL deletes it.
# --------------------------------------------------------------------------------------------------------------

REPORT_ID_PAYLOAD_TYPE = EventPayloadType("REPORT_ID")
ACTIVE_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE = EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE")
ACTIVE_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE = EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE_REASON")
RESERVED_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE = EventPayloadType("RESERVED_FLEX_DELTA_OVERRIDE")
RESERVED_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE = EventPayloadType("RESERVED_FLEX_DELTA_OVERRIDE_REASON")

# Each override and the reason that MUST accompany it.
OVERRIDE_AND_REASON_PAYLOAD_TYPES = (
    (ACTIVE_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE, ACTIVE_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE),
    (RESERVED_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE, RESERVED_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE),
)

OVERRIDE_PAYLOAD_TYPES = tuple(override for override, _ in OVERRIDE_AND_REASON_PAYLOAD_TYPES)

# Every payload type this event kind may carry, used to recognise the kind.
OVERRIDE_EVENT_PAYLOAD_TYPES = frozenset(
    {
        REPORT_ID_PAYLOAD_TYPE,
        ACTIVE_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE,
        ACTIVE_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE,
        RESERVED_FLEX_DELTA_OVERRIDE_PAYLOAD_TYPE,
        RESERVED_FLEX_DELTA_OVERRIDE_REASON_PAYLOAD_TYPE,
    }
)

# See the "Flex delta override reasons" table. A reason outside this set means the BL should have
# used OTHER, and could propose the reason for a future version of the profile.
KNOWN_OVERRIDE_REASONS = frozenset(
    {
        "CONGESTION_AREA_FLEXIBILITY_EXCEEDED",
        "SHARE_LIMIT_EXCEEDED",
        "DECREASE_NOT_ALLOWED",
        "BASELINE_EXCEEDED",
        "OTHER",
    }
)


def _override_carried_payload_types(self: Event) -> list[EventPayloadType]:
    """Collects the payload types carried across the event's intervals, duplicates included."""
    return [payload.type for interval in self.intervals or () for payload in interval.payloads]


def _override_targets_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the override names exactly one resource group."""
    if not self.targets or len(self.targets) != 1:
        return [
            error(
                "The flex delta override event must target exactly one resource group, identified by its Group-ID.",
                "targets",
                self.targets,
            )
        ]

    return []


def _override_interval_period_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the override is open ended."""
    if self.interval_period is not None:
        return [
            error(
                "The flex delta override event must not define an intervalPeriod at the event level. The "
                "override applies from createdDateTime until it is superseded.",
                "interval_period",
                self.interval_period,
            )
        ]

    return []


def _override_payload_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the payload descriptors of the override.

    The event MUST declare one descriptor for each payload type carried in the interval, with a
    units field of KW on ACTIVE_FLEX_DELTA_OVERRIDE and on RESERVED_FLEX_DELTA_OVERRIDE.
    """
    validation_errors: list[InitErrorDetails] = []
    payload_descriptors = self.payload_descriptors or ()
    declared = [descriptor.payload_type for descriptor in payload_descriptors]
    carried = set(_override_carried_payload_types(self))

    if len(declared) != len(set(declared)) or set(declared) != carried:
        validation_errors.append(
            error(
                "The flex delta override event must declare exactly one payload descriptor for each payload "
                "type carried in its interval.",
                "payload_descriptors",
                self.payload_descriptors,
            )
        )

    if any(
        descriptor.units != Unit.KW
        for descriptor in payload_descriptors
        if descriptor.payload_type in OVERRIDE_PAYLOAD_TYPES
    ):
        validation_errors.append(
            error(
                "The 'ACTIVE_FLEX_DELTA_OVERRIDE' and 'RESERVED_FLEX_DELTA_OVERRIDE' payload descriptors must "
                "have a units field of 'KW'.",
                "payload_descriptors",
                self.payload_descriptors,
            )
        )

    return validation_errors


def _report_id_compliant(self: Event, payloads: Sequence[EventPayload]) -> list[InitErrorDetails]:
    """Validates that the override identifies exactly one flex delta report to correct, by its UUID."""
    report_ids = [payload for payload in payloads if payload.type == REPORT_ID_PAYLOAD_TYPE]

    if len(report_ids) != 1 or len(report_ids[0].values) != 1:
        return [
            error(
                "The flex delta override event interval must carry exactly one 'REPORT_ID' payload with exactly "
                "one value, the object ID of the flex delta report being overridden.",
                "intervals",
                self.intervals,
            )
        ]

    if not is_uuid(report_ids[0].values[0]):
        return [
            error(
                "The 'REPORT_ID' payload value must be the object ID of the flex delta report being overridden, "
                "which is a UUID.",
                "intervals",
                self.intervals,
            )
        ]

    return []


def _override_value_compliant(value: AllowedPayloadInputs) -> bool:
    """Validates one override value: a double in KW, at most two decimals, at most zero."""
    power_value = as_power_value(value)
    return power_value is not None and power_value <= 0


def _overrides_compliant(self: Event, payloads: Sequence[EventPayload]) -> list[InitErrorDetails]:
    """
    Validates the overrides carried and the reason that must accompany each of them.

    The interval MUST carry at least one of ACTIVE_FLEX_DELTA_OVERRIDE and
    RESERVED_FLEX_DELTA_OVERRIDE. Each override carried MUST be accompanied by exactly one matching
    reason, and a reason MUST NOT be carried for an override that is absent.
    """
    validation_errors: list[InitErrorDetails] = []
    carried = [payload.type for payload in payloads]

    if not any(payload_type in carried for payload_type in OVERRIDE_PAYLOAD_TYPES):
        validation_errors.append(
            error(
                "The flex delta override event interval must carry at least one of "
                "'ACTIVE_FLEX_DELTA_OVERRIDE' and 'RESERVED_FLEX_DELTA_OVERRIDE'.",
                "intervals",
                self.intervals,
            )
        )

    for override_type, reason_type in OVERRIDE_AND_REASON_PAYLOAD_TYPES:
        overrides = [payload for payload in payloads if payload.type == override_type]
        reasons = [payload for payload in payloads if payload.type == reason_type]

        if not overrides:
            if reasons:
                validation_errors.append(
                    error(
                        f"The flex delta override event interval must not carry a '{reason_type}' payload when "
                        "the matching override is absent.",
                        "intervals",
                        self.intervals,
                    )
                )
            continue

        if (
            len(overrides) != 1
            or len(overrides[0].values) != 1
            or not _override_value_compliant(overrides[0].values[0])
        ):
            validation_errors.append(
                error(
                    f"The '{override_type}' payload must carry exactly one value in KW, a double with at most "
                    "two decimals, equal to or smaller than zero.",
                    "intervals",
                    self.intervals,
                )
            )

        if len(reasons) != 1 or len(reasons[0].values) != 1 or reasons[0].values[0] not in KNOWN_OVERRIDE_REASONS:
            validation_errors.append(
                error(
                    f"The '{override_type}' payload must be accompanied by exactly one '{reason_type}' payload "
                    "carrying exactly one reason from the flex delta override reasons table.",
                    "intervals",
                    self.intervals,
                )
            )

    return validation_errors


def _override_intervals_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the single interval of the override.

    The event MUST contain exactly one interval with id 0, which MUST NOT define its own
    intervalPeriod.
    """
    validation_errors: list[InitErrorDetails] = []
    intervals = self.intervals or ()

    if len(intervals) != 1:
        return [error("The flex delta override event must contain exactly one interval.", "intervals", self.intervals)]

    interval = intervals[0]

    if interval.id != 0:
        validation_errors.append(
            error("The flex delta override event interval must have an id of 0.", "intervals", self.intervals)
        )

    if interval.interval_period is not None:
        validation_errors.append(
            error(
                "The flex delta override event interval must not define its own intervalPeriod.",
                "intervals",
                self.intervals,
            )
        )

    validation_errors.extend(_report_id_compliant(self, interval.payloads))
    validation_errors.extend(_overrides_compliant(self, interval.payloads))

    return validation_errors


def validate_flex_delta_override_event_compliant(event: Event) -> list[InitErrorDetails] | None:
    """
    Validates that an event is a compliant flex delta override.

    Args:
        event: The event to validate.

    Returns:
        The validation errors found, or None when the override is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_override_targets_compliant(event))
    validation_errors.extend(_override_interval_period_compliant(event))
    validation_errors.extend(_override_payload_descriptors_compliant(event))
    validation_errors.extend(_override_intervals_compliant(event))

    return validation_errors or None


# --------------------------------------------------------------------------------------------------------------
# Flexibility dispatch (FLEX) event.
#
# A flexibility dispatch is the DSO instructing a resource group to deliver part or all of the
# flexibility it has offered, as specified in "Flexibility dispatch event" of the OpenADR DER profile
# specification v1.0.0. Each dispatched interval sets a ceiling on the group's total offtake, equal to
# the group's ACTIVE_BASELINE minus the interval's FLEX value.
#
# Two rules from that chapter cannot be checked against a single event object and are deliberately
# left out:
#
# - The called amount MUST NOT exceed the group's computed ACTIVE_AVAILABLE_FLEX. That value lives on
#   the resource group, not on the event.
# - Once a FLEX value above 0 is called, no FLEX value may be above 0 after the targeted resource
#   group's MAX_DURATION has passed. Same reason.
#
# Both are checked by a caller that holds the resource group; `validate_flex_dispatch_event_compliant`
# accepts optional bounds for exactly that purpose.
# --------------------------------------------------------------------------------------------------------------

FLEX_PAYLOAD_TYPE = EventPayloadType("FLEX")
ACK_PAYLOAD_TYPE = ReportPayloadType("ACK")
DELIVERED_FLEX_PAYLOAD_TYPE = ReportPayloadType("DELIVERED_FLEX")

# The event-level intervalPeriod covers the 24 hours from the publication deadline plus 24h.
EVENT_WINDOW_DURATION = timedelta(days=1)

# The ACK descriptor acknowledges on retrieval; the DELIVERED_FLEX descriptor asks for a single
# report covering every interval, once they have all transpired ([OADR3-UG] section 7.5).
ACK_DESCRIPTOR_FREQUENCY = 0
DELIVERED_FLEX_DESCRIPTOR_FREQUENCY = -1
DELIVERED_FLEX_DESCRIPTOR_REPEAT = 1

REPORT_DESCRIPTOR_COUNT = 2


def _dispatch_payload_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the payload descriptors of the dispatch.

    The flexibility dispatch event MUST declare exactly one FLEX descriptor, with a units field of
    'KW'.
    """
    validation_errors: list[InitErrorDetails] = []
    payload_descriptors = self.payload_descriptors or ()

    if len(payload_descriptors) != 1 or payload_descriptors[0].payload_type != FLEX_PAYLOAD_TYPE:
        validation_errors.append(
            error(
                "The flexibility dispatch event must declare exactly one payload descriptor, with a payload "
                "type of 'FLEX'.",
                "payload_descriptors",
                self.payload_descriptors,
            )
        )
        return validation_errors

    if payload_descriptors[0].units != Unit.KW:
        validation_errors.append(
            error(
                "The FLEX payload descriptor must have a units field of 'KW'.",
                "payload_descriptors",
                self.payload_descriptors,
            )
        )

    return validation_errors


def _dispatch_report_descriptors_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates that the dispatch asks for both an acknowledgment and a delivery report.

    The flexibility dispatch event MUST include exactly two report descriptors: one ACK, instructing
    the VEN to acknowledge receipt on retrieval, and one DELIVERED_FLEX, instructing it to report
    what the group delivered once every interval has transpired.
    """
    validation_errors: list[InitErrorDetails] = []
    report_descriptors = self.report_descriptors or ()

    acknowledgments = [d for d in report_descriptors if d.payload_type == ACK_PAYLOAD_TYPE]
    deliveries = [d for d in report_descriptors if d.payload_type == DELIVERED_FLEX_PAYLOAD_TYPE]

    if len(report_descriptors) != REPORT_DESCRIPTOR_COUNT or len(acknowledgments) != 1 or len(deliveries) != 1:
        validation_errors.append(
            error(
                "The flexibility dispatch event must include exactly two report descriptors, one 'ACK' and one "
                "'DELIVERED_FLEX'.",
                "report_descriptors",
                self.report_descriptors,
            )
        )
        return validation_errors

    if acknowledgments[0].frequency != ACK_DESCRIPTOR_FREQUENCY:
        validation_errors.append(
            error(
                "The ACK report descriptor must set frequency to 0, so that the VEN acknowledges on retrieval.",
                "report_descriptors",
                self.report_descriptors,
            )
        )

    delivery = deliveries[0]
    if (
        delivery.report_intervals != ReportIntervals.INTERVALS
        or delivery.frequency != DELIVERED_FLEX_DESCRIPTOR_FREQUENCY
        or delivery.repeat != DELIVERED_FLEX_DESCRIPTOR_REPEAT
    ):
        validation_errors.append(
            error(
                "The DELIVERED_FLEX report descriptor must set reportIntervals to 'INTERVALS' and leave frequency "
                "and repeat at their OpenADR defaults of -1 and 1.",
                "report_descriptors",
                self.report_descriptors,
            )
        )

    return validation_errors


def _dispatch_targets_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the targeting of the dispatch.

    The targets MUST contain exactly one Group-ID: the resource group the flexibility is called
    from. A FLEX event MUST NOT target more than one resource group, and MUST NOT target individual
    resources or EANs.
    """
    if not self.targets or len(self.targets) != 1:
        return [
            error(
                "The flexibility dispatch event must target exactly one resource group, identified by its Group-ID.",
                "targets",
                self.targets,
            )
        ]

    return []


def _dispatch_interval_period_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates the event-level intervalPeriod.

    A FLEX event MUST define a single intervalPeriod at the event level, with a start equal to the
    publication deadline plus 24h and a duration of P1D. The deadline itself cannot be checked from
    the object; the duration can.
    """
    if self.interval_period is None:
        return [
            error(
                "The flexibility dispatch event must define a single intervalPeriod at the event level.",
                "interval_period",
                self.interval_period,
            )
        ]

    if self.interval_period.duration != EVENT_WINDOW_DURATION:
        return [
            error(
                "The flexibility dispatch event-level intervalPeriod must have a duration of P1D.",
                "interval_period",
                self.interval_period,
            )
        ]

    return []


def _dispatch_intervals_compliant(self: Event) -> list[InitErrorDetails]:  # noqa: C901
    """
    Validates the intervals of the dispatch.

    Ids MUST be unique integers assigned in ascending order starting at 0, every interval MUST define
    its own intervalPeriod of any duration, intervals MUST NOT overlap, and every interval MUST fall
    within the event's own window. Payloads MUST carry exactly one FLEX entry with a
    non-empty list of values, every value a double in KW with at most two decimals, of zero or
    larger.
    """
    validation_errors: list[InitErrorDetails] = []
    intervals = self.intervals or ()

    if not intervals:
        validation_errors.append(
            error("The flexibility dispatch event must contain at least one interval.", "intervals", self.intervals)
        )
        return validation_errors

    previous_id = -1
    placements: list[tuple[int, datetime, datetime]] = []

    for position, interval in enumerate(intervals):
        if interval.id <= previous_id or (position == 0 and interval.id != 0):
            validation_errors.append(
                error(
                    "The flexibility dispatch event interval ids must be unique integers, assigned in ascending "
                    "order starting at 0.",
                    "intervals",
                    self.intervals,
                )
            )
        previous_id = interval.id

        if interval.interval_period is None:
            validation_errors.append(
                error(
                    "Every flexibility dispatch event interval must define its own intervalPeriod.",
                    "intervals",
                    self.intervals,
                )
            )
            continue

        duration = interval.interval_period.duration

        if self.interval_period is not None:
            window_start = self.interval_period.start
            window_end = window_start + self.interval_period.duration
            if interval.interval_period.start < window_start or interval.interval_period.start + duration > window_end:
                validation_errors.append(
                    error(
                        "Every flexibility dispatch event interval must fall within the event-level intervalPeriod.",
                        "intervals",
                        self.intervals,
                    )
                )

        interval_start = interval.interval_period.start
        interval_end = interval_start + duration
        placements.append((position, interval_start, interval_end))

        if len(interval.payloads) != 1 or interval.payloads[0].type != FLEX_PAYLOAD_TYPE:
            validation_errors.append(
                error(
                    "Every flexibility dispatch event interval must carry exactly one payload of type 'FLEX'.",
                    "intervals",
                    self.intervals,
                )
            )
            continue

        values = interval.payloads[0].values
        if not values:
            validation_errors.append(
                error("The FLEX payload must carry at least one value.", "intervals", self.intervals)
            )
            continue

        parsed_values = [as_power_value(value) for value in values]
        flex_values = [flex_value for flex_value in parsed_values if flex_value is not None]
        if len(flex_values) != len(parsed_values):
            validation_errors.append(
                error(
                    "Every FLEX value must be a double in KW with at most two decimals.",
                    "intervals",
                    self.intervals,
                )
            )
            continue

        if any(flex_value < 0 for flex_value in flex_values):
            validation_errors.append(
                error("Every FLEX value must be equal to or larger than zero.", "intervals", self.intervals)
            )

    validation_errors.extend(_overlap_errors(self, placements))

    return validation_errors


def _overlap_errors(self: Event, placements: list[tuple[int, datetime, datetime]]) -> list[InitErrorDetails]:
    """
    Validates that no two intervals overlap.

    Ordered by start rather than by id: the specification is explicit that ids identify an interval
    so a report can point back at it, and MUST NOT be used to determine chronological order.
    """
    chronological = sorted(placements, key=lambda placement: placement[1])

    for first, second in pairwise(chronological):
        if second[1] < first[2]:
            return [
                error(
                    "Flexibility dispatch event intervals must not overlap. Gaps between intervals are allowed.",
                    "intervals",
                    self.intervals,
                )
            ]

    return []


def validate_flex_dispatch_event_compliant(
    event: Event,
    *,
    max_duration: timedelta | None = None,
    max_callable_kw: float | None = None,
) -> list[InitErrorDetails] | None:
    """
    Validates that an event is a compliant flexibility dispatch.

    Args:
        event: The event to validate.
        max_duration: The MAX_DURATION attribute of the targeted resource group, when known. It runs
            from the first FLEX value above 0. Omit to skip the check.
        max_callable_kw: The group's computed ACTIVE_AVAILABLE_FLEX at publication, when known — the
            magnitude of the ACTIVE_FLEX_DELTA in the most recent flex delta report, or of the
            ACTIVE_FLEX_DELTA_OVERRIDE where the BL has overridden it. Omit to skip the check.

    Returns:
        The validation errors found, or None when the dispatch is compliant.

    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_dispatch_payload_descriptors_compliant(event))
    validation_errors.extend(_dispatch_report_descriptors_compliant(event))
    validation_errors.extend(_dispatch_targets_compliant(event))
    validation_errors.extend(_dispatch_interval_period_compliant(event))
    validation_errors.extend(_dispatch_intervals_compliant(event))
    validation_errors.extend(_bounds_compliant(event, max_duration=max_duration, max_callable_kw=max_callable_kw))

    return validation_errors or None


def _bounds_compliant(
    self: Event,
    *,
    max_duration: timedelta | None,
    max_callable_kw: float | None,
) -> list[InitErrorDetails]:
    """
    Validates the dispatch against the properties of the resource group it targets.

    Both bounds live on the resource group rather than on the event, so both are skipped when the
    caller does not supply them.

    MAX_DURATION is a timer that starts at the first moment a FLEX value above 0 is called: once it
    has passed, no FLEX value may be above 0 any more. It does not reset, and gaps do not pause it.
    """
    validation_errors: list[InitErrorDetails] = []

    active_periods = _active_periods(self)
    if max_duration is not None and active_periods:
        deadline = min(start for start, _ in active_periods) + max_duration
        if any(end > deadline for _, end in active_periods):
            validation_errors.append(
                error(
                    "No FLEX value may be above 0 once the MAX_DURATION of the targeted resource group has "
                    "passed since the first FLEX value above 0.",
                    "intervals",
                    self.intervals,
                )
            )

    for interval in self.intervals or ():
        if max_callable_kw is None or len(interval.payloads) != 1:
            continue

        # Values that are not a valid power value are reported by _dispatch_intervals_compliant.
        flex_values = (as_power_value(value) for value in interval.payloads[0].values)
        if any(flex_value is not None and flex_value > max_callable_kw for flex_value in flex_values):
            validation_errors.append(
                error(
                    "The FLEX value must not exceed the ACTIVE_AVAILABLE_FLEX of the targeted resource group. "
                    "Reserved flexibility is never callable.",
                    "intervals",
                    self.intervals,
                )
            )

    return validation_errors


def _active_periods(self: Event) -> list[tuple[datetime, datetime]]:
    """
    Collects the periods during which a FLEX value above 0 is called, one per value.

    An interval's values split its intervalPeriod evenly: with N values, value i covers the i-th
    N-th of the interval. Values that are not a valid power value are reported by
    _dispatch_intervals_compliant and skipped here.
    """
    periods: list[tuple[datetime, datetime]] = []

    for interval in self.intervals or ():
        if interval.interval_period is None or len(interval.payloads) != 1 or not interval.payloads[0].values:
            continue

        values = interval.payloads[0].values
        step = interval.interval_period.duration / len(values)
        for index, value in enumerate(values):
            flex_value = as_power_value(value)
            if flex_value is not None and flex_value > 0:
                start = interval.interval_period.start + index * step
                periods.append((start, start + step))

    return periods


# --------------------------------------------------------------------------------------------------------------
# Discriminator: routes an Event to the kind-specific validator above, based on the payload types it carries.
# --------------------------------------------------------------------------------------------------------------

BASELINE_EVENT_PAYLOAD_TYPES = frozenset({ACTIVE_BASELINE_PAYLOAD_TYPE, RESERVED_BASELINE_PAYLOAD_TYPE})


class EventKind(StrEnum):
    """The kinds of event the OpenADR DER profile specification v1.0.0 defines."""

    REPORTING_ANCHOR = "REPORTING_ANCHOR"
    """The report-only event that gives reports without an originating event an eventID."""

    BASELINE = "BASELINE"
    """The calculated aggregated baseline of a resource group."""

    FLEX_DELTA_OVERRIDE = "FLEX_DELTA_OVERRIDE"
    """The BL correcting the flexibility a Service Provider reported."""

    FLEXIBILITY_DISPATCH = "FLEXIBILITY_DISPATCH"
    """The DSO calling flexibility from a resource group."""


def _carried_payload_types(event: Event) -> frozenset[EventPayloadType]:
    """
    Collects every payload type the event carries.

    The payload descriptors and the interval payloads are unioned rather than read from the
    descriptors alone, so that an event which declares no descriptors still routes to the kind its
    payloads belong to, and is told there that its descriptors are missing.
    """
    declared = {descriptor.payload_type for descriptor in event.payload_descriptors or ()}
    carried = {payload.type for interval in event.intervals or () for payload in interval.payloads}
    return frozenset(declared | carried)


def event_kind(event: Event) -> EventKind | None:
    """
    Determines which kind of event this is, from the payload types it carries.

    Args:
        event: The event to classify.

    Returns:
        The kind of event, or None when the payload types match no kind the profile defines.

    """
    payload_types = _carried_payload_types(event)

    if FLEX_PAYLOAD_TYPE in payload_types:
        return EventKind.FLEXIBILITY_DISPATCH

    if payload_types & BASELINE_EVENT_PAYLOAD_TYPES:
        return EventKind.BASELINE

    if payload_types & OVERRIDE_EVENT_PAYLOAD_TYPES:
        return EventKind.FLEX_DELTA_OVERRIDE

    if not payload_types:
        return EventKind.REPORTING_ANCHOR

    return None


def validate_event_nlflex_compliant(event: Event) -> list[InitErrorDetails] | None:
    """
    Validates that an event is compliant with the OpenADR DER profile specification v1.0.0.

    Dispatches to the applicable object constraints and requirements based on the payload types the
    event carries.

    Args:
        event: The event to validate.

    Returns:
        The validation errors found, or None when the event is compliant.

    """
    kind = event_kind(event)

    if kind is EventKind.FLEXIBILITY_DISPATCH:
        return validate_flex_dispatch_event_compliant(event)

    if kind is EventKind.BASELINE:
        return validate_baseline_event_compliant(event)

    if kind is EventKind.FLEX_DELTA_OVERRIDE:
        return validate_flex_delta_override_event_compliant(event)

    if kind is EventKind.REPORTING_ANCHOR:
        return validate_reporting_anchor_event_compliant(event)

    return [
        error(
            "The event does not match any event kind defined by the profile. An event is identified by the "
            "payload types it carries: 'FLEX' for a flexibility dispatch, 'ACTIVE_BASELINE' and "
            "'RESERVED_BASELINE' for a baseline event, 'REPORT_ID' and the flex delta override payload types "
            "for an override, and none at all for the reporting anchor event.",
            "payload_descriptors",
            event.payload_descriptors,
        )
    ]

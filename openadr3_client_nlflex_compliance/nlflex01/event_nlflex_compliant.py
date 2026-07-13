# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Module which implements NL-Flex 0.1 compliance validators for the event OpenADR3 types.

In this (incomplete) version of the NL-Flex profile, events are only used to communicate the
BASELINE of a resource group to the Service Provider (see Section 11.5.1, "Baseline event" of the
NL-Flex specification). This module validates that events conform to the object constraints and
requirements of a BASELINE event.
"""

from datetime import timedelta

from openadr3_client.oadr310.models.event.event import Event
from openadr3_client.oadr310.models.report.report_payload import ReportPayloadType
from pydantic import TypeAdapter
from pydantic_core import InitErrorDetails, PydanticCustomError

BASELINE_PAYLOAD_TYPE = "BASELINE"
FLEX_DELTA_PAYLOAD_TYPE = ReportPayloadType("FLEX_DELTA")

# The duration of a BASELINE event's intervalPeriod MUST be equal to P9999Y (infinity).
INFINITE_DURATION: timedelta = TypeAdapter(timedelta).validate_python("P9999Y")


def _interval_period_nlflex_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates that the event has a single, event-level intervalPeriod with an infinite duration.

    A BASELINE event MUST define a single intervalPeriod at the event level, with a duration equal
    to P9999Y (infinity), indicating that the event is active until a new BASELINE event is issued.
    """
    validation_errors: list[InitErrorDetails] = []

    if self.interval_period is None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must define an intervalPeriod at the event level.",
                ),
                loc=("interval_period",),
                input=self.interval_period,
                ctx={},
            )
        )
    elif self.interval_period.duration != INFINITE_DURATION:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event intervalPeriod duration must be equal to P9999Y (infinity).",
                ),
                loc=("interval_period",),
                input=self.interval_period,
                ctx={},
            )
        )

    return validation_errors


def _targets_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the event targets the resource group the DR signals apply to."""
    validation_errors: list[InitErrorDetails] = []

    if not self.targets:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must target the resource group the limits apply to.",
                ),
                loc=("targets",),
                input=self.targets,
                ctx={},
            )
        )

    return validation_errors


def _payload_descriptors_nlflex_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates that the payload descriptor of the event is NL-Flex compliant.

    The event MUST declare exactly one BASELINE payload descriptor, with a units field of 'KW'.
    """
    validation_errors: list[InitErrorDetails] = []

    if not self.payload_descriptors:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must have a payload descriptor.",
                ),
                loc=("payload_descriptors",),
                input=self.payload_descriptors,
                ctx={},
            )
        )
        return validation_errors

    if len(self.payload_descriptors) != 1:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must have exactly one payload descriptor.",
                ),
                loc=("payload_descriptors",),
                input=self.payload_descriptors,
                ctx={},
            )
        )

    payload_descriptor = self.payload_descriptors[0]

    if payload_descriptor.payload_type != BASELINE_PAYLOAD_TYPE:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The payload descriptor must have a payload type of 'BASELINE'.",
                ),
                loc=("payload_descriptors",),
                input=self.payload_descriptors,
                ctx={},
            )
        )

    if payload_descriptor.units != "KW":
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The payload descriptor must have a units of 'KW' (case sensitive).",
                ),
                loc=("payload_descriptors",),
                input=self.payload_descriptors,
                ctx={},
            )
        )

    return validation_errors


def _report_descriptors_nlflex_compliant(self: Event) -> list[InitErrorDetails]:
    """Validates that the event instructs the VEN to submit a FLEX_DELTA report."""
    validation_errors: list[InitErrorDetails] = []

    report_descriptors = self.report_descriptors or ()
    flex_delta_report_descriptors = [rd for rd in report_descriptors if rd.payload_type == FLEX_DELTA_PAYLOAD_TYPE]

    if not flex_delta_report_descriptors:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must include a reportDescriptor instructing the VEN to submit a FLEX_DELTA report.",
                ),
                loc=("report_descriptors",),
                input=self.report_descriptors,
                ctx={},
            )
        )

    return validation_errors


def _event_interval_nlflex_compliant(self: Event) -> list[InitErrorDetails]:
    """
    Validates that the event interval is NL-Flex compliant.

    The event MUST contain exactly one interval with id 0. The interval MUST NOT define its own
    intervalPeriod (the event-level intervalPeriod applies), and its payloads MUST carry exactly one
    BASELINE entry.
    """
    validation_errors: list[InitErrorDetails] = []

    intervals = self.intervals or ()

    if len(intervals) != 1:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event must contain exactly one interval.",
                ),
                loc=("intervals",),
                input=self.intervals,
                ctx={},
            )
        )
        return validation_errors

    interval = intervals[0]

    if interval.id != 0:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event interval must have an id value of 0.",
                ),
                loc=("intervals",),
                input=self.intervals,
                ctx={},
            )
        )

    if interval.interval_period is not None:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event interval must not define its own intervalPeriod.",
                ),
                loc=("intervals",),
                input=self.intervals,
                ctx={},
            )
        )

    if len(interval.payloads) != 1:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event interval must have exactly one payload.",
                ),
                loc=("intervals",),
                input=self.intervals,
                ctx={},
            )
        )
    elif interval.payloads[0].type != BASELINE_PAYLOAD_TYPE:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The event interval payload must have a payload type of 'BASELINE'.",
                ),
                loc=("intervals",),
                input=self.intervals,
                ctx={},
            )
        )

    return validation_errors


def validate_event_nlflex_compliant(event: Event) -> list[InitErrorDetails] | None:
    """
    Validates that events are NL-Flex 0.1 compliant.

    Validates the object constraints and requirements of a BASELINE event, as specified in Section
    11.5.1, "Baseline event" of the NL-Flex specification.
    """
    validation_errors: list[InitErrorDetails] = []

    validation_errors.extend(_targets_compliant(event))
    validation_errors.extend(_interval_period_nlflex_compliant(event))
    validation_errors.extend(_payload_descriptors_nlflex_compliant(event))
    validation_errors.extend(_report_descriptors_nlflex_compliant(event))
    validation_errors.extend(_event_interval_nlflex_compliant(event))

    return validation_errors or None

# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Module which implements NL-Flex 0.1 compliance validators for the report OpenADR3 types.

Section 11.6, "Reports" of the NL-Flex specification defines three distinct report shapes that
all use the same underlying OpenADR3 Report object:

- Resource group registration/deregistration reports (Section 11.6.1), discriminated by a
  reportName of RESOURCE_REGISTRATION.
- Flexibility (FLEX_DELTA) reports (Section 11.6.2), which do not have a fixed reportName.
- Operational status reports (Section 11.6.3), discriminated by a reportName of
  OPERATIONAL_STATUS.

This module dispatches on reportName to validate the object constraints and requirements of
whichever report shape applies.
"""

from typing import LiteralString

from openadr3_client.oadr310.models.report.report import Report, ReportResource
from openadr3_client.oadr310.models.report.report_payload import ReportPayloadType
from pydantic_core import InitErrorDetails, PydanticCustomError

REGISTRATION_REPORT_NAME = "RESOURCE_REGISTRATION"
OPERATIONAL_STATUS_REPORT_NAME = "OPERATIONAL_STATUS"

AGGREGATED_REPORT_RESOURCE_NAME = "AGGREGATED_REPORT"

RESOURCE_GROUP_TARGET_PAYLOAD_TYPE = ReportPayloadType("RESOURCE_GROUP_TARGET")
REGISTRATION_REQUEST_PAYLOAD_TYPE = ReportPayloadType("REGISTRATION_REQUEST")
DE_REGISTRATION_REQUEST_PAYLOAD_TYPE = ReportPayloadType("DE_REGISTRATION_REQUEST")
OPERATIONAL_STATUS_PAYLOAD_TYPE = ReportPayloadType("OPERATIONAL_STATUS")
FLEX_DELTA_PAYLOAD_TYPE = ReportPayloadType("FLEX_DELTA")

# See Table 7, "Operational status values" of the NL-Flex specification.
KNOWN_OPERATIONAL_STATUS_VALUES = frozenset({"NORMAL", "ERROR", "PENDING"})

# A registration report interval MUST contain exactly a RESOURCE_GROUP_TARGET and a
# REGISTRATION_REQUEST or DE_REGISTRATION_REQUEST payload (see Section 11.6.1).
REGISTRATION_REPORT_INTERVAL_PAYLOAD_COUNT = 2


def _single_aggregated_report_resource(
    self: Report,
    error_message: LiteralString,
) -> tuple[list[InitErrorDetails], ReportResource | None]:
    """Validates that the report contains exactly one AGGREGATED_REPORT resource entry."""
    validation_errors: list[InitErrorDetails] = []

    if len(self.resources) != 1 or self.resources[0].resource_name != AGGREGATED_REPORT_RESOURCE_NAME:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError("value_error", error_message),
                loc=("resources",),
                input=self.resources,
                ctx={},
            )
        )
        return validation_errors, None

    return validation_errors, self.resources[0]


def _registration_report_compliant(self: Report) -> list[InitErrorDetails]:
    """
    Validates that a RESOURCE_REGISTRATION report is NL-Flex compliant.

    See Section 11.6.1, "Resource group registration and deregistration" of the NL-Flex
    specification.
    """
    validation_errors, aggregated_resource = _single_aggregated_report_resource(
        self,
        "The report must contain exactly one resource entry with resourceName AGGREGATED_REPORT.",
    )

    if aggregated_resource is None:
        return validation_errors

    if len(aggregated_resource.intervals) != 1 or aggregated_resource.intervals[0].id != 0:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The report resource must contain exactly one interval with id 0.",
                ),
                loc=("resources",),
                input=self.resources,
                ctx={},
            )
        )
        return validation_errors

    payloads = aggregated_resource.intervals[0].payloads

    resource_group_target_payloads = [p for p in payloads if p.type == RESOURCE_GROUP_TARGET_PAYLOAD_TYPE]
    registration_payloads = [
        p for p in payloads if p.type in (REGISTRATION_REQUEST_PAYLOAD_TYPE, DE_REGISTRATION_REQUEST_PAYLOAD_TYPE)
    ]

    if (
        len(payloads) != REGISTRATION_REPORT_INTERVAL_PAYLOAD_COUNT
        or len(resource_group_target_payloads) != 1
        or len(registration_payloads) != 1
    ):
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The report interval must contain exactly two payloads: one RESOURCE_GROUP_TARGET and one "
                    "REGISTRATION_REQUEST or DE_REGISTRATION_REQUEST.",
                ),
                loc=("resources",),
                input=self.resources,
                ctx={},
            )
        )
        return validation_errors

    if len(resource_group_target_payloads[0].values) != 1:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The RESOURCE_GROUP_TARGET payload must contain exactly one value, the Group-ID.",
                ),
                loc=("resources",),
                input=self.resources,
                ctx={},
            )
        )

    # Not checked here: registration_payloads[0].values already has at least one entry, since
    # _BasePayload rejects empty values tuples before this validator ever runs.

    return validation_errors


def _flexibility_report_compliant(self: Report) -> list[InitErrorDetails]:
    """
    Validates that a FLEX_DELTA (flexibility) report is NL-Flex compliant.

    See Section 11.6.2, "Flexibility reporting" of the NL-Flex specification.
    """
    validation_errors, aggregated_resource = _single_aggregated_report_resource(
        self,
        "The report must contain exactly one resource entry with resourceName AGGREGATED_REPORT.",
    )

    if aggregated_resource is None:
        return validation_errors

    # Not checked here: aggregated_resource.intervals already has at least one entry, since
    # ReportResource rejects empty intervals tuples before this validator ever runs.
    for interval in aggregated_resource.intervals:
        if len(interval.payloads) != 1 or interval.payloads[0].type != FLEX_DELTA_PAYLOAD_TYPE:
            validation_errors.append(
                InitErrorDetails(
                    type=PydanticCustomError(
                        "value_error",
                        "Each report interval must carry exactly one FLEX_DELTA payload.",
                    ),
                    loc=("resources",),
                    input=self.resources,
                    ctx={},
                )
            )
            continue

        if not all(value <= 0 for value in interval.payloads[0].values):
            validation_errors.append(
                InitErrorDetails(
                    type=PydanticCustomError(
                        "value_error",
                        "The FLEX_DELTA payload values must be zero or negative.",
                    ),
                    loc=("resources",),
                    input=self.resources,
                    ctx={},
                )
            )

    return validation_errors


def _operational_status_report_compliant(self: Report) -> list[InitErrorDetails]:
    """
    Validates that an OPERATIONAL_STATUS report is NL-Flex compliant.

    See Section 11.6.3, "Operational status reporting" of the NL-Flex specification.
    """
    validation_errors: list[InitErrorDetails] = []

    if not self.resources:
        validation_errors.append(
            InitErrorDetails(
                type=PydanticCustomError(
                    "value_error",
                    "The report must contain one resource entry per resource being reported on.",
                ),
                loc=("resources",),
                input=self.resources,
                ctx={},
            )
        )
        return validation_errors

    for resource in self.resources:
        if not resource.intervals or resource.intervals[0].id != 0:
            validation_errors.append(
                InitErrorDetails(
                    type=PydanticCustomError(
                        "value_error",
                        "The report resource must contain at least one interval, with ids starting at 0.",
                    ),
                    loc=("resources",),
                    input=self.resources,
                    ctx={},
                )
            )
            continue

        for interval in resource.intervals:
            if len(interval.payloads) != 1 or interval.payloads[0].type != OPERATIONAL_STATUS_PAYLOAD_TYPE:
                validation_errors.append(
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "value_error",
                            "Each report interval must carry exactly one OPERATIONAL_STATUS payload.",
                        ),
                        loc=("resources",),
                        input=self.resources,
                        ctx={},
                    )
                )
                continue

            payload_values = interval.payloads[0].values
            if len(payload_values) != 1 or payload_values[0] not in KNOWN_OPERATIONAL_STATUS_VALUES:
                validation_errors.append(
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "value_error",
                            "The OPERATIONAL_STATUS payload must contain exactly one value from Table 7, "
                            "'Operational status values'.",
                        ),
                        loc=("resources",),
                        input=self.resources,
                        ctx={},
                    )
                )

    return validation_errors


def validate_report_nlflex_compliant(report: Report) -> list[InitErrorDetails] | None:
    """
    Validates that a report is NL-Flex 0.1 compliant.

    Dispatches to the applicable object constraints and requirements based on the report's
    reportName, as specified in Section 11.6, "Reports" of the NL-Flex specification.
    """
    if report.report_name == REGISTRATION_REPORT_NAME:
        validation_errors = _registration_report_compliant(report)
    elif report.report_name == OPERATIONAL_STATUS_REPORT_NAME:
        validation_errors = _operational_status_report_compliant(report)
    else:
        validation_errors = _flexibility_report_compliant(report)

    return validation_errors or None

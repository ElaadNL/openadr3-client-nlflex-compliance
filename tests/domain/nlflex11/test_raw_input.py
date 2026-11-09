# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest

from openadr3_client_nlflex_compliance.nlflex11.raw_input import (
    validate_raw_event,
    validate_raw_program,
    validate_raw_report,
    validate_raw_resource,
    validate_raw_resource_group,
    validate_raw_ven,
)

DAYS_MESSAGE = "Durations must not use days, such as 'P1D'. Use hours instead, such as 'PT24H'."
FORMAT_MESSAGE = "Durations must be ISO 8601 strings, such as 'PT1H'."
ZULU_MESSAGE = "Timestamps must be RFC 3339 strings in UTC with the 'Z' notation"

# The FLEX event of the DER profile v1.1.0 examples (flex-event.yml), as the VTN returns it.
FLEX_EVENT_EXAMPLE: dict[str, Any] = {
    "id": "f0000000-0000-4000-8000-000000000000",
    "createdDateTime": "2026-01-01T06:00:00.000Z",
    "modificationDateTime": "2026-01-01T06:00:00.000Z",
    "objectType": "EVENT",
    "programID": "dbb3ec95-d96d-449c-b991-154b77491bcd",
    "eventName": "Flex dispatch - GROUP-0001",
    "targets": ["GROUP-0001"],
    "payloadDescriptors": [{"payloadType": "FLEX", "units": "KW"}],
    "reportDescriptors": [
        {"payloadType": "ACK", "aggregate": True, "frequency": 0, "repeat": 1},
        {
            "payloadType": "DELIVERED_FLEX",
            "units": "KW",
            "aggregate": True,
            "reportIntervals": "INTERVALS",
            "frequency": -1,
            "repeat": 1,
        },
    ],
    "intervalPeriod": {"start": "2026-01-01T23:00:00.000Z", "duration": "PT24H"},
    "intervals": [
        {
            "id": 0,
            "intervalPeriod": {"start": "2026-01-02T15:00:00.000Z", "duration": "PT6H"},
            "payloads": [{"type": "FLEX", "values": [0, 0, 0, 0, 200, 200, 200, 200, 0, 0, 0, 0]}],
        }
    ],
}


def _event_with(path: tuple[str | int, ...], value: Any) -> dict[str, Any]:  # noqa: ANN401
    data: dict[str, Any] = {
        "intervalPeriod": {"start": "2026-01-14T00:00:00Z", "duration": "PT24H"},
        "intervals": [{"id": 0, "intervalPeriod": {"start": "2026-01-14T00:00:00Z", "duration": "PT1H"}}],
    }
    node: Any = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def test_the_flex_event_example_raw_is_clean() -> None:
    """The profile's own example passes, so the checks do not reject what the spec shows."""
    assert validate_raw_event(FLEX_EVENT_EXAMPLE) == []


@pytest.mark.parametrize(
    "path",
    [
        ("intervals", 0, "intervalPeriod", "duration"),
        ("intervalPeriod", "duration"),
        ("intervals", 0, "intervalPeriod", "randomizeStart"),
        ("intervalPeriod", "randomizeStart"),
        ("duration",),
    ],
)
def test_p1d_is_rejected_at_event_and_interval_level(path: tuple[str | int, ...]) -> None:
    """A day duration is rejected at every place an event carries a duration."""
    errors = validate_raw_event(_event_with(path, "P1D"))

    assert [error["loc"] for error in errors] == [path]
    assert DAYS_MESSAGE in str(errors[0]["type"])


@pytest.mark.parametrize("duration", ["PT24H", "PT1H30M", "PT15M", "PT0.5S", "-PT1H", "P1W", "P1Y"])
def test_iso8601_duration_without_days_passes(duration: str) -> None:
    """ISO 8601 durations without the day designator pass; weeks and years are not named by the rule."""
    assert validate_raw_event(_event_with(("intervalPeriod", "duration"), duration)) == []


@pytest.mark.parametrize(
    "duration",
    [86400, 86400.0, "86400", "1 day", "P", "PT", "PT1D", "p1d", "P1\N{ARABIC-INDIC DIGIT ONE}D"],
    ids=["int", "float", "digit-string", "free-text", "bare-p", "bare-pt", "day-in-time", "lowercase", "arabic-indic"],
)
def test_a_numeric_duration_is_rejected(duration: object) -> None:
    """Shapes the parser accepts or OpenADR does not define, such as a number of seconds, are rejected."""
    errors = validate_raw_event(_event_with(("intervalPeriod", "duration"), duration))

    assert [error["loc"] for error in errors] == [("intervalPeriod", "duration")]
    assert FORMAT_MESSAGE in str(errors[0]["type"])


@pytest.mark.parametrize("ts", ["2026-01-13T23:00:00+00:00", "2026-01-14T00:00:00+01:00"])
def test_a_plus_01_00_timestamp_is_rejected(ts: str) -> None:
    """An offset notation is rejected even when it denotes UTC."""
    start = validate_raw_event(_event_with(("intervalPeriod", "start"), ts))
    interval_start = validate_raw_event(_event_with(("intervals", 0, "intervalPeriod", "start"), ts))
    created = validate_raw_event({"createdDateTime": ts})

    assert [error["loc"] for error in start] == [("intervalPeriod", "start")]
    assert [error["loc"] for error in interval_start] == [("intervals", 0, "intervalPeriod", "start")]
    assert [error["loc"] for error in created] == [("createdDateTime",)]
    assert ZULU_MESSAGE in str(created[0]["type"])


@pytest.mark.parametrize(
    "ts",
    [1768345200, 1768345200.0, "1768345200", "2026-01-13T23:00Z", "2026-01-13 23:00:00Z", "20260113T230000Z"],
    ids=["epoch-int", "epoch-float", "epoch-string", "no-seconds", "space-separator", "basic-format"],
)
def test_non_rfc3339_timestamp_fails(ts: object) -> None:
    """Shapes the parser accepts but RFC 3339 does not, such as Unix epoch numbers, are rejected."""
    errors = validate_raw_event({"createdDateTime": ts})

    assert [error["loc"] for error in errors] == [("createdDateTime",)]
    assert ZULU_MESSAGE in str(errors[0]["type"])


@pytest.mark.parametrize(
    "ts", ["2026-01-14T00:00:00Z", "2026-01-14T00:00:00z", "2026-01-14t00:00:00Z", "2026-01-14T00:00:00.000Z"]
)
def test_rfc3339_zulu_passes(ts: str) -> None:
    """Milliseconds are a SHOULD in the profile, so a timestamp without them passes."""
    assert validate_raw_event({"createdDateTime": ts, "modificationDateTime": ts}) == []


def test_free_text_is_not_flagged() -> None:
    """Only the listed fields are read, so a name that looks like a duration is never flagged."""
    assert validate_raw_event({"eventName": "P1D"}) == []


def test_absent_and_null_fields_are_skipped() -> None:
    """Missing and null values are skipped; the fields are optional."""
    data = {"intervalPeriod": None, "duration": None, "createdDateTime": None}

    assert validate_raw_event(data) == []
    assert validate_raw_event({"intervals": None}) == []
    assert validate_raw_event({"intervals": ["x", {"intervalPeriod": None}]}) == []
    assert validate_raw_report({"resources": None}) == []
    assert validate_raw_report({"resources": ["x", {"intervalPeriod": None, "intervals": None}]}) == []


def test_program_checks_audit_timestamps_and_interval_period() -> None:
    """A program carries audit timestamps and an optional intervalPeriod."""
    ts = "2026-01-14T00:00:00+01:00"

    errors = validate_raw_program({"createdDateTime": ts, "intervalPeriod": {"duration": "P1D"}})

    assert [error["loc"] for error in errors] == [("createdDateTime",), ("intervalPeriod", "duration")]


@pytest.mark.parametrize("validate", [validate_raw_ven, validate_raw_resource, validate_raw_resource_group])
def test_ven_resource_and_resource_group_check_audit_timestamps(validate: Any) -> None:  # noqa: ANN401
    """These objects carry no duration fields, only the two audit timestamps."""
    ts = "2026-01-14T00:00:00+01:00"

    errors = validate({"createdDateTime": ts, "modificationDateTime": ts, "intervalPeriod": {"duration": "P1D"}})

    assert [error["loc"] for error in errors] == [("createdDateTime",), ("modificationDateTime",)]


def test_report_checks_audit_timestamps_and_resource_and_interval_periods() -> None:
    """A report holds its periods per resource and per interval, never at report level."""
    ts = "2026-01-14T00:00:00+01:00"
    data = {
        "createdDateTime": ts,
        "resources": [
            {
                "resourceName": "AGGREGATED_REPORT",
                "intervalPeriod": {"start": ts, "duration": "P1D"},
                "intervals": [{"id": 0, "intervalPeriod": {"duration": "P1D", "randomizeStart": "P1D"}}],
            }
        ],
    }

    errors = validate_raw_report(data)

    assert [error["loc"] for error in errors] == [
        ("createdDateTime",),
        ("resources", 0, "intervalPeriod", "start"),
        ("resources", 0, "intervalPeriod", "duration"),
        ("resources", 0, "intervals", 0, "intervalPeriod", "duration"),
        ("resources", 0, "intervals", 0, "intervalPeriod", "randomizeStart"),
    ]


def test_a_clean_report_passes() -> None:
    """A report without a timestamp or duration problem has no errors."""
    data = {
        "createdDateTime": "2026-01-01T06:00:00.000Z",
        "resources": [{"resourceName": "AGGREGATED_REPORT", "intervals": [{"id": 0, "payloads": []}]}],
    }

    assert validate_raw_report(data) == []

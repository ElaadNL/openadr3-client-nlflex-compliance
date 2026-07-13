# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from openadr3_client._models.common.interval import Interval
from openadr3_client._models.common.interval_period import IntervalPeriod
from openadr3_client.oadr310.models.event.event import NewEvent
from openadr3_client.oadr310.models.event.event_payload import (
    EventPayload,
    EventPayloadDescriptor,
    EventPayloadType,
)
from openadr3_client.oadr310.models.report.report_payload import (
    ReportDescriptor,
    ReportPayloadType,
    ReportReadingType,
)
from openadr3_client.oadr310.models.unit import Unit
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex01.event_nlflex_compliant import INFINITE_DURATION
from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

_UNSET: Any = object()

BASELINE_EVENT_PAYLOAD_TYPE = EventPayloadType("BASELINE")


def _default_valid_targets() -> tuple[str, ...]:
    """Helper function to create a default target that is NL-Flex compliant."""
    return ("GROUP-0001",)


def _default_valid_interval_period() -> IntervalPeriod:
    """Helper function to create a default intervalPeriod that is NL-Flex compliant."""
    return IntervalPeriod(start=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC), duration=INFINITE_DURATION)


def _default_valid_payload_descriptors() -> tuple[EventPayloadDescriptor, ...]:
    """Helper function to create a default payload descriptor that is NL-Flex compliant."""
    return (EventPayloadDescriptor(payload_type=BASELINE_EVENT_PAYLOAD_TYPE, units=Unit.KW),)


def _default_valid_report_descriptors() -> tuple[ReportDescriptor, ...]:
    """Helper function to create a default report descriptor that is NL-Flex compliant."""
    return (
        ReportDescriptor(
            payload_type=ReportPayloadType("FLEX_DELTA"),
            reading_type=ReportReadingType("AGGREGATED_REPORT"),
            units=Unit.KW,
            aggregate=True,
            repeat=-1,
        ),
    )


def _default_valid_intervals() -> tuple[Interval[EventPayload], ...]:
    """Helper function to create a default interval that is NL-Flex compliant."""
    return (
        Interval(
            id=0,
            interval_period=None,
            payloads=(EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(200,)),),
        ),
    )


def _create_event(
    targets: tuple[str, ...] | None = _UNSET,
    interval_period: IntervalPeriod | None = _UNSET,
    payload_descriptors: tuple[EventPayloadDescriptor, ...] | None = _UNSET,
    report_descriptors: tuple[ReportDescriptor, ...] | None = _UNSET,
    intervals: tuple[Interval[EventPayload], ...] = _UNSET,
) -> NewEvent:
    """
    Helper function to create an event with the specified values.

    Any argument left unset defaults to a NL-Flex compliant BASELINE event value. Passing
    ``None`` explicitly is preserved, to allow testing the absence of a field.
    """
    return NewEvent(
        programID="test-program",
        event_name="test-event",
        targets=_default_valid_targets() if targets is _UNSET else targets,
        interval_period=_default_valid_interval_period() if interval_period is _UNSET else interval_period,
        payload_descriptors=(
            _default_valid_payload_descriptors() if payload_descriptors is _UNSET else payload_descriptors
        ),
        report_descriptors=(
            _default_valid_report_descriptors() if report_descriptors is _UNSET else report_descriptors
        ),
        intervals=_default_valid_intervals() if intervals is _UNSET else intervals,
    )


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the NL-Flex plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


def test_baseline_event_valid() -> None:
    """Test that a fully NL-Flex compliant BASELINE event is accepted."""
    event = _create_event()

    assert event.targets == _default_valid_targets()
    assert event.intervals is not None
    assert event.intervals[0].id == 0


def test_missing_interval_period() -> None:
    """Test that an event without an event-level intervalPeriod raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event must define an intervalPeriod at the event level."),
    ):
        _ = _create_event(interval_period=None)


def test_interval_period_duration_not_infinite() -> None:
    """Test that an event with a finite intervalPeriod duration raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event intervalPeriod duration must be equal to P9999Y (infinity)."),
    ):
        _ = _create_event(
            interval_period=IntervalPeriod(
                start=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC), duration=timedelta(hours=1)
            ),
        )


def test_missing_targets() -> None:
    """Test that an event without targets raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event must target the resource group the limits apply to."),
    ):
        _ = _create_event(targets=())


def test_no_payload_descriptors() -> None:
    """Test that an event with no payload descriptor raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The event must have a payload descriptor.")):
        _ = _create_event(payload_descriptors=None)


def test_multiple_payload_descriptors() -> None:
    """Test that an event with multiple payload descriptors raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The event must have exactly one payload descriptor.")):
        _ = _create_event(
            payload_descriptors=(
                EventPayloadDescriptor(payload_type=BASELINE_EVENT_PAYLOAD_TYPE, units=Unit.KW),
                EventPayloadDescriptor(payload_type=EventPayloadType.SIMPLE, units=Unit.KW),
            ),
        )


def test_invalid_payload_type_in_descriptor() -> None:
    """Test that an invalid payload type in the payload descriptor raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The payload descriptor must have a payload type of 'BASELINE'."),
    ):
        _ = _create_event(
            payload_descriptors=(EventPayloadDescriptor(payload_type=EventPayloadType.SIMPLE, units=Unit.KW),),
        )


def test_invalid_unit_in_descriptor() -> None:
    """Test that an invalid unit in the payload descriptor raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The payload descriptor must have a units of 'KW'")):
        _ = _create_event(
            payload_descriptors=(EventPayloadDescriptor(payload_type=BASELINE_EVENT_PAYLOAD_TYPE, units=Unit.KVA),),
        )


def test_missing_flex_delta_report_descriptor() -> None:
    """Test that an event without a FLEX_DELTA report descriptor raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event must include a reportDescriptor instructing the VEN to submit a FLEX_DELTA report."),
    ):
        _ = _create_event(report_descriptors=None)


def test_multiple_intervals_not_allowed() -> None:
    """Test that an event with more than one interval raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The event must contain exactly one interval.")):
        _ = _create_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(200,)),),
                ),
                Interval(
                    id=1,
                    interval_period=None,
                    payloads=(EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(100,)),),
                ),
            ),
        )


def test_interval_id_not_zero() -> None:
    """Test that an event interval with an id other than 0 raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The event interval must have an id value of 0.")):
        _ = _create_event(
            intervals=(
                Interval(
                    id=1,
                    interval_period=None,
                    payloads=(EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(200,)),),
                ),
            ),
        )


def test_interval_own_interval_period_not_allowed() -> None:
    """Test that an event interval with its own intervalPeriod raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event interval must not define its own intervalPeriod."),
    ):
        _ = _create_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=IntervalPeriod(
                        start=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
                        duration=INFINITE_DURATION,
                    ),
                    payloads=(EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(200,)),),
                ),
            ),
        )


def test_interval_multiple_payloads_not_allowed() -> None:
    """Test that an event interval with multiple payloads raises an error."""
    with pytest.raises(ValidationError, match=re.escape("The event interval must have exactly one payload.")):
        _ = _create_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(
                        EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(200,)),
                        EventPayload(type=BASELINE_EVENT_PAYLOAD_TYPE, values=(100,)),
                    ),
                ),
            ),
        )


def test_interval_payload_type_invalid() -> None:
    """Test that an event interval with an invalid payload type raises an error."""
    with pytest.raises(
        ValidationError,
        match=re.escape("The event interval payload must have a payload type of 'BASELINE'."),
    ):
        _ = _create_event(
            intervals=(
                Interval(
                    id=0, interval_period=None, payloads=(EventPayload(type=EventPayloadType.SIMPLE, values=(200,)),)
                ),
            ),
        )


def test_event_multiple_errors_grouped() -> None:
    """Test that multiple errors are grouped together and returned as a single error."""
    with pytest.raises(
        ValidationError,
        match="2 validation errors for NewEvent",
    ) as exc_info:
        _ = _create_event(targets=(), report_descriptors=None)

    grouped_errors = exc_info.value.errors()

    assert len(grouped_errors) == 2
    assert grouped_errors[0].get("type") == "value_error"
    assert grouped_errors[1].get("type") == "value_error"
    assert grouped_errors[0].get("msg") == "The event must target the resource group the limits apply to."
    assert (
        grouped_errors[1].get("msg")
        == "The event must include a reportDescriptor instructing the VEN to submit a FLEX_DELTA report."
    )


def test_plugin_system_integration() -> None:
    """Test that the plugin system correctly integrates with the Event validation."""
    validators = ValidatorPluginRegistry.get_model_validators(NewEvent)
    assert len(validators) == 1

    valid_event = _create_event()
    assert valid_event.event_name == "test-event"

    with pytest.raises(ValidationError) as exc_info:
        _create_event(targets=(), report_descriptors=None)

    errors = exc_info.value.errors()
    assert len(errors) == 2

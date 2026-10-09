# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

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
    ReportIntervals,
    ReportPayloadType,
)
from openadr3_client.oadr310.models.unit import Unit

from openadr3_client_nlflex_compliance.nlflex10.event_nlflex_compliant import (
    EventKind,
    event_kind,
    validate_baseline_event_compliant,
    validate_event_nlflex_compliant,
    validate_flex_delta_override_event_compliant,
    validate_flex_dispatch_event_compliant,
    validate_reporting_anchor_event_compliant,
)

_UNSET: Any = object()

# The worked example of "Flexibility dispatch event": a window opening at the publication deadline
# plus 24h, holding a PT4H dispatch of 200 KW flanked by an hour of FLEX 0 either side.
WINDOW_START = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)


def _anchor_event() -> NewEvent:
    """Helper function to create the compliant reporting anchor event of the specification."""
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="Reporting anchor",
        report_descriptors=(
            ReportDescriptor(payload_type=ReportPayloadType("REGISTRATION_REQUEST"), frequency=0, repeat=-1),
            ReportDescriptor(payload_type=ReportPayloadType("DE_REGISTRATION_REQUEST"), frequency=0, repeat=-1),
            ReportDescriptor(payload_type=ReportPayloadType("OPERATIONAL_STATUS"), frequency=0, repeat=-1),
        ),
    )


def _baseline_event() -> NewEvent:
    """Helper function to create the compliant baseline event of the specification."""
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="DER limits - GROUP-0001",
        targets=("GROUP-0001",),
        payload_descriptors=(
            EventPayloadDescriptor(payload_type=EventPayloadType("ACTIVE_BASELINE"), units=Unit.KW),
            EventPayloadDescriptor(payload_type=EventPayloadType("RESERVED_BASELINE"), units=Unit.KW),
        ),
        report_descriptors=(
            ReportDescriptor(
                payload_type=ReportPayloadType("ACTIVE_FLEX_DELTA"),
                units=Unit.KW,
                aggregate=True,
                report_intervals=ReportIntervals.OPEN_INTERVALS,
                frequency=0,
                repeat=-1,
            ),
            ReportDescriptor(
                payload_type=ReportPayloadType("RESERVED_FLEX_DELTA"),
                units=Unit.KW,
                aggregate=True,
                report_intervals=ReportIntervals.OPEN_INTERVALS,
                frequency=0,
                repeat=-1,
            ),
        ),
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(
                    EventPayload(type=EventPayloadType("ACTIVE_BASELINE"), values=(500,)),
                    EventPayload(type=EventPayloadType("RESERVED_BASELINE"), values=(500,)),
                ),
            ),
        ),
    )


def _override_event() -> NewEvent:
    """Helper function to create the compliant flex delta override event of the specification."""
    payloads = (
        EventPayload(type=EventPayloadType("REPORT_ID"), values=("c0000000-0000-4000-8000-000000000000",)),
        EventPayload(type=EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE"), values=(-300,)),
        EventPayload(type=EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE_REASON"), values=("DECREASE_NOT_ALLOWED",)),
    )
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="Flex delta override - GROUP-0001",
        targets=("GROUP-0001",),
        payload_descriptors=(
            EventPayloadDescriptor(payload_type=EventPayloadType("REPORT_ID")),
            EventPayloadDescriptor(payload_type=EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE"), units=Unit.KW),
            EventPayloadDescriptor(payload_type=EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE_REASON")),
        ),
        intervals=(Interval(id=0, interval_period=None, payloads=payloads),),
    )


def _dispatch_event() -> NewEvent:
    """Helper function to create the compliant flexibility dispatch event of the specification."""
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="Flex dispatch - GROUP-0001",
        targets=("GROUP-0001",),
        payload_descriptors=(EventPayloadDescriptor(payload_type=EventPayloadType("FLEX"), units=Unit.KW),),
        report_descriptors=(
            ReportDescriptor(payload_type=ReportPayloadType("ACK"), aggregate=True, frequency=0, repeat=1),
            ReportDescriptor(
                payload_type=ReportPayloadType("DELIVERED_FLEX"),
                units=Unit.KW,
                aggregate=True,
                report_intervals=ReportIntervals.INTERVALS,
                frequency=-1,
                repeat=1,
            ),
        ),
        interval_period=IntervalPeriod(start=WINDOW_START, duration=timedelta(hours=24)),
        intervals=(
            Interval(
                id=0,
                interval_period=IntervalPeriod(
                    start=datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC), duration=timedelta(hours=4)
                ),
                payloads=(EventPayload(type=EventPayloadType("FLEX"), values=(200,)),),
            ),
        ),
    )


def test_the_anchor_event_is_recognised() -> None:
    """An event carrying no payload types at all is the report-only anchor event."""
    assert event_kind(_anchor_event()) is EventKind.REPORTING_ANCHOR


def test_the_baseline_event_is_recognised() -> None:
    """ACTIVE_BASELINE and RESERVED_BASELINE identify a baseline event."""
    assert event_kind(_baseline_event()) is EventKind.BASELINE


def test_the_override_event_is_recognised() -> None:
    """REPORT_ID and the override payload types identify a flex delta override."""
    assert event_kind(_override_event()) is EventKind.FLEX_DELTA_OVERRIDE


def test_the_dispatch_event_is_recognised() -> None:
    """FLEX identifies a flexibility dispatch."""
    assert event_kind(_dispatch_event()) is EventKind.FLEXIBILITY_DISPATCH


def test_an_event_is_recognised_from_its_interval_payloads_alone() -> None:
    """An event that declares no descriptors still routes to the right kind, and is told what it is missing."""
    event = NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        targets=("GROUP-0001",),
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(
                    EventPayload(type=EventPayloadType("ACTIVE_BASELINE"), values=(500,)),
                    EventPayload(type=EventPayloadType("RESERVED_BASELINE"), values=(500,)),
                ),
            ),
        ),
    )

    assert event_kind(event) is EventKind.BASELINE

    errors = validate_event_nlflex_compliant(event)
    assert errors is not None
    assert any("exactly two payload descriptors" in str(error["type"]) for error in errors)


def test_an_unrecognised_event_kind_is_reported_as_such() -> None:
    """An event carrying a foreign payload type is not silently validated as some other kind."""
    event = NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        targets=("GROUP-0001",),
        payload_descriptors=(EventPayloadDescriptor(payload_type=EventPayloadType.PRICE),),
        intervals=(
            Interval(id=0, interval_period=None, payloads=(EventPayload(type=EventPayloadType.PRICE, values=(10,)),)),
        ),
    )

    assert event_kind(event) is None

    errors = validate_event_nlflex_compliant(event)
    assert errors is not None
    assert len(errors) == 1
    assert any("does not match any event kind" in str(error["type"]) for error in errors)


def test_every_compliant_event_kind_validates_clean() -> None:
    """Each of the four kinds routes to its own validator and passes it."""
    for event in (_anchor_event(), _baseline_event(), _override_event(), _dispatch_event()):
        assert validate_event_nlflex_compliant(event) is None


def test_a_dispatch_event_is_validated_against_dispatch_rules() -> None:
    """A broken dispatch is told about dispatch rules, not about baseline rules."""
    event = NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        targets=("GROUP-0001", "GROUP-0002"),
        payload_descriptors=(EventPayloadDescriptor(payload_type=EventPayloadType("FLEX"), units=Unit.KW),),
        report_descriptors=_dispatch_event().report_descriptors,
        interval_period=IntervalPeriod(start=WINDOW_START, duration=timedelta(hours=24)),
        intervals=_dispatch_event().intervals,
    )

    errors = validate_event_nlflex_compliant(event)

    assert errors is not None
    assert any("exactly one resource group" in str(error["type"]) for error in errors)
    assert not any("baseline" in str(error["type"]).lower() for error in errors)


# --- Reporting anchor event ----------------------------------------------------------------------


def _default_valid_anchor_report_descriptors() -> tuple[ReportDescriptor, ...]:
    """Helper function to create the three ad hoc report descriptors an anchor event declares."""
    return (
        ReportDescriptor(payload_type=ReportPayloadType("REGISTRATION_REQUEST"), frequency=0, repeat=-1),
        ReportDescriptor(payload_type=ReportPayloadType("DE_REGISTRATION_REQUEST"), frequency=0, repeat=-1),
        ReportDescriptor(payload_type=ReportPayloadType("OPERATIONAL_STATUS"), frequency=0, repeat=-1),
    )


def _create_anchor_event(
    targets: tuple[str, ...] | None = _UNSET,
    interval_period: IntervalPeriod | None = _UNSET,
    report_descriptors: tuple[ReportDescriptor, ...] | None = _UNSET,
    intervals: tuple[Interval[EventPayload], ...] | None = _UNSET,
) -> NewEvent:
    """
    Helper function to create an event with the specified values.

    Any argument left unset defaults to a compliant reporting anchor event value. Passing ``None``
    explicitly is preserved, to allow testing the absence of a field.
    """
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="Reporting anchor",
        targets=None if targets is _UNSET else targets,
        interval_period=None if interval_period is _UNSET else interval_period,
        payload_descriptors=None,
        report_descriptors=(
            _default_valid_anchor_report_descriptors() if report_descriptors is _UNSET else report_descriptors
        ),
        intervals=None if intervals is _UNSET else intervals,
    )


def test_reporting_anchor_event_valid() -> None:
    """An anchor event matching the specification's example is compliant."""
    assert validate_reporting_anchor_event_compliant(_create_anchor_event()) is None


def test_targets_must_not_be_set() -> None:
    """The anchor event is public, so every VEN in the program can see it and report against it."""
    errors = validate_reporting_anchor_event_compliant(_create_anchor_event(targets=("GROUP-0001",)))

    assert errors is not None
    assert any("must not define any targets" in str(error["type"]) for error in errors)


def test_interval_period_must_not_be_defined() -> None:
    """The anchor event has no temporal span of its own and never expires."""
    event = _create_anchor_event(
        interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1))
    )

    errors = validate_reporting_anchor_event_compliant(event)

    assert errors is not None
    assert any("must not define an intervalPeriod" in str(error["type"]) for error in errors)


def test_intervals_must_not_be_defined() -> None:
    """A report-only event has no intervals."""
    event = _create_anchor_event(
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(EventPayload(type=EventPayloadType("ACTIVE_BASELINE"), values=(500,)),),
            ),
        )
    )

    errors = validate_reporting_anchor_event_compliant(event)

    assert errors is not None
    assert any("must not define any intervals" in str(error["type"]) for error in errors)


def test_all_three_report_descriptors_are_required() -> None:
    """Dropping one leaves a report shape with no event to reference."""
    errors = validate_reporting_anchor_event_compliant(
        _create_anchor_event(report_descriptors=_default_valid_anchor_report_descriptors()[:2])
    )

    assert errors is not None
    assert any("exactly one report descriptor for 'OPERATIONAL_STATUS'" in str(error["type"]) for error in errors)


def test_a_duplicated_report_descriptor_is_rejected() -> None:
    """Exactly one descriptor per payload type."""
    descriptors = _default_valid_anchor_report_descriptors()
    errors = validate_reporting_anchor_event_compliant(
        _create_anchor_event(report_descriptors=(*descriptors, descriptors[0]))
    )

    assert errors is not None
    assert any("exactly one report descriptor for 'REGISTRATION_REQUEST'" in str(error["type"]) for error in errors)


def test_an_unknown_report_descriptor_is_rejected() -> None:
    """The anchor event asks for these three report streams and nothing else."""
    errors = validate_reporting_anchor_event_compliant(
        _create_anchor_event(
            report_descriptors=(
                *_default_valid_anchor_report_descriptors(),
                ReportDescriptor(payload_type=ReportPayloadType("DELIVERED_FLEX"), frequency=0, repeat=-1),
            )
        )
    )

    assert errors is not None
    assert any("exactly three report descriptors" in str(error["type"]) for error in errors)


def test_report_descriptors_are_required() -> None:
    """An anchor event with no report descriptors asks for nothing and serves no purpose."""
    errors = validate_reporting_anchor_event_compliant(_create_anchor_event(report_descriptors=None))

    assert errors is not None
    assert any("exactly three report descriptors" in str(error["type"]) for error in errors)


def test_report_descriptors_must_be_ad_hoc() -> None:
    """Frequency 0 means the VEN reports at moments of its own choosing."""
    errors = validate_reporting_anchor_event_compliant(
        _create_anchor_event(
            report_descriptors=(
                ReportDescriptor(payload_type=ReportPayloadType("REGISTRATION_REQUEST"), frequency=-1, repeat=-1),
                *_default_valid_anchor_report_descriptors()[1:],
            )
        )
    )

    assert errors is not None
    assert any("frequency to 0 and repeat to -1" in str(error["type"]) for error in errors)


def test_report_descriptors_must_repeat_indefinitely() -> None:
    """Repeat -1 means for the whole time the program is in use."""
    errors = validate_reporting_anchor_event_compliant(
        _create_anchor_event(
            report_descriptors=(
                ReportDescriptor(payload_type=ReportPayloadType("REGISTRATION_REQUEST"), frequency=0, repeat=1),
                *_default_valid_anchor_report_descriptors()[1:],
            )
        )
    )

    assert errors is not None
    assert any("frequency to 0 and repeat to -1" in str(error["type"]) for error in errors)


# --- Baseline event --------------------------------------------------------------------------

ACTIVE_BASELINE = EventPayloadType("ACTIVE_BASELINE")
RESERVED_BASELINE = EventPayloadType("RESERVED_BASELINE")


def _default_valid_baseline_payload_descriptors() -> tuple[EventPayloadDescriptor, ...]:
    """Helper function to create the two baseline payload descriptors, both in KW."""
    return (
        EventPayloadDescriptor(payload_type=ACTIVE_BASELINE, units=Unit.KW),
        EventPayloadDescriptor(payload_type=RESERVED_BASELINE, units=Unit.KW),
    )


def _baseline_flex_delta_descriptor(payload_type: str) -> ReportDescriptor:
    """Helper function to create one open ended, ad hoc flex delta report descriptor."""
    return ReportDescriptor(
        payload_type=ReportPayloadType(payload_type),
        units=Unit.KW,
        aggregate=True,
        report_intervals=ReportIntervals.OPEN_INTERVALS,
        frequency=0,
        repeat=-1,
    )


def _default_valid_baseline_report_descriptors() -> tuple[ReportDescriptor, ...]:
    """Helper function to create the two flex delta report descriptors a baseline event carries."""
    return (
        _baseline_flex_delta_descriptor("ACTIVE_FLEX_DELTA"),
        _baseline_flex_delta_descriptor("RESERVED_FLEX_DELTA"),
    )


def _default_valid_baseline_intervals() -> tuple[Interval[EventPayload], ...]:
    """Helper function to create the single interval carrying both baselines."""
    return (
        Interval(
            id=0,
            interval_period=None,
            payloads=(
                EventPayload(type=ACTIVE_BASELINE, values=(500,)),
                EventPayload(type=RESERVED_BASELINE, values=(500,)),
            ),
        ),
    )


def _create_baseline_event(
    targets: tuple[str, ...] | None = _UNSET,
    interval_period: IntervalPeriod | None = _UNSET,
    payload_descriptors: tuple[EventPayloadDescriptor, ...] | None = _UNSET,
    report_descriptors: tuple[ReportDescriptor, ...] | None = _UNSET,
    intervals: tuple[Interval[EventPayload], ...] | None = _UNSET,
) -> NewEvent:
    """
    Helper function to create an event with the specified values.

    Any argument left unset defaults to a compliant baseline event value. Passing ``None``
    explicitly is preserved, to allow testing the absence of a field.
    """
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="DER limits - GROUP-0001",
        targets=("GROUP-0001",) if targets is _UNSET else targets,
        interval_period=None if interval_period is _UNSET else interval_period,
        payload_descriptors=(
            _default_valid_baseline_payload_descriptors() if payload_descriptors is _UNSET else payload_descriptors
        ),
        report_descriptors=(
            _default_valid_baseline_report_descriptors() if report_descriptors is _UNSET else report_descriptors
        ),
        intervals=_default_valid_baseline_intervals() if intervals is _UNSET else intervals,
    )


def test_baseline_event_valid() -> None:
    """A baseline event matching the specification's example is compliant."""
    assert validate_baseline_event_compliant(_create_baseline_event()) is None


def test_targets_are_required() -> None:
    """The event targets the resource group the limits apply to."""
    errors = validate_baseline_event_compliant(_create_baseline_event(targets=()))

    assert errors is not None
    assert any("must target the resource group" in str(error["type"]) for error in errors)


def test_baseline_event_level_interval_period_is_rejected() -> None:
    """v1.0.0 forbids what the v0.1 draft required: the event's validity has no end."""
    event = _create_baseline_event(
        interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1))
    )

    errors = validate_baseline_event_compliant(event)

    assert errors is not None
    assert any("must not define an intervalPeriod at the event level" in str(error["type"]) for error in errors)


def test_both_payload_descriptors_are_required() -> None:
    """A single BASELINE descriptor was the draft's shape; v1.0.0 splits it in two."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            payload_descriptors=(EventPayloadDescriptor(payload_type=ACTIVE_BASELINE, units=Unit.KW),)
        )
    )

    assert errors is not None
    assert any("exactly two payload descriptors" in str(error["type"]) for error in errors)


def test_baseline_payload_descriptor_units_must_be_kw() -> None:
    """The units field MUST be KW on both descriptors."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            payload_descriptors=(
                EventPayloadDescriptor(payload_type=ACTIVE_BASELINE, units=Unit.KW),
                EventPayloadDescriptor(payload_type=RESERVED_BASELINE, units=Unit.KWH),
            )
        )
    )

    assert errors is not None
    assert any("units field of 'KW'" in str(error["type"]) for error in errors)


def test_both_flex_delta_report_descriptors_are_required() -> None:
    """The VEN answers a baseline event with an active and a reserved flex delta."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(report_descriptors=(_baseline_flex_delta_descriptor("ACTIVE_FLEX_DELTA"),))
    )

    assert errors is not None
    assert any("'RESERVED_FLEX_DELTA'" in str(error["type"]) for error in errors)


def test_report_descriptors_must_be_open_ended() -> None:
    """OPEN_INTERVALS, frequency 0 and repeat -1 let the VEN report more than once per event."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            report_descriptors=(
                ReportDescriptor(
                    payload_type=ReportPayloadType("ACTIVE_FLEX_DELTA"),
                    units=Unit.KW,
                    aggregate=True,
                    report_intervals=ReportIntervals.INTERVALS,
                    frequency=0,
                    repeat=-1,
                ),
                _baseline_flex_delta_descriptor("RESERVED_FLEX_DELTA"),
            )
        )
    )

    assert errors is not None
    assert any("'OPEN_INTERVALS'" in str(error["type"]) for error in errors)


def test_baseline_exactly_one_interval() -> None:
    """The baseline is one open ended value pair, so one interval carries it."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                *_default_valid_baseline_intervals(),
                Interval(
                    id=1,
                    interval_period=None,
                    payloads=(
                        EventPayload(type=ACTIVE_BASELINE, values=(500,)),
                        EventPayload(type=RESERVED_BASELINE, values=(500,)),
                    ),
                ),
            )
        )
    )

    assert errors is not None
    assert any("exactly one interval" in str(error["type"]) for error in errors)


def test_baseline_interval_id_must_be_zero() -> None:
    """The single interval has an id of 0."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                Interval(
                    id=1,
                    interval_period=None,
                    payloads=(
                        EventPayload(type=ACTIVE_BASELINE, values=(500,)),
                        EventPayload(type=RESERVED_BASELINE, values=(500,)),
                    ),
                ),
            )
        )
    )

    assert errors is not None
    assert any("id of 0" in str(error["type"]) for error in errors)


def test_baseline_interval_must_not_define_its_own_interval_period() -> None:
    """Neither the event nor its interval carries an intervalPeriod."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1)),
                    payloads=(
                        EventPayload(type=ACTIVE_BASELINE, values=(500,)),
                        EventPayload(type=RESERVED_BASELINE, values=(500,)),
                    ),
                ),
            )
        )
    )

    assert errors is not None
    assert any("must not define its own intervalPeriod" in str(error["type"]) for error in errors)


def test_both_interval_payloads_are_required_even_when_one_is_zero() -> None:
    """Both MUST be present even when one of them is zero."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(EventPayload(type=ACTIVE_BASELINE, values=(500,)),),
                ),
            )
        )
    )

    assert errors is not None
    assert any("exactly two payloads" in str(error["type"]) for error in errors)


def test_a_zero_reserved_baseline_is_valid() -> None:
    """A group with no PENDING children reports a reserved baseline of zero, not no payload."""
    event = _create_baseline_event(
        intervals=(
            Interval(
                id=0,
                interval_period=None,
                payloads=(
                    EventPayload(type=ACTIVE_BASELINE, values=(500,)),
                    EventPayload(type=RESERVED_BASELINE, values=(0,)),
                ),
            ),
        )
    )

    assert validate_baseline_event_compliant(event) is None


def test_a_baseline_with_three_decimals_is_rejected() -> None:
    """A power value is a double with at most two decimal places."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(
                        EventPayload(type=ACTIVE_BASELINE, values=(500.125,)),
                        EventPayload(type=RESERVED_BASELINE, values=(500,)),
                    ),
                ),
            )
        )
    )

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_a_baseline_payload_carries_a_single_value() -> None:
    """The baseline is one number per part of the group, not a series."""
    errors = validate_baseline_event_compliant(
        _create_baseline_event(
            intervals=(
                Interval(
                    id=0,
                    interval_period=None,
                    payloads=(
                        EventPayload(type=ACTIVE_BASELINE, values=(500, 400)),
                        EventPayload(type=RESERVED_BASELINE, values=(500,)),
                    ),
                ),
            )
        )
    )

    assert errors is not None
    assert any("exactly one value" in str(error["type"]) for error in errors)


# --- Flex delta override event ------------------------------------------------------------------

REPORT_ID = EventPayloadType("REPORT_ID")
ACTIVE_OVERRIDE = EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE")
ACTIVE_REASON = EventPayloadType("ACTIVE_FLEX_DELTA_OVERRIDE_REASON")
RESERVED_OVERRIDE = EventPayloadType("RESERVED_FLEX_DELTA_OVERRIDE")
RESERVED_REASON = EventPayloadType("RESERVED_FLEX_DELTA_OVERRIDE_REASON")

OVERRIDDEN_REPORT_ID = "c0000000-0000-4000-8000-000000000000"


def _default_valid_override_payloads() -> tuple[EventPayload, ...]:
    """Helper function to create the payloads of the specification's override example."""
    return (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
        EventPayload(type=RESERVED_OVERRIDE, values=(-50,)),
        EventPayload(type=RESERVED_REASON, values=("SHARE_LIMIT_EXCEEDED",)),
    )


def _override_descriptors_for(payloads: tuple[EventPayload, ...]) -> tuple[EventPayloadDescriptor, ...]:
    """Helper function to declare one descriptor per payload type carried, in KW on the overrides."""
    return tuple(
        EventPayloadDescriptor(
            payload_type=payload.type,
            units=Unit.KW if payload.type in (ACTIVE_OVERRIDE, RESERVED_OVERRIDE) else None,
        )
        for payload in payloads
    )


def _create_override_event(
    targets: tuple[str, ...] | None = _UNSET,
    interval_period: IntervalPeriod | None = _UNSET,
    payload_descriptors: tuple[EventPayloadDescriptor, ...] | None = _UNSET,
    intervals: tuple[Interval[EventPayload], ...] | None = _UNSET,
    payloads: tuple[EventPayload, ...] = _UNSET,
) -> NewEvent:
    """
    Helper function to create an event with the specified values.

    Any argument left unset defaults to a compliant flex delta override value. Passing ``payloads``
    rebuilds both the single interval and the matching payload descriptors, which is what most rule
    tests need; passing ``intervals`` or ``payload_descriptors`` overrides that.
    """
    carried = _default_valid_override_payloads() if payloads is _UNSET else payloads
    return NewEvent(
        programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
        event_name="Flex delta override - GROUP-0001",
        targets=("GROUP-0001",) if targets is _UNSET else targets,
        interval_period=None if interval_period is _UNSET else interval_period,
        payload_descriptors=(
            _override_descriptors_for(carried) if payload_descriptors is _UNSET else payload_descriptors
        ),
        report_descriptors=None,
        intervals=((Interval(id=0, interval_period=None, payloads=carried),) if intervals is _UNSET else intervals),
    )


def test_flex_delta_override_event_valid() -> None:
    """An override matching the specification's example is compliant."""
    assert validate_flex_delta_override_event_compliant(_create_override_event()) is None


def test_overriding_only_the_active_delta_is_valid() -> None:
    """The two are evaluated separately, so the BL may override one and leave the other."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    assert validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads)) is None


def test_override_exactly_one_target() -> None:
    """The override names exactly one resource group."""
    errors = validate_flex_delta_override_event_compliant(_create_override_event(targets=("GROUP-0001", "GROUP-0002")))

    assert errors is not None
    assert any("exactly one resource group" in str(error["type"]) for error in errors)


def test_override_event_level_interval_period_is_rejected() -> None:
    """An override applies from createdDateTime until it is superseded."""
    event = _create_override_event(
        interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1))
    )

    errors = validate_flex_delta_override_event_compliant(event)

    assert errors is not None
    assert any("must not define an intervalPeriod at the event level" in str(error["type"]) for error in errors)


def test_a_descriptor_is_required_for_every_carried_payload_type() -> None:
    """One descriptor for each payload type carried in the interval."""
    errors = validate_flex_delta_override_event_compliant(
        _create_override_event(payload_descriptors=(EventPayloadDescriptor(payload_type=REPORT_ID),))
    )

    assert errors is not None
    assert any("one payload descriptor for each payload type" in str(error["type"]) for error in errors)


def test_override_descriptor_units_must_be_kw() -> None:
    """The units field MUST be KW on both override descriptors."""
    payloads = _default_valid_override_payloads()
    descriptors = tuple(
        EventPayloadDescriptor(payload_type=payload.type, units=Unit.KWH if payload.type == ACTIVE_OVERRIDE else None)
        for payload in payloads
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payload_descriptors=descriptors))

    assert errors is not None
    assert any("units field of 'KW'" in str(error["type"]) for error in errors)


def test_override_exactly_one_interval() -> None:
    """The override is a single correction, carried in one interval."""
    interval = Interval(id=0, interval_period=None, payloads=_default_valid_override_payloads())

    errors = validate_flex_delta_override_event_compliant(_create_override_event(intervals=(interval, interval)))

    assert errors is not None
    assert any("exactly one interval" in str(error["type"]) for error in errors)


def test_override_interval_id_must_be_zero() -> None:
    """The single interval has an id of 0."""
    errors = validate_flex_delta_override_event_compliant(
        _create_override_event(
            intervals=(Interval(id=1, interval_period=None, payloads=_default_valid_override_payloads()),)
        )
    )

    assert errors is not None
    assert any("id of 0" in str(error["type"]) for error in errors)


def test_override_interval_must_not_define_its_own_interval_period() -> None:
    """Neither the event nor its interval carries an intervalPeriod."""
    interval = Interval(
        id=0,
        interval_period=IntervalPeriod(start=datetime(2026, 1, 1, tzinfo=UTC), duration=timedelta(days=1)),
        payloads=_default_valid_override_payloads(),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(intervals=(interval,)))

    assert errors is not None
    assert any("must not define its own intervalPeriod" in str(error["type"]) for error in errors)


def test_report_id_is_required() -> None:
    """An override without the report it corrects cannot be applied to anything."""
    payloads = (
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("'REPORT_ID'" in str(error["type"]) for error in errors)


def test_report_id_carries_exactly_one_value() -> None:
    """An override corrects one report."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID, "c0000000-0000-4000-8000-000000000001")),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("'REPORT_ID'" in str(error["type"]) for error in errors)


def test_report_id_must_be_a_uuid() -> None:
    """The REPORT_ID payload value is the report's object ID, which is a UUID."""
    payloads = (
        EventPayload(type=REPORT_ID, values=("not-a-uuid",)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("'REPORT_ID'" in str(error["type"]) and "UUID" in str(error["type"]) for error in errors)


def test_report_id_cannot_be_an_integer() -> None:
    """A REPORT_ID of an integer is not a UUID either."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(42,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("'REPORT_ID'" in str(error["type"]) and "UUID" in str(error["type"]) for error in errors)


def test_at_least_one_override_is_required() -> None:
    """An override event that overrides nothing is not an override event."""
    payloads = (EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),)

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("at least one of" in str(error["type"]) for error in errors)


def test_an_override_without_a_reason_is_rejected() -> None:
    """The BL MUST state a reason for each value it overrides."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("accompanied by exactly one" in str(error["type"]) for error in errors)


def test_a_reason_without_an_override_is_rejected() -> None:
    """A reason MUST NOT be carried for an override that is absent."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
        EventPayload(type=RESERVED_REASON, values=("SHARE_LIMIT_EXCEEDED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("when the matching override is absent" in str(error["type"]) for error in errors)


def test_an_unknown_reason_is_rejected() -> None:
    """A reason not in the table means the BL should have used OTHER."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300,)),
        EventPayload(type=ACTIVE_REASON, values=("WE_FELT_LIKE_IT",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("accompanied by exactly one" in str(error["type"]) for error in errors)


def test_a_positive_override_is_rejected() -> None:
    """An override carries the same constraints as the flex delta it replaces: at most zero."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(300,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("equal to or smaller than zero" in str(error["type"]) for error in errors)


def test_an_override_with_three_decimals_is_rejected() -> None:
    """A power value is a double with at most two decimal places."""
    payloads = (
        EventPayload(type=REPORT_ID, values=(OVERRIDDEN_REPORT_ID,)),
        EventPayload(type=ACTIVE_OVERRIDE, values=(-300.125,)),
        EventPayload(type=ACTIVE_REASON, values=("DECREASE_NOT_ALLOWED",)),
    )

    errors = validate_flex_delta_override_event_compliant(_create_override_event(payloads=payloads))

    assert errors is not None
    assert any("equal to or smaller than zero" in str(error["type"]) for error in errors)


# --- Flexibility dispatch event -----------------------------------------------------------------

FLEX = EventPayloadType("FLEX")

PRE_DISPATCH_START = datetime(2026, 1, 2, 16, 0, 0, tzinfo=UTC)
DISPATCH_START = datetime(2026, 1, 2, 17, 0, 0, tzinfo=UTC)
POST_DISPATCH_START = datetime(2026, 1, 2, 21, 0, 0, tzinfo=UTC)


def _default_valid_dispatch_payload_descriptors() -> tuple[EventPayloadDescriptor, ...]:
    """Helper function to create the single FLEX payload descriptor a dispatch must declare."""
    return (EventPayloadDescriptor(payload_type=FLEX, units=Unit.KW),)


def _default_valid_dispatch_report_descriptors() -> tuple[ReportDescriptor, ...]:
    """Helper function to create the ACK and DELIVERED_FLEX report descriptors of a dispatch."""
    return (
        ReportDescriptor(payload_type=ReportPayloadType("ACK"), aggregate=True, frequency=0, repeat=1),
        ReportDescriptor(
            payload_type=ReportPayloadType("DELIVERED_FLEX"),
            units=Unit.KW,
            aggregate=True,
            report_intervals=ReportIntervals.INTERVALS,
            frequency=-1,
            repeat=1,
        ),
    )


def _dispatch_interval(
    interval_id: int, start: datetime, duration: timedelta, flex_value: float
) -> Interval[EventPayload]:
    """Helper function to create a single event interval."""
    return Interval(
        id=interval_id,
        interval_period=IntervalPeriod(start=start, duration=duration),
        payloads=(EventPayload(type=FLEX, values=(flex_value,)),),
    )


def _default_valid_dispatch_intervals() -> tuple[Interval[EventPayload], ...]:
    """Helper function to create a PT4H dispatch flanked by an hour of FLEX 0 either side."""
    return (
        _dispatch_interval(0, PRE_DISPATCH_START, timedelta(hours=1), 0),
        _dispatch_interval(1, DISPATCH_START, timedelta(hours=4), 200),
        _dispatch_interval(2, POST_DISPATCH_START, timedelta(hours=1), 0),
    )


def _create_dispatch_event(
    targets: tuple[str, ...] | None = _UNSET,
    interval_period: IntervalPeriod | None = _UNSET,
    payload_descriptors: tuple[EventPayloadDescriptor, ...] | None = _UNSET,
    report_descriptors: tuple[ReportDescriptor, ...] | None = _UNSET,
    intervals: tuple[Interval[EventPayload], ...] = _UNSET,
) -> NewEvent:
    """
    Helper function to create an event with the specified values.

    Any argument left unset defaults to a compliant flexibility dispatch value. Passing ``None``
    explicitly is preserved, to allow testing the absence of a field.
    """
    return NewEvent(
        programID="test-program",
        event_name="Flex dispatch - GROUP-0001",
        targets=("GROUP-0001",) if targets is _UNSET else targets,
        interval_period=(
            IntervalPeriod(start=WINDOW_START, duration=timedelta(hours=24))
            if interval_period is _UNSET
            else interval_period
        ),
        payload_descriptors=(
            _default_valid_dispatch_payload_descriptors() if payload_descriptors is _UNSET else payload_descriptors
        ),
        report_descriptors=(
            _default_valid_dispatch_report_descriptors() if report_descriptors is _UNSET else report_descriptors
        ),
        intervals=_default_valid_dispatch_intervals() if intervals is _UNSET else intervals,
    )


def test_flex_dispatch_event_valid() -> None:
    """A dispatch matching the specification's worked example is compliant."""
    assert validate_flex_dispatch_event_compliant(_create_dispatch_event()) is None


def test_payload_descriptor_must_be_flex() -> None:
    """A dispatch declares exactly one FLEX payload descriptor."""
    event = _create_dispatch_event(
        payload_descriptors=(EventPayloadDescriptor(payload_type=EventPayloadType("ACTIVE_BASELINE"), units=Unit.KW),)
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("payload type of 'FLEX'" in str(error["type"]) for error in errors)


def test_dispatch_payload_descriptor_units_must_be_kw() -> None:
    """The FLEX payload descriptor is expressed in KW."""
    event = _create_dispatch_event(payload_descriptors=(EventPayloadDescriptor(payload_type=FLEX, units=Unit.KWH),))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("units field of 'KW'" in str(error["type"]) for error in errors)


def test_both_report_descriptors_required() -> None:
    """A dispatch asks for an acknowledgment and a delivery report, and nothing else."""
    event = _create_dispatch_event(
        report_descriptors=(ReportDescriptor(payload_type=ReportPayloadType("ACK"), frequency=0),)
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("exactly two report descriptors" in str(error["type"]) for error in errors)


def test_acknowledgment_descriptor_is_ad_hoc() -> None:
    """The ACK descriptor sets frequency 0, so the VEN acknowledges on retrieval."""
    event = _create_dispatch_event(
        report_descriptors=(
            ReportDescriptor(payload_type=ReportPayloadType("ACK"), frequency=-1),
            *_default_valid_dispatch_report_descriptors()[1:],
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("frequency to 0" in str(error["type"]) for error in errors)


def test_delivery_descriptor_reports_per_interval() -> None:
    """The DELIVERED_FLEX descriptor asks for one report covering every interval."""
    event = _create_dispatch_event(
        report_descriptors=(
            _default_valid_dispatch_report_descriptors()[0],
            ReportDescriptor(
                payload_type=ReportPayloadType("DELIVERED_FLEX"),
                report_intervals=ReportIntervals.OPEN_INTERVALS,
            ),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("reportIntervals to 'INTERVALS'" in str(error["type"]) for error in errors)


def test_dispatch_exactly_one_target() -> None:
    """A dispatch calls flexibility from exactly one resource group."""
    errors = validate_flex_dispatch_event_compliant(_create_dispatch_event(targets=("GROUP-0001", "GROUP-0002")))

    assert errors is not None
    assert any("exactly one resource group" in str(error["type"]) for error in errors)


def test_event_level_interval_period_required() -> None:
    """A dispatch defines the 24-hour window it covers at the event level."""
    errors = validate_flex_dispatch_event_compliant(_create_dispatch_event(interval_period=None))

    assert errors is not None
    assert any("intervalPeriod at the event level" in str(error["type"]) for error in errors)


@pytest.mark.parametrize("hours", [23, 24, 25])
def test_event_window_may_be_23_24_or_25_hours(hours: int) -> None:
    """The event-level window is PT23H, PT24H or PT25H, to cover days with a DST transition."""
    event = _create_dispatch_event(interval_period=IntervalPeriod(start=WINDOW_START, duration=timedelta(hours=hours)))

    assert validate_flex_dispatch_event_compliant(event) is None


@pytest.mark.parametrize("hours", [12, 22, 26])
def test_event_window_of_another_duration_is_rejected(hours: int) -> None:
    """Any event-level window other than PT23H, PT24H or PT25H is rejected."""
    event = _create_dispatch_event(interval_period=IntervalPeriod(start=WINDOW_START, duration=timedelta(hours=hours)))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("duration of PT23H, PT24H or PT25H" in str(error["type"]) for error in errors)


def test_intervals_must_fall_within_the_window() -> None:
    """Every interval sits inside the event's own window."""
    event = _create_dispatch_event(
        intervals=(_dispatch_interval(0, WINDOW_START + timedelta(days=1), timedelta(hours=2), 100),)
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("within the event-level" in str(error["type"]) for error in errors)


def test_flex_value_cannot_be_negative() -> None:
    """A dispatch never asks for a reduction of feed-in: only offtake congestion is in scope."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=2), -10),))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("larger than zero" in str(error["type"]) for error in errors)


def test_interval_ids_ascend_from_zero() -> None:
    """Interval ids are unique integers, assigned in ascending order starting at 0."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(3, DISPATCH_START, timedelta(hours=2), 100),
            _dispatch_interval(1, DISPATCH_START + timedelta(hours=3), timedelta(hours=2), 100),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("ascending order starting at 0" in str(error["type"]) for error in errors)


def test_intervals_must_not_overlap() -> None:
    """Intervals never overlap; gaps between them are allowed."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, DISPATCH_START, timedelta(hours=4), 100),
            _dispatch_interval(1, DISPATCH_START + timedelta(hours=3), timedelta(hours=2), 100),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("must not overlap" in str(error["type"]) for error in errors)


def test_gaps_between_intervals_are_allowed() -> None:
    """A gap carries no dispatch, which is a legitimate shape."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, WINDOW_START + timedelta(hours=1), timedelta(hours=2), 100),
            _dispatch_interval(1, WINDOW_START + timedelta(hours=8), timedelta(hours=2), 100),
        )
    )

    assert validate_flex_dispatch_event_compliant(event) is None


def _flex_values_interval(start: datetime, duration: timedelta, values: tuple[Any, ...]) -> Interval[EventPayload]:
    """Helper function to create a single event interval whose FLEX payload carries the given values."""
    return Interval(
        id=0,
        interval_period=IntervalPeriod(start=start, duration=duration),
        payloads=(EventPayload(type=FLEX, values=values),),
    )


def test_a_flex_payload_with_multiple_values_is_valid() -> None:
    """The FLEX payload carries a list of values; the profile does not prescribe how many."""
    event = _create_dispatch_event(
        intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=2), (100, 200, 150.25)),)
    )

    assert validate_flex_dispatch_event_compliant(event) is None


def test_a_flex_payload_without_values_is_rejected() -> None:
    """The list of FLEX values must not be empty; built unvalidated, as the base model rejects it too."""
    event = _create_dispatch_event(
        intervals=(
            Interval(
                id=0,
                interval_period=IntervalPeriod(start=DISPATCH_START, duration=timedelta(hours=2)),
                payloads=(EventPayload.model_construct(type=FLEX, values=()),),
            ),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("at least one value" in str(error["type"]) for error in errors)


def test_every_flex_value_is_checked_for_decimals() -> None:
    """A single value with three decimals among valid ones rejects the payload."""
    event = _create_dispatch_event(
        intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=2), (100, 200.125)),)
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_every_flex_value_is_checked_for_type() -> None:
    """A boolean among valid values rejects the payload."""
    event = _create_dispatch_event(intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=2), (100, True)),))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_every_flex_value_is_checked_for_sign() -> None:
    """A negative value among valid ones rejects the payload."""
    event = _create_dispatch_event(intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=2), (100, -10)),))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("larger than zero" in str(error["type"]) for error in errors)


def test_every_flex_value_is_bounded_by_offered_flexibility() -> None:
    """A single value above the group's ACTIVE_AVAILABLE_FLEX rejects the call."""
    event = _create_dispatch_event(intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=2), (10, 20)),))

    errors = validate_flex_dispatch_event_compliant(event, max_callable_kw=12.5)

    assert errors is not None
    assert any("ACTIVE_AVAILABLE_FLEX" in str(error["type"]) for error in errors)


def test_an_interval_may_have_any_duration() -> None:
    """The profile no longer prescribes interval durations."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, DISPATCH_START, timedelta(hours=3), 100),
            _dispatch_interval(1, DISPATCH_START + timedelta(hours=3), timedelta(minutes=30), 0),
        )
    )

    assert validate_flex_dispatch_event_compliant(event) is None


def test_flex_values_of_zero_do_not_count_towards_max_duration() -> None:
    """A PT4H call flanked by FLEX 0 on both sides spans six hours against a PT4H group, and is valid."""
    assert validate_flex_dispatch_event_compliant(_create_dispatch_event(), max_duration=timedelta(hours=4)) is None


def test_an_event_without_any_call_satisfies_any_max_duration() -> None:
    """The MAX_DURATION timer never starts when no FLEX value is above 0."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=6), 0),))

    assert validate_flex_dispatch_event_compliant(event, max_duration=timedelta(hours=2)) is None


def test_a_call_longer_than_max_duration_is_rejected() -> None:
    """A single PT6H call exceeds a PT4H group."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=6), 100),))

    errors = validate_flex_dispatch_event_compliant(event, max_duration=timedelta(hours=4))

    assert errors is not None
    assert any("MAX_DURATION" in str(error["type"]) for error in errors)


def test_a_call_after_a_gap_still_counts_towards_max_duration() -> None:
    """The timer keeps running through a gap: a call at 20:00 is past 17:00 plus PT2H."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, DISPATCH_START, timedelta(hours=2), 100),
            _dispatch_interval(1, DISPATCH_START + timedelta(hours=3), timedelta(hours=1), 100),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event, max_duration=timedelta(hours=2))

    assert errors is not None
    assert any("MAX_DURATION" in str(error["type"]) for error in errors)


def test_zero_values_after_max_duration_are_allowed() -> None:
    """Once MAX_DURATION has passed, FLEX values of 0 are still allowed."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, DISPATCH_START, timedelta(hours=2), 100),
            _dispatch_interval(1, DISPATCH_START + timedelta(hours=2), timedelta(hours=2), 0),
        )
    )

    assert validate_flex_dispatch_event_compliant(event, max_duration=timedelta(hours=2)) is None


def test_max_duration_starts_at_the_first_value_above_zero_within_an_interval() -> None:
    """Values split their interval evenly: four values over PT4H each cover an hour."""
    late_call = _create_dispatch_event(
        intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=4), (0, 0, 5, 5)),)
    )
    early_call = _create_dispatch_event(
        intervals=(_flex_values_interval(DISPATCH_START, timedelta(hours=4), (0, 5, 5, 5)),)
    )

    assert validate_flex_dispatch_event_compliant(late_call, max_duration=timedelta(hours=2)) is None
    errors = validate_flex_dispatch_event_compliant(early_call, max_duration=timedelta(hours=2))
    assert errors is not None
    assert any("MAX_DURATION" in str(error["type"]) for error in errors)


def test_max_duration_follows_time_rather_than_interval_ids() -> None:
    """Ids do not determine chronological order: the timer starts at the earliest call, here id 1."""
    event = _create_dispatch_event(
        intervals=(
            _dispatch_interval(0, DISPATCH_START + timedelta(hours=3), timedelta(hours=1), 100),
            _dispatch_interval(1, DISPATCH_START, timedelta(hours=1), 100),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event, max_duration=timedelta(hours=2))

    assert errors is not None
    assert any("MAX_DURATION" in str(error["type"]) for error in errors)


def test_call_must_not_exceed_offered_flexibility() -> None:
    """The called amount is bounded by the group's ACTIVE_AVAILABLE_FLEX."""
    errors = validate_flex_dispatch_event_compliant(_create_dispatch_event(), max_callable_kw=12.5)

    assert errors is not None
    assert any("ACTIVE_AVAILABLE_FLEX" in str(error["type"]) for error in errors)


def test_call_within_offered_flexibility() -> None:
    """A dispatch at or below the offer is valid; a FLEX value of 0 always is."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=2), 10),))

    assert validate_flex_dispatch_event_compliant(event, max_callable_kw=12.5) is None


def test_a_flex_value_with_three_decimals_is_rejected() -> None:
    """Every power value in the profile is a double with at most two decimal places."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=2), 200.125),))

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)


def test_a_flex_value_with_two_decimals_is_accepted() -> None:
    """Two decimals is the limit, not a rejection."""
    event = _create_dispatch_event(intervals=(_dispatch_interval(0, DISPATCH_START, timedelta(hours=2), 200.25),))

    assert validate_flex_dispatch_event_compliant(event) is None


def test_a_boolean_flex_value_is_rejected() -> None:
    """Bool is a subclass of int in Python, so it needs rejecting explicitly."""
    event = _create_dispatch_event(
        intervals=(
            Interval(
                id=0,
                interval_period=IntervalPeriod(start=DISPATCH_START, duration=timedelta(hours=2)),
                payloads=(EventPayload(type=FLEX, values=(True,)),),
            ),
        )
    )

    errors = validate_flex_dispatch_event_compliant(event)

    assert errors is not None
    assert any("at most two decimals" in str(error["type"]) for error in errors)

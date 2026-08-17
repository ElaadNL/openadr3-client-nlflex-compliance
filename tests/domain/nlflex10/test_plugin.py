# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

import re

import pytest
from openadr3_client._models.common.attribute import Attribute
from openadr3_client._models.common.interval import Interval
from openadr3_client._models.common.value_map_collection import ValuesMap
from openadr3_client.extensions.resource_group.models.resource_group import NewResourceGroup
from openadr3_client.oadr310.models.event.event import NewEvent
from openadr3_client.oadr310.models.event.event_payload import (
    EventPayload,
    EventPayloadDescriptor,
    EventPayloadType,
)
from openadr3_client.oadr310.models.program.program import NewProgram
from openadr3_client.oadr310.models.report.report import NewReport, ReportResource
from openadr3_client.oadr310.models.report.report_payload import (
    ReportDescriptor,
    ReportIntervals,
    ReportPayload,
    ReportPayloadType,
)
from openadr3_client.oadr310.models.resource.resource import NewResourceBlRequest
from openadr3_client.oadr310.models.unit import Unit
from openadr3_client.oadr310.models.ven.ven import NewVenBlRequest
from openadr3_client.plugin import ValidatorPluginRegistry
from pydantic import ValidationError

from openadr3_client_nlflex_compliance.nlflex10.plugin import Nlflex10ValidatorPlugin

SERVICE_PROVIDER_EAN13 = "8712345678906"
DSO_EAN13 = "8716871000002"  # Liander, from the DSO identifiers table


@pytest.fixture(autouse=True)
def clear_plugins():
    """Clear plugins before each test and register the v1.0.0 plugin."""
    ValidatorPluginRegistry.clear_plugins()
    ValidatorPluginRegistry.register_plugin(Nlflex10ValidatorPlugin.setup())
    yield
    ValidatorPluginRegistry.clear_plugins()


def test_exactly_one_validator_is_registered_per_model() -> None:
    """A plugin registers one validator per model class, which is why the entry points discriminate."""
    for model in (NewEvent, NewReport, NewProgram, NewVenBlRequest, NewResourceBlRequest, NewResourceGroup):
        assert len(ValidatorPluginRegistry.get_model_validators(model)) == 1


def test_a_compliant_ven_is_accepted() -> None:
    """Registering the plugin does not break the construction of a compliant object."""
    ven = NewVenBlRequest(ven_name=SERVICE_PROVIDER_EAN13, clientID="elaad-client", targets=("GROUP-0001",))

    assert ven.ven_name == SERVICE_PROVIDER_EAN13


def test_a_non_compliant_ven_is_rejected_on_construction() -> None:
    """The plugin runs as a pydantic model validator, so a bad object cannot be built."""
    with pytest.raises(ValidationError, match=re.escape("Service Provider identifier")):
        NewVenBlRequest(ven_name="SP-ZON", clientID="elaad-client")


def test_a_non_compliant_baseline_event_is_rejected_on_construction() -> None:
    """A v0.1-shaped baseline event no longer constructs."""
    with pytest.raises(ValidationError, match=re.escape("exactly two payload descriptors")):
        NewEvent(
            programID="dbb3ec95-d96d-449c-b991-154b77491bcd",
            targets=("GROUP-0001",),
            payload_descriptors=(
                EventPayloadDescriptor(payload_type=EventPayloadType("ACTIVE_BASELINE"), units=Unit.KW),
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


def test_multiple_errors_are_grouped() -> None:
    """Every violated rule is reported at once, rather than the first one."""
    with pytest.raises(ValidationError) as exc_info:
        NewResourceGroup(
            resource_group_name="GROUP-0001",
            targets=("GROUP-0002",),
            attributes=ValuesMap(
                [
                    Attribute(type="DSO_ID", values=("DSB-LIA",)),
                    Attribute(type="SERVICE_PROVIDER_ID", values=(SERVICE_PROVIDER_EAN13,)),
                    Attribute(type="CONGESTION_POINT_ID", values=("CP-0001",)),
                    Attribute(type="MAX_DURATION", values=("PT4H",)),
                ]
            ),
        )

    errors = exc_info.value.errors()
    assert len(errors) == 2
    assert all(error.get("type") == "value_error" for error in errors)


def test_a_non_compliant_report_is_rejected_on_construction() -> None:
    """The report entry point is registered too."""
    with pytest.raises(ValidationError, match=re.escape("clientName")):
        NewReport(
            eventID="f0000000-0000-4000-8000-000000000000",
            client_name="elaad-client",
            resources=(
                ReportResource(
                    resource_name="AGGREGATED_REPORT",
                    intervals=(
                        Interval(
                            id=0,
                            interval_period=None,
                            payloads=(ReportPayload(type=ReportPayloadType("ACK"), values=(True,)),),
                        ),
                    ),
                ),
            ),
        )


def test_a_non_compliant_program_is_rejected_on_construction() -> None:
    """Events in this profile are immutable, which the program must advertise."""
    with pytest.raises(ValidationError, match=re.escape("BINDING_EVENTS")):
        NewProgram(
            program_name="DSO-SP DER interface",
            attributes=ValuesMap(
                [
                    Attribute(type="PROGRAM_TYPE", values=("DSO_SP_INTERFACE-1.0.0",)),
                    Attribute(type="RETAILER_NAME", values=(DSO_EAN13,)),
                ]
            ),
        )

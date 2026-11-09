# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validators for the OpenADR DER profile specification v1.1.0.

The public entry point is Nlflex11ValidatorPlugin, which registers one validator per model class.
Since v1.1.0 puts two kinds of program, four kinds of event and five kinds of report behind three
model classes, the entry points for those discriminate and delegate to a section per kind, within
program_nlflex_compliant, event_nlflex_compliant and report_nlflex_compliant respectively.

Rules that compare objects are not registered in the plugin, which sees one object at a time. They are
exported for callers that hold both objects: validate_event_program_ownership and
validate_programs_lock_step, and optional keyword arguments on the dispatch and delivery validators
(MAX_DURATION and ACTIVE_AVAILABLE_FLEX of the targeted resource group, the intervals of the FLEX event).

The raw-input functions (validate_raw_event and its siblings) check the rules that the parser hides, such
as days in durations and non-Zulu timestamps. Callers run them on the raw JSON before parsing, and they
are not registered either.
"""

from openadr3_client_nlflex_compliance.nlflex11.event_nlflex_compliant import (
    validate_baseline_event_compliant,
    validate_event_nlflex_compliant,
    validate_event_program_ownership,
    validate_flex_delta_override_event_compliant,
    validate_flex_dispatch_event_compliant,
    validate_reporting_anchor_event_compliant,
)
from openadr3_client_nlflex_compliance.nlflex11.plugin import Nlflex11ValidatorPlugin
from openadr3_client_nlflex_compliance.nlflex11.program_nlflex_compliant import (
    validate_program_nlflex_compliant,
    validate_programs_lock_step,
)
from openadr3_client_nlflex_compliance.nlflex11.raw_input import (
    validate_raw_event,
    validate_raw_program,
    validate_raw_report,
    validate_raw_resource,
    validate_raw_resource_group,
    validate_raw_ven,
)
from openadr3_client_nlflex_compliance.nlflex11.report_nlflex_compliant import (
    validate_flex_acknowledgment_report_compliant,
    validate_flex_delivery_report_compliant,
    validate_flex_delta_report_compliant,
    validate_operational_status_report_compliant,
    validate_registration_report_compliant,
    validate_report_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex11.resource_group_nlflex_compliant import (
    validate_resource_group_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex11.resource_nlflex_compliant import validate_resource_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex11.ven_nlflex_compliant import validate_ven_nlflex_compliant

__all__ = [
    "Nlflex11ValidatorPlugin",
    "validate_baseline_event_compliant",
    "validate_event_nlflex_compliant",
    "validate_event_program_ownership",
    "validate_flex_acknowledgment_report_compliant",
    "validate_flex_delivery_report_compliant",
    "validate_flex_delta_override_event_compliant",
    "validate_flex_delta_report_compliant",
    "validate_flex_dispatch_event_compliant",
    "validate_operational_status_report_compliant",
    "validate_program_nlflex_compliant",
    "validate_programs_lock_step",
    "validate_raw_event",
    "validate_raw_program",
    "validate_raw_report",
    "validate_raw_resource",
    "validate_raw_resource_group",
    "validate_raw_ven",
    "validate_registration_report_compliant",
    "validate_report_nlflex_compliant",
    "validate_reporting_anchor_event_compliant",
    "validate_resource_group_nlflex_compliant",
    "validate_resource_nlflex_compliant",
    "validate_ven_nlflex_compliant",
]

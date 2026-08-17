# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
Compliance validators for the OpenADR DER profile specification v1.0.0.

The public entry point is Nlflex10ValidatorPlugin, which registers one validator per model class.
Since v1.0.0 puts four kinds of object behind Event and five behind Report, the entry points for
those two discriminate and delegate to a section per kind, within event_nlflex_compliant and
report_nlflex_compliant respectively.

A handful of rules compare an object against another object: a dispatch interval against the
MAX_DURATION and ACTIVE_AVAILABLE_FLEX of the resource group it targets, and a delivery report
against the intervals of the FLEX event it reports on. They are optional keyword arguments on the
per-kind validators, which a caller holding both objects can supply; the plugin sees one object at a
time and skips them.
"""

from openadr3_client_nlflex_compliance.nlflex10.event_nlflex_compliant import (
    validate_event_nlflex_compliant,
    validate_flex_dispatch_event_compliant,
)
from openadr3_client_nlflex_compliance.nlflex10.plugin import Nlflex10ValidatorPlugin
from openadr3_client_nlflex_compliance.nlflex10.program_nlflex_compliant import validate_program_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.report_nlflex_compliant import (
    validate_flex_delivery_report_compliant,
    validate_report_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex10.resource_group_nlflex_compliant import (
    validate_resource_group_nlflex_compliant,
)
from openadr3_client_nlflex_compliance.nlflex10.resource_nlflex_compliant import validate_resource_nlflex_compliant
from openadr3_client_nlflex_compliance.nlflex10.ven_nlflex_compliant import validate_ven_nlflex_compliant

__all__ = [
    "Nlflex10ValidatorPlugin",
    "validate_event_nlflex_compliant",
    "validate_flex_delivery_report_compliant",
    "validate_flex_dispatch_event_compliant",
    "validate_program_nlflex_compliant",
    "validate_report_nlflex_compliant",
    "validate_resource_group_nlflex_compliant",
    "validate_resource_nlflex_compliant",
    "validate_ven_nlflex_compliant",
]

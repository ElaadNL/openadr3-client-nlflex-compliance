<!--
SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>

SPDX-License-Identifier: Apache-2.0
-->

[![CodeQL Advanced](https://github.com/ElaadNL/openadr3-client-nlflex-compliance/actions/workflows/codeql.yml/badge.svg)](https://github.com/ElaadNL/openadr3-client-nlflex-compliance/actions/workflows/codeql.yml)
[![Python Default CI](https://github.com/ElaadNL/openadr3-client-nlflex-compliance/actions/workflows/ci.yml/badge.svg)](https://github.com/ElaadNL/openadr3-client-nlflex-compliance/actions/workflows/ci.yml)
![PYPI-DL](https://img.shields.io/pypi/dm/openadr3-client-nlflex-compliance?style=flat)
[![image](https://img.shields.io/pypi/v/openadr3-client-nlflex-compliance?label=pypi)](https://pypi.python.org/pypi/openadr3-client-nlflex-compliance)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FElaadNL%2Fopenadr3-client-nlflex-compliance%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

# OpenADR3 client

This repository contains a plugin for the [OpenADR3-client](https://github.com/ElaadNL/openadr3-client) library that adds additional Pydantic validators to the OpenADR3 domain models to ensure compliance with the OpenADR DER profile specification, the Dutch DSO to aggregator interface. Since compliance with the profile is a superset of OpenADR3, adding validation rules on top of the OpenADR3 models is sufficient to ensure compliance.

Registering the plugin is done using the global ValidatorPluginRegistry class:

```python
from openadr3_client.plugin import ValidatorPluginRegistry
from openadr3_client_nlflex_compliance.nlflex10.plugin import Nlflex10ValidatorPlugin

ValidatorPluginRegistry.register_plugin(Nlflex10ValidatorPlugin.setup())
```

## Version support

The package provides a validator implementation per version of the profile specification, in a subpackage named for that version:

- **Nlflex11ValidatorPlugin** (`nlflex11`): OpenADR DER profile specification v1.1.0
- **Nlflex10ValidatorPlugin** (`nlflex10`): OpenADR DER profile specification v1.0.0

The specification each plugin validates against ships in the `spec/` directory of this repository, together with the worked message examples the test suite validates against.

Register the plugin for the version of the specification you implement. An earlier plugin, `Nlflex01ValidatorPlugin`, validated the unreleased NL-Flex v0.1 draft and has been removed: the released v1.0.0 contradicts that draft on several rules rather than only extending it.

### Raw-input checks (nlflex11)

"Timestamps and durations" of the v1.1.0 profile forbids days in durations (`P1D`, use `PT24H`) and requires timestamps in UTC with the `Z` notation. The parser is more lenient: `P1D` and `PT24H` become the same `timedelta`, `Z` and `+01:00` are both accepted and normalised to aware datetimes, and plain numbers are accepted too. These rules therefore cannot be checked on the parsed model, where the plugin validators run. Run the raw-input functions on the raw JSON before parsing it, and raise or report their errors:

```python
from pydantic import ValidationError
from openadr3_client_nlflex_compliance.nlflex11 import validate_raw_event

raw_event = response.json()  # the dict as returned by the VTN, not yet parsed
errors = validate_raw_event(raw_event)
if errors:
    raise ValidationError.from_exception_data("Event", errors)
```

`validate_raw_program`, `validate_raw_report`, `validate_raw_ven`, `validate_raw_resource` and `validate_raw_resource_group` work the same way. They are deliberately not registered in the plugin.

### Checks across objects (nlflex11)

The plugin sees one object at a time, so rules that compare objects are not registered. A caller that holds both objects runs them itself:

- `validate_event_program_ownership(event, program)` checks that an event lives in the kind of program that owns its kind of event (registration or dispatch).
- `validate_programs_lock_step(programs)` checks that the registration program and every dispatch program advertise the same profile version, within each MAJOR version. During a phase out both MAJOR versions are present, so each is checked on its own. The registration and dispatch programs currently live on separate VTN deployments, so pass the programs from both.
- `validate_flex_dispatch_event_compliant(event, max_duration=..., max_callable_kw=...)` takes the `MAX_DURATION` and `ACTIVE_AVAILABLE_FLEX` of the targeted resource group as keyword-only arguments and checks the dispatch intervals against them.
- `validate_flex_delivery_report_compliant(report, event_intervals=...)` takes the intervals of the FLEX event as a keyword-only argument and checks that the delivery report has one matching interval per event interval.

`validate_event_program_ownership` and `validate_programs_lock_step` return a list of errors, empty when compliant. `validate_flex_dispatch_event_compliant` and `validate_flex_delivery_report_compliant` return a list of errors, or None when compliant. Raise or report the errors the same way as above.

## License

This project is licensed under the Apache-2.0 - see LICENSE for details.

## Licenses third-party libraries

This project includes third-party libraries, which are licensed under their own respective Open-Source licenses.
SPDX-License-Identifier headers are used to show which license is applicable. The concerning license files can be found in the LICENSES directory.

---

## About ElaadNL

ElaadNL is a Dutch research institute founded and funded by the Dutch District Service Operators (DSOs). ElaadNL was originally tasked by the DSOs to kickstart and foster the adoption of Electric Vehicles by installing the first Dutch charging stations, as well as monitoring the effects EVs have on the grid.

A major result of this pioneering work, was the creation of the Open Charge Point Protocol (OCPP), which today is the de-facto standard for CPOs to communicate with and manage their chargepoints. The protocol is now managed in a spin-off organization: the Open Charge Alliance, which is still closely connected with ElaadNL.

Whereas ElaadNL initially focused mainly on EVs, it has now expanded its mandate to include residential energy use with the goal of increasing the adoption of demand response measures. The reason for this move is to improve efficient use of the resources of the DSO in order to reduce grid congestion, which is a major problem challenge for the Dutch DSOs as well as society as a whole.

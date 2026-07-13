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

This repository contains a plugin for the [OpenADR3-client](https://github.com/ElaadNL/openadr3-client) library that adds additional Pydantic validators to the OpenADR3 domain models to ensure NL-Flex compliance. Since NL-Flex compliance is a superset of OpenADR3, adding validation rules on top of the OpenADR3 models is sufficient to ensure compliance.

The package currently implements the `nlflex01` profile, tracking the draft NL-Flex specification (version 0.1, not yet finalized as 1.0). See `spec/nlflex-spec-draft.pdf` for the specification this profile is based on.

Registering the plugin is done using the global ValidatorPluginRegistry class:

```python
    from openadr3_client.plugin import ValidatorPluginRegistry, ValidatorPlugin
    from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

    ValidatorPluginRegistry.register_plugin(
        Nlflex01ValidatorPlugin().setup()
    )
```

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

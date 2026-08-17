# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
OpenADR3 DER profile compliance plugin.

This package provides validation plugins for OpenADR3 models to ensure compliance with the OpenADR
DER profile specification, the Dutch DSO to Service Provider interface. The specification it
validates against ships in the spec/ directory of this repository.

The main entry point is the Nlflex10ValidatorPlugin, which can be registered with the OpenADR3
client's validator plugin registry.

Example:
    ```python
    from openadr3_client.plugin import ValidatorPluginRegistry
    from openadr3_client_nlflex_compliance.nlflex10.plugin import Nlflex10ValidatorPlugin

    # Register the DER profile v1.0.0 validation plugin
    ValidatorPluginRegistry.register_plugin(Nlflex10ValidatorPlugin.setup())
    ```

"""

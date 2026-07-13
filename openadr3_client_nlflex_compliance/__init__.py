# SPDX-FileCopyrightText: Contributors to openadr3-client-nlflex-compliance <https://github.com/ElaadNL/openadr3-client-nlflex-compliance>
#
# SPDX-License-Identifier: Apache-2.0

"""
OpenADR3 NL-Flex Compliance Plugin.

This package provides validation plugins for OpenADR3 models to ensure compliance
with the NL-Flex DSO-Service Provider interface specification.

The main entry point is the Nlflex01ValidatorPlugin which can be registered
with the OpenADR3 client's validator plugin registry.

Example:
    ```python
    from openadr3_client.plugin import ValidatorPluginRegistry
    from openadr3_client_nlflex_compliance.nlflex01.plugin import Nlflex01ValidatorPlugin

    # Register the NL-Flex validation plugin
    ValidatorPluginRegistry.register_plugin(Nlflex01ValidatorPlugin.setup())
    ```

"""

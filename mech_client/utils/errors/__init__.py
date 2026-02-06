# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Error handling utilities for mech client."""

from mech_client.utils.errors.exceptions import (
    AgentModeError,
    ConfigurationError,
    ContractError,
    DeliveryTimeoutError,
    IPFSError,
    MechClientError,
    PaymentError,
    RpcError,
    SubgraphError,
    ToolError,
    TransactionError,
    ValidationError,
)
from mech_client.utils.errors.handlers import (
    handle_cli_errors,
    handle_contract_errors,
    handle_rpc_errors,
    handle_subgraph_errors,
)
from mech_client.utils.errors.messages import ErrorMessages


__all__ = [
    # Base exception
    "MechClientError",
    # Specific exceptions
    "RpcError",
    "SubgraphError",
    "ContractError",
    "ValidationError",
    "ConfigurationError",
    "TransactionError",
    "IPFSError",
    "ToolError",
    "AgentModeError",
    "PaymentError",
    "DeliveryTimeoutError",
    # Error handlers
    "handle_cli_errors",
    "handle_rpc_errors",
    "handle_contract_errors",
    "handle_subgraph_errors",
    # Error messages
    "ErrorMessages",
]

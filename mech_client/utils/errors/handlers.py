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

"""Error handler decorators for CLI commands."""

import functools
import os
from typing import Callable

import requests
from click import ClickException
from web3.exceptions import ContractLogicError, Web3ValidationError

from mech_client.utils.errors.exceptions import (
    AgentModeError,
    ConfigurationError,
    ContractError,
    DeliveryTimeoutError,
    IPFSError,
    PaymentError,
    RpcError,
    SubgraphError,
    ToolError,
    TransactionError,
    ValidationError,
)
from mech_client.utils.errors.messages import ErrorMessages


# pylint: disable=too-many-statements
def handle_cli_errors(func: Callable) -> Callable:
    """
    Decorator to handle common CLI command errors.

    Catches standard exceptions and converts them to user-friendly
    ClickException with actionable error messages.

    :param func: CLI command function to wrap
    :return: Wrapped function with error handling
    """

    @functools.wraps(func)
    # pylint: disable=too-many-statements
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except ClickException:
            # Already a ClickException, re-raise as-is
            raise
        except RpcError as e:
            rpc_url = e.rpc_url or os.getenv("MECHX_CHAIN_RPC", "default")
            raise ClickException(ErrorMessages.rpc_error(rpc_url, str(e))) from e
        except SubgraphError as e:
            subgraph_url = e.subgraph_url or os.getenv("MECHX_SUBGRAPH_URL", "not set")
            raise ClickException(
                ErrorMessages.subgraph_error(subgraph_url, str(e))
            ) from e
        except ContractError as e:
            raise ClickException(ErrorMessages.contract_logic_error(str(e))) from e
        except ValidationError as e:
            raise ClickException(ErrorMessages.validation_error(str(e))) from e
        except TransactionError as e:
            raise ClickException(f"Transaction error: {e}") from e
        except PaymentError as e:
            raise ClickException(f"Payment error: {e}") from e
        except IPFSError as e:
            operation = "operation"
            if "upload" in str(e).lower():
                operation = "upload"
            elif "download" in str(e).lower():
                operation = "download"
            raise ClickException(ErrorMessages.ipfs_error(operation, str(e))) from e
        except ToolError as e:
            raise ClickException(f"Tool error: {e}") from e
        except AgentModeError as e:
            raise ClickException(f"Agent mode error: {e}") from e
        except ConfigurationError as e:
            raise ClickException(f"Configuration error: {e}") from e
        except DeliveryTimeoutError as e:
            raise ClickException(str(e)) from e
        except requests.exceptions.HTTPError as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
            raise ClickException(ErrorMessages.rpc_error(rpc_url, str(e))) from e
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
            raise ClickException(
                ErrorMessages.rpc_network_error(rpc_url, str(e))
            ) from e
        except TimeoutError as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC")
            raise ClickException(ErrorMessages.rpc_timeout(rpc_url, str(e))) from e
        except ContractLogicError as e:
            raise ClickException(ErrorMessages.contract_logic_error(str(e))) from e
        except Web3ValidationError as e:
            raise ClickException(ErrorMessages.validation_error(str(e))) from e
        except (ValueError, FileNotFoundError) as e:
            raise ClickException(str(e)) from e
        except Exception as e:
            # Catch-all for unexpected errors
            raise ClickException(
                f"Unexpected error: {e}\n\n"
                f"If this persists, please report it as an issue."
            ) from e

    return wrapper


def handle_rpc_errors(func: Callable) -> Callable:
    """
    Decorator to handle RPC-specific errors.

    Catches HTTP errors, connection errors, and timeouts when communicating
    with RPC endpoints.

    :param func: Function to wrap
    :return: Wrapped function with RPC error handling
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
            raise RpcError(f"HTTP error from RPC: {e}", rpc_url=rpc_url) from e
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC", "default")
            raise RpcError(
                f"Network error connecting to RPC: {e}", rpc_url=rpc_url
            ) from e
        except TimeoutError as e:
            rpc_url = os.getenv("MECHX_CHAIN_RPC")
            raise RpcError(
                f"Timeout waiting for RPC response: {e}", rpc_url=rpc_url
            ) from e

    return wrapper


def handle_contract_errors(func: Callable) -> Callable:
    """
    Decorator to handle smart contract interaction errors.

    Catches contract logic errors and validation errors from Web3.

    :param func: Function to wrap
    :return: Wrapped function with contract error handling
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except ContractLogicError as e:
            raise ContractError(f"Contract logic error: {e}") from e
        except Web3ValidationError as e:
            raise ContractError(f"Contract validation error: {e}") from e

    return wrapper


def handle_subgraph_errors(func: Callable) -> Callable:
    """
    Decorator to handle subgraph query errors.

    Catches HTTP errors and network errors when querying subgraph endpoints.

    :param func: Function to wrap
    :return: Wrapped function with subgraph error handling
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):  # type: ignore
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "not set")
            raise SubgraphError(
                f"HTTP error from subgraph: {e}", subgraph_url=subgraph_url
            ) from e
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as e:
            subgraph_url = os.getenv("MECHX_SUBGRAPH_URL", "not set")
            raise SubgraphError(
                f"Network error connecting to subgraph: {e}",
                subgraph_url=subgraph_url,
            ) from e

    return wrapper

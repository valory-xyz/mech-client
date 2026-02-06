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

"""User-friendly error message templates."""

from typing import Optional


class ErrorMessages:
    """Collection of user-friendly error message templates.

    Provides consistent, actionable error messages for common failure
    scenarios. All messages include context and suggested solutions.
    """

    @staticmethod
    def rpc_error(rpc_url: str, error_details: str) -> str:
        """
        Format RPC endpoint error message.

        :param rpc_url: RPC endpoint URL that failed
        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"RPC endpoint error: {error_details}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the RPC endpoint is available and accessible\n"
            f"  2. Set a different RPC endpoint:\n"
            f"     export MECHX_CHAIN_RPC='https://your-rpc-url'\n"
            f"  3. Check your network connection"
        )

    @staticmethod
    def rpc_network_error(rpc_url: str, error_details: str) -> str:
        """
        Format RPC network connection error message.

        :param rpc_url: RPC endpoint URL that failed
        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"Network error connecting to RPC endpoint: {error_details}\n\n"
            f"Current RPC: {rpc_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check your internet connection\n"
            f"  2. Verify the RPC URL is correct\n"
            f"  3. Try a different RPC provider:\n"
            f"     export MECHX_CHAIN_RPC='https://your-rpc-url'"
        )

    @staticmethod
    def rpc_timeout(rpc_url: Optional[str], error_details: str) -> str:
        """
        Format RPC timeout error message.

        :param rpc_url: RPC endpoint URL (optional)
        :param error_details: Specific error details
        :return: Formatted error message
        """
        msg = (
            "Timeout while waiting for transaction receipt via HTTP RPC.\n\n"
            f"Error details: {error_details}\n\n"
        )

        if rpc_url:
            msg += f"Current MECHX_CHAIN_RPC: {rpc_url}\n\n"
        else:
            msg += "Using default RPC endpoint from config\n\n"

        msg += (
            "Possible causes:\n"
            "  • RPC endpoint is slow, rate-limiting, or unavailable\n"
            "  • Network connectivity issues\n\n"
            "Recommended actions:\n"
            "  1. Check if your transaction succeeded on a block explorer\n"
            "  2. Try a reliable RPC provider (Alchemy, Infura, Ankr)\n"
            "  3. Set a different HTTP RPC endpoint:\n"
            "     export MECHX_CHAIN_RPC='https://your-http-rpc-url'"
        )
        return msg

    @staticmethod
    def subgraph_error(subgraph_url: str, error_details: str) -> str:
        """
        Format subgraph query error message.

        :param subgraph_url: Subgraph endpoint URL that failed
        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"Subgraph endpoint error: {error_details}\n\n"
            f"Current subgraph URL: {subgraph_url}\n\n"
            f"Possible solutions:\n"
            f"  1. Check if the subgraph endpoint is available\n"
            f"  2. Set a different subgraph URL:\n"
            f"     export MECHX_SUBGRAPH_URL='https://your-subgraph-url'\n"
            f"  3. Check your network connection"
        )

    @staticmethod
    def contract_logic_error(error_details: str) -> str:
        """
        Format smart contract logic error message.

        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"Smart contract error: {error_details}\n\n"
            f"This may indicate:\n"
            f"  • Insufficient balance or missing approvals\n"
            f"  • Invalid parameters passed to contract\n"
            f"  • Contract requirements not met\n\n"
            f"Please verify your addresses and balances."
        )

    @staticmethod
    def validation_error(error_details: str) -> str:
        """
        Format transaction validation error message.

        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"Transaction validation error: {error_details}\n\n"
            f"The transaction failed validation before being sent.\n\n"
            f"Possible causes:\n"
            f"  • Invalid amount or address format\n"
            f"  • Gas estimation failed\n"
            f"  • Nonce issues\n\n"
            f"Please verify your inputs and try again."
        )

    @staticmethod
    def missing_env_var(var_name: str, purpose: str) -> str:
        """
        Format missing environment variable error message.

        :param var_name: Name of the missing environment variable
        :param purpose: What the variable is used for
        :return: Formatted error message
        """
        return (
            f"Environment variable {var_name} is required for {purpose}.\n\n"
            f"Please set it:\n"
            f"  export {var_name}='your-value'"
        )

    @staticmethod
    def chain_not_supported(chain: str, feature: str, supported_chains: str) -> str:
        """
        Format chain not supported error message.

        :param chain: Chain that is not supported
        :param feature: Feature that requires support
        :param supported_chains: Comma-separated list of supported chains
        :return: Formatted error message
        """
        return (
            f"Chain {chain!r} does not support {feature}.\n\n"
            f"Supported chains: {supported_chains}"
        )

    @staticmethod
    def insufficient_balance(token_name: str, required: str, available: str) -> str:
        """
        Format insufficient balance error message.

        :param token_name: Name of the token
        :param required: Required amount
        :param available: Available amount
        :return: Formatted error message
        """
        return (
            f"Insufficient {token_name} balance.\n\n"
            f"Required: {required}\n"
            f"Available: {available}\n\n"
            f"Please add more {token_name} to your account."
        )

    @staticmethod
    def agent_mode_not_setup(chain: str) -> str:
        """
        Format agent mode not setup error message.

        :param chain: Chain for which agent mode is not set up
        :return: Formatted error message
        """
        return (
            f"Agent mode is not set up for chain: {chain}\n\n"
            f"Please run the setup command:\n"
            f"  mechx setup --chain-config {chain}"
        )

    @staticmethod
    def tool_not_found(tool_id: str, service_id: int) -> str:
        """
        Format tool not found error message.

        :param tool_id: Tool ID that was not found
        :param service_id: Service ID to query
        :return: Formatted error message
        """
        return (
            f"Tool {tool_id!r} not found.\n\n"
            f"Use 'mechx tool list {service_id}' to see available tools."
        )

    @staticmethod
    def ipfs_error(operation: str, error_details: str) -> str:
        """
        Format IPFS operation error message.

        :param operation: IPFS operation that failed (upload, download)
        :param error_details: Specific error details
        :return: Formatted error message
        """
        return (
            f"IPFS {operation} error: {error_details}\n\n"
            f"This may indicate:\n"
            f"  • IPFS gateway is unavailable\n"
            f"  • Network connectivity issues\n"
            f"  • Invalid IPFS hash\n\n"
            f"Please try again in a few moments."
        )

    @staticmethod
    def delivery_timeout(timeout_seconds: float, request_ids: list) -> str:
        """
        Format delivery timeout error message.

        :param timeout_seconds: Timeout duration in seconds
        :param request_ids: Request IDs that timed out
        :return: Formatted error message
        """
        return (
            f"Timeout after {timeout_seconds}s waiting for delivery.\n\n"
            f"Request IDs: {', '.join(request_ids)}\n\n"
            f"The mech may still be processing your request.\n"
            f"Check back later or increase the timeout."
        )

    @staticmethod
    def private_key_error(error_type: str, details: str) -> str:
        """
        Format private key error message.

        :param error_type: Type of error (permission, decryption, not_found)
        :param details: Specific error details
        :return: Formatted error message
        """
        if error_type == "permission":
            return (
                f"Permission denied when reading private key: {details}\n\n"
                f"Fix file permissions:\n"
                f"  chmod 600 ethereum_private_key.txt"
            )
        if error_type == "decryption":
            return (
                f"Failed to decrypt private key: {details}\n\n"
                f"Possible causes:\n"
                f"  • Incorrect password\n"
                f"  • Corrupted keyfile\n"
                f"  • Invalid keyfile format\n\n"
                f"Verify your OPERATE_PASSWORD or re-run setup."
            )
        if error_type == "not_found":
            return (
                f"Private key file not found: {details}\n\n"
                f"Provide a valid private key path:\n"
                f"  --key /path/to/key"
            )
        return f"Private key error: {details}"

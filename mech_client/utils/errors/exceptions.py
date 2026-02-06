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

"""Custom exception classes for mech client errors."""

from typing import Optional


class MechClientError(Exception):
    """Base exception for all mech client errors.

    All custom exceptions in the mech client should inherit from this base
    class to enable consistent error handling.
    """

    def __init__(self, message: str, details: Optional[str] = None):
        """
        Initialize mech client error.

        :param message: Primary error message
        :param details: Optional additional details or context
        """
        self.message = message
        self.details = details
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """
        Format the complete error message.

        :return: Formatted error message with details if present
        """
        if self.details:
            return f"{self.message}\n\nDetails: {self.details}"
        return self.message


class RpcError(MechClientError):
    """Exception raised for RPC endpoint errors.

    Includes HTTP errors, connection errors, and timeouts when communicating
    with blockchain RPC endpoints.
    """

    def __init__(
        self, message: str, rpc_url: Optional[str] = None, details: Optional[str] = None
    ):
        """
        Initialize RPC error.

        :param message: Error message
        :param rpc_url: RPC endpoint URL that failed
        :param details: Additional error details
        """
        self.rpc_url = rpc_url
        super().__init__(message, details)


class SubgraphError(MechClientError):
    """Exception raised for subgraph query errors.

    Includes GraphQL query failures, network errors, and malformed responses
    from subgraph endpoints.
    """

    def __init__(
        self,
        message: str,
        subgraph_url: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """
        Initialize subgraph error.

        :param message: Error message
        :param subgraph_url: Subgraph endpoint URL that failed
        :param details: Additional error details
        """
        self.subgraph_url = subgraph_url
        super().__init__(message, details)


class ContractError(MechClientError):
    """Exception raised for smart contract interaction errors.

    Includes contract logic errors, validation errors, and transaction
    failures when interacting with on-chain contracts.
    """

    def __init__(
        self,
        message: str,
        contract_address: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """
        Initialize contract error.

        :param message: Error message
        :param contract_address: Contract address that caused the error
        :param details: Additional error details
        """
        self.contract_address = contract_address
        super().__init__(message, details)


class ValidationError(MechClientError):
    """Exception raised for validation errors.

    Includes input validation failures, parameter checking, and business rule
    violations before operations are attempted.
    """

    def __init__(
        self, message: str, field: Optional[str] = None, details: Optional[str] = None
    ):
        """
        Initialize validation error.

        :param message: Error message
        :param field: Field name that failed validation
        :param details: Additional validation error details
        """
        self.field = field
        super().__init__(message, details)


class ConfigurationError(MechClientError):
    """Exception raised for configuration errors.

    Includes missing configuration files, invalid configuration values, and
    environment setup issues.
    """


class TransactionError(MechClientError):
    """Exception raised for transaction execution errors.

    Includes transaction building, signing, and submission failures.
    """

    def __init__(
        self, message: str, tx_hash: Optional[str] = None, details: Optional[str] = None
    ):
        """
        Initialize transaction error.

        :param message: Error message
        :param tx_hash: Transaction hash if available
        :param details: Additional transaction error details
        """
        self.tx_hash = tx_hash
        super().__init__(message, details)


class IPFSError(MechClientError):
    """Exception raised for IPFS operation errors.

    Includes upload/download failures, gateway errors, and content
    retrieval issues.
    """

    def __init__(
        self,
        message: str,
        ipfs_hash: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """
        Initialize IPFS error.

        :param message: Error message
        :param ipfs_hash: IPFS hash (CID) related to the error
        :param details: Additional IPFS error details
        """
        self.ipfs_hash = ipfs_hash
        super().__init__(message, details)


class ToolError(MechClientError):
    """Exception raised for tool-related errors.

    Includes tool discovery failures, metadata parsing errors, and tool
    execution issues.
    """

    def __init__(
        self, message: str, tool_id: Optional[str] = None, details: Optional[str] = None
    ):
        """
        Initialize tool error.

        :param message: Error message
        :param tool_id: Tool identifier related to the error
        :param details: Additional tool error details
        """
        self.tool_id = tool_id
        super().__init__(message, details)


class AgentModeError(MechClientError):
    """Exception raised for agent mode operation errors.

    Includes Safe multisig setup failures, Operate middleware errors, and
    agent configuration issues.
    """


class PaymentError(MechClientError):
    """Exception raised for payment-related errors.

    Includes insufficient balance, token approval failures, and payment
    strategy errors.
    """

    def __init__(
        self,
        message: str,
        payment_type: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """
        Initialize payment error.

        :param message: Error message
        :param payment_type: Payment type that caused the error
        :param details: Additional payment error details
        """
        self.payment_type = payment_type
        super().__init__(message, details)


class DeliveryTimeoutError(MechClientError):
    """Exception raised when waiting for mech delivery times out.

    Raised when the maximum timeout is reached while waiting for mech
    responses to be delivered.
    """

    def __init__(self, message: str, request_ids: Optional[list] = None):
        """
        Initialize delivery timeout error.

        :param message: Error message
        :param request_ids: Request IDs that timed out
        """
        self.request_ids = request_ids or []
        super().__init__(message)

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

"""Marketplace service for orchestrating mech requests."""

import functools
import inspect
import logging
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import requests
from aea_ledger_ethereum import EthereumCrypto
from eth_account import Account
from mech_client.domain.delivery import (
    DeliveryResult,
    OffchainDeliveryWatcher,
    OnchainDeliveryWatcher,
)
from mech_client.domain.payment import PaymentStrategyFactory
from mech_client.domain.payment.addresses import DEPOSIT_PAYMENT_TYPES
from mech_client.domain.request_id import request_digest
from mech_client.domain.signing import Signer
from mech_client.domain.tools import ToolManager
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.blockchain.receipt_waiter import (
    wait_for_receipt,
    watch_for_marketplace_request_ids,
)
from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.ipfs import IPFSClient, push_metadata_to_ipfs
from mech_client.services.base_service import BaseTransactionService
from mech_client.utils.validators import ensure_checksummed_address
from safe_eth.eth import EthereumClient
from web3.contract import Contract as Web3Contract
from web3.exceptions import Web3Exception
from web3.types import TxReceipt

logger = logging.getLogger(__name__)

# HTTP status the offchain mech returns when the requester's prepaid balance is
# insufficient (structured 402 challenge, see mech task_execution handlers).
HTTP_UNAUTHORIZED = 401
HTTP_PAYMENT_REQUIRED = 402
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_CLIENT_ERRORS = range(400, 500)
# The responseTimeout written into every request, in seconds: past it the
# mech is out of time by the request's own terms.
RESPONSE_TIMEOUT_SECONDS = 300
# Outbound HTTP timeout (seconds) for the offchain request POST.
OFFCHAIN_HTTP_TIMEOUT = 30
# Hard cap on auto-deposit: refuse to top up more than this multiple of the
# requester's signed ``max_delivery_rate`` in a single retry. The mech URL is
# auto-discovered from on-chain metadata, so without a cap a compromised or
# buggy mech could return a huge ``required`` and drain the user's wallet
# into their own balance tracker. Funds aren't stolen (they sit in the user's
# tracker, bounded by ``check_balance``) but they're locked up and the user's
# wallet drained. 10x is generous for legitimate price moves between
# signature and request, tight enough that catastrophic drain stays bounded.
_MAX_AUTO_DEPOSIT_RATIO = 10


def _accepted_note(accepted_ids: List[str], request_nonces: List[int]) -> str:
    """Name the requests accepted earlier in a failed call, if any.

    :param accepted_ids: Hex ids accepted earlier in the call, in order
    :param request_nonces: Nonces of every request in the call
    :return: The note to append to the error message, or ""
    """
    if not accepted_ids:
        return ""
    accepted = ", ".join(
        f"{rid} (nonce {n})" for rid, n in zip(accepted_ids, request_nonces)
    )
    return f" Accepted earlier in this call, not watched: {accepted}."


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to ``int`` with a numeric fallback.

    The 402 challenge body comes from an untrusted source (the mech). A buggy
    or hostile mech can send ``"required": "N/A"`` or similar non-numeric
    strings; ``int(...)`` would raise ``ValueError`` and surface as a raw
    traceback to the requester. Falling back to ``default`` here turns a
    malformed field into an actionable "insufficient balance" message
    downstream instead.

    :param value: the value to coerce.
    :param default: the value to return when ``value`` is None or not coercible.
    :return: an int.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class OnchainRequestResult(TypedDict):
    """What :meth:`MarketplaceService.send_request` returns on the on-chain path.

    The shape is a documented public contract, so spell it out: a key typo at
    a call site is then a mypy error rather than a runtime ``KeyError``.

    ``receipt`` is web3's ``TxReceipt``, an ``AttributeDict`` — a dict subclass
    that also allows attribute access, which a plain ``Dict[str, Any]`` would
    have hidden from consumers.
    """

    tx_hash: str
    request_ids: List[str]
    receipt: TxReceipt
    deliveries: Dict[str, DeliveryResult]


class OffchainRequestResult(TypedDict):
    """What :meth:`MarketplaceService.send_request` returns on the offchain path.

    There is no transaction to report, so ``tx_hash`` and ``receipt`` are
    always ``None`` — typed as such rather than ``Optional`` so that the two
    cannot be described independently. ``request_ids`` is populated here too.
    """

    tx_hash: None
    request_ids: List[str]
    nonces: List[int]
    receipt: None
    deliveries: Dict[str, DeliveryResult]


class _FieldsError(ValueError):
    """A ``ValueError`` whose keyword-only fields survive pickle and copy."""

    def __reduce__(self) -> Tuple[Any, ...]:
        """Rebuild with the keyword-only fields, which ``args`` lacks.

        :return: The callable and arguments that rebuild this exception
        """
        fields = {k: v for k, v in vars(self).items() if not k.startswith("_")}
        return functools.partial(type(self), str(self), **fields), ()


class _OffchainRequestError(_FieldsError):
    """An error about one request of an offchain call."""


class OffchainRequestRejected(_OffchainRequestError):
    """The mech answered an offchain request with an HTTP error."""

    def __init__(  # pylint: disable=too-many-arguments  # the spec's fields, kw-only
        self,
        message: str,
        *,
        request_id: str,
        nonce: int,
        status: int,
        reason: str,
        unsent: List[int],
        deposited: int = 0,
    ) -> None:
        """
        Initialize the rejection.

        :param message: Human-readable error message
        :param request_id: Hex id of the rejected request, as in ``request_ids``
        :param nonce: Marketplace nonce of the rejected request
        :param status: HTTP status the mech answered with
        :param reason: The mech's ``reason`` as a string, else the HTTP reason
        :param unsent: Nonces of this call after the rejected one, not sent
        :param deposited: Amount auto-deposited for this request before the
            mech answered 402 again, else 0
        """
        super().__init__(message)
        self.request_id = request_id
        self.nonce = nonce
        self.status = status
        self.reason = reason
        self.unsent = unsent
        self.deposited = deposited

    @property
    def retryable(self) -> bool:
        """True for HTTP 503; the mech uses it mostly, not only, for transient failures."""
        return self.status == HTTP_SERVICE_UNAVAILABLE


class OffchainTopUpFailed(_OffchainRequestError):
    """The auto top-up after the mech's HTTP 402 failed; the request was not accepted."""

    def __init__(
        self, message: str, *, request_id: str, nonce: int, unsent: List[int]
    ) -> None:
        """
        Initialize the failure.

        :param message: Human-readable error message, naming the top-up's cause
        :param request_id: Hex id of the request, as in ``request_ids``
        :param nonce: Marketplace nonce of the request
        :param unsent: Nonces of this call after this one, not sent
        """
        super().__init__(message)
        self.request_id = request_id
        self.nonce = nonce
        self.unsent = unsent


class RequestIdMismatch(_FieldsError):
    """The RPC's ``getRequestId`` disagrees with the locally derived request id.

    Raised before ``on_request_id`` and before signing: nothing of this
    request was signed or sent.
    """

    def __init__(
        self, message: str, *, expected: str, reported: str, nonce: int
    ) -> None:
        """
        Initialize the mismatch.

        :param message: Human-readable error message
        :param expected: Hex id derived locally, unprefixed as in ``request_ids``
        :param reported: Hex id the RPC's ``getRequestId`` answered
        :param nonce: Marketplace nonce of the request
        """
        super().__init__(message)
        self.expected = expected
        self.reported = reported
        self.nonce = nonce


class MechPriceExceeded(_FieldsError):
    """The mech's price for the call is above the caller's ``max_price``.

    Raised before any deposit, signature or POST.
    """

    def __init__(self, message: str, *, price: int, max_price: int) -> None:
        """
        Initialize the refusal.

        :param message: Human-readable error message
        :param price: The mech's ``max_delivery_rate`` times the request count
        :param max_price: The caller's cap
        """
        super().__init__(message)
        self.price = price
        self.max_price = max_price


class MechInfo(NamedTuple):
    """What the mech contract says about a mech."""

    mech: str
    service_id: int
    payment_type: PaymentType
    # per request, in the payment asset's base units
    max_delivery_rate: int


class _MechRefusal(ValueError):
    """A 402 path the offchain request could not get past."""

    def __init__(
        self, message: str, response: requests.Response, deposited: int = 0
    ) -> None:
        """
        Initialize the refusal.

        :param message: Human-readable error message
        :param response: The mech's last HTTP response
        :param deposited: Amount auto-deposited before that response
        """
        super().__init__(message)
        self.response = response
        self.deposited = deposited


class _TopUpFailure(ValueError):
    """An auto top-up that failed on the requester's side."""


#: The two are a discriminated union rather than one shape with optional
#: fields: `tx_hash` and `receipt` are set together or absent together, and
#: `Optional` on both would admit the two states where only one is filled in.
RequestResult = Union[OnchainRequestResult, OffchainRequestResult]


@dataclass(frozen=True)
class PaymentChallenge:
    """Typed view of the structured 402 challenge the mech returns.

    Keeping this typed (rather than a bare ``Dict[str, Any]``) means a key
    typo at a call site is a mypy error rather than a runtime ``KeyError``,
    and the ``shortfall`` math lives in one place instead of being
    re-computed at every consumer.
    """

    required: int
    current_balance: int
    pay_to: str
    asset: str
    chain_id: int
    error: str

    @property
    def shortfall(self) -> int:
        """The deficit the requester needs to top up. Never negative."""
        return max(0, self.required - self.current_balance)


class MarketplaceService(
    BaseTransactionService
):  # pylint: disable=too-many-instance-attributes,too-few-public-methods
    """Service for orchestrating mech marketplace requests.

    Composes payment strategies, execution strategies, tool management,
    and delivery watching to provide high-level marketplace operations.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        chain_config: str,
        agent_mode: bool,
        crypto: Optional[EthereumCrypto] = None,
        safe_address: Optional[str] = None,
        ethereum_client: Optional[EthereumClient] = None,
        signer: Optional[Signer] = None,
        rpc_url: Optional[str] = None,
    ):
        """
        Initialize marketplace service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param crypto: Ethereum crypto object for local signing (alternative to signer)
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        :param signer: Signer for externalized signing (alternative to crypto)
        :param rpc_url: RPC endpoint for this service; None keeps the
            MECHX_CHAIN_RPC / operate config / mechs.json lookup
        """
        super().__init__(
            chain_config=chain_config,
            agent_mode=agent_mode,
            crypto=crypto,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
            signer=signer,
            rpc_url=rpc_url,
        )

        # Create tool manager
        self.tool_manager = ToolManager(chain_config, rpc_url=rpc_url)

        # Create IPFS client
        self.ipfs_client = IPFSClient()

    def _log_terms_notice(self, mech_address: str, metadata: Any) -> None:
        """
        State whose terms apply before the request is signed.

        A Valory mech gets the approved Valory notice. Any other mech, or one
        the check could not identify, gets the terms link its operator
        published, passed on as published: this client states no terms on
        that operator's behalf. A check that could not complete is logged as
        a warning.

        :param mech_address: The address of the mech about to be called
        :param metadata: The mech's already fetched metadata document, or None
        """
        report = self.tool_manager.terms_report(mech_address, metadata)
        if report["valory_operated"]:
            logger.info(report["terms"])
            return
        note = report.get("identification_note")
        if note:
            logger.warning(note)
        terms_url = report.get("terms_url")
        if terms_url:
            logger.info(f"The operator of this Mech publishes terms at {terms_url}")

    async def send_request(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        prompts: Tuple[str, ...],
        tools: Tuple[str, ...],
        priority_mech: Optional[str] = None,
        use_prepaid: bool = False,
        use_offchain: bool = False,
        auto_deposit: bool = False,
        extra_attributes: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        nonces: Optional[Sequence[int]] = None,
        on_request_id: Optional[Callable[[bytes, int], None]] = None,
        max_price: Optional[int] = None,
    ) -> RequestResult:
        """
        Send marketplace request(s) to mech(s).

        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech: Priority mech address (optional)
        :param use_prepaid: Use prepaid balance instead of per-request payment
        :param use_offchain: Use offchain mech (URL discovered from metadata)
        :param auto_deposit: On an offchain HTTP 402, top up the prepaid balance
            with the shortfall and retry once (only applies to the offchain path)
        :param extra_attributes: Extra attributes for metadata. An
            ``extra_attributes["nonce"]`` replaces the random metadata salt,
            so the same inputs sign the same request id.
        :param timeout: Timeout for delivery watching
        :param nonces: Offchain only: the marketplace nonce for each prompt,
            instead of ``mapNonces(sender) + i``. Integers, strictly
            increasing, none below ``mapNonces(sender)``.
        :param on_request_id: Offchain only, synchronous: called with each raw
            32-byte request id and its nonce just before the request is
            signed, once the id derived locally from ``domainSeparator()``
            has been checked against ``getRequestId``. If it raises, that
            request and the rest of the call are neither signed nor sent;
            earlier ones were already sent.
        :param max_price: The most the requests may cost, in the payment
            asset's base units. When the mech's ``max_delivery_rate`` times
            the number of prompts exceeds it, :class:`MechPriceExceeded` is
            raised before any deposit, signature or POST. The cap covers that
            request price only: an auto-deposit after an HTTP 402 is bounded
            separately, by ``_MAX_AUTO_DEPOSIT_RATIO`` times the rate.
            ``None`` sets no cap.
        :return: A :class:`RequestResult` with ``tx_hash`` and ``receipt``
            (both ``None`` on the offchain path, which has no transaction),
            ``request_ids``, and ``deliveries`` mapping each request ID to a
            :class:`DeliveryResult` carrying the parsed content the mech
            delivered plus the gateway URL it was read from. ``deliveries``
            has the same shape regardless of whether delivery was on-chain
            or offchain. The offchain result also lists the ``nonces`` used.
            A mech's HTTP error raises :class:`OffchainRequestRejected`; an RPC
            whose ``getRequestId`` disagrees with the local derivation raises
            :class:`RequestIdMismatch` before signing.
        """
        # Validate inputs
        if len(prompts) != len(tools):
            raise ValueError(
                f"Number of prompts ({len(prompts)}) must match number of tools ({len(tools)})"
            )
        if not use_offchain and (nonces is not None or on_request_id is not None):
            raise ValueError("nonces and on_request_id apply only to offchain requests")
        if nonces is not None:
            if len(nonces) != len(prompts):
                raise ValueError(
                    f"Number of nonces ({len(nonces)}) must match number of prompts ({len(prompts)})"
                )
            if not all(isinstance(n, int) and not isinstance(n, bool) for n in nonces):
                raise ValueError(f"Nonces {list(nonces)} must be integers")
            if any(b <= a for a, b in zip(nonces, nonces[1:])):
                raise ValueError(f"Nonces {list(nonces)} must be strictly increasing")

        if max_price is not None and (
            not isinstance(max_price, int) or isinstance(max_price, bool)
        ):
            raise ValueError(f"max_price {max_price!r} must be an integer")

        marketplace_contract = self.marketplace_contract()

        priority_mech_address = priority_mech or self.mech_config.priority_mech_address
        if not priority_mech_address:
            raise ValueError("No priority mech address specified")
        info = self.mech_info(priority_mech_address)
        payment_type, service_id, max_delivery_rate = (
            info.payment_type,
            info.service_id,
            info.max_delivery_rate,
        )
        # the mech contract's own rate, not mechs.json's chain-wide default price
        price = max_delivery_rate * len(prompts)
        if max_price is not None and price > max_price:
            raise MechPriceExceeded(
                f"Mech {info.mech} charges up to {price} for {len(prompts)} "
                f"request(s) ({max_delivery_rate} each), above max_price "
                f"{max_price}. Nothing was paid, signed or sent.",
                price=price,
                max_price=max_price,
            )

        # One metadata read per request: the tool check, the terms notice and
        # the offchain URL lookup all derive from this document.
        read = self.tool_manager.read_tools_metadata(service_id)
        metadata = read.document
        self._validate_tools(tools, service_id, metadata)

        response_timeout = RESPONSE_TIMEOUT_SECONDS

        self._log_terms_notice(priority_mech_address, metadata)

        # Branch between on-chain and off-chain flows
        if use_offchain:
            offchain_url = self.tool_manager.offchain_url_from_metadata(
                service_id, read
            )
            logger.info(f"Discovered offchain URL for the mech: {offchain_url}")

            return await self._send_offchain_request(
                marketplace_contract=marketplace_contract,
                prompts=prompts,
                tools=tools,
                priority_mech_address=priority_mech_address,
                max_delivery_rate=max_delivery_rate,
                payment_type=payment_type,
                response_timeout=response_timeout,
                mech_offchain_url=offchain_url,
                extra_attributes=extra_attributes,
                timeout=timeout or 300.0,
                auto_deposit=auto_deposit,
                nonces=nonces,
                on_request_id=on_request_id,
            )

        # On-chain flow
        # Create payment strategy
        payment_strategy = PaymentStrategyFactory.create(
            payment_type=payment_type,
            ledger_api=self.ledger_api,
            chain_id=self.mech_config.ledger_config.chain_id,
        )

        # Prepare metadata and upload to IPFS
        logger.info("Uploading metadata to IPFS...")
        data_hashes = []
        for prompt, tool in zip(prompts, tools):
            data_hash, _ = push_metadata_to_ipfs(prompt, tool, extra_attributes or {})
            data_hashes.append(data_hash)
        logger.info(f"Uploaded {len(data_hashes)} metadata hash(es) to IPFS")

        # Handle payment (approval if needed)
        # `is_token()` also matches TOKEN_NVM_USDC, which the factory routes
        # to NVMPaymentStrategy (no ERC20 approve) — gate on the exact types
        # that resolve to TokenPaymentStrategy, mirroring factory.py:59.
        if not use_prepaid and payment_type in (
            PaymentType.OLAS_TOKEN,
            PaymentType.USDC_TOKEN,
        ):
            balance_tracker = payment_strategy.get_balance_tracker_address()
            # The marketplace pulls up to `price` via
            # `BalanceTracker.checkAndRecordDeliveryRates`, so approve that much.
            # Check balance
            logger.info(f"Checking {payment_type.name} token balance...")
            sender = self.executor.get_sender_address()
            if not payment_strategy.check_balance(sender, price):
                raise ValueError(
                    f"Insufficient balance for token payment. Required: {price} wei. "
                    f"Please check your token balance for address: {sender}"
                )

            # Approve. TokenPaymentStrategy.approve_if_needed always returns
            # the hash of a sent transaction or raises; the base signature is
            # Optional[str] only because NativePaymentStrategy is a no-op.
            logger.info(
                f"Approving {price} wei ({max_delivery_rate} per request "
                f"x {len(prompts)}) for spender {balance_tracker}..."
            )
            approval_tx_hash = cast(
                str,
                payment_strategy.approve_if_needed(
                    payer_address=sender,
                    spender_address=balance_tracker,
                    amount=price,
                    executor=self.executor,
                ),
            )
            # Wait for the approval to be mined before submitting the request.
            # Otherwise the request transaction is built on the pre-approval
            # ("latest") nonce while the approval is still pending, so both grab
            # the same nonce -> "replacement transaction underpriced", and the
            # allowance may not yet be on-chain when the request pulls payment.
            approval_receipt = wait_for_receipt(approval_tx_hash, self.ledger_api)
            if approval_receipt.get("status") != 1:
                raise ValueError(
                    f"Token approval transaction reverted. Hash: {approval_tx_hash}. "
                    f"The request was not sent. This often means the approval ran "
                    f"out of gas; check the transaction on the block explorer."
                )
            logger.info("Token approval complete")

        logger.info("Submitting marketplace request transaction...")
        tx_hash = self._send_marketplace_request(
            marketplace_contract=marketplace_contract,
            data_hashes=data_hashes,
            max_delivery_rate=max_delivery_rate,
            payment_type=payment_type,
            priority_mech=priority_mech_address,
            response_timeout=response_timeout,
            use_prepaid=use_prepaid,
        )
        tx_url = self.mech_config.transaction_url.format(transaction_digest=tx_hash)
        logger.info(f"Transaction submitted: {tx_url}")

        # Wait for receipt and check success
        receipt = wait_for_receipt(tx_hash, self.ledger_api)
        if receipt.get("status") != 1:
            raise ValueError(
                f"Transaction reverted. Hash: {tx_hash}. "
                f"This may indicate insufficient gas or a contract error. "
                f"Check the transaction on the block explorer: "
                f"{tx_url}"
            )
        request_ids = watch_for_marketplace_request_ids(
            marketplace_contract, self.ledger_api, tx_hash, tx_receipt=receipt
        )
        logger.info(f"Transaction confirmed: {tx_url}")

        # Watch for on-chain delivery (scan from tx block to catch all Deliver events)
        logger.info("Waiting for mech delivery...")
        watcher = OnchainDeliveryWatcher(marketplace_contract, self.ledger_api, timeout)
        tx_block = receipt.get("blockNumber")
        results = await watcher.watch(request_ids, from_block=tx_block)

        return {
            "tx_hash": tx_hash,
            "request_ids": request_ids,
            "deliveries": results,
            "receipt": receipt,
        }

    async def _send_offchain_request(  # pylint: disable=too-many-arguments,too-many-locals,unused-argument
        self,
        marketplace_contract: Web3Contract,
        prompts: Tuple[str, ...],
        tools: Tuple[str, ...],
        priority_mech_address: str,
        max_delivery_rate: int,
        payment_type: PaymentType,
        response_timeout: int,
        mech_offchain_url: str,
        extra_attributes: Optional[Dict[str, Any]],
        timeout: float,
        auto_deposit: bool = False,
        nonces: Optional[Sequence[int]] = None,
        on_request_id: Optional[Callable[[bytes, int], None]] = None,
    ) -> OffchainRequestResult:
        """
        Send offchain request to mech HTTP endpoint.

        :param marketplace_contract: Marketplace contract instance
        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech_address: Mech address
        :param max_delivery_rate: Max delivery rate from mech
        :param payment_type: Payment type
        :param response_timeout: Response timeout in seconds
        :param mech_offchain_url: Base URL of offchain mech
        :param extra_attributes: Extra attributes for metadata
        :param timeout: Delivery watching timeout
        :param auto_deposit: On a 402, deposit the shortfall and retry once
        :param nonces: Marketplace nonce per prompt (see ``send_request``)
        :param on_request_id: Pre-sign hook (see ``send_request``)
        :return: Dictionary with request results
        """
        logger.info("Sending offchain mech marketplace request...")

        # In agent mode the requester of record is the Safe (msg.sender on
        # the on-chain path, ``mapNonces`` key, and requester bound into
        # ``getRequestId``); in client mode it is the EOA. The signature is
        # verified against this address downstream (Safe.isValidSignature
        # for the Safe branch, plain ecrecover for the EOA branch).
        sender = self.requester()
        current_nonce = marketplace_contract.functions.mapNonces(sender).call()
        if nonces is None:
            request_nonces = [current_nonce + i for i in range(len(prompts))]
        else:
            request_nonces = list(nonces)
            stale = [n for n in request_nonces if n < current_nonce]
            if stale:
                raise ValueError(
                    f"Nonce(s) {stale} are below the requester's marketplace "
                    f"nonce {current_nonce} and can never settle."
                )

        # See request_digest for why the signed id is derived locally.
        domain_separator = bytes(
            marketplace_contract.functions.domainSeparator().call()
        )
        marketplace_address = str(marketplace_contract.address)
        mech_address = ensure_checksummed_address(priority_mech_address)
        payment_type_bytes = bytes.fromhex(payment_type.value)

        # Prepare and send each request
        request_ids_hex: List[str] = []

        for i, (prompt, tool) in enumerate(zip(prompts, tools)):
            # Prepare metadata (get hash and data without uploading)
            # Import here to avoid circular dependency
            from mech_client.infrastructure.ipfs.metadata import (  # pylint: disable=import-outside-toplevel
                fetch_ipfs_hash,
            )

            nonce = request_nonces[i]
            try:
                data_hash, data_hash_full, ipfs_data = fetch_ipfs_hash(
                    prompt, tool, extra_attributes or {}
                )
                request_id_bytes = request_digest(
                    domain_separator=domain_separator,
                    marketplace=marketplace_address,
                    mech=mech_address,
                    requester=sender,
                    data_hash=bytes.fromhex(data_hash.removeprefix("0x")),
                    delivery_rate=max_delivery_rate,
                    payment_type=payment_type_bytes,
                    nonce=nonce,
                )
                reported = bytes(
                    marketplace_contract.functions.getRequestId(
                        mech_address,
                        sender,
                        data_hash,
                        max_delivery_rate,
                        "0x" + payment_type.value,
                        nonce,
                    ).call()
                )
            except (OSError, ValueError, Web3Exception) as e:
                if not request_ids_hex:
                    raise
                # earlier requests went out: say so, as a transport error does
                raise ValueError(
                    f"Failed to derive the request id for nonce {nonce}: {e}"
                    + _accepted_note(request_ids_hex, request_nonces)
                ) from e
            logger.info(
                f"Prompt sent directly to the mech (not published to IPFS); "
                f"content CID {data_hash_full}"
            )
            if reported != request_id_bytes:
                raise RequestIdMismatch(
                    f"The RPC's getRequestId answered {reported.hex()} for nonce "
                    f"{nonce}, not the locally derived {request_id_bytes.hex()}; "
                    f"nothing was signed or sent for it. Check the RPC "
                    f"(MECHX_CHAIN_RPC or rpc_url)."
                    + _accepted_note(request_ids_hex, request_nonces),
                    expected=request_id_bytes.hex(),
                    reported=reported.hex(),
                    nonce=nonce,
                )

            request_id_int = int.from_bytes(request_id_bytes, byteorder="big")
            request_id_hex = request_id_bytes.hex()

            if on_request_id is not None:
                returned = cast(Any, on_request_id)(request_id_bytes, nonce)
                if inspect.isawaitable(returned):
                    if inspect.iscoroutine(returned):
                        returned.close()
                    raise TypeError(
                        "on_request_id must be synchronous; an awaitable would "
                        "never run before the request is signed"
                    )

            # Signature encoding depends on how the marketplace verifies the
            # requester: Safe.isValidSignature (agent mode) requires the
            # SafeMessage-wrapped hash to be signed; plain ecrecover
            # (client mode) requires the raw digest.
            signature = self._sign_request_digest(sender, request_id_bytes)

            # Prepare payload
            payload = {
                "sender": sender,
                "signature": signature,
                "ipfs_hash": data_hash,
                "request_id": request_id_int,
                "delivery_rate": max_delivery_rate,
                "nonce": nonce,
                "ipfs_data": ipfs_data,
            }

            # Send HTTP POST request (handles a structured 402 + receipt header)
            url = f"{mech_offchain_url.rstrip('/')}/send_signed_requests"
            try:
                response = self._post_offchain_request(
                    url, payload, payment_type, auto_deposit, max_delivery_rate
                )
            except _MechRefusal as e:
                raise self._rejection(
                    e.response,
                    request_id_hex,
                    request_nonces,
                    request_ids_hex,
                    str(e),
                    e.deposited,
                ) from e
            except _TopUpFailure as e:
                raise OffchainTopUpFailed(
                    str(e) + _accepted_note(request_ids_hex, request_nonces),
                    request_id=request_id_hex,
                    nonce=nonce,
                    unsent=request_nonces[i + 1 :],
                ) from e
            except requests.exceptions.RequestException as e:
                raise ValueError(
                    f"Failed to send offchain request: {e}"
                    + _accepted_note(request_ids_hex, request_nonces)
                ) from e
            if not response.ok:
                raise self._rejection(
                    response, request_id_hex, request_nonces, request_ids_hex
                )

            request_ids_hex.append(request_id_hex)
            logger.info(f"Created offchain request with ID {request_id_int}")

        # Watch for offchain delivery
        logger.info("Waiting for offchain mech marketplace deliver...")
        watcher = OffchainDeliveryWatcher(mech_offchain_url, timeout)
        results = await watcher.watch(request_ids_hex)

        return {
            "tx_hash": None,  # No on-chain transaction for offchain requests
            "request_ids": request_ids_hex,
            "nonces": request_nonces,
            "deliveries": results,
            "receipt": None,  # No receipt for offchain requests
        }

    @staticmethod
    def _rejection(
        response: requests.Response,
        request_id: str,
        request_nonces: List[int],
        accepted_ids: List[str],
        message: Optional[str] = None,
        deposited: int = 0,
    ) -> OffchainRequestRejected:
        """Build the error for a request the mech answered with an HTTP error.

        :param response: The mech's HTTP response
        :param request_id: Hex id of the rejected request
        :param request_nonces: Nonces of every request in the call
        :param accepted_ids: Hex ids accepted earlier in the call, in order
        :param message: Error message, else the generic rejection text
        :param deposited: Amount auto-deposited before the response
        :return: The rejection to raise
        """
        index = len(accepted_ids)
        try:
            reason = str(response.json().get("reason") or "")
        except (ValueError, AttributeError):
            reason = ""
        reason = reason or response.reason
        if message is None:
            message = (
                f"Offchain request rejected: {reason} (HTTP {response.status_code})"
            )
        return OffchainRequestRejected(
            message + _accepted_note(accepted_ids, request_nonces),
            request_id=request_id,
            nonce=request_nonces[index],
            status=response.status_code,
            reason=reason,
            unsent=request_nonces[index + 1 :],
            deposited=deposited,
        )

    def requester(self) -> str:
        """Return the requester of record: the address requests are made from.

        In agent mode this is the Safe (matching the onchain flow where the
        Safe is ``msg.sender`` on the marketplace call); in client mode it
        is the EOA. Offchain requests use it for ``mapNonces``,
        ``getRequestId`` and the payload ``sender`` field so the mech,
        subgraph and settlement path all agree on who owns the request; a
        nonce allocator keys its queue on it.

        :return: Checksummed requester address
        :raises ValueError: if agent mode is set but no Safe address was
            passed to the service constructor
        """
        if self.agent_mode:
            if not self.safe_address:
                raise ValueError(
                    "Agent-mode offchain requests require a Safe address; "
                    "pass safe_address=... to MarketplaceService."
                )
            return ensure_checksummed_address(self.safe_address)
        return ensure_checksummed_address(self.signer.address)

    def _sign_request_digest(self, sender: str, request_id_bytes: bytes) -> str:
        """Sign the request-id digest and return the 0x-prefixed hex signature.

        Client mode: sign the raw 32-byte digest so the marketplace's
        ``ecrecover(digest, v, r, s)`` recovers to the EOA. External signer
        services commonly default to EIP-191
        (``eth_account.Account.sign_message``), which produces a signature
        that recovers to a *different* address; on-chain that fails silently
        (the request is treated as coming from an unpaid sender). Recovering
        locally and comparing against ``signer.address`` turns that
        misconfiguration into an immediate, actionable error at fire time.

        Agent mode: sign the SafeMessage-wrapped hash so
        ``Safe.isValidSignature(digest, sig)`` returns the ERC-1271 magic
        value on-chain. Raw-digest signing fails with ``GS026`` on Safe
        v1.3.0+ with the standard fallback handler. The wrapped hash is
        computed locally by the signer (no RPC round-trip).

        ``sender`` is the requester of record already resolved by the
        caller (Safe in agent mode, EOA in client mode). Threading it in
        rather than re-resolving keeps the address the signature is bound
        to identical to the address the caller wrote into the payload and
        ``getRequestId``.

        :param sender: Checksummed requester address (agent mode: Safe;
            client mode: EOA). Must equal the ``sender`` field of the
            outbound payload and the requester argument to
            ``getRequestId``.
        :param request_id_bytes: the 32-byte request-id digest to sign.
        :return: 0x-prefixed hex signature, as sent to the mech.
        :raises ValueError: if the signature has the wrong length, uses an
            unsupported ``v`` byte, or (client mode) does not recover to
            the signer's address.
        """
        if self.agent_mode:
            if not hasattr(self.signer, "sign_safe_message"):
                raise ValueError(
                    "The provided Signer implementation must define "
                    "sign_safe_message for agent-mode offchain requests. "
                    "See mech_client.domain.signing.Signer."
                )
            signature = self.signer.sign_safe_message(
                sender,
                self.mech_config.ledger_config.chain_id,
                request_id_bytes,
            )
            if len(signature) != 65:
                raise ValueError(
                    f"Signer returned a {len(signature)}-byte signature; "
                    f"expected 65 bytes (r ‖ s ‖ v). See "
                    f"Signer.sign_safe_message."
                )
            if signature[64] not in (27, 28):
                raise ValueError(
                    f"Signer returned v={signature[64]}; "
                    f"sign_safe_message requires raw-hash signing with v "
                    f"in {{27, 28}} (v=0 is read as a contract signature "
                    f"and v=1 as an approved hash by Safe, both fail as "
                    f"GS026). See Signer.sign_safe_message."
                )
            return "0x" + signature.hex()

        signature = self.signer.sign_message(request_id_bytes)
        if len(signature) != 65:
            raise ValueError(
                f"Signer returned a {len(signature)}-byte signature; expected "
                f"65 bytes (r ‖ s ‖ v). See Signer.sign_message."
            )
        # Local recovery expects v in {27, 28}; the contract accepts {0, 1}
        # too, so normalize only for the check and send the original bytes.
        normalized = signature
        if signature[64] < 27:
            normalized = signature[:64] + bytes([signature[64] + 27])
        try:
            # Raw-hash recovery mirroring the on-chain ecrecover.
            # protected-access: private-but-stable eth_account API;
            # no-value-for-parameter: _recover_hash is a combomethod, which
            # pylint misreads as an unbound instance method.
            # pylint: disable-next=protected-access,no-value-for-parameter
            recovered = Account._recover_hash(request_id_bytes, signature=normalized)
        except Exception as e:
            raise ValueError(
                f"Signer returned a signature that cannot be recovered over "
                f"the request digest (v byte {signature[64]}): {e}. See "
                f"Signer.sign_message for the expected encoding."
            ) from e
        if recovered.lower() != self.signer.address.lower():
            raise ValueError(
                f"Signer produced a signature that recovers to {recovered}, "
                f"not the signer address {self.signer.address}. Most likely "
                f"the signer applied an EIP-191 personal-message prefix; the "
                f"marketplace contract requires raw-digest signing (see "
                f"Signer.sign_message)."
            )
        return "0x" + signature.hex()

    def _post_offchain_request(
        self,
        url: str,
        payload: Dict[str, Any],
        payment_type: PaymentType,
        auto_deposit: bool,
        max_delivery_rate: int,
    ) -> requests.Response:
        """POST an offchain request, handling a structured HTTP 402.

        On a 402 (insufficient prepaid balance) the mech returns a structured
        challenge. When ``auto_deposit`` is set, the shortfall is deposited and
        the request is retried once; otherwise an actionable error is raised.
        ``max_delivery_rate`` (the requester's signed per-request maximum) is
        used as a hard ceiling on the auto-deposit amount so a hostile or
        buggy mech can't drain the wallet by returning an inflated ``required``.
        A ``Payment-Receipt`` header on the response is logged.

        :param url: the mech's ``/send_signed_requests`` endpoint.
        :param payload: the signed request payload.
        :param payment_type: the request's payment type (for the deposit asset).
        :param auto_deposit: whether to auto-deposit + retry once on a 402.
        :param max_delivery_rate: the requester's signed per-request maximum,
            used to cap the auto-deposit amount (see ``_MAX_AUTO_DEPOSIT_RATIO``).
        :return: the (possibly retried) HTTP response.
        :raises _MechRefusal: on a 402 when auto-deposit is disabled, on a
            non-positive shortfall that auto-deposit can't act on, or on a
            second 402 after the deposit landed.
        :raises _TopUpFailure: if the auto-deposit fails on the requester's side.
        """
        response = self._do_offchain_post(url, payload)
        if response.status_code == HTTP_PAYMENT_REQUIRED:
            challenge = self._parse_402_challenge(response)
            if not auto_deposit:
                raise _MechRefusal(
                    "Offchain request requires payment: need "
                    f"{challenge.required} (current balance "
                    f"{challenge.current_balance}) deposited to "
                    f"{challenge.pay_to}. Re-run with auto-deposit enabled or "
                    f"top up your prepaid balance. ({challenge.error})",
                    response,
                )
            if challenge.shortfall <= 0:
                # Auto-deposit can't do anything useful here: either the body
                # was malformed (``_safe_int`` returned 0 for required) or the
                # mech is reporting current_balance >= required while still
                # returning 402. Retrying with the same payload won't help
                # because nothing about the request changes. Surface the
                # situation honestly instead of running a no-op deposit + retry
                # that would otherwise hit the second-402 path with a message
                # claiming a deposit happened.
                raise _MechRefusal(
                    "Offchain request rejected with HTTP 402 but the challenge "
                    f"reports no shortfall (required={challenge.required}, "
                    f"current balance={challenge.current_balance}). The mech "
                    f"may be returning a malformed body or a stale balance. "
                    f"({challenge.error})",
                    response,
                )
            try:
                deposited = self._auto_deposit_for_402(
                    payment_type, challenge, max_delivery_rate
                )
            except ValueError as e:
                raise _TopUpFailure(str(e)) from e
            response = self._do_offchain_post(url, payload)
            if response.status_code == HTTP_PAYMENT_REQUIRED:
                # The deposit tx already confirmed (DepositService waits for
                # receipt), so silently returning the second 402 would surface
                # downstream as a generic "Payment Required (HTTP 402)" error
                # with no hint that funds moved. Raise explicitly so the user
                # sees how much is still short and which balance tracker holds
                # the deposit they just paid for.
                retry = self._parse_402_challenge(response)
                raise _MechRefusal(
                    "Auto-deposit did not clear the 402: deposited to "
                    f"{retry.pay_to} but the mech still requires "
                    f"{retry.required} (current balance {retry.current_balance}, "
                    f"remaining shortfall {retry.shortfall}). The deposit may "
                    f"not be mined yet, the price may have moved, or the asset "
                    f"may be wrong. ({retry.error})",
                    response,
                    deposited=deposited,
                )
        self._log_payment_receipt(response)
        return response

    @staticmethod
    def _do_offchain_post(url: str, payload: Dict[str, Any]) -> requests.Response:
        """POST the offchain payload. Centralises the headers + timeout."""
        return requests.post(
            url=url,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=OFFCHAIN_HTTP_TIMEOUT,
        )

    @staticmethod
    def _parse_402_challenge(response: requests.Response) -> PaymentChallenge:
        """Parse the structured 402 challenge body + WWW-Authenticate header.

        :param response: the 402 HTTP response from the mech.
        :return: the normalised challenge as a typed PaymentChallenge.
        """
        authenticate = response.headers.get("WWW-Authenticate")
        if authenticate:
            logger.info(f"Mech payment challenge: {authenticate}")
        try:
            body = response.json()
        except ValueError:
            # A non-JSON 402 body is the mech violating its own response
            # contract; log enough of it for an operator to debug, but don't
            # blow up the request. Downstream auto-deposit math degrades to a
            # zero-shortfall no-op, and the no-auto-deposit error message
            # surfaces "need 0 ... deposited to ''" which is at least
            # truthful given the body the mech sent.
            logger.warning(
                "402 body was not valid JSON; falling back to defaults. "
                "Raw body (first 500 chars): %r",
                response.text[:500],
            )
            body = {}
        return PaymentChallenge(
            required=_safe_int(body.get("required")),
            current_balance=_safe_int(body.get("currentBalance")),
            pay_to=str(body.get("payTo", "")),
            asset=str(body.get("asset", "")),
            chain_id=_safe_int(body.get("chainId")),
            error=str(body.get("error", "payment required")),
        )

    def _auto_deposit_for_402(
        self,
        payment_type: PaymentType,
        challenge: PaymentChallenge,
        max_delivery_rate: int,
    ) -> int:
        """Deposit the 402 shortfall into the prepaid balance.

        Refuses to deposit when the shortfall exceeds
        ``_MAX_AUTO_DEPOSIT_RATIO * max_delivery_rate`` — see the constant's
        docstring for why the cap exists.

        :param payment_type: the request's payment type (native vs token).
        :param challenge: the parsed 402 challenge.
        :param max_delivery_rate: the requester's signed per-request maximum.
        :return: the amount deposited, in a confirmed transaction.
        :raises ValueError: if the payment type doesn't support auto-deposit,
            if the requested deposit would exceed the safety cap, or if the
            deposit transaction reverted.
        """
        if challenge.shortfall <= 0:
            return 0
        if payment_type not in DEPOSIT_PAYMENT_TYPES:
            raise ValueError(
                f"Auto-deposit is not supported for payment type {payment_type.name}"
            )
        cap = max_delivery_rate * _MAX_AUTO_DEPOSIT_RATIO
        if challenge.shortfall > cap:
            # A mech with a hostile or buggy `required` field can otherwise
            # extract the user's full wallet balance in a single retry. Cap
            # at a generous multiple of the per-request maximum the user
            # actually signed; anything beyond that has to be a manual
            # deposit so the user can see the amount before it leaves their
            # wallet.
            raise ValueError(
                f"Auto-deposit refused: mech demanded a {challenge.shortfall} "
                f"shortfall which exceeds the safety cap of {cap} "
                f"({_MAX_AUTO_DEPOSIT_RATIO}x your signed max_delivery_rate of "
                f"{max_delivery_rate}). If this is legitimate, deposit the "
                f"amount manually so it leaves your wallet under your direct "
                f"control."
            )
        # Imported here to avoid a circular import at module load.
        from mech_client.services.deposit_service import (  # pylint: disable=import-outside-toplevel
            DepositService,
        )

        deposit_service = DepositService(
            chain_config=self.chain_config,
            agent_mode=self.agent_mode,
            safe_address=self.safe_address,
            ethereum_client=self.ethereum_client,
            signer=self.signer,
            rpc_url=self.rpc_url,
        )
        logger.info(
            f"Auto-depositing {challenge.shortfall} to top up the prepaid balance..."
        )
        # Per-asset dispatch over DEPOSIT_PAYMENT_TYPES. A payment type added
        # there needs a branch here too; the assertion-shaped raise below
        # catches the mismatch if only the set is updated.
        if payment_type == PaymentType.NATIVE:
            tx_hash = deposit_service.deposit_native(challenge.shortfall)
        elif payment_type == PaymentType.OLAS_TOKEN:
            tx_hash = deposit_service.deposit_token(challenge.shortfall, "olas")
        elif payment_type == PaymentType.USDC_TOKEN:
            tx_hash = deposit_service.deposit_token(challenge.shortfall, "usdc")
        else:  # pragma: no cover - guarded by the membership check above
            raise ValueError(
                f"Internal error: {payment_type.name} is listed as supported "
                f"but has no deposit dispatch branch."
            )
        # DepositService waits for the receipt but does not check its status.
        if wait_for_receipt(tx_hash, self.ledger_api).get("status") != 1:
            raise ValueError(
                f"Auto-deposit transaction {tx_hash} reverted; nothing was deposited."
            )
        return challenge.shortfall

    @staticmethod
    def _log_payment_receipt(response: requests.Response) -> None:
        """Log the ``Payment-Receipt`` header if the mech returned one.

        :param response: the HTTP response from the mech.
        """
        receipt = response.headers.get("Payment-Receipt")
        if receipt:
            logger.info(f"Payment-Receipt: {receipt}")

    def _validate_tools(
        self, tools: Tuple[str, ...], service_id: int, metadata: Any
    ) -> None:
        """
        Validate that tools exist for the service.

        Reads the available tools from the mech's metadata document and
        validates that all requested tools are available.

        :param tools: Tuple of tool identifiers
        :param service_id: Service ID of the mech
        :param metadata: The mech's metadata document, or None if unreadable
        :raises ValueError: If any tool is invalid or not available
        """
        # Basic validation - check for empty tools
        for tool in tools:
            if not tool:
                raise ValueError("Empty tool identifier")

        try:
            tools_info = self.tool_manager.tools_from_metadata(service_id, metadata)
        except (AttributeError, KeyError, TypeError) as e:
            # If fetching fails due to unexpected metadata structure,
            # warn but allow request to proceed
            logger.warning(
                f"Failed to fetch tool metadata for service {service_id}: {e}. "
                f"Tool validation skipped."
            )
            return

        if not tools_info:
            # If we can't fetch tools, warn but don't fail
            # This allows requests to proceed even if metadata fetch fails
            logger.warning(
                f"Could not fetch tool metadata for service {service_id}. "
                f"Tool validation skipped."
            )
            return

        # Get list of available tool names
        available_tools = {tool.tool_name for tool in tools_info.tools}

        # Validate each requested tool
        for tool in tools:
            if tool not in available_tools:
                raise ValueError(
                    f"Tool {tool!r} not available for service {service_id}. "
                    f"Available tools: {', '.join(sorted(available_tools))}"
                )

    def marketplace_contract(self) -> Web3Contract:
        """
        Get the marketplace contract instance for this service's chain and RPC.

        :return: Marketplace contract
        :raises ValueError: If marketplace not available on this chain
        """
        if not self.mech_config.mech_marketplace_contract:
            raise ValueError(
                f"Marketplace contract not available on {self.chain_config}"
            )

        abi = get_abi("MechMarketplace.json")
        return get_contract(
            self.mech_config.mech_marketplace_contract,
            abi,
            self.ledger_api,
        )

    def mech_info(self, mech: str) -> MechInfo:
        """
        Read a mech's service id, payment type and price from its contract.

        :param mech: The mech address
        :return: The mech's :class:`MechInfo`
        :raises ValueError: If no mech address is given
        """
        if not mech:
            raise ValueError("No mech address specified")

        abi = get_abi("IMech.json")
        mech_contract = get_contract(mech, abi, self.ledger_api)

        # Fetch mech info
        payment_type_bytes = mech_contract.functions.paymentType().call()
        max_delivery_rate = mech_contract.functions.maxDeliveryRate().call()
        service_id = mech_contract.functions.serviceId().call()

        # Convert payment type bytes to PaymentType enum
        payment_type = PaymentType.from_value(payment_type_bytes.hex())

        return MechInfo(
            mech=mech,
            service_id=service_id,
            payment_type=payment_type,
            max_delivery_rate=max_delivery_rate,
        )

    def _send_marketplace_request(  # pylint: disable=too-many-arguments,too-many-locals
        self,
        marketplace_contract: Web3Contract,
        data_hashes: List[str],
        max_delivery_rate: int,
        payment_type: PaymentType,
        priority_mech: str,
        response_timeout: int,
        use_prepaid: bool,
    ) -> str:
        """
        Send marketplace request transaction.

        :param marketplace_contract: Marketplace contract instance
        :param data_hashes: List of IPFS data hashes
        :param max_delivery_rate: Maximum delivery rate
        :param payment_type: Payment type
        :param priority_mech: Priority mech address
        :param response_timeout: Response timeout in seconds
        :param use_prepaid: Whether to use prepaid balance
        :return: Transaction hash
        """
        # Build transaction arguments
        method_name = "requestBatch" if len(data_hashes) > 1 else "request"

        sender = self.executor.get_sender_address()
        value = (
            0
            if payment_type.is_token() or use_prepaid
            else max_delivery_rate * len(data_hashes)
        )

        # Convert payment type to bytes32; allow optional 0x prefix for robustness
        payment_type_hex = payment_type.value.removeprefix("0x")
        try:
            payment_type_bytes = bytes.fromhex(payment_type_hex)
        except ValueError as e:
            raise ValueError(
                f"Invalid payment type value {payment_type.value!r}: {e}"
            ) from e

        # Payment data (empty bytes for now - can be extended for additional payment info)
        payment_data = b""

        # Ensure priority mech address is checksummed (required by web3.py)
        priority_mech_checksummed = ensure_checksummed_address(priority_mech)

        # Build method arguments according to ABI
        if len(data_hashes) > 1:
            # requestBatch(bytes[] requestDatas, uint256 maxDeliveryRate, bytes32 paymentType,
            #              address priorityMech, uint256 responseTimeout, bytes paymentData)
            method_args = {
                "requestDatas": data_hashes,
                "maxDeliveryRate": max_delivery_rate,
                "paymentType": payment_type_bytes,
                "priorityMech": priority_mech_checksummed,
                "responseTimeout": response_timeout,
                "paymentData": payment_data,
            }
        else:
            # request(bytes requestData, uint256 maxDeliveryRate, bytes32 paymentType,
            #         address priorityMech, uint256 responseTimeout, bytes paymentData)
            method_args = {
                "requestData": data_hashes[0],
                "maxDeliveryRate": max_delivery_rate,
                "paymentType": payment_type_bytes,
                "priorityMech": priority_mech_checksummed,
                "responseTimeout": response_timeout,
                "paymentData": payment_data,
            }

        # gas_limit is the initial value; when is_gas_estimation_enabled is true
        # (default), EthereumApi.build_transaction() overwrites it with
        # eth_estimateGas(). gas_limit serves as fallback when estimation is
        # disabled or fails. Agent mode ignores this entirely (Safe uses gas=0).
        tx_args = {
            "sender_address": sender,
            "value": value,
            "gas": self.mech_config.gas_limit,
        }

        # Execute transaction
        return self.executor.execute_transaction(
            contract=marketplace_contract,
            method_name=method_name,
            method_args=method_args,
            tx_args=tx_args,
        )

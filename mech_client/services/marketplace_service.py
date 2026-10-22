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

import logging
import secrets
from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Literal,
    Optional,
    Tuple,
    TypedDict,
    Union,
    cast,
    get_args,
)

import requests
from aea_ledger_ethereum import EthereumCrypto
from eth_account import Account
from mech_client.domain.delivery import (
    DeliveryResult,
    OffchainDeliveryWatcher,
    OnchainDeliveryWatcher,
)
from mech_client.domain.operator import read_expected_costs
from mech_client.domain.payment import PaymentStrategyFactory
from mech_client.domain.signing import Signer
from mech_client.domain.tools import ToolManager
from mech_client.domain.tools.manager import payment_asset
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.blockchain.receipt_waiter import (
    wait_for_receipt,
    watch_for_marketplace_request_ids,
)
from mech_client.infrastructure.config import PaymentType
from mech_client.infrastructure.ipfs import IPFSClient, push_metadata_to_ipfs
from mech_client.services.base_service import BaseTransactionService
from mech_client.utils.constants import UINT256_MAX
from mech_client.utils.validators import ensure_checksummed_address
from safe_eth.eth import EthereumClient
from web3.contract import Contract as Web3Contract
from web3.types import TxReceipt

logger = logging.getLogger(__name__)

# HTTP status the offchain mech returns when the requester's prepaid balance is
# insufficient (structured 402 challenge, see mech task_execution handlers).
HTTP_PAYMENT_REQUIRED = 402
# HTTP status the offchain mech returns when it cannot serve a request right
# now; see ``EXPLICIT_NONCE_DISABLED_REASON`` for the one case that is retried.
HTTP_SERVICE_UNAVAILABLE = 503
# Outbound HTTP timeout (seconds) for the offchain request POST.
OFFCHAIN_HTTP_TIMEOUT = 30

# How an offchain request's nonce is chosen, which decides the view that
# derives its request id and the marketplace path that settles it. This is
# the one description; the docs' "Offchain Requests" section is the
# user-facing copy.
#
# ``explicit`` (the default): the requester picks a random nonce per request
# and a settlement deadline, the id is the marketplace's EIP-712 digest from
# ``getRequestIdWithNonce`` (its own signing domain), the payload says so in
# ``nonce_mode`` and carries ``deadline``, and the marketplace's
# per-request-id record is the only replay guard, so independently signed
# requests settle in any order and in independent transactions, up to the
# deadline.
# ``sequential``: the nonce is the requester's ``mapNonces`` counter, the id
# comes from ``getRequestId``, the payload is the one every mech has always
# accepted, and settlement consumes the counter in order.
# A mech with the explicit-nonce path switched off answers an explicit
# request with HTTP 503 and ``EXPLICIT_NONCE_DISABLED_REASON``; the request,
# and the rest of the batch, is then resent sequentially. A mech on a
# release that predates ``nonce_mode`` is not covered by that fallback.
# The two ids are domain-separated: a signature for one path is rejected on
# the other.
NonceMode = Literal["explicit", "sequential"]
NONCE_MODE_EXPLICIT: NonceMode = "explicit"
NONCE_MODE_SEQUENTIAL: NonceMode = "sequential"
# Verbatim ``reason`` a mech sends with its 503 when explicit-nonce requests
# are not enabled on it (mech ``task_execution`` handlers).
EXPLICIT_NONCE_DISABLED_REASON = "explicit-nonce requests are not enabled on this mech"
# How long, from the latest block, an explicit-nonce authorisation stays
# settleable. The marketplace reverts a settlement past the signed deadline, so
# the window must cover the mech's execution and settlement, not only the
# answer; a mech refuses a request whose deadline is closer than its own floor.
EXPLICIT_NONCE_DEADLINE_SECONDS = 15 * 60
# Width of a requester-chosen nonce. The marketplace requires it to be unique
# per (mech, request data, signed maximum, payment type); the request data
# already carries a per-request UUID, so 256 random bits are not what keeps
# ids distinct, they are what keeps them independent of ``mapNonces``.
EXPLICIT_NONCE_BITS = 256
# Without a chosen cap, an off-chain request signs this multiple of the
# expected cost the mech publishes for the tool: headroom sized from the
# spread of charges observed across mechs (valory-xyz/mech#505). What is
# not charged is not paid.
DEFAULT_CAP_FACTOR = 2
# A default cap this many times the mech's advertised maximum is logged as a
# warning: the manifest is the operator's own document, and the cap also sets
# the auto-deposit ceiling (``_MAX_AUTO_DEPOSIT_RATIO`` times the cap).
CAP_WARNING_FACTOR = 10
# Hard cap on auto-deposit: refuse to top up more than this multiple of the
# requester's signed ``max_delivery_rate`` in a single retry. The mech URL is
# auto-discovered from on-chain metadata, so without a cap a compromised or
# buggy mech could return a huge ``required`` and drain the user's wallet
# into their own balance tracker. Funds aren't stolen (they sit in the user's
# tracker, bounded by ``check_balance``) but they're locked up and the user's
# wallet drained. 10x is generous for legitimate price moves between
# signature and request, tight enough that catastrophic drain stays bounded.
_MAX_AUTO_DEPOSIT_RATIO = 10
# Payment types that ``_auto_deposit_for_402`` knows how to top up via the
# balance tracker. NVM subscription types (``NATIVE_NVM`` / ``TOKEN_NVM_USDC``)
# are intentionally excluded: they're paid via subscription, not via a
# balance-tracker deposit. Listing the supported set explicitly (rather than
# falling through ``if/elif/else``) makes the contract visible — a sixth
# ``PaymentType`` added later forces this set and the dispatch below to be
# updated together, surfacing the gap statically instead of at offchain-402
# runtime.
_SUPPORTED_DEPOSIT_PAYMENT_TYPES: FrozenSet[PaymentType] = frozenset(
    {PaymentType.NATIVE, PaymentType.OLAS_TOKEN, PaymentType.USDC_TOKEN}
)


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
    receipt: None
    deliveries: Dict[str, DeliveryResult]


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
    ):
        """
        Initialize marketplace service.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        :param agent_mode: True for agent mode (Safe), False for client mode (EOA)
        :param crypto: Ethereum crypto object for local signing (alternative to signer)
        :param safe_address: Safe address (required for agent mode)
        :param ethereum_client: Ethereum client (required for agent mode)
        :param signer: Signer for externalized signing (alternative to crypto)
        """
        super().__init__(
            chain_config=chain_config,
            agent_mode=agent_mode,
            crypto=crypto,
            safe_address=safe_address,
            ethereum_client=ethereum_client,
            signer=signer,
        )

        # Create tool manager
        self.tool_manager = ToolManager(chain_config)

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
        nonce_mode: NonceMode = NONCE_MODE_EXPLICIT,
        deadline_seconds: int = EXPLICIT_NONCE_DEADLINE_SECONDS,
        max_cost: Optional[int] = None,
    ) -> RequestResult:
        """
        Send marketplace request(s) to mech(s).

        Off-chain, the requester sets the cap signed into each request and the
        mech charges its actual cost at delivery, at or below it; what it does
        not charge stays in the requester's balance. The cap is ``max_cost``
        when given, else :data:`DEFAULT_CAP_FACTOR` times the expected cost the
        mech's manifest publishes for the tool, else the mech's advertised
        ``maxDeliveryRate``. On-chain the marketplace records the advertised
        ``maxDeliveryRate`` as the charge, so that is what is signed, and a
        ``max_cost`` below it refuses the request before anything is sent.

        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech: Priority mech address (optional)
        :param use_prepaid: Use prepaid balance instead of per-request payment
        :param use_offchain: Use offchain mech (URL discovered from metadata)
        :param auto_deposit: On an offchain HTTP 402, top up the prepaid balance
            with the shortfall and retry once (only applies to the offchain path)
        :param extra_attributes: Extra attributes for metadata
        :param timeout: Timeout for delivery watching
        :param nonce_mode: ``explicit`` or ``sequential``, see :data:`NonceMode`.
            On-chain requests take their nonce from the marketplace and
            ignore this.
        :param deadline_seconds: How long from the latest block an explicit
            request stays settleable, see :data:`EXPLICIT_NONCE_DEADLINE_SECONDS`.
            Sequential and on-chain requests ignore this.
        :param max_cost: The most to pay per request, in base units of the
            mech's payment asset. Off-chain it is the signed cap; on-chain
            the advertised charge must be at or below it.
        :return: A :class:`RequestResult` with ``tx_hash`` and ``receipt``
            (both ``None`` on the offchain path, which has no transaction),
            ``request_ids``, and ``deliveries`` mapping each request ID to a
            :class:`DeliveryResult` carrying the parsed content the mech
            delivered, the gateway URL it was read from and, for offchain
            delivery, what the mech charged. ``deliveries`` has the same shape
            regardless of whether delivery was on-chain or offchain.
        """
        # Validate inputs
        if len(prompts) != len(tools):
            raise ValueError(
                f"Number of prompts ({len(prompts)}) must match number of tools ({len(tools)})"
            )
        if nonce_mode not in get_args(NonceMode):
            raise ValueError(
                f"Unknown nonce_mode {nonce_mode!r}; expected one of {get_args(NonceMode)}"
            )
        if max_cost is not None and not 0 < max_cost <= UINT256_MAX:
            raise ValueError(
                f"max_cost must be a positive amount no larger than a contract "
                f"can carry (2**256 - 1), got {max_cost}"
            )

        # Get marketplace contract
        marketplace_contract = self._get_marketplace_contract()

        # Fetch mech info (payment type, service ID, max delivery rate)
        payment_type, service_id, advertised_max = self._fetch_mech_info(priority_mech)

        # One metadata read per request: the tool check, the terms notice, the
        # expected costs and the offchain URL lookup all derive from this document.
        metadata = self.tool_manager.fetch_tools_metadata(service_id)
        self._validate_tools(tools, service_id, metadata)
        max_delivery_rate = self._resolve_signed_rate(
            tools=tools,
            metadata=metadata,
            payment_type=payment_type,
            advertised_max=advertised_max,
            max_cost=max_cost,
            use_offchain=use_offchain,
        )

        # Get priority mech address (use configured or provided)
        priority_mech_address = priority_mech or self.mech_config.priority_mech_address
        if not priority_mech_address:
            raise ValueError("No priority mech address specified")

        # Response timeout (5 minutes, matching historic default)
        response_timeout = 300

        self._log_terms_notice(priority_mech_address, metadata)

        # Branch between on-chain and off-chain flows
        if use_offchain:
            offchain_url = self.tool_manager.offchain_url_from_metadata(
                service_id, metadata
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
                nonce_mode=nonce_mode,
                deadline_seconds=deadline_seconds,
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
            # The marketplace pulls up to `max_delivery_rate * numRequests`
            # from the requester via `BalanceTracker.checkAndRecordDeliveryRates`.
            # Use the per-mech `max_delivery_rate` (read from the mech
            # contract) instead of the static chain-wide `mech_config.price`
            # from mechs.json — the latter is a default that does not match
            # per-mech pricing and under-funds the approve whenever a mech's
            # rate exceeds it, making the marketplace's transferFrom revert
            # with "ERC20: transfer amount exceeds allowance".
            price = max_delivery_rate * len(prompts)

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

    def _resolve_signed_rate(  # pylint: disable=too-many-arguments
        self,
        tools: Tuple[str, ...],
        metadata: Any,
        payment_type: PaymentType,
        advertised_max: int,
        max_cost: Optional[int],
        use_offchain: bool,
    ) -> int:
        """
        Pick the per-request rate signed into this batch.

        On-chain the marketplace records the mech's advertised maximum as the
        charge and refuses a lower one, so the advertised maximum is signed
        and a lower ``max_cost`` stops the request here. Off-chain the signed
        value is a cap the mech charges at or below: ``max_cost`` when given,
        else, for each tool, :data:`DEFAULT_CAP_FACTOR` times the expected cost
        the manifest publishes in the mech's payment asset, falling back to
        the advertised maximum for a tool without one. One batch signs one
        rate, the largest of its tools', so every request in it is covered.
        An unreadable manifest signs the advertised maximum with one warning.
        A derived cap above :data:`CAP_WARNING_FACTOR` times the advertised
        maximum is signed with a warning, since the manifest is the operator's
        and the cap also sets the auto-deposit ceiling.

        :param tools: The tool of each request in the batch
        :param metadata: The mech's manifest document, or None if unreadable
        :param payment_type: The mech's payment type
        :param advertised_max: The mech's on-chain ``maxDeliveryRate``
        :param max_cost: The requester's own cap, or None to derive one
        :param use_offchain: Whether the batch goes to the mech's HTTP endpoint
        :return: The rate to sign into every request of the batch
        :raises ValueError: If an on-chain request's charge is above ``max_cost``
        """
        if not use_offchain:
            if max_cost is not None and advertised_max > max_cost:
                raise ValueError(
                    f"The mech charges {advertised_max} per on-chain request, "
                    f"above the {max_cost} allowed. On-chain requests pay the "
                    f"mech's advertised maxDeliveryRate; raise max_cost or send "
                    f"the request off-chain, where the cap is yours."
                )
            return advertised_max
        if max_cost is not None:
            logger.info(f"Signing your cap of {max_cost} per request")
            return max_cost

        if not isinstance(metadata, dict):
            logger.warning(
                f"The mech's manifest could not be read, so no expected cost is "
                f"known; its advertised maximum of {advertised_max} is signed as "
                f"the cap. Pass max_cost to choose your own."
            )
            return advertised_max

        asset = payment_asset(payment_type)
        published = read_expected_costs(metadata)
        caps: Dict[str, int] = {}
        for tool in dict.fromkeys(tools):
            cost = published.get(tool)
            if cost is not None and cost.asset != asset:
                logger.warning(
                    f"The expected cost of {tool} is stated in {cost.asset}, "
                    f"not the mech's payment asset {asset}; it is ignored."
                )
                cost = None
            if cost is None:
                logger.warning(
                    f"The mech publishes no expected cost for {tool}; its "
                    f"advertised maximum of {advertised_max} is signed as the "
                    f"cap for it. Pass max_cost to choose your own."
                )
                caps[tool] = advertised_max
                continue
            caps[tool] = min(DEFAULT_CAP_FACTOR * cost.amount, UINT256_MAX)
            logger.info(
                f"Signing a cap of {caps[tool]} per {tool} request, "
                f"{DEFAULT_CAP_FACTOR}x the expected cost of {cost.amount} "
                f"{asset} the mech publishes"
            )
        cap = max(caps.values())
        if cap > CAP_WARNING_FACTOR * advertised_max:
            logger.warning(
                f"The cap of {cap} derived from the manifest is more than "
                f"{CAP_WARNING_FACTOR}x the mech's advertised maximum of "
                f"{advertised_max}. The manifest is the operator's own document "
                f"and this cap also sets the auto-deposit ceiling; pass max_cost "
                f"to choose your own."
            )
        return cap

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
        nonce_mode: NonceMode = NONCE_MODE_EXPLICIT,
        deadline_seconds: int = EXPLICIT_NONCE_DEADLINE_SECONDS,
    ) -> OffchainRequestResult:
        """
        Send offchain request to mech HTTP endpoint.

        ``max_delivery_rate`` is the requester's cap, signed into every
        request; the mech charges at or below it and reports the charge with
        the delivery.

        :param marketplace_contract: Marketplace contract instance
        :param prompts: Tuple of prompt strings
        :param tools: Tuple of tool identifiers
        :param priority_mech_address: Mech address
        :param max_delivery_rate: The per-request cap, see ``_resolve_signed_rate``
        :param payment_type: Payment type
        :param response_timeout: Response timeout in seconds
        :param mech_offchain_url: Base URL of offchain mech
        :param extra_attributes: Extra attributes for metadata
        :param timeout: Delivery watching timeout
        :param auto_deposit: On a 402, deposit the shortfall and retry once
        :param nonce_mode: ``explicit`` or ``sequential``, see :data:`NonceMode`.
        :param deadline_seconds: Settlement window of an explicit request, from
            the latest block.
        :return: Dictionary with request results
        """
        logger.info("Sending offchain mech marketplace request...")

        # In agent mode the requester of record is the Safe (msg.sender on
        # the on-chain path, ``mapNonces`` key, and requester bound into
        # the request id); in client mode it is the EOA. The signature is
        # verified against this address downstream (Safe.isValidSignature
        # for the Safe branch, plain ecrecover for the EOA branch).
        sender = self._resolve_offchain_sender()
        mech = ensure_checksummed_address(priority_mech_address)
        # payment_type.value is already a hex string, just add 0x prefix
        payment_type_hex = "0x" + payment_type.value
        url = f"{mech_offchain_url.rstrip('/')}/send_signed_requests"

        # The sequential counter is read once and advanced locally for every
        # request sent on that path, so a batch numbers its requests
        # contiguously. Explicit requests leave it untouched, and only read
        # it if the mech turns them away.
        next_sequential_nonce: Optional[int] = None
        if nonce_mode == NONCE_MODE_SEQUENTIAL:
            next_sequential_nonce = marketplace_contract.functions.mapNonces(
                sender
            ).call()
        # One deadline for the batch, from chain time rather than the local
        # clock, since the marketplace compares it with ``block.timestamp``.
        deadline: Optional[int] = None
        if nonce_mode == NONCE_MODE_EXPLICIT:
            latest = marketplace_contract.w3.eth.get_block("latest")
            deadline = int(latest["timestamp"]) + int(deadline_seconds)

        # Prepare and send each request
        request_ids_hex = []

        for prompt, tool in zip(prompts, tools):
            # Prepare metadata (get hash and data without uploading)
            # Import here to avoid circular dependency
            from mech_client.infrastructure.ipfs.metadata import (  # pylint: disable=import-outside-toplevel
                fetch_ipfs_hash,
            )

            data_hash, data_hash_full, ipfs_data = fetch_ipfs_hash(
                prompt, tool, extra_attributes or {}
            )
            logger.info(
                f"Prompt sent directly to the mech (not published to IPFS); "
                f"content CID {data_hash_full}"
            )

            # Send HTTP POST request (handles a structured 402 + receipt header).
            # At most two rounds: the second only when an explicit request was
            # turned away for its nonce, in which case the mech answers every
            # explicit request that way and the rest of the batch goes
            # sequential too. A refused request was never accepted, so
            # nothing of it is in flight.
            try:
                while True:
                    if nonce_mode == NONCE_MODE_EXPLICIT:
                        nonce = secrets.randbits(EXPLICIT_NONCE_BITS)
                    else:
                        if next_sequential_nonce is None:
                            next_sequential_nonce = (
                                marketplace_contract.functions.mapNonces(sender).call()
                            )
                        nonce = next_sequential_nonce
                        next_sequential_nonce = nonce + 1
                    request_id_bytes, payload = self._build_offchain_payload(
                        marketplace_contract,
                        sender,
                        mech,
                        data_hash,
                        max_delivery_rate,
                        payment_type_hex,
                        nonce,
                        nonce_mode,
                        ipfs_data,
                        deadline,
                    )
                    response = self._post_offchain_request(
                        url, payload, payment_type, auto_deposit, max_delivery_rate
                    )
                    if nonce_mode == NONCE_MODE_SEQUENTIAL:
                        break
                    if not self._explicit_nonce_refused(response):
                        break
                    logger.warning(
                        "The mech does not accept explicit nonces; resending "
                        "with the marketplace's sequential nonce instead."
                    )
                    nonce_mode = NONCE_MODE_SEQUENTIAL
                if not response.ok:
                    reason = self._rejection_reason(response)
                    raise ValueError(
                        f"Offchain request rejected: {reason or response.reason} "
                        f"(HTTP {response.status_code})"
                    )

                request_ids_hex.append(request_id_bytes.hex())

                logger.info(f"Created offchain request with ID {payload['request_id']}")

            except requests.exceptions.RequestException as e:
                raise ValueError(f"Failed to send offchain request: {e}") from e

        # Watch for offchain delivery
        logger.info("Waiting for offchain mech marketplace deliver...")
        watcher = OffchainDeliveryWatcher(mech_offchain_url, timeout)
        results = await watcher.watch(request_ids_hex)

        return {
            "tx_hash": None,  # No on-chain transaction for offchain requests
            "request_ids": request_ids_hex,
            "deliveries": results,
            "receipt": None,  # No receipt for offchain requests
        }

    def _build_offchain_payload(  # pylint: disable=too-many-arguments
        self,
        marketplace_contract: Web3Contract,
        sender: str,
        mech: str,
        data_hash: str,
        max_delivery_rate: int,
        payment_type_hex: str,
        nonce: int,
        nonce_mode: NonceMode,
        ipfs_data: str,
        deadline: Optional[int] = None,
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Derive, sign and package one offchain request.

        The request id comes from the marketplace view for the nonce mode:
        ``getRequestIdWithNonce`` (with the deadline) for an explicit nonce,
        ``getRequestId`` for a sequential one. The two are domain-separated
        on-chain, so the signature only verifies on the path the mech is told
        about through ``nonce_mode``; a sequential payload carries no such
        field and is the payload every mech has always accepted.

        :param marketplace_contract: Marketplace contract instance
        :param sender: Checksummed requester of record (Safe or EOA)
        :param mech: Checksummed mech address
        :param data_hash: Truncated content hash of the request metadata
        :param max_delivery_rate: The per-request maximum being signed
        :param payment_type_hex: The mech's payment type as 0x-prefixed hex
        :param nonce: The nonce to sign: a requester-chosen value (explicit)
            or the requester's ``mapNonces`` counter (sequential)
        :param nonce_mode: ``explicit`` or ``sequential``
        :param ipfs_data: The request metadata as the JSON string that was
            hashed, sent to the mech in place of an IPFS upload
        :param deadline: Last settlement timestamp, signed into an explicit
            request; must be given for ``explicit``
        :return: The 32-byte request id and the form payload to POST
        :raises ValueError: when an explicit request has no deadline
        """
        if nonce_mode == NONCE_MODE_EXPLICIT:
            if deadline is None:
                raise ValueError("an explicit-nonce request needs a deadline")
            request_id_bytes = marketplace_contract.functions.getRequestIdWithNonce(
                mech,
                sender,
                data_hash,
                max_delivery_rate,
                payment_type_hex,
                nonce,
                deadline,
            ).call()
        else:
            request_id_bytes = marketplace_contract.functions.getRequestId(
                mech,
                sender,
                data_hash,
                max_delivery_rate,
                payment_type_hex,
                nonce,
            ).call()

        # Signature encoding depends on how the marketplace verifies the
        # requester: Safe.isValidSignature (agent mode) requires the
        # SafeMessage-wrapped hash to be signed; plain ecrecover
        # (client mode) requires the raw digest.
        signature = self._sign_request_digest(sender, request_id_bytes)

        payload: Dict[str, Any] = {
            "sender": sender,
            "signature": signature,
            "ipfs_hash": data_hash,
            "request_id": int.from_bytes(request_id_bytes, byteorder="big"),
            "delivery_rate": max_delivery_rate,
            "nonce": nonce,
            "ipfs_data": ipfs_data,
        }
        if nonce_mode == NONCE_MODE_EXPLICIT:
            payload["nonce_mode"] = NONCE_MODE_EXPLICIT
            payload["deadline"] = deadline
        return request_id_bytes, payload

    @staticmethod
    def _rejection_reason(response: requests.Response) -> str:
        """Return the ``reason`` from a mech's JSON rejection body, else ``""``.

        :param response: the HTTP response from the mech.
        :return: the reason string, empty when the body carries none.
        """
        try:
            return str(response.json().get("reason", ""))
        except Exception:  # pylint: disable=broad-except
            return ""

    @classmethod
    def _explicit_nonce_refused(cls, response: requests.Response) -> bool:
        """Whether the mech turned the request away for using an explicit nonce.

        Only the exact 503 the mech sends for a disabled explicit-nonce path
        counts; any other rejection, including a 503 for another reason, is
        reported to the caller as it is.

        :param response: the HTTP response from the mech.
        :return: True if the request should be resent with a sequential nonce.
        """
        return (
            response.status_code == HTTP_SERVICE_UNAVAILABLE
            and cls._rejection_reason(response) == EXPLICIT_NONCE_DISABLED_REASON
        )

    def _resolve_offchain_sender(self) -> str:
        """Return the requester address bound into the offchain request.

        In agent mode this is the Safe (matching the onchain flow where the
        Safe is ``msg.sender`` on the marketplace call); in client mode it
        is the EOA. Callers use this for ``mapNonces``, the request-id
        views, and the payload ``sender`` field so the mech, subgraph, and
        settlement path all agree on who owns the request.

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
        the request-id view.

        :param sender: Checksummed requester address (agent mode: Safe;
            client mode: EOA). Must equal the ``sender`` field of the
            outbound payload and the requester argument to the request-id
            view.
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
        :raises ValueError: on a 402 when auto-deposit is disabled, on a
            non-positive shortfall that auto-deposit can't act on, on a deposit
            request that would exceed the safety cap, or on a second 402 after
            the deposit landed.
        """
        response = self._do_offchain_post(url, payload)
        if response.status_code == HTTP_PAYMENT_REQUIRED:
            challenge = self._parse_402_challenge(response)
            if not auto_deposit:
                raise ValueError(
                    "Offchain request requires payment: need "
                    f"{challenge.required} (current balance "
                    f"{challenge.current_balance}) deposited to "
                    f"{challenge.pay_to}. Re-run with auto-deposit enabled or "
                    f"top up your prepaid balance. ({challenge.error})"
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
                raise ValueError(
                    "Offchain request rejected with HTTP 402 but the challenge "
                    f"reports no shortfall (required={challenge.required}, "
                    f"current balance={challenge.current_balance}). The mech "
                    f"may be returning a malformed body or a stale balance. "
                    f"({challenge.error})"
                )
            self._auto_deposit_for_402(payment_type, challenge, max_delivery_rate)
            response = self._do_offchain_post(url, payload)
            if response.status_code == HTTP_PAYMENT_REQUIRED:
                # The deposit tx already confirmed (DepositService waits for
                # receipt), so silently returning the second 402 would surface
                # downstream as a generic "Payment Required (HTTP 402)" error
                # with no hint that funds moved. Raise explicitly so the user
                # sees how much is still short and which balance tracker holds
                # the deposit they just paid for.
                retry = self._parse_402_challenge(response)
                raise ValueError(
                    "Auto-deposit did not clear the 402: deposited to "
                    f"{retry.pay_to} but the mech still requires "
                    f"{retry.required} (current balance {retry.current_balance}, "
                    f"remaining shortfall {retry.shortfall}). The deposit may "
                    f"not be mined yet, the price may have moved, or the asset "
                    f"may be wrong. ({retry.error})"
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
    ) -> None:
        """Deposit the 402 shortfall into the prepaid balance.

        Refuses to deposit when the shortfall exceeds
        ``_MAX_AUTO_DEPOSIT_RATIO * max_delivery_rate`` — see the constant's
        docstring for why the cap exists.

        :param payment_type: the request's payment type (native vs token).
        :param challenge: the parsed 402 challenge.
        :param max_delivery_rate: the requester's signed per-request maximum.
        :raises ValueError: if the payment type doesn't support auto-deposit,
            or if the requested deposit would exceed the safety cap.
        """
        if challenge.shortfall <= 0:
            return
        if payment_type not in _SUPPORTED_DEPOSIT_PAYMENT_TYPES:
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
        )
        logger.info(
            f"Auto-depositing {challenge.shortfall} to top up the prepaid balance..."
        )
        # Per-asset dispatch over the supported-types frozenset. A future
        # payment type would need to be added to _SUPPORTED_DEPOSIT_PAYMENT_TYPES
        # AND get a branch here; the assertion-shaped raise below catches the
        # mismatch if only the set is updated.
        if payment_type == PaymentType.NATIVE:
            deposit_service.deposit_native(challenge.shortfall)
        elif payment_type == PaymentType.OLAS_TOKEN:
            deposit_service.deposit_token(challenge.shortfall, "olas")
        elif payment_type == PaymentType.USDC_TOKEN:
            deposit_service.deposit_token(challenge.shortfall, "usdc")
        else:  # pragma: no cover - guarded by the membership check above
            raise ValueError(
                f"Internal error: {payment_type.name} is listed as supported "
                f"but has no deposit dispatch branch."
            )

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

    def _get_marketplace_contract(self) -> Web3Contract:
        """
        Get marketplace contract instance.

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

    def _fetch_mech_info(
        self, priority_mech: Optional[str]
    ) -> Tuple[PaymentType, int, int]:
        """
        Fetch mech information from contract.

        :param priority_mech: Priority mech address
        :return: Tuple of (payment_type, service_id, max_delivery_rate)
        """
        # Get mech contract
        mech_address = priority_mech or self.mech_config.priority_mech_address
        if not mech_address:
            raise ValueError("No mech address specified")

        abi = get_abi("IMech.json")
        mech_contract = get_contract(mech_address, abi, self.ledger_api)

        # Fetch mech info
        payment_type_bytes = mech_contract.functions.paymentType().call()
        max_delivery_rate = mech_contract.functions.maxDeliveryRate().call()
        service_id = mech_contract.functions.serviceId().call()

        # Convert payment type bytes to PaymentType enum
        payment_type = PaymentType.from_value(payment_type_bytes.hex())

        return payment_type, service_id, max_delivery_rate

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

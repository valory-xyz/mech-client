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

"""Tool manager for fetching and managing mech tools."""

import json
import logging
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from aea_ledger_ethereum import EthereumApi
from mech_client.domain.identification import (
    Identification,
    VALORY_TERMS_NOTICE,
    identify,
)
from mech_client.domain.operator import (
    BENCHMARK_NOTE,
    DomainVerification,
    read_benchmarks,
    read_expected_costs,
    read_operator,
    verify_domain,
)
from mech_client.domain.tools.models import ToolInfo, ToolsForMarketplaceMech
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.config.loader import get_mech_config
from mech_client.infrastructure.config.payment_config import PaymentType
from mech_client.infrastructure.ipfs.local_cid import compute_cidv1_bytes
from mech_client.infrastructure.subgraph.queries import (
    MechRecord,
    query_erc8004_agent_id,
    query_mech_record,
)
from mech_client.utils.errors.exceptions import ManifestError
from web3.constants import ADDRESS_ZERO

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
TOOLS = "tools"
TOOL_METADATA = "toolMetadata"
# A terms link comes from an operator's own document, so it is only passed on
# when it is a plain https URL of a sane length.
TERMS_URL_MAX_LENGTH = 2048
IDENTIFICATION_NOTE = "Could not check whether Valory operates this mech."
DELIVERY_NOTE = (
    "Counts cover requests made on-chain and off-chain requests the mech "
    "settled on-chain, not split by path. An off-chain request that was never "
    "delivered appears nowhere on-chain."
)
PAYMENT_NOTE = (
    "No price is quoted here: the mech contract quotes the charge at request "
    "time, and its maximum delivery rate is only a ceiling."
)
EXPECTED_COST_NOTE = (
    "Expected costs are the operator's estimate per tool, in base units of the "
    "stated asset, for choosing a cap. The mech charges its actual cost, at or "
    "below the cap signed into the request."
)
MANIFEST_HASH_NOTE = (
    "The manifest served for service {service_id} does not hash to the CID "
    "recorded on-chain; it is not used."
)
# The on-chain metadata URI ends in the manifest's CIDv1 in base16: dag-pb
# over a 32-byte sha2-256 multihash. The served bytes must hash to it.
MANIFEST_CID_PREFIX = "f01701220"
NAME_NOTE = (
    "The name is the operator's own text and is not checked; only the domain is."
)
DOMAIN_CHECK_FAILED_NOTE = (
    "The operator's domain could not be checked; it will be checked again next time."
)
MANIFEST_UNREADABLE_NOTE = (
    "The mech's manifest could not be read; only the terms are reported."
)
RECORD_UNAVAILABLE_NOTE = (
    "The operator and delivery record could not be read ({reason}); only the "
    "terms are reported."
)
PAYMENT_LABELS = {
    PaymentType.NATIVE: "native",
    PaymentType.OLAS_TOKEN: "olas",
    PaymentType.USDC_TOKEN: "usdc",
    PaymentType.NATIVE_NVM: "native_nvm",
    PaymentType.TOKEN_NVM_USDC: "usdc_nvm",
}
UNKNOWN_PAYMENT = "unknown"
# The asset a mech is paid in, as a manifest states it next to an amount.
PAYMENT_ASSETS = {
    PaymentType.NATIVE: "native",
    PaymentType.OLAS_TOKEN: "olas",
    PaymentType.USDC_TOKEN: "usdc",
    PaymentType.NATIVE_NVM: "native",
    PaymentType.TOKEN_NVM_USDC: "usdc",
}


def payment_asset(payment_type: PaymentType) -> str:
    """
    Name the asset a mech's payment type is settled in.

    :param payment_type: The mech's payment type
    :return: The asset name a manifest's ``expectedCost.asset`` must carry
    """
    return PAYMENT_ASSETS[payment_type]


def manifest_matches_uri(metadata_uri: str, body: bytes) -> bool:
    """
    Tell whether the bytes served for a manifest hash to the CID its URI names.

    The URI comes from the ComplementaryServiceMetadata contract and ends in
    the CID recorded on-chain; the body comes from whatever gateway serves it.
    The CID is recomputed the way ``ipfs add`` does for a single-block file,
    which every manifest is.

    :param metadata_uri: The on-chain metadata URI
    :param body: The bytes the URI served
    :return: True only when the body hashes to the CID in the URI
    """
    recorded = urlparse(metadata_uri).path.rstrip("/").rsplit("/", 1)[-1].lower()
    if not recorded.startswith(MANIFEST_CID_PREFIX):
        return False
    try:
        return recorded == "f" + compute_cidv1_bytes(body).hex()
    except ValueError:
        return False


def payment_label(payment_type: str) -> str:
    """
    Name the payment method behind a mech's on-chain payment type.

    :param payment_type: The bytes32 payment type as the indexer stores it
    :return: The method name, or "unknown" for a payment type this client does not know
    """
    value = payment_type.lower()
    if value.startswith("0x"):
        value = value[2:]
    try:
        return PAYMENT_LABELS[PaymentType.from_value(value)]
    except ValueError:
        return UNKNOWN_PAYMENT


def claimed_operator(
    chain_config: str, chain_id: int, service_id: int, manifest: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Report the operator's domain, whether it backs the mech, and the name it claims.

    The domain is the identity: it is verified only when it publishes the
    mech's ERC-8004 identity in its proof file, and anything short of that is
    unverified with the reason. The name is never checked and is reported as
    the operator's own claim.

    :param chain_config: Chain configuration name
    :param chain_id: The chain the mech is deployed on
    :param service_id: The mech's Olas service id
    :param manifest: The mech's parsed manifest document
    :return: The operator block, or None when the manifest publishes no usable one
    """
    operator = read_operator(manifest)
    if operator is None:
        return None
    # Any failure in the lookup or the check leaves the domain unverified; it
    # never withholds the rest of the report.
    try:
        agent_id = query_erc8004_agent_id(chain_config, service_id)
        verification = verify_domain(operator.domain, chain_id, agent_id)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(f"Could not check the operator domain {operator.domain}: {exc}")
        verification = DomainVerification(False, DOMAIN_CHECK_FAILED_NOTE)
    block: Dict[str, Any] = {
        "domain": operator.domain,
        "url": operator.url,
        "domain_verified": verification.verified,
    }
    if verification.note:
        block["verification_note"] = verification.note
    block["claimed_name"] = operator.name
    block["name_note"] = NAME_NOTE
    return block


class ToolManager:
    """Manager for fetching and caching tool information.

    Provides methods for discovering tools, fetching metadata, and
    retrieving tool schemas from marketplace mechs.
    """

    def __init__(self, chain_config: str):
        """
        Initialize tool manager.

        :param chain_config: Chain configuration name (gnosis, base, etc.)
        """
        self.chain_config = chain_config
        self.mech_config = get_mech_config(chain_config)
        self.ledger_api = EthereumApi(**asdict(self.mech_config.ledger_config))

    def fetch_tools_metadata(self, service_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch tools metadata for specified service ID.

        Queries the complementary metadata hash contract to get the metadata
        URI, fetches the document from that URI and accepts it only when its
        bytes hash to the CID the URI names, so a gateway cannot substitute
        another document for the one recorded on-chain.

        :param service_id: The service ID of the mech
        :return: Dictionary containing tools and metadata, or None if error
        :raises ValueError: If metadata hash address not configured
        """
        if self.mech_config.complementary_metadata_hash_address == ADDRESS_ZERO:
            raise ValueError(
                f"Metadata hash not yet implemented on {self.chain_config}"
            )

        try:
            abi = get_abi("ComplementaryServiceMetadata.json")
            metadata_contract = get_contract(
                self.mech_config.complementary_metadata_hash_address,
                abi,
                self.ledger_api,
            )
            metadata_uri = metadata_contract.functions.tokenURI(service_id).call()
            body = requests.get(metadata_uri, timeout=DEFAULT_TIMEOUT).content
            if not manifest_matches_uri(metadata_uri, body):
                logger.error(MANIFEST_HASH_NOTE.format(service_id=service_id))
                return None
            return json.loads(body)
        except (ValueError, NotImplementedError, IOError) as e:
            logger.error(f"Error fetching tools for service {service_id}: {e}")
            return None

    def get_offchain_url(self, service_id: int) -> str:
        """
        Get the offchain URL from the mech's on-chain metadata.

        :param service_id: The service ID of the mech
        :return: The offchain URL string
        """
        return self.offchain_url_from_metadata(
            service_id, self.fetch_tools_metadata(service_id)
        )

    @staticmethod
    def offchain_url_from_metadata(service_id: int, metadata: Any) -> str:
        """
        Read the ``url`` field from an already fetched metadata document.

        :param service_id: The service ID of the mech (for error messages)
        :param metadata: The parsed metadata document, or None
        :return: The offchain URL string
        :raises ValueError: If there is no document or it has no URL
        """
        if not metadata:
            raise ValueError(
                f"Could not fetch metadata for service {service_id}. "
                f"Cannot discover offchain URL."
            )

        url = (metadata.get("url") or "").strip()
        if not url:
            raise ValueError(
                f"Metadata for service {service_id} does not contain an offchain URL. "
                f"The mech operator must publish a 'url' field in the metadata."
            )

        return url

    @staticmethod
    def extract_terms_url(metadata: Any) -> Optional[str]:
        """
        Read the ``termsUrl`` field from an already fetched metadata document.

        The document is the operator's own, so the value is only returned when
        it is an https URL with a host, no whitespace or control characters,
        and at most TERMS_URL_MAX_LENGTH characters.

        :param metadata: The parsed metadata document, or None
        :return: The stripped terms URL, or None
        """
        if not isinstance(metadata, dict):
            return None
        terms_url = metadata.get("termsUrl")
        if not isinstance(terms_url, str):
            return None
        terms_url = terms_url.strip()
        if not terms_url or len(terms_url) > TERMS_URL_MAX_LENGTH:
            return None
        if any(
            char.isspace() or unicodedata.category(char).startswith("C")
            for char in terms_url
        ):
            return None
        try:
            parsed = urlparse(terms_url)
            host = parsed.hostname
        except ValueError:
            return None
        if parsed.scheme != "https" or not host:
            return None
        return terms_url

    def terms_report(self, mech_address: str, metadata: Any) -> Dict[str, Any]:
        """
        Say whose terms a request to this mech falls under.

        Keeps the legal rule in one place: only a mech identified as Valory
        operated gets the Valory terms statement. The operator's own link is
        passed on as published, not endorsed.

        :param mech_address: The address of the mech about to be called
        :param metadata: The mech's already fetched metadata document, or None
        :return: ``valory_operated`` always; ``terms`` for a Valory mech;
            ``identification_note`` when the check could not tell; and
            ``terms_url`` when the operator published a valid link
        """
        chain_id = self.mech_config.ledger_config.chain_id
        identification = identify(mech_address, chain_id)
        report: Dict[str, Any] = {
            "valory_operated": identification is Identification.VALORY
        }
        if identification is Identification.VALORY:
            report["terms"] = VALORY_TERMS_NOTICE
        elif identification is Identification.UNKNOWN:
            report["identification_note"] = IDENTIFICATION_NOTE
        terms_url = self.extract_terms_url(metadata)
        if terms_url:
            report["terms_url"] = terms_url
        return report

    def mech_report(
        self, mech_address: str, metadata: Any, record: Optional[MechRecord] = None
    ) -> Dict[str, Any]:
        """
        Report who runs a mech and how it has behaved, for a buyer deciding to pay.

        Everything ``terms_report`` says, plus the operator the manifest
        claims and whether its domain backs the claim, the benchmark link
        the operator publishes per tool, the mech's on-chain delivery record
        and age, and its payment method. Fails closed: an unreadable manifest
        means no report, and anything not verified says so.

        :param mech_address: The address of the mech
        :param metadata: The mech's already fetched manifest document, or None
        :param record: The mech's already fetched on-chain record, or None to query it
        :return: The terms report keys; ``operator`` when the manifest names
            one; ``benchmarks`` and ``benchmark_note`` when a tool links one;
            ``delivery`` and ``payment`` always
        :raises ManifestError: If the manifest could not be read
        """
        if not isinstance(metadata, dict):
            raise ManifestError(
                f"The manifest of mech {mech_address} could not be read, "
                f"so no report is made for it."
            )
        report = self.terms_report(mech_address, metadata)
        if record is None:
            record = query_mech_record(self.chain_config, mech_address)
        operator = claimed_operator(
            self.chain_config,
            self.mech_config.ledger_config.chain_id,
            record.service_id,
            metadata,
        )
        if operator is not None:
            report["operator"] = operator
        benchmarks = read_benchmarks(metadata)
        if benchmarks:
            report["benchmarks"] = benchmarks
            report["benchmark_note"] = BENCHMARK_NOTE
        report["delivery"] = self.delivery_record(record)
        report["payment"] = {
            "type": payment_label(record.payment_type),
            "note": PAYMENT_NOTE,
        }
        expected_costs = read_expected_costs(metadata)
        if expected_costs:
            report["payment"]["expected_costs"] = {
                tool: {"asset": cost.asset, "amount": str(cost.amount)}
                for tool, cost in expected_costs.items()
            }
            report["payment"]["expected_cost_note"] = EXPECTED_COST_NOTE
        return report

    def mech_report_or_terms(self, mech_address: str, metadata: Any) -> Dict[str, Any]:
        """
        Report on a mech before paying it, falling back to the terms alone.

        The terms decide what a request agrees to; the operator and record only
        inform the choice. So an unreadable manifest or an indexer that cannot
        be read never hides the terms or blocks the request: the report is the
        terms with ``report_note`` saying why the rest is missing. Otherwise it
        is ``mech_report``.

        :param mech_address: The address of the mech about to be called
        :param metadata: The mech's already fetched manifest document, or None
        :return: ``mech_report``, or ``terms_report`` plus ``report_note``
        """
        if not isinstance(metadata, dict):
            report = self.terms_report(mech_address, None)
            report["report_note"] = MANIFEST_UNREADABLE_NOTE
            return report
        try:
            record = query_mech_record(self.chain_config, mech_address)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                f"Mech record unavailable for {mech_address} on "
                f"{self.chain_config}: {exc}"
            )
            report = self.terms_report(mech_address, metadata)
            report["report_note"] = RECORD_UNAVAILABLE_NOTE.format(
                reason=type(exc).__name__
            )
            return report
        return self.mech_report(mech_address, metadata, record=record)

    @staticmethod
    def delivery_record(record: MechRecord) -> Dict[str, Any]:
        """
        Shape a mech's on-chain record for a report.

        :param record: The mech's record from the marketplace indexer
        :return: The counters, the creation time in ISO 8601 UTC, the age in
            whole days, and the note on what the counters cover
        """
        now = datetime.now(timezone.utc)
        return {
            "received_requests": record.received_requests,
            "self_delivered": record.self_delivered,
            "delivered_by_others": record.delivered_by_others,
            "since": record.created_at.isoformat(),
            "age_days": max((now - record.created_at).days, 0),
            "note": DELIVERY_NOTE,
        }

    def get_tools(self, service_id: int) -> Optional[ToolsForMarketplaceMech]:
        """
        Get list of tools for a marketplace mech.

        :param service_id: The service ID of the mech
        :return: ToolsForMarketplaceMech with tool list, or None if error
        """
        return self.tools_from_metadata(
            service_id, self.fetch_tools_metadata(service_id)
        )

    @staticmethod
    def tools_from_metadata(
        service_id: int, metadata: Any
    ) -> Optional[ToolsForMarketplaceMech]:
        """
        Build the tool list from an already fetched metadata document.

        :param service_id: The service ID of the mech
        :param metadata: The parsed metadata document, or None
        :return: ToolsForMarketplaceMech with tool list, or None if unavailable
        """
        if not metadata:
            return None

        tools = metadata.get(TOOLS, [])
        if not tools:
            logger.warning(f"No tools found for service {service_id}")
            return None

        tool_infos = [
            ToolInfo(
                tool_name=tool,
                unique_identifier=f"{service_id}-{tool}",
            )
            for tool in tools
        ]

        return ToolsForMarketplaceMech(
            service_id=service_id,
            tools=tool_infos,
        )

    def get_tool_description(self, tool_id: str) -> str:
        """
        Get description for a specific tool.

        :param tool_id: Tool ID in format "service_id-tool_name"
        :return: Tool description
        :raises ValueError: If tool_id format invalid or tool not found
        """
        service_id, tool_name = self._parse_tool_id(tool_id)
        metadata = self.fetch_tools_metadata(service_id)
        if not metadata:
            raise ValueError(f"Could not fetch metadata for service {service_id}")

        tool_metadata = metadata.get(TOOL_METADATA, {})
        if tool_name not in tool_metadata:
            raise ValueError(f"Tool {tool_name} not found in metadata")

        return tool_metadata[tool_name].get("description", "No description available")

    def get_tool_schema(self, tool_id: str) -> Dict[str, Any]:
        """
        Get input/output schema for a specific tool.

        :param tool_id: Tool ID in format "service_id-tool_name"
        :return: Dictionary with name, description, input, output keys
        :raises ValueError: If tool_id format invalid or tool not found
        """
        service_id, tool_name = self._parse_tool_id(tool_id)
        metadata = self.fetch_tools_metadata(service_id)
        if not metadata:
            raise ValueError(f"Could not fetch metadata for service {service_id}")

        tool_metadata = metadata.get(TOOL_METADATA, {})
        if tool_name not in tool_metadata:
            raise ValueError(f"Tool {tool_name} not found in metadata")

        tool_info = tool_metadata[tool_name]
        return {
            "name": tool_name,
            "description": tool_info.get("description", ""),
            "input": tool_info.get("input", {}),
            "output": tool_info.get("output", {}),
        }

    @staticmethod
    def _parse_tool_id(tool_id: str) -> tuple:
        """
        Parse tool ID into service ID and tool name.

        :param tool_id: Tool ID in format "service_id-tool_name"
        :return: Tuple of (service_id, tool_name)
        :raises ValueError: If tool_id format invalid
        """
        if "-" not in tool_id:
            raise ValueError(
                f"Invalid tool ID format: {tool_id}. Expected: service_id-tool_name"
            )

        parts = tool_id.split("-", 1)
        try:
            service_id = int(parts[0])
        except ValueError as e:
            raise ValueError(
                f"Invalid service ID in tool ID: {parts[0]}. Must be an integer."
            ) from e

        tool_name = parts[1]
        return service_id, tool_name

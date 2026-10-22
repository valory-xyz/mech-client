# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
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


"""Who runs a mech, as its manifest claims, and whether the domain backs the claim."""

import json
import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from mech_client.utils.logger import get_logger

logger = get_logger(__name__)

# Manifest values are operator-written data: type-checked, stripped, capped, never followed.
TEXT_MAX_LENGTH = 2048
# The longest name DNS allows; part of what a hostname is, not a cap of ours.
DNS_NAME_MAX_LENGTH = 253
# One hostname label: lowercase ASCII letters and digits, inner hyphens only.
_HOSTNAME_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
# The last label is a top-level domain: letters only, or punycode. This keeps
# every IPv4 spelling out, dotted-decimal and hex alike.
_TOP_LABEL = re.compile(r"[a-z]{1,63}|xn--[a-z0-9-]{1,59}")
# Widest integer accepted from a manifest or proof: a uint256 has at most 78 digits.
AGENT_ID_MAX_DIGITS = 78
AMOUNT_MAX_DIGITS = AGENT_ID_MAX_DIGITS

# ERC-8004 IdentityRegistry. One address on every chain the mechs run on.
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
PROOF_PATH = "/.well-known/agent-registration.json"
# Per read, not in total: a host that trickles its body stalls only the report
# on its own mech, which is the operator's to fix.
PROOF_FETCH_TIMEOUT = 5
PROOF_MAX_BYTES = 64 * 1024
PROOF_CHUNK_BYTES = 8 * 1024

BENCHMARK_NOTE = (
    "Benchmark links are the operator's own claim. This client does not check them."
)


def clean_text(value: Any) -> Optional[str]:
    """
    Read a free-text field from the manifest: a stripped, printable, capped string.

    :param value: The raw manifest value
    :return: The stripped text, or None when it is not a usable string
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > TEXT_MAX_LENGTH:
        return None
    if any(unicodedata.category(char).startswith("C") for char in text):
        return None
    return text


def https_url(value: Any) -> Optional[str]:
    """
    Read a URL field from the manifest: clean text, parsed, https, with a host.

    :param value: The raw manifest value
    :return: The URL, or None when it is not an https URL with a host
    """
    url = clean_text(value)
    if url is None or any(char.isspace() for char in url):
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme != "https" or not host:
        return None
    return url


def hostname(value: Any) -> Optional[str]:
    """
    Read the operator domain from the manifest.

    A bare lowercase hostname: ASCII labels matched in full, at least one dot,
    no scheme, path, port, credentials or trailing dot, ending in a top-level
    domain.

    :param value: The raw manifest value
    :return: The domain, or None when it is not a bare hostname
    """
    if not isinstance(value, str):
        return None
    domain = value.strip()
    if len(domain) > DNS_NAME_MAX_LENGTH or "." not in domain:
        return None
    labels = domain.split(".")
    if not all(_HOSTNAME_LABEL.fullmatch(label) for label in labels):
        return None
    if not _TOP_LABEL.fullmatch(labels[-1]):
        return None
    return domain


@dataclass(frozen=True)
class Operator:
    """Who runs the mech, as the manifest claims."""

    name: str
    domain: str

    @property
    def url(self) -> str:
        """
        The operator's web address, built from the domain.

        :return: The https URL of the domain
        """
        return f"https://{self.domain}"


def read_operator(manifest: Dict[str, Any]) -> Optional[Operator]:
    """
    Read the ``operator`` block from a manifest.

    :param manifest: The parsed manifest document
    :return: The operator, or None when the block is absent or unusable
    """
    block = manifest.get("operator")
    if not isinstance(block, dict):
        return None
    name = clean_text(block.get("name"))
    domain = hostname(block.get("domain"))
    if name is None or domain is None:
        return None
    return Operator(name=name, domain=domain)


def read_benchmarks(manifest: Dict[str, Any]) -> Dict[str, str]:
    """
    Read the benchmark link each tool's manifest entry publishes.

    :param manifest: The parsed manifest document
    :return: The https link by tool name; a tool without one is left out
    """
    tool_metadata = manifest.get("toolMetadata")
    if not isinstance(tool_metadata, dict):
        return {}
    links: Dict[str, str] = {}
    for tool, entry in tool_metadata.items():
        if not isinstance(tool, str) or not isinstance(entry, dict):
            continue
        block = entry.get("benchmark")
        url = https_url(block.get("url")) if isinstance(block, dict) else None
        if url is not None:
            links[tool] = url
    return links


@dataclass(frozen=True)
class ExpectedCost:
    """What a tool usually costs, as the operator publishes it: guidance for a cap, never a charge."""

    asset: str
    """The payment asset the amount is stated in, lowercase: ``native``, ``olas`` or ``usdc``."""

    amount: int
    """The amount in the asset's base units."""


def base_units(value: Any) -> Optional[int]:
    """
    Read an amount field from the manifest: a positive decimal integer string.

    Amounts travel as strings so that no reader rounds them through a float.

    :param value: The raw manifest value
    :return: The amount, or None when it is not a positive decimal string
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text.isascii() or not text.isdecimal() or len(text) > AMOUNT_MAX_DIGITS:
        return None
    amount = int(text)
    return amount if amount > 0 else None


def read_expected_costs(manifest: Dict[str, Any]) -> Dict[str, ExpectedCost]:
    """
    Read the expected cost each tool's manifest entry publishes.

    The block is ``toolMetadata.<tool>.expectedCost`` with ``asset`` and a
    decimal-string ``amount``. It is the operator's estimate for choosing a
    cap; the mech charges its actual cost, at or below the cap it is sent.

    :param manifest: The parsed manifest document
    :return: The expected cost by tool name; a tool without a usable one is left out
    """
    tool_metadata = manifest.get("toolMetadata")
    if not isinstance(tool_metadata, dict):
        return {}
    costs: Dict[str, ExpectedCost] = {}
    for tool, entry in tool_metadata.items():
        if not isinstance(tool, str) or not isinstance(entry, dict):
            continue
        block = entry.get("expectedCost")
        if not isinstance(block, dict):
            continue
        asset = clean_text(block.get("asset"))
        amount = base_units(block.get("amount"))
        if asset is None or amount is None:
            continue
        costs[tool] = ExpectedCost(asset.lower(), amount)
    return costs


def proof_url(domain: str) -> str:
    """
    Build the address of a domain's ERC-8004 proof file.

    :param domain: The operator domain
    :return: The https URL of the well-known proof file
    """
    return f"https://{domain}{PROOF_PATH}"


class ProofStatus(Enum):
    """How fetching a domain's proof file ended."""

    FOUND = "found"
    """The domain served a JSON object."""

    NOT_FOUND = "not_found"
    """The domain answered, and the answer is not a proof: 4xx, or not JSON."""

    REDIRECTED = "redirected"
    """The domain answered 3xx: the proof, if any, is served by another host."""

    UNAVAILABLE = "unavailable"
    """The domain could not be reached or answered 5xx, so nothing is known."""


@dataclass(frozen=True)
class ProofOutcome:
    """The result of fetching a domain's proof file."""

    status: ProofStatus
    proof: Optional[Dict[str, Any]] = None


def _read_proof_body(response: Any, url: str) -> ProofOutcome:
    """
    Read a 2xx proof body within the size cap, then parse it.

    :param response: The streaming response
    :param url: The proof URL, for the log
    :return: The outcome, with the parsed document when one was found
    """
    body = bytearray()
    for chunk in response.iter_content(PROOF_CHUNK_BYTES):
        body.extend(chunk)
        if len(body) > PROOF_MAX_BYTES:
            logger.debug(f"The domain proof at {url} exceeds {PROOF_MAX_BYTES} bytes")
            return ProofOutcome(ProofStatus.NOT_FOUND)
    try:
        document = json.loads(bytes(body))
    except (ValueError, RecursionError) as exc:
        logger.debug(f"The domain proof at {url} is not JSON: {exc}")
        return ProofOutcome(ProofStatus.NOT_FOUND)
    if not isinstance(document, dict):
        logger.debug(f"The domain proof at {url} is not a JSON object")
        return ProofOutcome(ProofStatus.NOT_FOUND)
    return ProofOutcome(ProofStatus.FOUND, document)


def fetch_domain_proof(domain: str) -> ProofOutcome:
    """
    Fetch the proof file from the exact host named in the manifest.

    Redirects are not followed: the proof must come from the named host. The
    body is capped. Nothing is cached.

    :param domain: The operator domain
    :return: The outcome, with the parsed document when one was found
    """
    url = proof_url(domain)
    try:
        with requests.get(
            url, timeout=PROOF_FETCH_TIMEOUT, allow_redirects=False, stream=True
        ) as response:
            if response.status_code >= 500:
                logger.warning(
                    f"The domain proof at {url} answered {response.status_code}; "
                    f"could not check the operator's domain."
                )
                return ProofOutcome(ProofStatus.UNAVAILABLE)
            if 300 <= response.status_code < 400:
                logger.debug(f"The domain proof at {url} redirects elsewhere")
                return ProofOutcome(ProofStatus.REDIRECTED)
            if not 200 <= response.status_code < 300:
                logger.debug(f"No domain proof at {url}: HTTP {response.status_code}")
                return ProofOutcome(ProofStatus.NOT_FOUND)
            return _read_proof_body(response, url)
    except requests.RequestException as exc:
        logger.warning(f"Could not fetch the domain proof at {url}: {exc}")
        return ProofOutcome(ProofStatus.UNAVAILABLE)


def _agent_id_of(entry: Any) -> Optional[int]:
    """
    Read the agent id of one proof registration.

    :param entry: One item of the proof's ``registrations`` list
    :return: The agent id, or None when the entry does not carry an integer one
    """
    if not isinstance(entry, dict):
        return None
    value = entry.get("agentId")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and len(value) <= AGENT_ID_MAX_DIGITS
    ):
        return int(value)
    return None


def proof_matches(proof: Dict[str, Any], chain_id: int, agent_id: int) -> bool:
    """
    Tell whether a proof lists this chain's identity registry with this agent id.

    :param proof: The parsed proof document
    :param chain_id: The chain the mech is deployed on
    :param agent_id: The mech's ERC-8004 agent id on that chain
    :return: True only when a registration matches both
    """
    registrations = proof.get("registrations")
    if not isinstance(registrations, list):
        return False
    expected = f"eip155:{chain_id}:{IDENTITY_REGISTRY}".lower()
    for entry in registrations:
        if _agent_id_of(entry) != agent_id:
            continue
        registry = entry.get("agentRegistry")
        if isinstance(registry, str) and registry.lower() == expected:
            return True
    return False


@dataclass(frozen=True)
class DomainVerification:
    """Whether the operator's domain backs the manifest's claim."""

    verified: bool
    note: Optional[str] = None


NO_AGENT_ID_NOTE = "The mech has no ERC-8004 identity to match the domain against."
PROOF_UNAVAILABLE_NOTE = (
    "The operator's domain could not be reached for its proof; it will be "
    "checked again next time."
)
PROOF_NOT_FOUND_NOTE = "The operator's domain publishes no proof for this mech."
PROOF_REDIRECTED_NOTE = (
    "The operator's domain redirects the proof request to another host. The "
    "manifest must name the exact host that serves the proof."
)
PROOF_MISMATCH_NOTE = "The operator's domain proof does not list this mech."


def verify_domain(
    domain: str, chain_id: int, agent_id: Optional[int]
) -> DomainVerification:
    """
    Check the operator's domain against the mech's ERC-8004 identity.

    Fails closed: anything short of a fetched proof naming this chain's
    registry and this agent id is unverified, and the note says why.

    :param domain: The operator domain from the manifest
    :param chain_id: The chain the mech is deployed on
    :param agent_id: The mech's ERC-8004 agent id, or None when it has none
    :return: Verified, or unverified with the reason
    """
    if agent_id is None:
        return DomainVerification(False, NO_AGENT_ID_NOTE)
    outcome = fetch_domain_proof(domain)
    if outcome.status is ProofStatus.UNAVAILABLE:
        return DomainVerification(False, PROOF_UNAVAILABLE_NOTE)
    if outcome.status is ProofStatus.REDIRECTED:
        return DomainVerification(False, PROOF_REDIRECTED_NOTE)
    if outcome.proof is None:
        return DomainVerification(False, PROOF_NOT_FOUND_NOTE)
    if not proof_matches(outcome.proof, chain_id, agent_id):
        return DomainVerification(False, PROOF_MISMATCH_NOTE)
    return DomainVerification(True)

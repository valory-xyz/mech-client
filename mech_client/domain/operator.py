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

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from mech_client.utils.logger import get_logger

logger = get_logger(__name__)

# The manifest is written by the operator. Every value read from it is data:
# type-checked, stripped, capped, and rejected on control characters. Nothing
# in it is interpreted or followed.
OPERATOR_NAME_MAX_LENGTH = 200
TEXT_MAX_LENGTH = 200
URL_MAX_LENGTH = 2048
HOSTNAME_MAX_LENGTH = 253
# One hostname label: lowercase ASCII letters and digits, inner hyphens only.
_HOSTNAME_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
BENCHMARK_WINDOWS = ("7d", "30d", "90d", "all")

# ERC-8004 IdentityRegistry. One address on every chain the mechs run on.
IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
PROOF_PATH = "/.well-known/agent-registration.json"
# Kept short: a report is read before a request, and must not hold one up.
PROOF_FETCH_TIMEOUT = 5

BENCHMARK_NOTE = (
    "Benchmark links are the operator's own claim. This client does not check them."
)


def _is_clean_text(value: str) -> bool:
    """
    Tell whether a string holds no control characters.

    :param value: The string to check
    :return: True when every character is printable
    """
    return not any(unicodedata.category(char).startswith("C") for char in value)


def clean_text(value: Any, max_length: int = TEXT_MAX_LENGTH) -> Optional[str]:
    """
    Read a short free-text field from the manifest.

    :param value: The raw manifest value
    :param max_length: The longest text passed on
    :return: The stripped text, or None when it is not a usable string
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > max_length or not _is_clean_text(text):
        return None
    return text


def https_url(value: Any) -> Optional[str]:
    """
    Read a URL field from the manifest.

    The URL is parsed, not prefix-tested, so "https://" alone fails: it needs
    the https scheme and a host, and may hold no whitespace or control
    characters.

    :param value: The raw manifest value
    :return: The stripped URL, or None when it is not an https URL with a host
    """
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url or len(url) > URL_MAX_LENGTH:
        return None
    if any(char.isspace() for char in url) or not _is_clean_text(url):
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
    no scheme, path, port, credentials or trailing dot. The last label must
    hold a letter, which keeps IPv4 literals out.

    :param value: The raw manifest value
    :return: The domain, or None when it is not a bare hostname
    """
    if not isinstance(value, str):
        return None
    domain = value.strip()
    if not domain or len(domain) > HOSTNAME_MAX_LENGTH or "." not in domain:
        return None
    labels = domain.split(".")
    if not all(_HOSTNAME_LABEL.fullmatch(label) for label in labels):
        return None
    if not any(char.isalpha() for char in labels[-1]):
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


@dataclass(frozen=True)
class Benchmark:
    """
    A tool's score link, as the manifest claims.

    No figure: the manifest may carry a ``value``, but a number this client
    has not checked would read as one it had, so only the link is passed on.
    """

    metric: str
    window: str
    url: str


def read_operator(manifest: Dict[str, Any]) -> Optional[Operator]:
    """
    Read the ``operator`` block from a manifest.

    :param manifest: The parsed manifest document
    :return: The operator, or None when the block is absent or unusable
    """
    block = manifest.get("operator")
    if not isinstance(block, dict):
        return None
    name = clean_text(block.get("name"), OPERATOR_NAME_MAX_LENGTH)
    domain = hostname(block.get("domain"))
    if name is None or domain is None:
        return None
    return Operator(name=name, domain=domain)


def read_benchmarks(manifest: Dict[str, Any]) -> Dict[str, Benchmark]:
    """
    Read every tool's ``benchmark`` block from a manifest.

    :param manifest: The parsed manifest document
    :return: Benchmarks keyed by tool name; a tool with an unusable block is left out
    """
    tool_metadata = manifest.get("toolMetadata")
    if not isinstance(tool_metadata, dict):
        return {}
    benchmarks: Dict[str, Benchmark] = {}
    for tool, entry in tool_metadata.items():
        if not isinstance(tool, str) or not isinstance(entry, dict):
            continue
        block = entry.get("benchmark")
        if not isinstance(block, dict):
            continue
        metric = clean_text(block.get("metric"))
        window = block.get("window")
        url = https_url(block.get("url"))
        if metric is None or window not in BENCHMARK_WINDOWS or url is None:
            continue
        benchmarks[tool] = Benchmark(metric=metric, window=window, url=url)
    return benchmarks


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
    """The domain answered, and the answer is not a proof: 3xx, 4xx, or not JSON."""

    UNAVAILABLE = "unavailable"
    """The domain could not be reached or answered 5xx, so nothing is known."""


@dataclass(frozen=True)
class ProofOutcome:
    """The result of fetching a domain's proof file."""

    status: ProofStatus
    proof: Optional[Dict[str, Any]] = None


def fetch_domain_proof(domain: str) -> ProofOutcome:
    """
    Fetch the proof file from the exact host named in the manifest.

    Redirects are not followed: a proof must be served by the host it vouches
    for, so a 3xx answer is a verdict, not an outage. The outcome is never
    cached; an unavailable proof is fetched again next time.

    :param domain: The operator domain
    :return: The outcome, with the parsed document when one was found
    """
    url = proof_url(domain)
    try:
        response = requests.get(url, timeout=PROOF_FETCH_TIMEOUT, allow_redirects=False)
    except requests.RequestException as exc:
        logger.warning(f"Could not fetch the domain proof at {url}: {exc}")
        return ProofOutcome(ProofStatus.UNAVAILABLE)
    if response.status_code >= 500:
        logger.warning(
            f"The domain proof at {url} answered {response.status_code}; "
            f"could not check the operator's domain."
        )
        return ProofOutcome(ProofStatus.UNAVAILABLE)
    if not 200 <= response.status_code < 300:
        logger.debug(f"No domain proof at {url}: HTTP {response.status_code}")
        return ProofOutcome(ProofStatus.NOT_FOUND)
    try:
        document = response.json()
    except ValueError as exc:
        logger.debug(f"The domain proof at {url} is not JSON: {exc}")
        return ProofOutcome(ProofStatus.NOT_FOUND)
    if not isinstance(document, dict):
        logger.debug(f"The domain proof at {url} is not a JSON object")
        return ProofOutcome(ProofStatus.NOT_FOUND)
    return ProofOutcome(ProofStatus.FOUND, document)


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
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def proof_matches(proof: Dict[str, Any], chain_id: int, agent_id: int) -> bool:
    """
    Tell whether a proof lists this chain's identity registry with this agent id.

    Ownership of the on-chain entry is not part of the check: every Olas entry
    is owned by the registry's bridger proxy, not by the operator.

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
    if outcome.proof is None:
        return DomainVerification(False, PROOF_NOT_FOUND_NOTE)
    if not proof_matches(outcome.proof, chain_id, agent_id):
        return DomainVerification(False, PROOF_MISMATCH_NOTE)
    return DomainVerification(True)

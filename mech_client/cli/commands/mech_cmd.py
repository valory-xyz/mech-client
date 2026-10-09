# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

"""Mech command for managing and querying AI mechs on the marketplace."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

import click
import requests
from mech_client.cli.validators import validate_chain_config, validate_ethereum_address
from mech_client.domain.identification import is_valory_operated
from mech_client.domain.tools.manager import ToolManager, claimed_operator
from mech_client.infrastructure.config import IPFS_URL_TEMPLATE, get_mech_config
from mech_client.infrastructure.subgraph.queries import (
    query_mech_creations,
    query_mech_record,
    query_mm_mechs_info,
)
from mech_client.utils.errors.exceptions import ManifestError
from mech_client.utils.errors.handlers import handle_cli_errors
from tabulate import tabulate  # type: ignore

METADATA_FETCH_TIMEOUT = 10
METADATA_FETCH_WORKERS = 8
# Shown in the Operator column for a mech the identification check confirms.
# Anything else is left blank rather than labelled: the check fails closed, so
# "not confirmed" covers both an independent mech and a lookup that failed,
# and naming an operator we have not identified would be a claim we cannot make.
VALORY_OPERATOR_LABEL = "Valory"
VERIFIED_LABEL = "verified"
UNVERIFIED_LABEL = "unverified"


def _fetch_manifest(metadata_link: Optional[str]) -> Optional[Dict[str, Any]]:
    """Read a mech's published manifest document.

    :param metadata_link: gateway URL of the manifest document, or None
    :return: the parsed document, or None when there is no link, the fetch
        fails, or the body is not a JSON object
    """
    if not metadata_link:
        return None
    try:
        document = requests.get(metadata_link, timeout=METADATA_FETCH_TIMEOUT).json()
    except (requests.RequestException, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _fetch_manifests(
    metadata_links: List[Optional[str]],
) -> List[Optional[Dict[str, Any]]]:
    """Fetch the manifest for every metadata link, in parallel, order kept.

    :param metadata_links: one gateway URL (or None) per mech, in table order
    :return: one parsed document (or None) per mech, in the same order
    """
    if not metadata_links:
        return []
    workers = min(METADATA_FETCH_WORKERS, len(metadata_links))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(_fetch_manifest, metadata_links))


def _valory_operated_labels(addresses: List[str], chain_id: int) -> List[str]:
    """Label each mech the identification check confirms, in parallel, order kept.

    :param addresses: one mech address per row, in table order
    :param chain_id: the chain the listed mechs are deployed on
    :return: the operator label per row, blank where not confirmed
    """
    if not addresses:
        return []
    workers = min(METADATA_FETCH_WORKERS, len(addresses))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        confirmed = executor.map(
            lambda address: is_valory_operated(address, chain_id), addresses
        )
    return [VALORY_OPERATOR_LABEL if is_valory else "" for is_valory in confirmed]


def _operator_claim_label(operator: Optional[Dict[str, Any]]) -> str:
    """Render an operator claim for a table cell.

    :param operator: the operator block of a report, or None
    :return: ``name (domain, verified|unverified)``, blank when none is published
    """
    if operator is None:
        return ""
    status = VERIFIED_LABEL if operator["domain_verified"] else UNVERIFIED_LABEL
    return f"{operator['name']} ({operator['domain']}, {status})"


def _claimed_operator_labels(
    chain_config: str,
    chain_id: int,
    service_ids: List[int],
    manifests: List[Optional[Dict[str, Any]]],
) -> List[str]:
    """Label the operator each manifest claims, checked, in parallel, order kept.

    :param chain_config: the chain configuration name
    :param chain_id: the chain the listed mechs are deployed on
    :param service_ids: one service id per row, in table order
    :param manifests: one parsed manifest (or None) per row, in table order
    :return: the claim label per row, blank where the manifest publishes none
        or could not be read
    """
    if not manifests:
        return []

    def label(row: Any) -> str:
        service_id, manifest = row
        if manifest is None:
            return ""
        return _operator_claim_label(
            claimed_operator(chain_config, chain_id, service_id, manifest)
        )

    workers = min(METADATA_FETCH_WORKERS, len(manifests))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(label, zip(service_ids, manifests)))


def _since(created_at: Optional[datetime]) -> str:
    """Render a creation time as a UTC date for a table cell.

    :param created_at: the creation time, or None when the indexer has no row
    :return: the date in ISO 8601, blank when unknown
    """
    return created_at.date().isoformat() if created_at else ""


@click.group()
def mech() -> None:
    """Manage and query AI mechs on the marketplace.

    Commands for discovering and retrieving information about available
    AI mechs (on-chain AI agents) on the Mech Marketplace.
    """


@mech.command(name="list")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism, robinhood).",
)
@handle_cli_errors
def mech_list(  # pylint: disable=too-many-locals  # one local per column source
    chain_config: str,
) -> None:
    """List available mechs on the marketplace.

    Fetches information about all mechs from the marketplace subgraph,
    including service IDs, addresses, delivery counts, delivery record and
    metadata links, reads each mech's terms link and operator claim from its
    published manifest, checks the claimed domain against the mech's ERC-8004
    identity, and marks the mechs the identification check confirms as Valory
    operated.

    Uses default subgraph URL from configuration. Can be overridden with
    MECHX_SUBGRAPH_URL environment variable.

    Example: mechx mech list --chain-config gnosis

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism, robinhood).
    """
    # Validate chain config
    validated_chain = validate_chain_config(chain_config)

    # Query subgraph for mechs (uses default from config or MECHX_SUBGRAPH_URL override)
    mech_list_data = query_mm_mechs_info(chain_config=validated_chain)
    if not mech_list_data:
        click.echo("No mechs found")
        return

    # Format and display results
    headers = [
        "AI Agent Id",
        "Mech Type",
        "Mech Address",
        "Total Deliveries",
        "Received",
        "Self-delivered",
        "By others",
        "Since",
        "Metadata Link",
        "Terms",
        "Operator",
        "Claimed Operator",
    ]

    metadata_links = [
        (
            IPFS_URL_TEMPLATE.format(items["service"]["metadata"][0]["metadata"][2:])
            if items["service"].get("metadata")
            else None
        )
        for items in mech_list_data
    ]
    manifests = _fetch_manifests(metadata_links)
    terms_urls = [ToolManager.extract_terms_url(manifest) for manifest in manifests]
    chain_id = get_mech_config(validated_chain).ledger_config.chain_id
    addresses = [items["address"] for items in mech_list_data]
    operators = _valory_operated_labels(addresses, chain_id)
    claims = _claimed_operator_labels(
        validated_chain,
        chain_id,
        [int(items["service"]["id"]) for items in mech_list_data],
        manifests,
    )
    created_at = query_mech_creations(validated_chain, addresses)
    data = [
        (
            items["service"]["id"],
            items["mech_type"],
            items["address"],
            items["service"]["totalDeliveries"],
            items.get("receivedRequests", ""),
            items.get("selfDeliveredFromReceived", ""),
            items.get("deliveredByOthersFromReceived", ""),
            _since(created_at.get(items["address"].lower())),
            metadata_link,
            terms_url,
            operator,
            claim,
        )
        for items, metadata_link, terms_url, operator, claim in zip(
            mech_list_data, metadata_links, terms_urls, operators, claims
        )
    ]

    click.echo(tabulate(data, headers=headers, tablefmt="grid"))
    click.echo(
        "Received, Self-delivered and By others count on-chain requests and "
        "off-chain requests settled on-chain; an off-chain request that was "
        "never delivered is not counted. A claimed operator is the manifest's "
        "own statement, verified only when its domain publishes the mech's "
        "ERC-8004 identity."
    )


def _render_report(mech_address: str, report: Dict[str, Any]) -> List[str]:
    """Lay a mech report out as labelled lines.

    :param mech_address: the address the report is about
    :param report: the report from ``ToolManager.mech_report``
    :return: the lines to print, in order
    """
    lines = [f"Mech {mech_address}"]
    operator = report.get("operator")
    if operator is None:
        lines.append("Operator: not published in the mech's manifest")
    else:
        status = (
            f"domain {VERIFIED_LABEL}"
            if operator["domain_verified"]
            else f"domain {UNVERIFIED_LABEL}: {operator['verification_note']}"
        )
        lines.append(f"Operator: {operator['name']} ({operator['url']}), {status}")
    if report["valory_operated"]:
        lines.append(f"Terms: {report['terms']}")
    elif "identification_note" in report:
        lines.append(f"Terms: {report['identification_note']}")
    if "terms_url" in report:
        lines.append(f"Terms link: {report['terms_url']}")
    delivery = report["delivery"]
    lines.append(
        f"Delivery record: {delivery['received_requests']} received, "
        f"{delivery['self_delivered']} self-delivered, "
        f"{delivery['delivered_by_others']} delivered by others, "
        f"since {delivery['since']} ({delivery['age_days']} days)"
    )
    lines.append(f"  {delivery['note']}")
    payment = report["payment"]
    lines.append(f"Payment: {payment['type']}. {payment['note']}")
    benchmarks = report.get("benchmarks")
    if benchmarks:
        lines.append(f"Benchmarks: {report['benchmark_note']}")
        for tool, benchmark in benchmarks.items():
            lines.append(
                f"  {tool}: {benchmark['metric']} over {benchmark['window']}, "
                f"{benchmark['url']}"
            )
    else:
        lines.append("Benchmarks: none published in the mech's manifest")
    return lines


@mech.command(name="info")
@click.option(
    "--chain-config",
    type=str,
    required=True,
    help="Chain configuration name (gnosis, base, polygon, optimism, robinhood).",
)
@click.option(
    "--address",
    "mech_address",
    type=str,
    required=True,
    help="Address of the mech to report on.",
)
@handle_cli_errors
def mech_info(chain_config: str, mech_address: str) -> None:
    """Report who runs a mech and how it has behaved.

    Reads the mech's record from the marketplace subgraph and its manifest
    from IPFS, then reports the operator the manifest claims and whether the
    claimed domain publishes the mech's ERC-8004 identity, the terms that
    apply, the delivery record and age, the payment method, and the
    benchmark link the operator publishes per tool. Benchmark links are the
    operator's claim and are not checked. No price is shown: the mech
    contract quotes it at request time.

    Example: mechx mech info --chain-config gnosis --address 0x...

    :param chain_config: Chain configuration name (gnosis, base, polygon, optimism, robinhood).
    :param mech_address: Address of the mech to report on.
    """
    validated_chain = validate_chain_config(chain_config)
    address = validate_ethereum_address(mech_address, "Mech address")
    record = query_mech_record(validated_chain, address)
    if record.metadata_hash is None:
        raise ManifestError(
            f"Mech {address} publishes no manifest, so no report is made for it."
        )
    manifest = _fetch_manifest(IPFS_URL_TEMPLATE.format(record.metadata_hash[2:]))
    report = ToolManager(validated_chain).mech_report(address, manifest, record)
    for line in _render_report(address, report):
        click.echo(line)

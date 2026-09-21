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
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from aea_ledger_ethereum import EthereumApi
from mech_client.domain.identification import (
    Identification,
    VALORY_TERMS_NOTICE,
    identify,
)
from mech_client.domain.tools.models import ToolInfo, ToolsForMarketplaceMech
from mech_client.infrastructure.blockchain.abi_loader import get_abi
from mech_client.infrastructure.blockchain.contracts import get_contract
from mech_client.infrastructure.config.loader import get_mech_config
from web3.constants import ADDRESS_ZERO

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
TOOLS = "tools"
TOOL_METADATA = "toolMetadata"
# A terms link comes from an operator's own document, so it is only passed on
# when it is a plain https URL of a sane length.
TERMS_URL_MAX_LENGTH = 2048
IDENTIFICATION_NOTE = "Could not check whether Valory operates this mech."


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
        URI, then fetches the metadata from that URI.

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
            return requests.get(metadata_uri, timeout=DEFAULT_TIMEOUT).json()
        except (json.JSONDecodeError, NotImplementedError, IOError) as e:
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

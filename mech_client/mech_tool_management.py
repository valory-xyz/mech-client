"""Module for managing mechanical tools and their interactions with blockchain."""

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from aea_ledger_ethereum import EthereumApi

from mech_client.interact import (
    AGENT_REGISTRY_ABI_PATH,
    fetch_tools,
    get_abi,
    get_contract,
    get_mech_config,
)


def get_total_supply(chain_config: str = "gnosis") -> int:
    """
    Fetches the total supply of tokens from a contract using the chain configuration.

    :param chain_config: The chain configuration to use.
    :type chain_config: str
    :return: The total supply of tokens.
    :rtype: int
    """
    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config

    # Setup Ethereum API
    ledger_api = EthereumApi(**asdict(ledger_config))

    # Fetch ABI and create contract instance
    abi = get_abi(AGENT_REGISTRY_ABI_PATH)
    contract = get_contract(mech_config.agent_registry_contract, abi, ledger_api)

    # Call the totalSupply function
    return contract.functions.totalSupply().call()


def get_agent_tools(
    agent_id: int, chain_config: str = "gnosis", include_metadata: bool = False
) -> Optional[Union[List[str], Tuple[List[str], Dict[str, Any]]]]:
    """
    Fetch tools for a given agent ID.

    :param agent_id: The ID of the agent.
    :param chain_config: The chain configuration to use (default is "gnosis").
    :param include_metadata: To include tools metadata or not (default is False)
    :return: A list of tools if successful, or a tuple of (list of tools, metadata) if metadata is included, or None if an error occurs.
    """
    try:
        # Get the mech configuration
        mech_config = get_mech_config(chain_config)
        ledger_config = mech_config.ledger_config

        # Setup Ethereum API
        ledger_api = EthereumApi(**asdict(ledger_config))

        # Fetch tools for the given agent ID
        return fetch_tools(
            agent_id=agent_id,
            ledger_api=ledger_api,
            agent_registry_contract=mech_config.agent_registry_contract,
            contract_abi_path=AGENT_REGISTRY_ABI_PATH,
            include_metadata=include_metadata,
        )
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"An error occurred while fetching tools for agent {agent_id}: {e}")
        return None


def get_tools_for_agents(
    agent_id: Optional[int] = None, chain_config: str = "gnosis"
) -> Dict[str, Any]:
    """
    Retrieve tools for specified agents or all agents if no specific agent is provided.

    :param agent_id: Optional; specific agent ID to fetch tools for.
    :param chain_config: The chain configuration to use.
    :return: Dictionary of tools with identifiers or a mapping of agent IDs to tools.
    """
    try:
        total_supply = get_total_supply(chain_config)

        if agent_id is not None:
            result = get_agent_tools(agent_id, chain_config, True)

            if result is not None:
                (tools, tool_metadata) = result

                if isinstance(tools, list) and isinstance(tool_metadata, dict):
                    tools_with_ids = [
                        {
                            "tool_name": tool,
                            "unique_identifier": f"{agent_id}-{tool}",
                            "is_marketplace_supported": (
                                tool_metadata.get(tool, {}).get(
                                    "isMechMarketplaceSupported", None
                                )
                            ),
                        }
                        for tool in tools
                    ]
                else:
                    tools_with_ids = []
                return {"agent_id": agent_id, "tools": tools_with_ids}

        all_tools_with_ids = []
        agent_tools_map = {}

        for current_agent_id in range(1, total_supply + 1):
            result = get_agent_tools(current_agent_id, chain_config, True)
            if result is not None:
                (tools, tool_metadata) = result

                if isinstance(tools, list) and isinstance(tool_metadata, dict):
                    tools_with_ids = [
                        {
                            "tool_name": tool,
                            "unique_identifier": f"{current_agent_id}-{tool}",
                            "is_marketplace_supported": (
                                tool_metadata.get(tool, {}).get(
                                    "isMechMarketplaceSupported", None
                                )
                            ),
                        }
                        for tool in tools
                    ]
                    agent_tools_map[current_agent_id] = tools
                    all_tools_with_ids.extend(tools_with_ids)

        return {
            "all_tools_with_identifiers": all_tools_with_ids,
            "agent_tools_map": agent_tools_map,
        }
    except Exception as e:
        print(f"Error in get_tools_for_agents: {str(e)}")
        raise


def get_tool_description(unique_identifier: str, chain_config: str = "gnosis") -> str:
    """
    Fetch the description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Description of the tool or a default message if not available.
    """
    parts = unique_identifier.split("-")
    agent_id = int(parts[0])
    tool_name = "-".join(parts[1:])

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    tools_result = fetch_tools(
        agent_id=agent_id,
        ledger_api=ledger_api,
        agent_registry_contract=mech_config.agent_registry_contract,
        contract_abi_path=AGENT_REGISTRY_ABI_PATH,
        include_metadata=True,
    )
    if isinstance(tools_result, tuple) and len(tools_result) == 2:
        _, tool_metadata = tools_result
        tool_info = tool_metadata.get(tool_name, {})
        if isinstance(tool_info, dict):
            return tool_info.get("description", "Description not available")
    return "Description not available"


def get_tool_io_schema(
    unique_identifier: str, chain_config: str = "gnosis"
) -> Dict[str, Any]:
    """
    Fetch the input and output schema along with tool name and description of a specific tool based on a unique identifier.

    :param unique_identifier: The unique identifier for the tool.
    :param chain_config: The chain configuration to use.
    :return: Dictionary containing name, description, input and output schemas.
    """
    parts = unique_identifier.split("-")
    agent_id = int(parts[0])
    tool_name = "-".join(parts[1:])

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    tools_result = fetch_tools(
        agent_id=agent_id,
        ledger_api=ledger_api,
        agent_registry_contract=mech_config.agent_registry_contract,
        contract_abi_path=AGENT_REGISTRY_ABI_PATH,
        include_metadata=True,
    )
    if isinstance(tools_result, tuple) and len(tools_result) == 2:
        _, tool_metadata = tools_result
        tool_info = tool_metadata.get(tool_name, {})
        if isinstance(tool_info, dict):
            return {
                "name": tool_info.get("name", {}),
                "description": tool_info.get("description", {}),
                "input": tool_info.get("input", {}),
                "output": tool_info.get("output", {}),
            }

    return {"input": {}, "output": {}}

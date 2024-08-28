import json
import requests
from web3 import Web3
from mech_client.interact import get_mech_config, fetch_tools
from aea_ledger_ethereum import EthereumApi
from dataclasses import asdict
from typing import List, Dict, Optional, Set, Union, Any


def get_total_supply(chain_config: str = "gnosis") -> int:
    """
    Get the total supply from the contract.
    
    :param chain_config: The chain configuration to use (default is "gnosis").
    :return: The total supply as an integer.
    """
    mech_config = get_mech_config(chain_config)
    ledger_config = mech_config.ledger_config

    # Setup Web3
    w3 = Web3(Web3.HTTPProvider(ledger_config.address))

    # Fetch ABI from the contract_abi_url
    response = requests.get(mech_config.contract_abi_url.format(contract_address=mech_config.agent_registry_contract))
    response_json = response.json()


    # Try to extract the ABI from different possible response structures
    if 'result' in response_json and isinstance(response_json['result'], str):
        contract_abi = json.loads(response_json['result'])
    elif 'abi' in response_json:
        contract_abi = response_json['abi']
    else:
        raise ValueError(f"Unexpected API response structure: {response_json}")

    # Create a contract instance
    contract = w3.eth.contract(address=mech_config.agent_registry_contract, abi=contract_abi)

    # Call the totalSupply function
    total_supply = contract.functions.totalSupply().call()

    return total_supply

def get_agent_tools(agent_id: int, chain_config: str = "gnosis") -> Optional[List[str]]:
    """
    Fetch tools for a given agent ID.
    
    :param agent_id: The ID of the agent.
    :param chain_config: The chain configuration to use (default is "gnosis").
    :return: A list of tools if successful, None otherwise.
    """
    try:
        # Get the mech configuration
        mech_config = get_mech_config(chain_config)
        ledger_config = mech_config.ledger_config

        # Setup Ethereum API
        ledger_api = EthereumApi(**asdict(ledger_config))

        # Fetch tools for the given agent ID
        tools = fetch_tools(
            agent_id=agent_id,
            ledger_api=ledger_api,
            agent_registry_contract=mech_config.agent_registry_contract,
            contract_abi_url=mech_config.contract_abi_url
        )
        
        return tools
    except Exception as e:
        print(f"An error occurred while fetching tools for agent {agent_id}: {e}")
        return None


def get_tools_for_agents(agent_id: Optional[int] = None, chain_config: str = "gnosis") -> Dict[str, Any]:
    try:
        mech_config = get_mech_config(chain_config)
        total_supply = get_total_supply(chain_config)

        if agent_id is not None:
            tools = get_agent_tools(agent_id, chain_config)
            tools_with_ids = [{"tool_name": tool, "unique_identifier": f"{agent_id}-{tool}"} for tool in tools] if tools else []
            return {
                "agent_id": agent_id,
                "tools": tools_with_ids
            }
        else:
            all_tools_with_ids = []
            agent_tools_map = {}

            for current_agent_id in range(1, total_supply + 1):
                tools = get_agent_tools(current_agent_id, chain_config)
                if tools:
                    tools_with_ids = [{"tool_name": tool, "unique_identifier": f"{current_agent_id}-{tool}"} for tool in tools]
                    agent_tools_map[current_agent_id] = tools  # Only store tool names
                    all_tools_with_ids.extend(tools_with_ids)

            return {
                "all_tools_with_identifiers": all_tools_with_ids,
                "agent_tools_map": agent_tools_map,
            }
    except Exception as e:
        print(f"Error in get_tools_for_agents: {str(e)}")
        raise
    
def get_tool_description(unique_identifier: str, chain_config: str = "gnosis") -> str:
    """Fetch the description of a specific tool based on a unique identifier."""
    parts = unique_identifier.split('-')
    agent_id = int(parts[0])
    tool_name = '-'.join(parts[1:])

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)  # Pass chain_config dynamically
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    _, tool_metadata = fetch_tools(
            agent_id=agent_id,
            ledger_api=ledger_api,
            agent_registry_contract=mech_config.agent_registry_contract,
            contract_abi_url=mech_config.contract_abi_url,
            include_metadata=True
    )
    tool_info = tool_metadata.get(tool_name, {})
    return tool_info.get('description', 'Description not available')

def get_tool_io_schema(unique_identifier: str, chain_config: str = "gnosis") -> Dict[str, Any]:
    """Fetch the input and output schema of a specific tool based on a unique identifier."""
    parts = unique_identifier.split('-')
    agent_id = int(parts[0])
    tool_name = '-'.join(parts[1:])

    # Get the mech configuration
    mech_config = get_mech_config(chain_config)  # Pass chain_config dynamically
    ledger_api = EthereumApi(**asdict(mech_config.ledger_config))

    _, tool_metadata = fetch_tools(
            agent_id=agent_id,
            ledger_api=ledger_api,
            agent_registry_contract=mech_config.agent_registry_contract,
            contract_abi_url=mech_config.contract_abi_url,
            include_metadata=True
    )
    tool_info = tool_metadata.get(tool_name, {})
    return {
        "input": tool_info.get('input', {}),
        "output": tool_info.get('output', {})
    }

# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""Subgraph client for mech."""

from string import Template
from typing import Optional


AGENT_QUERY_TEMPLATE = Template(
    """{
    createMeches(where:{agentId:$agent_id}) {
        mech
    }
}
"""
)

DEFAULT_TIMEOUT = 600.0
CHAIN_TO_ADDRESSES = {
    "gnosis": {
        6: "0x77af31De935740567Cf4fF1986D04B2c964A786a",
        9: "0x552cea7bc33cbbeb9f1d90c1d11d2c6daeffd053",
        19: "0x45b73d649c7b982548d5a6dd3d35e1c5c48997d0",
    },
}


def query_agent_address(  # pylint: disable=too-many-return-statements
    agent_id: int,
    chain_config: Optional[str] = None,
) -> Optional[str]:
    """
    Query agent address from subgraph.

    :param agent_id: The ID of the agent.
    :type agent_id: int
    :type chain_config: Optional[str]:
    :return: The agent address if found, None otherwise.
    :rtype: Optional[str]
    """
    # temporary hard coded until subgraph present
    if not chain_config:
        raise ValueError("Chain config not specified")
    return CHAIN_TO_ADDRESSES.get(chain_config, {}).get(agent_id, None)

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

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

MECH_SUBGRAPH_URL = "https://api.studio.thegraph.com/query/46780/mech/v0.0.1"
AGENT_QUERY_TEMPLATE = Template(
    """{
    createMeches(where:{agentId:$agent_id}) {
        mech
    }
}
"""
)


def query_agent_address(agent_id: int) -> Optional[str]:
    """Query agent address from subgraph."""
    client = Client(transport=AIOHTTPTransport(url=MECH_SUBGRAPH_URL))
    response = client.execute(
        document=gql(
            request_string=AGENT_QUERY_TEMPLATE.substitute({"agent_id": agent_id})
        )
    )
    mechs = response["createMeches"]
    if len(mechs) == 0:
        return None

    (record,) = mechs
    return record["mech"]

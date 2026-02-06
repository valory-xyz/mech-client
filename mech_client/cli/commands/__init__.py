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

"""CLI command modules."""

from mech_client.cli.commands.deposit_cmd import deposit
from mech_client.cli.commands.ipfs_cmd import ipfs
from mech_client.cli.commands.mech_cmd import mech
from mech_client.cli.commands.request_cmd import request
from mech_client.cli.commands.setup_cmd import setup
from mech_client.cli.commands.subscription_cmd import subscription
from mech_client.cli.commands.tool_cmd import tool


__all__ = [
    "setup",
    "request",
    "mech",
    "tool",
    "deposit",
    "subscription",
    "ipfs",
]

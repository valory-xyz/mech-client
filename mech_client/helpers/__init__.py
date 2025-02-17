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

"""Helper packages."""

from pathlib import Path


ACN_PROTOCOL_PACKAGE = (
    Path(__file__).parents[2] / "packages" / "valory" / "protocols" / "acn"
)
P2P_CLIENT_PACKAGE = (
    Path(__file__).parents[2]
    / "packages"
    / "valory"
    / "connections"
    / "p2p_libp2p_client"
)
ACN_DATA_SHARE_PROTOCOL_PACKAGE = (
    Path(__file__).parents[2] / "packages" / "valory" / "protocols" / "acn_data_share"
)

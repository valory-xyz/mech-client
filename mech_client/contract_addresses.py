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

"""Contract addresses for mech marketplace and payment systems."""

from typing import Dict


# Balance tracker contracts for native token payments
CHAIN_TO_NATIVE_BALANCE_TRACKER: Dict[int, str] = {
    100: "0x21cE6799A22A3Da84B7c44a814a9c79ab1d2A50D",  # Gnosis
    42161: "",  # Arbitrum (not supported)
    137: "0xc096362fa6f4A4B1a9ea68b1043416f3381ce300",  # Polygon
    8453: "0xB3921F8D8215603f0Bd521341Ac45eA8f2d274c1",  # Base
    42220: "",  # Celo (not supported)
    10: "0x4Cd816ce806FF1003ee459158A093F02AbF042a8",  # Optimism
}

# Balance tracker contracts for OLAS token payments
CHAIN_TO_TOKEN_BALANCE_TRACKER_OLAS: Dict[int, str] = {
    100: "0x53Bd432516707a5212A70216284a99A563aAC1D1",  # Gnosis
    42161: "",  # Arbitrum (not supported)
    137: "0x1521918961bDBC9Ed4C67a7103D5999e4130E6CB",  # Polygon
    8453: "0x43fB32f25dce34EB76c78C7A42C8F40F84BCD237",  # Base
    42220: "",  # Celo (not supported)
    10: "0x70A0D93fb0dB6EAab871AB0A3BE279DcA37a2bcf",  # Optimism
}

# Balance tracker contracts for USDC token payments
CHAIN_TO_TOKEN_BALANCE_TRACKER_USDC: Dict[int, str] = {
    100: "",  # Gnosis (not supported)
    42161: "",  # Arbitrum (not supported)
    137: "0x5C50ebc17d002A4484585C8fbf62f51953493c0B",  # Polygon
    8453: "0x0443C55e151dBA13fae079518F9dd01ff9c21CB2",  # Base
    42220: "",  # Celo (not supported)
    10: "0xA123748Ce7609F507060F947b70298D0bde621E6",  # Optimism
}

# OLAS token addresses by chain
CHAIN_TO_PRICE_TOKEN_OLAS: Dict[int, str] = {
    100: "0xcE11e14225575945b8E6Dc0D4F2dD4C570f79d9f",  # Gnosis
    42161: "",  # Arbitrum (not supported)
    137: "0xFEF5d947472e72Efbb2E388c730B7428406F2F95",  # Polygon
    8453: "0x54330d28ca3357F294334BDC454a032e7f353416",  # Base
    42220: "",  # Celo (not supported)
    10: "0xFC2E6e6BCbd49ccf3A5f029c79984372DcBFE527",  # Optimism
}

# USDC token addresses by chain
CHAIN_TO_PRICE_TOKEN_USDC: Dict[int, str] = {
    100: "",  # Gnosis (not supported)
    42161: "",  # Arbitrum (not supported)
    137: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",  # Polygon
    8453: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # Base
    42220: "",  # Celo (not supported)
    10: "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",  # Optimism
}

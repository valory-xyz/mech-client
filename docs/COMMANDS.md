# Command Reference

This document provides detailed information about each CLI command, including external dependencies and environment variables.

## Overview

**Total commands: 11** (10 with detailed diagrams - utility commands have minimal dependencies)

### Legend

```
[Command] → External Resource (Environment Variable if configurable)
├─ Resource Type: description
└─ Contract: contract name
```

## Commands

### 1. setup

```
mechx setup
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Blockchain queries for Safe setup
├─ Olas Operate Middleware
│  └─ Service configuration and deployment
└─ Local Files
   ├─ ~/.operate_mech_client/ (service configs)
   └─ .env (OPERATE_PASSWORD)

ENV VARS:
  MECHX_CHAIN_RPC (optional, uses default from mechs.json)
  OPERATE_PASSWORD (loaded from .env or prompted)
```

### 2. request

```
mechx request --priority-mech 0x... --tools tool1 --prompts "..."
├─ HTTP RPC (MECHX_CHAIN_RPC) ← PRIMARY DEPENDENCY
│  ├─ Send transaction (approve, request)
│  ├─ Wait for transaction receipt ← TIMES OUT HERE IF RPC SLOW
│  └─ Poll for Deliver events
├─ IPFS Gateway (https://gateway.autonolas.tech/ipfs/)
│  ├─ Upload: prompt + tool metadata
│  └─ Download: mech response data
├─ Smart Contracts (on-chain)
│  ├─ MechMarketplace: request(), requestBatch()
│  ├─ IMech: paymentType(), serviceId(), maxDeliveryRate()
│  ├─ BalanceTracker: mapRequesterBalances() (if prepaid)
│  ├─ ERC20 Token: approve(), balanceOf() (if token payment)
│  └─ ERC1155: balanceOf() (if NVM subscription)
└─ [If Agent Mode]
   ├─ Safe Multisig (via safe-eth-py)
   └─ Olas Operate Middleware (fetch safe address)

OPTIONAL:
├─ Offchain Mech HTTP (MECHX_MECH_OFFCHAIN_URL)
│  └─ If --use-offchain flag set

ENV VARS:
  MECHX_CHAIN_RPC (required for reliable operation) ← SET THIS
  MECHX_MECH_OFFCHAIN_URL (required if --use-offchain)

NOTES:
  - NO WebSocket (WSS) used for marketplace mechs
  - Delivery watched via HTTP RPC polling only
  - If HTTP RPC is slow/unavailable, command times out at "Waiting for transaction receipt..."
```

### 3. deposit native

```
mechx deposit native --chain-config gnosis --mech-type native --amount 0.01
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  ├─ Check native balance
│  ├─ Send transfer transaction
│  └─ Wait for receipt
└─ Smart Contracts
   ├─ BalanceTrackerFixedPriceNative: deposit()
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - Prepaid balance for marketplace requests
  - Supports both agent mode (Safe) and client mode (EOA)
```

### 4. deposit token

```
mechx deposit token --chain-config gnosis --token-type olas --amount 1000000000000000000
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  ├─ Check ERC20 balance
│  ├─ Send approve() transaction
│  ├─ Send deposit() transaction
│  └─ Wait for receipts
└─ Smart Contracts
   ├─ ERC20 Token: approve(), balanceOf()
   ├─ BalanceTrackerFixedPriceToken: deposit()
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)

SUPPORTED TOKENS:
  - olas: OLAS token (chain-specific address)
  - usdc: USDC token (not available on gnosis)
```

### 5. subscription purchase

```
mechx subscription purchase --chain-config gnosis --mech-type native_nvm
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Send NVM subscription transaction
├─ Nevermined Network
│  └─ Subscription plan management
└─ Smart Contracts
   ├─ NVM Subscription contracts
   └─ [If Agent Mode] Safe: execTransaction()

ENV VARS:
  MECHX_CHAIN_RPC (required)
  PLAN_DID (from mech_client/infrastructure/nvm/resources/envs/{chain}.env)
  NETWORK_NAME (from envs)
  CHAIN_ID (from envs)
```

### 6. mech list

```
mechx mech list --chain-config gnosis
├─ Subgraph GraphQL API (MECHX_SUBGRAPH_URL) ← Optional override
│  └─ Query: MechsOrderedByServiceDeliveries
│     ├─ Returns: service IDs, addresses, delivery counts
│     └─ Filters: totalDeliveries > 0
└─ [Output references]
   └─ IPFS Gateway links (metadata URLs)

ENV VARS:
  MECHX_SUBGRAPH_URL (optional - defaults provided for all supported chains)

NOTES:
  - Read-only command, no transactions
  - Does NOT use HTTP RPC
  - Default subgraph URLs provided for gnosis, base, polygon, optimism
  - Override with MECHX_SUBGRAPH_URL only if using custom subgraph
```

### 7. tool list

```
mechx tool list --agent-id <service_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash contract
└─ External HTTP
   └─ Fetch metadata from tokenURI(service_id)

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - For marketplace mechs only
  - Uses service_id (passed as --agent-id parameter)
```

### 8. tool describe

```
mechx tool describe <tool_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash.tokenURI(service_id)
└─ External HTTP
   └─ Fetch and parse tool metadata

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - tool_id format: "service_id-tool_name"
  - Example: "1-openai-gpt-3.5-turbo"
```

### 9. tool schema

```
mechx tool schema <tool_id> --chain-config gnosis
├─ HTTP RPC (MECHX_CHAIN_RPC)
│  └─ Query: ComplementaryMetadataHash.tokenURI(service_id)
└─ External HTTP
   └─ Fetch and parse tool metadata

ENV VARS:
  MECHX_CHAIN_RPC (required)

NOTES:
  - tool_id format: "service_id-tool_name"
  - Returns input/output schema for the tool
```

### 10. ipfs upload-prompt & ipfs upload

```
mechx ipfs upload-prompt "prompt" "tool"
mechx ipfs upload /path/to/file
└─ IPFS Gateway (https://gateway.autonolas.tech/ipfs/)
   └─ Upload file/metadata

ENV VARS:
  None (uses hardcoded IPFS gateway)

NOTES:
  - Utility commands, no blockchain interaction
  - No RPC or WSS needed
```

## Quick Reference: Environment Variables by Command

| Command | MECHX_CHAIN_RPC | MECHX_SUBGRAPH_URL | MECHX_MECH_OFFCHAIN_URL | OPERATE_PASSWORD |
|---------|----------------|--------------------|-----------------------|------------------|
| setup | ○ | | | ✓ |
| request | ✓ | | ○ | |
| deposit native | ✓ | | | |
| deposit token | ✓ | | | |
| subscription purchase | ✓ | | | |
| mech list | | ○ | | |
| tool list | ✓ | | | |
| tool describe | ✓ | | | |
| tool schema | ✓ | | | |
| ipfs upload-prompt | | | | |
| ipfs upload | | | | |

**Legend:**
- ✓ = Required for command to work
- ○ = Optional (uses default from mechs.json if not set)
- Empty = Not used

## Chain Support Matrix

**Supported chains:** `gnosis`, `base`, `polygon`, `optimism`

All commands require `--chain-config` with one of these four chain names. Arbitrum and Celo exist in the configuration but have no marketplace support and are currently non-functional.

| Chain | Chain ID | Marketplace | Agent Mode | Native Payment | NVM Subscriptions | OLAS Token | USDC Token | Subgraph |
|-------|----------|-------------|------------|----------------|-------------------|------------|------------|----------|
| Gnosis | 100 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Base | 8453 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Polygon | 137 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Optimism | 10 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Arbitrum | 42161 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Celo | 42220 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

**Feature Definitions:**
- **Marketplace**: Chain has `mech_marketplace_contract` deployed (non-zero address in `mechs.json`)
- **Agent Mode**: Supports `setup` command and Safe-based agent operations (all marketplace chains: Gnosis, Base, Polygon, Optimism)
- **Native Payment**: Supports `deposit native` command for prepaid native token deposits (Gnosis, Base, Polygon, Optimism)
- **NVM Subscriptions**: Supports `subscription purchase` command for Nevermined subscription-based payments (Gnosis, Base)
- **OLAS/USDC Token**: Payment token addresses configured in `infrastructure/config/contract_addresses.py`
- **Subgraph**: Default subgraph URL provided in `mechs.json` for all supported marketplace chains (Gnosis, Base, Polygon, Optimism). Override with `MECHX_SUBGRAPH_URL` if needed.

**Command Requirements:**
- `mech list`: Requires marketplace (default subgraph URLs provided; optionally override with `MECHX_SUBGRAPH_URL`)
- `request`: Requires marketplace contract and standard Olas service registry
- `deposit native`: Requires marketplace + native payment support (Gnosis, Base, Polygon, Optimism)
- `deposit token`: Requires marketplace + token addresses in config (Gnosis, Base, Polygon, Optimism)
- `subscription purchase`: Requires marketplace + NVM subscription support (Gnosis, Base)
- `setup`: All marketplace chains (Gnosis, Base, Polygon, Optimism)

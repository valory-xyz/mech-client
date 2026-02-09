# Manual Testing Guide

This guide provides step-by-step instructions for manually testing all CLI commands in the mech-client.

## Prerequisites

### Required Setup

1. **Python Environment**
   ```bash
   # Ensure Python 3.10 or 3.11 is installed
   python --version

   # Install mech-client
   pip install mech-client
   # OR for development:
   poetry install && poetry shell
   ```

2. **Private Key**
   ```bash
   # Create a private key file for testing
   # IMPORTANT: Use a test wallet with small amounts only!
   echo "your_private_key_here" > ethereum_private_key.txt
   chmod 600 ethereum_private_key.txt
   ```

3. **Environment Variables** (Optional but recommended)
   ```bash
   # Create .env file or export these:
   export MECHX_CHAIN_RPC='https://rpc.gnosischain.com'
   export MECHX_SUBGRAPH_URL='https://your-subgraph-url'  # For mech list command
   export MECHX_MECH_OFFCHAIN_URL='http://localhost:8000/'  # For offchain testing
   ```

4. **Funded Wallet**
   - Ensure your test wallet has native tokens (xDAI on Gnosis, ETH on other chains)
   - For token payments: ensure you have OLAS or USDC tokens
   - **Never use your main wallet for testing!**

---

## Understanding Payment Types

**Important**: Payment types are determined by each mech's smart contract, not by the user. The client automatically detects and handles the appropriate payment flow.

### Payment Types

| Payment Type | Description | How Client Handles Payment |
|--------------|-------------|----------------------------|
| **NATIVE** | Per-request native token | Sends native tokens (xDAI, ETH, MATIC) with transaction |
| **OLAS_TOKEN** | Per-request OLAS token | Approves & transfers OLAS tokens |
| **USDC_TOKEN** | Per-request USDC token | Approves & transfers USDC tokens |
| **NATIVE_NVM** | NVM subscription + native | Validates subscription NFT (requires `subscription purchase` first) |
| **TOKEN_NVM_USDC** | NVM subscription + USDC | Validates subscription NFT (requires `subscription purchase` first) |

### How It Works

1. **Client detects payment type**: Queries mech's contract to determine payment method
2. **Client handles payment automatically**:
   - For NATIVE: Sends tokens with transaction
   - For token payments (OLAS/USDC): Approves tokens, then sends request
   - For NVM subscriptions: Validates your subscription NFT
3. **Optional prepaid balance**: Use `--use-prepaid` flag to pay from prepaid balance instead of per-request (works for non-subscription mechs)

### Testing Different Payment Types

When testing, you'll encounter mechs with different payment types:
- Find NATIVE mechs for native token testing
- Find OLAS_TOKEN or USDC_TOKEN mechs for token payment testing
- Find NATIVE_NVM or TOKEN_NVM_USDC mechs for subscription testing (Gnosis/Base only)

---

## Testing Checklist

Use this checklist to track your testing progress:

- [ ] setup
- [ ] request (marketplace - native payment - client mode)
- [ ] request (marketplace - native payment - agent mode)
- [ ] request (marketplace - token payment - client mode)
- [ ] request (marketplace - token payment - agent mode)
- [ ] request (marketplace - prepaid - client mode)
- [ ] request (marketplace - prepaid - agent mode)
- [ ] request (marketplace - offchain)
- [ ] deposit native (client mode)
- [ ] deposit native (agent mode)
- [ ] deposit token (client mode)
- [ ] deposit token (agent mode)
- [ ] subscription purchase (client mode)
- [ ] subscription purchase (agent mode)
- [ ] mech list
- [ ] tool list
- [ ] tool describe
- [ ] tool schema
- [ ] ipfs upload-prompt
- [ ] ipfs upload
- [ ] ipfs to-png

---

## Command Tests

### 1. Setup Agent Mode

**Purpose**: Configure agent mode for Safe-based transactions

**Command**:
```bash
mechx setup --chain-config gnosis
```

**Expected Output**:
```
Agent mode enabled
Setting up agent mode using config at .../mech_client_gnosis.json...
[Various setup logs from Olas Operate]
```

**Success Criteria**:
- ✅ No errors during setup
- ✅ Directory created at `~/.operate_mech_client/`
- ✅ Service deployed successfully
- ✅ Safe address displayed in logs

**Verification**:
```bash
ls ~/.operate_mech_client/services/
# Should show a service directory
```

**Supported Chains**: gnosis, base, polygon, optimism

---

### 2. Request - Marketplace (Native Payment)

**Purpose**: Send a request to a marketplace mech with per-request native payment

**Prerequisites**:
- Funded wallet with native tokens (minimum ~0.02 xDAI)

**Command**:
```bash
# Client mode (simple)
mechx --client-mode request \
  --prompts "What is the weather in Paris today?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt

# OR Agent mode (if setup was run)
mechx request \
  --prompts "What is the weather in Paris today?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis
```

**Expected Output**:
```
Agent mode enabled
Sending marketplace request...
Fetching Mech Info...
Native Mech detected, fetching user native balance for price payment...
Sending Mech Marketplace request...
  - Prompt uploaded: https://gateway.autonolas.tech/ipfs/f01701220...
  - Transaction sent: https://gnosisscan.io/tx/0x5187fddd...
  - Waiting for transaction receipt...
  - Request ID: 123
  - Waiting for response...
  - Data arrived: https://gateway.autonolas.tech/ipfs/f01701220...
  - Data from agent:
{
  "requestId": 123,
  "result": "The weather in Paris today is..."
}
```

**Success Criteria**:
- ✅ Transaction URL includes "0x" prefix
- ✅ IPFS URLs are accessible
- ✅ Response received within reasonable time (~30-120 seconds)
- ✅ Result contains valid JSON data

**Troubleshooting**:
- If timeout: Check `MECHX_CHAIN_RPC` is set to a reliable provider
- If "insufficient funds": Ensure wallet has enough native tokens
- If mech address invalid: Verify the priority-mech address is correct

---

### 3. Request - Marketplace (Token Payment)

**Purpose**: Send a request with OLAS token payment

**Prerequisites**:
- Wallet funded with OLAS tokens
- Token approval may be required (automatic)

**Command**:
```bash
mechx --client-mode request \
  --prompts "Summarize the latest news about AI" \
  --priority-mech 0x4554fE75c1f8D614Fc8614Fef4c99D1E44e39fAE \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
...
Token Mech detected, approving OLAS token for price payment...
  - Transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Sending Mech Marketplace request...
...
```

**Success Criteria**:
- ✅ Token approval transaction succeeds
- ✅ Request transaction succeeds
- ✅ Response received

---

### 4. Request - Marketplace (Prepaid)

**Purpose**: Use prepaid balance for marketplace requests

**Prerequisites**:
- Prepaid deposit made (see deposit-native/deposit-token tests)

**Command**:
```bash
mechx --client-mode request \
  --prompts "What is 2+2?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-prepaid true \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
...
Using prepaid balance for request...
...
```

**Success Criteria**:
- ✅ No approval transaction
- ✅ Balance deducted from prepaid account
- ✅ Response received

---

### 5. Request - Marketplace (Offchain)

**Purpose**: Send request to offchain mech via HTTP

**Prerequisites**:
- Running offchain mech server
- `MECHX_MECH_OFFCHAIN_URL` environment variable set

**Command**:
```bash
export MECHX_MECH_OFFCHAIN_URL='http://localhost:8000/'

mechx --client-mode request \
  --prompts "Test offchain request" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-offchain true \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
...
Sending offchain request to http://localhost:8000/...
...
```

**Success Criteria**:
- ✅ Request sent to offchain URL
- ✅ Response received via HTTP (no blockchain polling)

---

### 6. Deposit Native (Client Mode)

**Purpose**: Deposit native tokens for prepaid marketplace requests using client mode (EOA)

**Prerequisites**:
- Funded wallet with native tokens

**Command**:
```bash
# Deposit 0.01 xDAI (18 decimals = 10000000000000000 wei)
mechx --client-mode deposit native \
  10000000000000000 \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
Running deposit native with agent_mode=False
Depositing native balance...
  - Transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Deposit successful!
```

**Success Criteria**:
- ✅ Transaction succeeds with "0x" prefix in URL
- ✅ Balance updated in BalanceTracker contract
- ✅ Can verify balance on block explorer

**Verification**:
Check your prepaid balance on the blockchain explorer for the BalanceTrackerFixedPriceNative contract.

**Supported Chains**: gnosis, base, polygon, optimism

---

### 6b. Deposit Native (Agent Mode)

**Purpose**: Deposit native tokens via Safe multisig in agent mode

**Prerequisites**:
- Agent mode setup completed (run `setup`)
- Safe address funded with native tokens

**Command**:
```bash
# No --client-mode flag = uses agent mode
mechx deposit native \
  10000000000000000 \
  --chain-config gnosis
```

**Expected Output**:
```
Agent mode enabled
Running deposit native with agent_mode=True
Depositing native balance via Safe...
  - Safe transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Deposit successful!
```

**Success Criteria**:
- ✅ Transaction sent from Safe address (not EOA)
- ✅ Transaction succeeds with "0x" prefix in URL
- ✅ Balance updated for Safe address in BalanceTracker contract

**Supported Chains**: gnosis, base, polygon, optimism

---

### 7. Deposit Token (Client Mode)

**Purpose**: Deposit ERC20 tokens (OLAS or USDC) for prepaid marketplace requests using client mode (EOA)

**Prerequisites**:
- Wallet funded with OLAS or USDC tokens

**Command**:
```bash
# Deposit 1 OLAS (18 decimals = 1000000000000000000 wei)
mechx --client-mode deposit token \
  1000000000000000000 \
  --chain-config gnosis \
  --token-type olas \
  --key ethereum_private_key.txt

# OR deposit 1 USDC (6 decimals = 1000000 smallest unit)
mechx --client-mode deposit token \
  1000000 \
  --chain-config base \
  --token-type usdc \
  --key ethereum_private_key.txt
```

**Note**: The `--token-type` parameter is **required** and must be either `olas` or `usdc`.

**Expected Output**:
```
Running deposit token with agent_mode=False
Approving token for deposit...
  - Transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Depositing token balance...
  - Transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Deposit successful!
```

**Success Criteria**:
- ✅ Approval transaction succeeds
- ✅ Deposit transaction succeeds
- ✅ Both transaction URLs have "0x" prefix
- ✅ Balance updated in BalanceTracker contract

**Supported Chains**: gnosis, base, polygon, optimism

---

### 7b. Deposit Token (Agent Mode)

**Purpose**: Deposit ERC20 tokens (OLAS or USDC) via Safe multisig in agent mode

**Prerequisites**:
- Agent mode setup completed (run `setup`)
- Safe address funded with OLAS or USDC tokens

**Command**:
```bash
# No --client-mode flag = uses agent mode
# Deposit OLAS
mechx deposit token \
  1000000000000000000 \
  --chain-config gnosis \
  --token-type olas

# OR deposit USDC
mechx deposit token \
  1000000 \
  --chain-config base \
  --token-type usdc
```

**Note**: The `--token-type` parameter is **required** and must be either `olas` or `usdc`.

**Expected Output**:
```
Agent mode enabled
Running deposit token with agent_mode=True
Approving token for deposit via Safe...
  - Safe transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Depositing token balance via Safe...
  - Safe transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for transaction receipt...
Deposit successful!
```

**Success Criteria**:
- ✅ Both transactions sent from Safe address (not EOA)
- ✅ Approval transaction succeeds
- ✅ Deposit transaction succeeds
- ✅ Both transaction URLs have "0x" prefix
- ✅ Balance updated for Safe address in BalanceTracker contract

**Supported Chains**: gnosis, base, polygon, optimism

---

### 8. Purchase NVM Subscription (Client Mode)

**Purpose**: Purchase Nevermined subscription for subscription-based payments using client mode (EOA)

The subscription purchase involves a 3-transaction workflow:
1. **Balance Check**: Validates sufficient funds before purchase
2. **Token Approval** (Base only): Approves USDC for lock payment contract
3. **Create Agreement**: On-chain agreement creation with payment
4. **Fulfill Agreement**: Completes subscription activation

**Prerequisites**:
- Chain supports NVM (gnosis or base only)
- Funded wallet:
  - **Gnosis**: Native xDAI (approximately 0.1 xDAI for subscription + gas)
  - **Base**: USDC tokens (approximately $5-10 USDC for subscription) + native ETH for gas

**Command**:
```bash
# Gnosis (native xDAI payment)
mechx --client-mode subscription purchase \
  --chain-config gnosis \
  --key ethereum_private_key.txt

# Base (USDC token payment)
mechx --client-mode subscription purchase \
  --chain-config base \
  --key ethereum_private_key.txt
```

**Expected Output (Gnosis)**:
```
Running purchase nvm subscription with agent_mode=False
Checking <address> balance for purchasing subscription...
  - Native balance: 1000000000000000000 wei (1.0 xDAI)
  - Required: 100000000000000000 wei (0.1 xDAI)
  - Balance check passed ✓
Sender credits before purchase: 0
Agreement creation transaction: 0x5187fddd...
  - Waiting for transaction receipt...
  - Transaction URL: https://gnosisscan.io/tx/0x5187fddd...
Fulfillment transaction: 0xabc123...
  - Waiting for transaction receipt...
  - Transaction URL: https://gnosisscan.io/tx/0xabc123...
Sender credits after purchase: 100
Subscription purchased successfully!
Agreement ID: 0xdef456...
Agreement TX: 0x5187fddd...
Fulfillment TX: 0xabc123...
```

**Expected Output (Base)**:
```
Running purchase nvm subscription with agent_mode=False
Checking <address> balance for purchasing subscription...
  - USDC balance: 10000000 (10.0 USDC)
  - Required: 5000000 (5.0 USDC)
  - Balance check passed ✓
Sender credits before purchase: 0
Approving USDC token for lock payment contract...
  - Token approval transaction: 0x111222...
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0x111222...
Agreement creation transaction: 0x5187fddd...
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0x5187fddd...
Fulfillment transaction: 0xabc123...
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0xabc123...
Sender credits after purchase: 100
Subscription purchased successfully!
Agreement ID: 0xdef456...
Agreement TX: 0x5187fddd...
Fulfillment TX: 0xabc123...
```

**Success Criteria**:
- ✅ Balance check passes before transactions
- ✅ [Base only] Token approval transaction succeeds
- ✅ Agreement creation transaction succeeds
- ✅ Fulfillment transaction succeeds
- ✅ All transaction URLs include "0x" prefix
- ✅ Credits increased after purchase (before: 0, after: > 0)
- ✅ Agreement ID returned (64-character hex string)
- ✅ Can use subscription for NVM-based mech requests

**Verification**:
```bash
# Check subscription NFT balance on block explorer
# Should see NFT balance increased for your address
# Subscription ID and agreement ID can be used to verify on-chain
```

**Transaction Count**:
- **Gnosis**: 2 transactions (create agreement, fulfill)
- **Base**: 3 transactions (approve USDC, create agreement, fulfill)

**Troubleshooting**:
- If "Insufficient balance": Ensure wallet has enough native/USDC tokens
- If approval fails (Base): Check USDC token balance and allowances
- If timeout: Set reliable `MECHX_CHAIN_RPC` provider
- If agreement fails: Verify plan DID is valid for the chain

**Supported Chains**: gnosis (native xDAI), base (USDC) ONLY

---

### 8b. Purchase NVM Subscription (Agent Mode)

**Purpose**: Purchase Nevermined subscription via Safe multisig in agent mode

Agent mode uses Safe multisig for all transactions in the 3-transaction workflow:
1. **Balance Check**: Validates Safe has sufficient funds
2. **Token Approval** (Base only): Safe approves USDC for lock payment contract
3. **Create Agreement**: Safe creates on-chain agreement with payment
4. **Fulfill Agreement**: Safe completes subscription activation

**Prerequisites**:
- Agent mode setup completed (run `mechx setup --chain-config <chain>`)
- Chain supports NVM (gnosis or base only)
- Safe address funded:
  - **Gnosis**: Native xDAI (approximately 0.1 xDAI for subscription + gas)
  - **Base**: USDC tokens (approximately $5-10 USDC for subscription) + native ETH for gas

**Command**:
```bash
# No --client-mode flag = uses agent mode (Safe)
# Gnosis
mechx subscription purchase --chain-config gnosis

# Base
mechx subscription purchase --chain-config base
```

**Expected Output (Gnosis - Agent Mode)**:
```
Agent mode enabled
Running purchase nvm subscription with agent_mode=True
Checking <safe_address> balance for purchasing subscription...
  - Native balance: 1000000000000000000 wei (1.0 xDAI)
  - Required: 100000000000000000 wei (0.1 xDAI)
  - Balance check passed ✓
Sender credits before purchase: 0
Agreement creation transaction: 0x5187fddd...
  - Safe transaction sent from: 0x<safe_address>
  - Waiting for transaction receipt...
  - Transaction URL: https://gnosisscan.io/tx/0x5187fddd...
Fulfillment transaction: 0xabc123...
  - Safe transaction sent from: 0x<safe_address>
  - Waiting for transaction receipt...
  - Transaction URL: https://gnosisscan.io/tx/0xabc123...
Sender credits after purchase: 100
Subscription purchased successfully!
Agreement ID: 0xdef456...
Agreement TX: 0x5187fddd...
Fulfillment TX: 0xabc123...
```

**Expected Output (Base - Agent Mode)**:
```
Agent mode enabled
Running purchase nvm subscription with agent_mode=True
Checking <safe_address> balance for purchasing subscription...
  - USDC balance: 10000000 (10.0 USDC)
  - Required: 5000000 (5.0 USDC)
  - Balance check passed ✓
Sender credits before purchase: 0
Approving USDC token for lock payment contract...
  - Safe transaction sent from: 0x<safe_address>
  - Token approval transaction: 0x111222...
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0x111222...
Agreement creation transaction: 0x5187fddd...
  - Safe transaction sent from: 0x<safe_address>
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0x5187fddd...
Fulfillment transaction: 0xabc123...
  - Safe transaction sent from: 0x<safe_address>
  - Waiting for transaction receipt...
  - Transaction URL: https://basescan.org/tx/0xabc123...
Sender credits after purchase: 100
Subscription purchased successfully!
Agreement ID: 0xdef456...
Agreement TX: 0x5187fddd...
Fulfillment TX: 0xabc123...
```

**Success Criteria**:
- ✅ All transactions sent from Safe address (verify on block explorer)
- ✅ Balance check validates Safe address funds (not EOA)
- ✅ [Base only] Token approval transaction from Safe succeeds
- ✅ Agreement creation transaction from Safe succeeds
- ✅ Fulfillment transaction from Safe succeeds
- ✅ All transaction URLs include "0x" prefix
- ✅ Credits increased for Safe address (before: 0, after: > 0)
- ✅ Agreement ID returned (64-character hex string)
- ✅ Subscription NFT balance attributed to Safe address
- ✅ Safe nonce increments correctly for each transaction

**Verification**:
```bash
# On block explorer, verify:
# - All transactions show Safe address as sender
# - Safe nonce sequence is correct (increments for each tx)
# - Subscription NFT balance attributed to Safe address
# - Agreement ID matches on-chain data
```

**Transaction Count**:
- **Gnosis**: 2 Safe transactions (create agreement, fulfill)
- **Base**: 3 Safe transactions (approve USDC, create agreement, fulfill)

**Important Notes**:
- All transactions must be executed by the Safe, not the EOA that owns the Safe
- Safe must have sufficient balance for subscription payment + gas fees
- Subscription NFT balance is tracked for the Safe address, not the EOA
- When making requests with the subscription, use the Safe as the requester address

**Troubleshooting**:
- If "Setup required": Run `mechx setup --chain-config <chain>` first
- If "Insufficient balance": Fund the Safe address, not the EOA
- If Safe nonce issues: Check Safe's pending transaction queue
- If approval fails (Base): Ensure Safe has USDC balance, not just EOA

**Supported Chains**: gnosis (native xDAI), base (USDC) ONLY

---

### 9. List Marketplace Mechs

**Purpose**: Query subgraph for marketplace mechs with most deliveries (top 20)

**Prerequisites**:
- `MECHX_SUBGRAPH_URL` environment variable set

**Command**:
```bash
export MECHX_SUBGRAPH_URL='https://api.studio.thegraph.com/query/57238/mech-marketplace-gnosis/version/latest'

mechx mech list --chain-config gnosis
```

**Expected Output**:
```
+-------------+-----------+------------------------------------------+------------------+------------------------------------------------+
| AI Agent Id | Mech Type | Mech Address                             | Total Deliveries | Metadata Link                                  |
+-------------+-----------+------------------------------------------+------------------+------------------------------------------------+
| 1           | Native    | 0x77af31De935740567Cf4fF1986D04B2c964A786a | 1234             | https://gateway.autonolas.tech/ipfs/f01701220... |
| 2           | Token     | 0x4554fE75c1f8D614Fc86014Fef4c99D1E44e39fAE | 567              | https://gateway.autonolas.tech/ipfs/f01701220... |
+-------------+-----------+------------------------------------------+------------------+------------------------------------------------+
```

**Success Criteria**:
- ✅ Table displays with multiple mechs
- ✅ Metadata links are accessible
- ✅ Service IDs are correct

**Note**: Requires valid subgraph URL - not included in default config

---

### 10. Tools for Marketplace Mech

**Purpose**: List tools available for a marketplace mech

**Command**:
```bash
mechx tool list 1 --chain-config gnosis
```

**Expected Output**:
```
+---------------------------------+------------------------+
| Tool Name                       | Unique Identifier      |
+---------------------------------+------------------------+
| openai-gpt-4o-2024-05-13        | 1-openai-gpt-4o-...    |
| claude-3-5-sonnet-20241022      | 1-claude-3-5-sonnet... |
+---------------------------------+------------------------+
```

**Success Criteria**:
- ✅ Tools listed for service ID
- ✅ Unique identifiers follow "service_id-tool_name" format

**Note**: Use service ID (not agent ID) for marketplace mechs

---

### 11. Tool Description for Marketplace Mech

**Purpose**: Get description of a marketplace mech tool

**Command**:
```bash
mechx tool describe 1-openai-gpt-4o-2024-05-13 --chain-config gnosis
```

**Expected Output**:
```
Description for tool 1-openai-gpt-4o-2024-05-13: Uses OpenAI's GPT-4o model to generate text responses.
```

**Success Criteria**:
- ✅ Description returned
- ✅ No errors

---

### 12. Tool I/O Schema for Marketplace Mech

**Purpose**: Get I/O schema for a marketplace mech tool

**Command**:
```bash
mechx tool schema 1-openai-gpt-4o-2024-05-13 --chain-config gnosis
```

**Expected Output**:
```
Tool Details:
[Table showing tool name and description]

Input Schema:
[Table showing input fields]

Output Schema:
[Table showing output fields]
```

**Success Criteria**:
- ✅ All three tables displayed
- ✅ Schema information complete

---

### 13. Prompt to IPFS

**Purpose**: Upload prompt and tool metadata to IPFS

**Command**:
```bash
mechx ipfs upload-prompt "What is AI?" "openai-gpt-4o-2024-05-13"
```

**Expected Output**:
```
Visit url: https://gateway.autonolas.tech/ipfs/f01701220abc123...
Hash for Request method: 0xdef456...
```

**Success Criteria**:
- ✅ IPFS URL accessible
- ✅ Hash includes "0x" prefix for request method
- ✅ Metadata retrievable from IPFS gateway

**Verification**:
```bash
# Visit the URL in a browser
# Should show JSON with prompt, tool, and nonce
```

---

### 14. Push to IPFS

**Purpose**: Upload any file to IPFS

**Command**:
```bash
# Create a test file
echo '{"test": "data"}' > test.json

mechx ipfs upload test.json
```

**Expected Output**:
```
IPFS file hash v1: bafybeiabc123...
IPFS file hash v1 hex: f01701220def456...
```

**Success Criteria**:
- ✅ Both hash formats returned
- ✅ File retrievable from IPFS gateway

---

### 15. To PNG

**Purpose**: Convert Stability AI diffusion model output from IPFS to PNG

**Prerequisites**:
- Valid IPFS hash from a diffusion model output

**Command**:
```bash
mechx ipfs to-png <ipfs_hash> output.png <request_id>
```

**Expected Output**:
```
PNG file saved to: output.png
```

**Success Criteria**:
- ✅ PNG file created
- ✅ Image viewable

**Note**: This is specifically for Stability AI diffusion model outputs

---

## Common Testing Scenarios

### Scenario 1: End-to-End Marketplace Request (Client Mode)

**Goal**: Test complete workflow from setup to response

**Steps**:
1. Set environment variables
2. Fund test wallet with 0.1 xDAI
3. Send marketplace request
4. Verify response received
5. Check transaction on block explorer

**Commands**:
```bash
export MECHX_CHAIN_RPC='https://rpc.gnosischain.com'

mechx --client-mode request \
  --prompts "What is the current time in UTC?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Duration**: 30-120 seconds

---

### Scenario 2: Agent Mode with Prepaid Balance

**Goal**: Test agent mode setup and prepaid workflow using Safe multisig

**Steps**:
1. Run `setup` to configure Safe
2. Fund Safe address with native tokens
3. Deposit native tokens to prepaid balance (via Safe)
4. Send prepaid marketplace request (via Safe)
5. Verify balance deducted from Safe's prepaid account

**Commands**:
```bash
# 1. Setup agent mode (creates Safe)
mechx setup --chain-config gnosis
# Note the Safe address from the output

# 2. Fund the Safe address with native tokens (manual step using your wallet)

# 3. Deposit via Safe (NO --client-mode flag = agent mode)
mechx deposit native 10000000000000000 --chain-config gnosis

# 4. Send prepaid request via Safe (NO --client-mode flag = agent mode)
mechx request \
  --prompts "Test prepaid request" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-prepaid true \
  --chain-config gnosis

# 5. Verify on block explorer that transactions came from Safe address
```

**Important**: All commands without `--client-mode` flag will use agent mode (Safe) after setup is run.

---

### Scenario 3: Comprehensive Agent Mode Testing

**Goal**: Test all transaction commands in agent mode (Safe multisig)

**Prerequisites**:
- Agent mode setup completed
- Safe address funded with native tokens and OLAS tokens

**Test Coverage**:
- [ ] Native payment marketplace request via Safe
- [ ] Token payment marketplace request via Safe
- [ ] Prepaid marketplace request via Safe
- [ ] Native deposit via Safe
- [ ] Token deposit via Safe
- [ ] NVM subscription purchase via Safe (gnosis/base only)

**Commands**:
```bash
# Verify agent mode is enabled
mechx --version  # Should show agent mode config

# Test 1: Native payment request (agent mode)
mechx request \
  --prompts "Agent mode native payment test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis

# Test 2: Native deposit (agent mode)
mechx deposit native 10000000000000000 --chain-config gnosis

# Test 3: Token deposit (agent mode)
mechx deposit token 1000000000000000000 --chain-config gnosis

# Test 4: Prepaid request (agent mode)
mechx request \
  --prompts "Agent mode prepaid test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-prepaid true \
  --chain-config gnosis

# Test 5: Token payment request (agent mode)
mechx request \
  --prompts "Agent mode token payment test" \
  --priority-mech 0x4554fE75c1f8D614Fc8614Fef4c99D1E44e39fAE \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis

# Test 6: NVM subscription (agent mode - gnosis/base only)
mechx subscription purchase --chain-config gnosis
```

**Success Criteria**:
- ✅ All transactions sent from Safe address (verify on block explorer)
- ✅ All transaction URLs include "0x" prefix
- ✅ Safe nonce increments correctly for each transaction
- ✅ All operations succeed without errors
- ✅ Balances tracked correctly for Safe address

**Verification**:
```bash
# On block explorer, verify:
# - All transactions show Safe address as sender
# - Safe nonce sequence is correct
# - Prepaid balances attributed to Safe address
```

---

### Scenario 4: Multi-Chain Testing

**Goal**: Verify functionality across different chains

**Chains to Test**: gnosis, base, polygon, optimism

**Test per Chain**:
- [ ] Interact command works
- [ ] Deposit native works
- [ ] Deposit token works
- [ ] Transaction URLs have "0x" prefix
- [ ] All RPC calls succeed

**Example for Base**:
```bash
export MECHX_CHAIN_RPC='https://mainnet.base.org'

mechx --client-mode request \
  --prompts "Hello from Base" \
  --priority-mech <base-mech-address> \
  --tools <tool-name> \
  --chain-config base \
  --key ethereum_private_key.txt
```

---

## Verification Checklist

After running tests, verify:

### Transaction Hashes
- [ ] All transaction URLs include "0x" prefix
- [ ] Transaction hashes are 66 characters (0x + 64 hex chars)
- [ ] Transactions visible on block explorer

### IPFS Hashes
- [ ] IPFS URLs are accessible
- [ ] Metadata contains correct prompt/tool
- [ ] Response data is valid JSON

### Balances
- [ ] Wallet balance decreased correctly
- [ ] Prepaid balance tracking works
- [ ] No unexpected gas costs

### Error Handling
- [ ] Clear error messages for missing env vars
- [ ] Helpful suggestions for common errors
- [ ] No raw Python tracebacks shown

### Performance
- [ ] Requests complete in reasonable time (< 2 minutes)
- [ ] No timeout errors with reliable RPC
- [ ] WebSocket connections stable (legacy mechs)

---

## Troubleshooting Guide

### Issue: "Timeout while waiting for transaction receipt"

**Cause**: Slow or rate-limited RPC endpoint

**Solution**:
```bash
# Use a reliable RPC provider
export MECHX_CHAIN_RPC='https://rpc.ankr.com/gnosis'
```

### Issue: Transaction hash missing "0x"

**Cause**: Outdated test - should be fixed in latest version

**Solution**: Update to latest mech-client version

### Issue: "Chain does not support marketplace deposits"

**Cause**: Chain doesn't have marketplace contract

**Solution**: Use supported chains (gnosis, base, polygon, optimism)

### Issue: "MECHX_SUBGRAPH_URL is required"

**Cause**: Subgraph URL not set for `mech list` command

**Solution**:
```bash
export MECHX_SUBGRAPH_URL='https://api.studio.thegraph.com/query/.../version/latest'
```

### Issue: "Permission denied" reading private key

**Cause**: File permissions too open

**Solution**:
```bash
chmod 600 ethereum_private_key.txt
```

---

## Testing Best Practices

1. **Use Test Wallets**: Never use your main wallet for testing
2. **Small Amounts**: Test with minimal token amounts
3. **Document Results**: Keep notes on what works/fails
4. **Test Incrementally**: Start with simple commands, move to complex
5. **Verify on Explorer**: Always check transactions on block explorer
6. **Clean Environment**: Test with fresh environment variables
7. **Network Selection**: Use testnets when available
8. **Log Everything**: Save command outputs for debugging

---

## Test Results Template

Use this template to document your testing:

```markdown
## Test Session: [Date]

**Tester**: [Name]
**Version**: [mech-client version]
**Chain**: [gnosis/base/polygon/optimism]

### Tests Completed

| Command | Mode | Status | Notes |
|---------|------|--------|-------|
| setup | N/A | ✅ / ❌ | |
| request (marketplace - native) | client | ✅ / ❌ | |
| request (marketplace - native) | agent | ✅ / ❌ | |
| request (marketplace - token) | client | ✅ / ❌ | |
| request (marketplace - token) | agent | ✅ / ❌ | |
| request (marketplace - prepaid) | client | ✅ / ❌ | |
| request (marketplace - prepaid) | agent | ✅ / ❌ | |
| deposit native | client | ✅ / ❌ | |
| deposit native | agent | ✅ / ❌ | |
| deposit token | client | ✅ / ❌ | |
| deposit token | agent | ✅ / ❌ | |
| subscription purchase | client | ✅ / ❌ | |
| subscription purchase | agent | ✅ / ❌ | |
| mech list | N/A | ✅ / ❌ | |
| tool list | N/A | ✅ / ❌ | |
| ipfs upload-prompt | N/A | ✅ / ❌ | |

### Issues Found

1. [Issue description]
   - Command: [command that failed]
   - Error: [error message]
   - Expected: [what should happen]
   - Actual: [what happened]

### Environment

- OS: [macOS/Linux/Windows]
- Python: [version]
- RPC Provider: [provider used]
- Wallet Balance: [before/after]

### Recommendations

[Any suggestions for improvements]
```

---

## Quick Reference

### Minimum Test Suite (20 minutes)

Quick smoke test for releases:

```bash
# 1. Version check
mechx --version

# 2. Help text
mechx --help

# 3. Simple marketplace request (client mode)
mechx --client-mode request \
  --prompts "Test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt

# 4. List tools
mechx tool list 1 --chain-config gnosis

# 5. IPFS upload
mechx ipfs upload-prompt "Test" "test-tool"
```

### Full Test Suite (2-3 hours)

Complete testing of all features:

1. Run all 15 command tests
2. Test both agent mode and client mode
3. Test all supported chains
4. Test error scenarios
5. Verify all transaction URLs
6. Document all results

---

## Support

If you encounter issues during testing:

1. Check the [Common Issues](https://github.com/valory-xyz/mech-client/blob/main/CLAUDE.md#common-issues--solutions) section in CLAUDE.md
2. Review error messages for actionable solutions
3. Verify environment variables are set correctly
4. Check RPC provider status
5. Report bugs at: https://github.com/valory-xyz/mech-client/issues

---

**Last Updated**: 2026-02-06
**Maintained By**: Valory AG
**License**: Apache 2.0

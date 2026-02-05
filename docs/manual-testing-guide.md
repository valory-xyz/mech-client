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
   export MECHX_WSS_ENDPOINT='wss://rpc.gnosischain.com/wss'
   export MECHX_SUBGRAPH_URL='https://your-subgraph-url'  # For fetch-mm-mechs-info
   export MECHX_MECH_OFFCHAIN_URL='http://localhost:8000/'  # For offchain testing
   ```

4. **Funded Wallet**
   - Ensure your test wallet has native tokens (xDAI on Gnosis, ETH on other chains)
   - For token payments: ensure you have OLAS or USDC tokens
   - **Never use your main wallet for testing!**

---

## Testing Checklist

Use this checklist to track your testing progress:

- [ ] setup-agent-mode
- [ ] interact (marketplace - native payment - client mode)
- [ ] interact (marketplace - native payment - agent mode)
- [ ] interact (marketplace - token payment - client mode)
- [ ] interact (marketplace - token payment - agent mode)
- [ ] interact (marketplace - prepaid - client mode)
- [ ] interact (marketplace - prepaid - agent mode)
- [ ] interact (marketplace - offchain)
- [ ] interact (legacy mech)
- [ ] deposit-native (client mode)
- [ ] deposit-native (agent mode)
- [ ] deposit-token (client mode)
- [ ] deposit-token (agent mode)
- [ ] purchase-nvm-subscription (client mode)
- [ ] purchase-nvm-subscription (agent mode)
- [ ] fetch-mm-mechs-info
- [ ] tools-for-agents
- [ ] tool-description (legacy)
- [ ] tool-io-schema (legacy)
- [ ] tools-for-marketplace-mech
- [ ] tool-description-for-marketplace-mech
- [ ] tool-io-schema-for-marketplace-mech
- [ ] prompt-to-ipfs
- [ ] push-to-ipfs
- [ ] to-png

---

## Command Tests

### 1. Setup Agent Mode

**Purpose**: Configure agent mode for Safe-based transactions

**Command**:
```bash
mechx setup-agent-mode --chain-config gnosis
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

### 2. Interact - Marketplace (Native Payment)

**Purpose**: Send a request to a marketplace mech with per-request native payment

**Prerequisites**:
- Funded wallet with native tokens (minimum ~0.02 xDAI)

**Command**:
```bash
# Client mode (simple)
mechx --client-mode interact \
  --prompts "What is the weather in Paris today?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt

# OR Agent mode (if setup-agent-mode was run)
mechx interact \
  --prompts "What is the weather in Paris today?" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis
```

**Expected Output**:
```
Agent mode enabled
Running interact with agent_mode=True
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

### 3. Interact - Marketplace (Token Payment)

**Purpose**: Send a request with OLAS token payment

**Prerequisites**:
- Wallet funded with OLAS tokens
- Token approval may be required (automatic)

**Command**:
```bash
mechx --client-mode interact \
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

### 4. Interact - Marketplace (Prepaid)

**Purpose**: Use prepaid balance for marketplace requests

**Prerequisites**:
- Prepaid deposit made (see deposit-native/deposit-token tests)

**Command**:
```bash
mechx --client-mode interact \
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

### 5. Interact - Marketplace (Offchain)

**Purpose**: Send request to offchain mech via HTTP

**Prerequisites**:
- Running offchain mech server
- `MECHX_MECH_OFFCHAIN_URL` environment variable set

**Command**:
```bash
export MECHX_MECH_OFFCHAIN_URL='http://localhost:8000/'

mechx --client-mode interact \
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

### 6. Interact - Legacy Mech

**Purpose**: Interact with legacy (non-marketplace) mech

**Prerequisites**:
- `MECHX_WSS_ENDPOINT` environment variable set

**Command**:
```bash
export MECHX_WSS_ENDPOINT='wss://rpc.gnosischain.com/wss'

mechx --client-mode interact \
  --prompts "What is the capital of France?" \
  --agent-id 6 \
  --tool openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
...
Legacy mech interaction mode
  - Transaction sent: https://gnosisscan.io/tx/0x...
  - Waiting for response via WebSocket...
  - Data arrived: ...
...
```

**Success Criteria**:
- ✅ WebSocket connection established
- ✅ Request and Deliver events received
- ✅ Response data retrieved

**Note**: Only supports single prompts (no batch requests)

---

### 7. Deposit Native (Client Mode)

**Purpose**: Deposit native tokens for prepaid marketplace requests using client mode (EOA)

**Prerequisites**:
- Funded wallet with native tokens

**Command**:
```bash
# Deposit 0.01 xDAI (18 decimals = 10000000000000000 wei)
mechx --client-mode deposit-native \
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

### 7b. Deposit Native (Agent Mode)

**Purpose**: Deposit native tokens via Safe multisig in agent mode

**Prerequisites**:
- Agent mode setup completed (run `setup-agent-mode`)
- Safe address funded with native tokens

**Command**:
```bash
# No --client-mode flag = uses agent mode
mechx deposit-native \
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

### 8. Deposit Token (Client Mode)

**Purpose**: Deposit OLAS tokens for prepaid marketplace requests using client mode (EOA)

**Prerequisites**:
- Wallet funded with OLAS tokens

**Command**:
```bash
# Deposit 1 OLAS (18 decimals = 1000000000000000000 wei)
mechx --client-mode deposit-token \
  1000000000000000000 \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

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

### 8b. Deposit Token (Agent Mode)

**Purpose**: Deposit OLAS tokens via Safe multisig in agent mode

**Prerequisites**:
- Agent mode setup completed (run `setup-agent-mode`)
- Safe address funded with OLAS tokens

**Command**:
```bash
# No --client-mode flag = uses agent mode
mechx deposit-token \
  1000000000000000000 \
  --chain-config gnosis
```

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

### 9. Purchase NVM Subscription (Client Mode)

**Purpose**: Purchase Nevermined subscription for subscription-based payments using client mode (EOA)

**Prerequisites**:
- Chain supports NVM (gnosis or base only)
- Funded wallet

**Command**:
```bash
mechx --client-mode purchase-nvm-subscription \
  --chain-config gnosis \
  --key ethereum_private_key.txt
```

**Expected Output**:
```
Running purchase nvm subscription with agent_mode=False
Purchasing NVM subscription...
  - Transaction sent: https://gnosisscan.io/tx/0x...
Subscription purchased successfully!
```

**Success Criteria**:
- ✅ Transaction succeeds
- ✅ Subscription ID returned
- ✅ Can use subscription for NVM-based mech requests

**Supported Chains**: gnosis, base (ONLY)

---

### 9b. Purchase NVM Subscription (Agent Mode)

**Purpose**: Purchase Nevermined subscription via Safe multisig in agent mode

**Prerequisites**:
- Agent mode setup completed (run `setup-agent-mode`)
- Chain supports NVM (gnosis or base only)
- Safe address funded

**Command**:
```bash
# No --client-mode flag = uses agent mode
mechx purchase-nvm-subscription \
  --chain-config gnosis
```

**Expected Output**:
```
Agent mode enabled
Running purchase nvm subscription with agent_mode=True
Purchasing NVM subscription via Safe...
  - Safe transaction sent: https://gnosisscan.io/tx/0x...
Subscription purchased successfully!
```

**Success Criteria**:
- ✅ Transaction sent from Safe address (not EOA)
- ✅ Transaction succeeds
- ✅ Subscription ID returned for Safe address
- ✅ Can use subscription for NVM-based mech requests

**Supported Chains**: gnosis, base (ONLY)

---

### 10. Fetch Marketplace Mechs Info

**Purpose**: Query subgraph for marketplace mechs with most deliveries

**Prerequisites**:
- `MECHX_SUBGRAPH_URL` environment variable set

**Command**:
```bash
export MECHX_SUBGRAPH_URL='https://api.studio.thegraph.com/query/57238/mech-marketplace-gnosis/version/latest'

mechx fetch-mm-mechs-info --chain-config gnosis
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

### 11. Tools for Agents (Legacy)

**Purpose**: List tools available for legacy mechs

**Command**:
```bash
# List all agents and their tools
mechx tools-for-agents --chain-config gnosis

# List tools for specific agent
mechx tools-for-agents --agent-id 6 --chain-config gnosis
```

**Expected Output** (specific agent):
```
+---------------------------------+------------------------+---------------------------+
| Tool Name                       | Unique Identifier      | Mech Marketplace Support  |
+---------------------------------+------------------------+---------------------------+
| openai-gpt-4o-2024-05-13        | 6-openai-gpt-4o-...    | ✓                         |
| prediction-online-sum-url-...   | 6-prediction-online... | ✓                         |
+---------------------------------+------------------------+---------------------------+
```

**Success Criteria**:
- ✅ Tools listed for agent
- ✅ Unique identifiers follow "agent_id-tool_name" format
- ✅ Marketplace support indicated

---

### 12. Tool Description (Legacy)

**Purpose**: Get description of a specific legacy mech tool

**Command**:
```bash
mechx tool-description 6-openai-gpt-4o-2024-05-13 --chain-config gnosis
```

**Expected Output**:
```
Description for tool 6-openai-gpt-4o-2024-05-13: Uses OpenAI's GPT-4o model to generate text responses based on prompts.
```

**Success Criteria**:
- ✅ Description returned
- ✅ No errors

**Note**: Tool ID format is "agent_id-tool_name"

---

### 13. Tool I/O Schema (Legacy)

**Purpose**: Get input/output schema for a legacy mech tool

**Command**:
```bash
mechx tool-io-schema 6-openai-gpt-4o-2024-05-13 --chain-config gnosis
```

**Expected Output**:
```
Tool Details:
+---------------------------+--------------------------------------------------+
| Tool Name                 | Tool Description                                  |
+---------------------------+--------------------------------------------------+
| openai-gpt-4o-2024-05-13  | Uses OpenAI's GPT-4o model...                    |
+---------------------------+--------------------------------------------------+

Input Schema:
+--------+------------------+
| Field  | Value            |
+--------+------------------+
| type   | string           |
| format | prompt           |
+--------+------------------+

Output Schema:
+---------+--------+------------------+
| Field   | Type   | Description      |
+---------+--------+------------------+
| result  | string | Generated text   |
+---------+--------+------------------+
```

**Success Criteria**:
- ✅ Tool details displayed
- ✅ Input schema shown
- ✅ Output schema shown

---

### 14. Tools for Marketplace Mech

**Purpose**: List tools available for a marketplace mech

**Command**:
```bash
mechx tools-for-marketplace-mech 1 --chain-config gnosis
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

### 15. Tool Description for Marketplace Mech

**Purpose**: Get description of a marketplace mech tool

**Command**:
```bash
mechx tool-description-for-marketplace-mech 1-openai-gpt-4o-2024-05-13 --chain-config gnosis
```

**Expected Output**:
```
Description for tool 1-openai-gpt-4o-2024-05-13: Uses OpenAI's GPT-4o model to generate text responses.
```

**Success Criteria**:
- ✅ Description returned
- ✅ No errors

---

### 16. Tool I/O Schema for Marketplace Mech

**Purpose**: Get I/O schema for a marketplace mech tool

**Command**:
```bash
mechx tool-io-schema-for-marketplace-mech 1-openai-gpt-4o-2024-05-13 --chain-config gnosis
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

### 17. Prompt to IPFS

**Purpose**: Upload prompt and tool metadata to IPFS

**Command**:
```bash
mechx prompt-to-ipfs "What is AI?" "openai-gpt-4o-2024-05-13"
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

### 18. Push to IPFS

**Purpose**: Upload any file to IPFS

**Command**:
```bash
# Create a test file
echo '{"test": "data"}' > test.json

mechx push-to-ipfs test.json
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

### 19. To PNG

**Purpose**: Convert Stability AI diffusion model output from IPFS to PNG

**Prerequisites**:
- Valid IPFS hash from a diffusion model output

**Command**:
```bash
mechx to-png <ipfs_hash> output.png <request_id>
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

mechx --client-mode interact \
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
1. Run `setup-agent-mode` to configure Safe
2. Fund Safe address with native tokens
3. Deposit native tokens to prepaid balance (via Safe)
4. Send prepaid marketplace request (via Safe)
5. Verify balance deducted from Safe's prepaid account

**Commands**:
```bash
# 1. Setup agent mode (creates Safe)
mechx setup-agent-mode --chain-config gnosis
# Note the Safe address from the output

# 2. Fund the Safe address with native tokens (manual step using your wallet)

# 3. Deposit via Safe (NO --client-mode flag = agent mode)
mechx deposit-native 10000000000000000 --chain-config gnosis

# 4. Send prepaid request via Safe (NO --client-mode flag = agent mode)
mechx interact \
  --prompts "Test prepaid request" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-prepaid true \
  --chain-config gnosis

# 5. Verify on block explorer that transactions came from Safe address
```

**Important**: All commands without `--client-mode` flag will use agent mode (Safe) after setup-agent-mode is run.

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
mechx interact \
  --prompts "Agent mode native payment test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis

# Test 2: Native deposit (agent mode)
mechx deposit-native 10000000000000000 --chain-config gnosis

# Test 3: Token deposit (agent mode)
mechx deposit-token 1000000000000000000 --chain-config gnosis

# Test 4: Prepaid request (agent mode)
mechx interact \
  --prompts "Agent mode prepaid test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --use-prepaid true \
  --chain-config gnosis

# Test 5: Token payment request (agent mode)
mechx interact \
  --prompts "Agent mode token payment test" \
  --priority-mech 0x4554fE75c1f8D614Fc8614Fef4c99D1E44e39fAE \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis

# Test 6: NVM subscription (agent mode - gnosis/base only)
mechx purchase-nvm-subscription --chain-config gnosis
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

mechx --client-mode interact \
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

**Cause**: Subgraph URL not set for fetch-mm-mechs-info

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

### Issue: WebSocket connection closed (legacy mechs)

**Cause**: WSS endpoint unavailable

**Solution**:
```bash
export MECHX_WSS_ENDPOINT='wss://rpc.gnosischain.com/wss'
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
| setup-agent-mode | N/A | ✅ / ❌ | |
| interact (marketplace - native) | client | ✅ / ❌ | |
| interact (marketplace - native) | agent | ✅ / ❌ | |
| interact (marketplace - token) | client | ✅ / ❌ | |
| interact (marketplace - token) | agent | ✅ / ❌ | |
| interact (marketplace - prepaid) | client | ✅ / ❌ | |
| interact (marketplace - prepaid) | agent | ✅ / ❌ | |
| interact (legacy) | client | ✅ / ❌ | |
| deposit-native | client | ✅ / ❌ | |
| deposit-native | agent | ✅ / ❌ | |
| deposit-token | client | ✅ / ❌ | |
| deposit-token | agent | ✅ / ❌ | |
| purchase-nvm-subscription | client | ✅ / ❌ | |
| purchase-nvm-subscription | agent | ✅ / ❌ | |
| fetch-mm-mechs-info | N/A | ✅ / ❌ | |
| tools-for-agents | N/A | ✅ / ❌ | |
| prompt-to-ipfs | N/A | ✅ / ❌ | |

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
mechx --client-mode interact \
  --prompts "Test" \
  --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a \
  --tools openai-gpt-4o-2024-05-13 \
  --chain-config gnosis \
  --key ethereum_private_key.txt

# 4. List tools
mechx tools-for-marketplace-mech 1 --chain-config gnosis

# 5. IPFS upload
mechx prompt-to-ipfs "Test" "test-tool"
```

### Full Test Suite (2-3 hours)

Complete testing of all features:

1. Run all 19 command tests
2. Test both agent mode and client mode
3. Test all supported chains
4. Test error scenarios
5. Verify all transaction URLs
6. Document all results

---

## Support

If you encounter issues during testing:

1. Check the [Common Issues](../CLAUDE.md#common-issues--solutions) section in CLAUDE.md
2. Review error messages for actionable solutions
3. Verify environment variables are set correctly
4. Check RPC provider status
5. Report bugs at: https://github.com/valory-xyz/mech-client/issues

---

**Last Updated**: 2026-02-05
**Maintained By**: Valory AG
**License**: Apache 2.0

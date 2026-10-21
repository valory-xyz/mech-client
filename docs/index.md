## **Overview**

This guide contains practical guidelines for interacting with Mechs.
A requester - whether it is an agent or an application - can choose between two methods for sending service requests:

- On-chain: The request is sent to the Mech contract. For Mechs registered on the [Mech Marketplace](https://stack.olas.network/mech-tools-dev/#the-mech-marketplace), it is relayed via the Mech Marketplace.

- Off-chain: The request is sent directly to the Mech AI agent. The Mech then sends the result (or delivery) to the Mech contract, which is subsequently relayed by the Mech Marketplace if the Mech is registered there.

To send a request, follow these steps:

**1.** Choose a Mech, and check [who runs it](#who-runs-a-mech-and-how-it-has-behaved);

**2.** Make an on-chain deposit according to the Mech’s [payment model](https://stack.olas.network/mech-tools-dev/#payment-models).

**3.** Choose a method for sending the request (on-chain or off-chain).

**4.** Send the request.

Detailed instructions for each step are provided below.

## Setup

**Requirements**: [Python](https://www.python.org/) >=3.10, <3.12 (Python 3.10 or 3.11), [uv](https://docs.astral.sh/uv/)

**1.** Install mech-client:

```bash
pip install mech-client
```

**2.** Setting up an EOA ([Externally Owned Account](https://ethereum.org/en/developers/docs/accounts/)) account:

**a.** Install browser extension of Metamask and open it.

**b.** Click on the account icon, then select “Add account or hardware wallet”, then “Add a new Ethereum account”. Provide a name for the account and click “Add account”.

**c.** Select the newly created account. Open the top-right menu, click “Account details”, then click “Show private key”.

**d.** Copy this key in the file `ethereum_private_key.txt` in your project folder. Make sure the file contains only the private key, with no leading or trailing spaces, tabs, or newlines.

## Agent Mode and Client Mode

There are two modes for on-chain interactions:

-   **Agent mode** (default, recommended): Registers your on-chain interactions as an agent on the Olas protocol via a Safe multisig. This allows agent-to-agent (A2A) activity to be reflected on the client.

-   **Client mode**: Simple on-chain interactions using an EOA (Externally Owned Account). Use `--client-mode` flag before commands:

    ```bash
    mechx --client-mode <rest of the cli command>
    ```

### Setting up agent mode

For better reliability, it is recommended to use a stable third-party RPC provider.

```bash
mechx setup --chain-config <chain_config>
```

Run `setup` for each chain you interact with, and ensure your `.env` file has the correct RPC endpoint.

## Supported Chains

**Supported chains:** `gnosis`, `base`, `polygon`, `optimism`, `robinhood`

All commands require `--chain-config` with one of these five chain names.

| Chain | Marketplace | Agent Mode | Native Payment | NVM Subscriptions | OLAS Payments | USDC Payments |
|-------|-------------|------------|----------------|-------------------|---------------|---------------|
| Gnosis | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Base | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Polygon | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Optimism | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Robinhood | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ (USDG) |

**Key:**
- **Marketplace**: All supported chains have marketplace contracts deployed.
- **Agent Mode**: Gnosis, Base, Polygon, Optimism and Robinhood support on-chain agent registration via `setup`.
- **Native Payment**: Chains supporting `deposit native` command for prepaid native token deposits.
- **NVM Subscriptions**: Chains supporting `subscription purchase` command for Nevermined subscription-based payments (Gnosis, Base only).
- **OLAS/USDC Payments**: Chains supporting `deposit token` command with OLAS or USDC tokens. On Robinhood the USDC payment type uses USDG, so `--token-type usdc` deposits USDG.

**Important Notes:**
- The `mech list` command works on all supported chains with default subgraph URLs provided (on Robinhood, the marketplace squid). The `MECHX_SUBGRAPH_URL` environment variable is optional and only needed to override defaults.
- For other marketplace commands (`request`, deposits), subgraph is not required.

## 1. How to Send a request to a Mech (registered on the Mech MarketPlace)

To send a request to a Mech that is accessible through the Mech Marketplace, first complete the [setup](#setup), then follow the [instructions](#1-2-in-terminal) below.

You will need to [choose a Mech](#1-1-choosing-a-mech), and then select one of the following methods to send a request:
- Via the [terminal](#1-2-in-terminal)
- Using a Python [script](#1-3-script-for-automatizing-request-sending)

Follow the instructions in the corresponding section.


### 1. 1. Choosing a Mech

- Use the command mechx in terminal, which is structured as follows.
```bash
mechx mech list --chain-config <chain-config>
```

Replace `<chain-config>` by the chosen network. Supported marketplace chains: gnosis, base, polygon, optimism, robinhood.

**Note**: Default subgraph URLs are provided for all supported chains (on Robinhood, the marketplace squid). You can optionally override the default:
```bash
export MECHX_SUBGRAPH_URL=<your-custom-subgraph-url>
```
```bash
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
| AI Agent Id  | Mech Type          | Mech Address                               |   Total Deliveries | Metadata Link                                                                                                 |
+==============+====================+============================================+====================+===============================================================================================================+
|         2182 | Fixed Price Native | 0xc05e7412439bd7e91730a6880e18d5d5873f632c |              41246 | https://gateway.autonolas.tech/ipfs/f01701220157d3b106831e2713b86af1b52af76a3ef28c52ae0853e9638180902ebee41d4 |
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
|         2235 | Fixed Price Native | 0xb3c6319962484602b00d5587e965946890b82101 |              10127 | https://gateway.autonolas.tech/ipfs/f01701220157d3b106831e2713b86af1b52af76a3ef28c52ae0853e9638180902ebee41d4 |
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
|         2198 | Fixed Price Native | 0x601024e27f1c67b28209e24272ced8a31fc8151f |               5714 | https://gateway.autonolas.tech/ipfs/f01701220157d3b106831e2713b86af1b52af76a3ef28c52ae0853e9638180902ebee41d4 |
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
|         1722 | Fixed Price Token  | 0x13f36b1a516290b7563b1de574a02ebeb48926a1 |                399 | https://gateway.autonolas.tech/ipfs/f01701220157d3b106831e2713b86af1b52af76a3ef28c52ae0853e9638180902ebee41d4 |
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
|         2135 | Fixed Price Native | 0xbead38e4c4777341bb3fd44e8cd4d1ba1a7ad9d7 |                353 | https://gateway.autonolas.tech/ipfs/f01701220157d3b106831e2713b86af1b52af76a3ef28c52ae0853e9638180902ebee41d4 |
+--------------+--------------------+--------------------------------------------+--------------------+---------------------------------------------------------------------------------------------------------------+
```


#### Who runs a Mech, and how it has behaved

Before paying a Mech you can ask who runs it and what its record is:

```bash
mechx mech info --chain-config <chain-config> --address <mech-address>
```

The report is built from the Mech's published metadata and the chain, and printed as JSON. It fails closed: a metadata file that cannot be read gives no report, and anything not verified says so.

- **Operator**: the domain the operator named, and whether it is verified. Verified means `https://<domain>/.well-known/agent-registration.json` lists this Mech's ERC-8004 agent id. It shows that the Mech's metadata and the domain point at each other, nothing more: a domain owner can list a Mech someone else runs, so it does not prove that one party controls both. The operator's display name is never checked and is reported as `claimed_name`.
- **Payment** (`payment.type`): the payment method, such as `native` or `usdc`. The report does not list tools; for those use `mechx tool list` (see [List tools available for a mech](#list-tools-available-for-a-mech)). No price is shown. `maxDeliveryRate` on the Mech contract is the most it can charge per request, and what your deposit must cover; the contract settles the actual charge at delivery, which can be less.
- **Delivery record** (`delivery`): `received_requests`, `self_delivered`, `delivered_by_others` (requests another Mech delivered after this one missed its deadline) and `age_days`. A request another Mech delivered was missed by this one too, so received minus `self_delivered` is what this Mech did not deliver: requests another Mech took over, requests no Mech answered, and any still within their deadline. Off-chain requests only enter the counts once the Mech settles them on-chain, so an off-chain request that was never delivered appears nowhere, and off-chain traffic always looks fully delivered.
- **Benchmark** (`benchmarks`): one link per tool to the operator's own figures. The report carries only the link; the metric and time window the operator chose are in the metadata entry, not in the report. The link is passed on as a claim and no number is shown; open it and judge it yourself, and if you use a Mech, measure it yourself.
- **Terms**: the terms link, when the operator published one in the metadata, as published.

> **Note:** Olas does not review Mechs or their claims. The report gives you what the operator published and what the chain records, and tells you which is which. Karma, the on-chain reputation score, is not part of this report; it is shown on the marketplace website.

The `AI Agent Id` column in `mech list` is the Olas service id. The ERC-8004 agent id used in domain proofs is a different number, the same only by coincidence on Gnosis; the report resolves it for you.

**Mechs run by Valory.** Valory creates one DNS name per Mech it operates: the Mech address without `0x`, a hyphen, then the chain id (100 for Gnosis), under `mech.valory.xyz`. If it resolves, Valory runs that Mech and the [Valory Mech Terms](https://www.valory.xyz/terms/mechs) apply. Newer `mech list` output marks these in an Operator column, not shown in the sample above.

```bash
dig +short c05e7412439bd7e91730a6880e18d5d5873f632c-100.mech.valory.xyz
```

**Without mech-client.** The marketplace publishes an ERC-8004 registration file and an A2A agent card for every service. The registration file links the metadata, the operator domain and the benchmark endpoint; the agent card lists the tools and the payment type, and names the operator as `provider` only when the domain proof matches. These endpoints belong to the marketplace and may change without this page. `<network>` is the chain's name on the marketplace, on every chain the Olas Marketplace is deployed to, and `<serviceId>` is the `AI Agent Id` shown on the marketplace website:

```
https://marketplace.olas.network/api/erc8004/<network>/ai-agents/<serviceId>
https://marketplace.olas.network/api/erc8004/<network>/ai-agents/<serviceId>/agent-card.json
```

To check a domain proof by hand: take the operator domain from the metadata, fetch `https://<domain>/.well-known/agent-registration.json`, and confirm it lists the same `agentId` and `agentRegistry` as the registration file above.

### 1. 2. In terminal

### 1. 2. 1. Request command

- Use the command mechx in terminal, which is structured as follows:

```bash
mechx request --prompts <prompt> --priority-mech <mech_address> --tools <tool> --chain-config <chain-config> --use-offchain
```

Replace each placeholder as follows:

- `<prompt>`: The request description to be sent to the Mech. For instance: "Write a short poem".

- `<mech_address>`: The address of the Mech to send the request to.

- `<tool>`: The name of the tool to use.

- `<chain-config>`: One of the keys in the dictionary defined in `mech_client/configs/mechs.json` (e.g., "gnosis"). This provides the client with a configuration for the chosen network.

- `--use-offchain`: Optional flag to use the off-chain method. Omit for on-chain requests.

### 1. 2. 2. Deposits and Payment Types

When you send a request, the Mech Client automatically detects the mech's payment type and handles the appropriate payment flow. You don't need to specify the payment type - the mech's smart contract declares it.

**Understanding Payment Types:**

There are **5 payment types** that mechs can use:

| Payment Type | Description | How to Pay |
|--------------|-------------|------------|
| **NATIVE** | Per-request native token | Client sends native tokens (xDAI, ETH, MATIC) with transaction |
| **OLAS_TOKEN** | Per-request OLAS token | Client approves and transfers OLAS tokens |
| **USDC_TOKEN** | Per-request USDC token | Client approves and transfers USDC tokens |
| **NATIVE_NVM** | NVM subscription with native token | Purchase subscription first, then unlimited requests |
| **TOKEN_NVM_USDC** | NVM subscription with USDC token | Purchase subscription first, then unlimited requests |

**Finding the maximum per request**

A Mech does not have a fixed price. It advertises a maximum per request, `maxDeliveryRate`, and that maximum is what the client signs into every request on your behalf. At delivery the Mech charges its actual cost, which can be anything up to the maximum; whatever it does not charge stays in your balance on the marketplace. To read the maximum in advance:

- Enter the Mech's address into the block explorer of the corresponding network.

- Click on "Contract", then "Read Contract".

- Find and click on the function maxDeliveryRate.

- The number is in the base units of the Mech's payment asset: wei for native and OLAS payments (18 decimals), and 6-decimal units for USDC.

For an off-chain request the client prints what the Mech charged under each delivery, as `Charged: <amount>`, in the same units.

Note: For Mechs using the Nevermined subscription model, this value corresponds to the maximum per request; actual usage may involve multiple requests per subscription.

**Making a deposit**

**Option 1: Prepaid balance (for NATIVE, OLAS_TOKEN, USDC_TOKEN mechs)**

You can deposit funds to your prepaid balance and use `--use-prepaid` flag when making requests:

- For NATIVE payment mechs:
```bash
mechx deposit native <amount> --chain-config <network_name>
```

- For OLAS_TOKEN payment mechs:
```bash
mechx deposit token <amount> --chain-config <network_name> --token-type olas
```

- For USDC_TOKEN payment mechs:
```bash
mechx deposit token <amount> --chain-config <network_name> --token-type usdc
```

**Note:** The `--token-type` parameter is required and must be explicitly specified (olas or usdc).

In all cases above, `<amount>` must cover the mech's maximum (as given by maxDeliveryRate) for every request you intend to send; a request is refused when the balance is below the maximum, even if the Mech would have charged less. What the Mech does not charge stays in your balance for later requests.

**Option 2: Per-request payment (for NATIVE, OLAS_TOKEN, USDC_TOKEN mechs)**

The client handles per-request payment automatically when you don't use `--use-prepaid`:
- NATIVE mechs: Native tokens sent with transaction
- OLAS_TOKEN mechs: OLAS tokens approved and transferred
- USDC_TOKEN mechs: USDC tokens approved and transferred

**Option 3: NVM Subscriptions (for NATIVE_NVM, TOKEN_NVM_USDC mechs)**

Purchase a subscription upfront for unlimited requests:

```bash
mechx subscription purchase --chain-config <network_name>
```

This purchases a fixed-price subscription (ERC1155 NFT) that enables multiple requests during the subscription period. No per-request payment needed.

**Note:** To use a custom private key file path, add the `--key <path>` option to any command.

### 1. 2. 3. Finding the response

After sending a request, a JSON response will appear below the line `"Data for agent"`. The key `"result"` in this JSON object contains the Mech's response to your request.

For example, the following command:

```bash
mechx request --prompts "write a short poem" --tools openai-gpt-3.5-turbo --chain-config gnosis --priority-mech <mech_address>
```

You should receive a response as follows:

```json
{
  "requestId": 123456789,
  "prompt": "write a short poem",
  "tool": "openai-gpt-3.5-turbo",
  "result": "Beneath the velvet night so deep,\nWhere stars their silent vigil keep,\nA whisper of the wind goes by,\nAs moonbeams dance across the sky.",
  "metadata": {}
}
```

**Troubleshooting: timeout waiting for response**

For some Mechs, the response may take a few minutes to arrive. If you encounter timeout issues, ensure you have a reliable RPC provider configured:

```bash
export MECHX_CHAIN_RPC=<your_rpc_url>
```

If the connection times out, you can retrieve the response manually. To do this:

- Note the `request_id` printed in the logs.

- Convert the request ID to hexadecimal:

```bash
printf "%x\n" <request_id>
```

- Go to the [Mech list](https://marketplace.olas.network/gnosis/ai-agents) and locate your Mech (by its AI Agent ID or address).

- Click on the Mech’s address to see a list of requests it has received.

- Find your request by matching the hexadecimal request ID.

- Click on "Delivers Data" to view the response.

**Troubleshooting: non-hexadecimal symbol**

You may encounter an error indicating that the private key contains invalid (non-hexadecimal) characters.
This can happen, in particular, on Windows systems, where some IDEs may automatically add a newline character (`\n`) at the end of a file—for example, in `ethereum_private_key.txt`.

To avoid this, check your IDE settings and ensure that the file contains only the private key with no trailing newline or whitespace.

**Troubleshooting: out of gas**

If an "Out of gas" error is encountered, an increase of the gas limit can solve the problem. To do this:

```bash
export MECHX_GAS_LIMIT=200000
```

### 1. 3. Script for automatizing request sending

The following script can be used in order to automatize request sending:

```python
from mech_client.marketplace_interact import marketplace_interact

PRIORITY_MECH_ADDRESS = "<priority_mech_address>"
PROMPT_TEXT = "<prompt_text>"
TOOL_NAME = "<tool_name>"
CHAIN_CONFIG = "<network_name>"
AGENT_MODE = False  # Set to True if using agent mode
SAFE_ADDRESS = ""   # Required if AGENT_MODE is True
USE_OFFCHAIN = False

result = marketplace_interact(
    prompts=(PROMPT_TEXT,),  # Note: must be a tuple
    priority_mech=PRIORITY_MECH_ADDRESS,
    agent_mode=AGENT_MODE,
    safe_address=SAFE_ADDRESS,
    use_offchain=USE_OFFCHAIN,
    tools=(TOOL_NAME,),      # Note: must be a tuple
    chain_config=CHAIN_CONFIG
)
```

Replace the placeholders as follows:

- `<priority_mech_address>`: the address of the targeted Mech,

- `<prompt_text>`: the text of the prompt to send,

- `<tool_name>`: the name of the tool to use,

- `<network_name>`: the name of the target network (e.g., "gnosis", "base").

**Note:** If using agent mode (`AGENT_MODE = True`), you must provide a valid `SAFE_ADDRESS`. For client mode, set `AGENT_MODE = False` and `SAFE_ADDRESS = ""`.

The variable **result** contains the response of the mech:

`result["deliveries"]` maps each request ID to a `DeliveryResult` — the same shape for
on-chain and off-chain requests alike. Each one carries two fields:

- `.data` is the parsed content the mech delivered. Mechs typically put their answer in
  the payload's `result` field as a JSON-encoded string, so reading it takes a
  `json.loads`; treat that as a convention rather than a guarantee and handle payloads
  that omit the field. It is `None` if the result file could not be read.
- `.url` is the IPFS URL that content was read from, so you can re-fetch or link to it.
  It is `None` for off-chain mechs that answer inline instead of pinning a result file.


## 2. Tool Management

### List tools available for a mech

To list the tools available for a specific marketplace mech, use the `tool list` command with an AI Agent ID:

```bash
mechx tool list 1722 --chain-config gnosis
```

```bash
+---------------------------------------------+-----------------------------------------------+
| Tool Name                                   | Unique Identifier                             |
+=============================================+===============================================+
| claude-prediction-offline                   | 1722-claude-prediction-offline                |
+---------------------------------------------+-----------------------------------------------+
| claude-prediction-online                    | 1722-claude-prediction-online                 |
+---------------------------------------------+-----------------------------------------------+
| deepmind-optimization                       | 1722-deepmind-optimization                    |
+---------------------------------------------+-----------------------------------------------+
```

### Get tool description

To get the description of a specific tool, use the `tool describe` command with the tool's unique identifier:

```bash
mechx tool describe 1722-openai-gpt-4 --chain-config gnosis
```

```bash
Description for tool 1722-openai-gpt-4: Performs a request to OpenAI's GPT-4 model.
```

### Get tool input/output schema

To get the input/output schema of a specific tool, use the `tool schema` command:

```bash
mechx tool schema 1722-openai-gpt-4 --chain-config gnosis
```

```bash
Tool Details:
+------------------------+---------------------------------------------+
| Tool Name              | Tool Description                            |
+========================+=============================================+
| OpenAI Request (GPT-4) | Performs a request to OpenAI's GPT-4 model. |
+------------------------+---------------------------------------------+
Input Schema:
+-------------+-----------------------------------------------+
| Field       | Value                                         |
+=============+===============================================+
| type        | text                                          |
+-------------+-----------------------------------------------+
| description | The request to relay to OpenAI's GPT-4 model. |
+-------------+-----------------------------------------------+
Output Schema:
+-----------+---------+-----------------------------------+
| Field     | Type    | Description                       |
+===========+=========+===================================+
| requestId | integer | Unique identifier for the request |
+-----------+---------+-----------------------------------+
| result    | string  | Response from OpenAI              |
+-----------+---------+-----------------------------------+
| prompt    | string  | User prompt to send to OpenAI     |
+-----------+---------+-----------------------------------+
```


## 3. Offchain Requests

The offchain URL is automatically discovered from the mech's on-chain metadata. No additional configuration is required — simply use the `--use-offchain` flag:

```bash
mechx request --prompts "test" --tools openai-gpt-4 --use-offchain --chain-config gnosis
```

The client queries the mech's `ComplementaryServiceMetadata` contract to find the `url` field published by the mech operator, then sends requests to that endpoint.

Each off-chain request is signed with a nonce. By default (`--nonce-mode explicit`) the client signs a random nonce chosen per request together with a settlement deadline (`--deadline-seconds` from the latest block, 15 minutes by default) and says so on the wire, so independently signed requests can settle in any order and in independent transactions, up to that deadline. The mech refuses a request whose deadline is too close for it to execute and settle. A Mech that has the explicit-nonce path switched off answers HTTP 503 and the client resends the request, and the rest of the batch, with the marketplace's sequential nonce counter for your address. A Mech on a release that predates this option does not take part in that fallback, so pass `--nonce-mode sequential` for it. `sequential` sends the same payload as before and settles requests in counter order:

```bash
mechx request --prompts "test" --tools openai-gpt-4 --use-offchain true --nonce-mode sequential --chain-config gnosis
```

The request's maximum is the Mech's advertised `maxDeliveryRate`. The Mech reports what it actually charged with the delivery, and the client prints it as `Charged: <amount>`.


## 4. Programmatic Usage

From a script, the same report is available as data:

```python
from mech_client.domain.tools import ToolManager

manager = ToolManager("gnosis")
service_id = 2182
mech = "0xc05e7412439bd7e91730a6880e18d5d5873f632c"
metadata = manager.fetch_tools_metadata(service_id)  # the Mech's published metadata, or None
report = manager.mech_report(mech, metadata)         # dict with the same fields as `mechx mech info`
```

Call `manager.mech_report_or_terms(mech, metadata)` before paying: when the metadata or the chain record cannot be read it returns the Valory terms check alone, with a `report_note` saying why.


You can use the Mech Client as a library in your Python project:

```python
from mech_client.services import MarketplaceService
from mech_client.domain.payment import PaymentType
from mech_client.infrastructure.config import get_mech_config
from aea_ledger_ethereum import EthereumApi, EthereumCrypto

# Configuration
PRIORITY_MECH_ADDRESS = "0x77af31De935740567Cf4fF1986D04B2c964A786a"
PROMPT_TEXT = "Will Gnosis pay reach 100k cards in 2024?"
TOOL_NAME = "openai-gpt-4o-2024-05-13"
CHAIN_CONFIG = "gnosis"
MODE = "client"  # Use "agent" for agent mode (Safe multisig)
SAFE_ADDRESS = ""  # Required if MODE is "agent"

# Setup ledger and crypto
config = get_mech_config(CHAIN_CONFIG)
crypto = EthereumCrypto("ethereum_private_key.txt")
ledger_api = EthereumApi(**config.ledger_config.__dict__)

# Create service
service = MarketplaceService(
    chain_config=CHAIN_CONFIG,
    ledger_api=ledger_api,
    payer_address=crypto.address,
    mode=MODE,
    safe_address=SAFE_ADDRESS if MODE == "agent" else None,
)

# Send request
result = service.send_request(
    priority_mech=PRIORITY_MECH_ADDRESS,
    tools=[TOOL_NAME],
    prompts=[PROMPT_TEXT],
    payment_type=PaymentType.NATIVE,  # or PaymentType.TOKEN, PaymentType.NATIVE_NVM
)

print(f"Transaction hash: {result['tx_hash']}")
print(f"Request ID: {result['request_ids'][0]}")
print(f"Result: {result.get('result')}")
```

You can also programmatically fetch tools for marketplace mechs:

```python
from mech_client.services import ToolService
from mech_client.infrastructure.config import get_mech_config
from aea_ledger_ethereum import EthereumApi

# Configuration
service_id = 1722
chain_config = "gnosis"

# Setup ledger API
config = get_mech_config(chain_config)
ledger_api = EthereumApi(**config.ledger_config.__dict__)

# Create tool service
tool_service = ToolService(
    chain_config=chain_config,
    ledger_api=ledger_api,
)

# Fetch tools for a specific marketplace mech
tools = tool_service.list_tools(service_id=service_id)
print(f"Tools for marketplace mech {service_id}:")
for tool_name, tool_id in tools:
    print(f"  {tool_name}: {tool_id}")
```


## 5. Chain Configuration

Default configurations for different chains are stored in `mech_client/configs/mechs.json`. You can override any configuration parameter by exporting the following environment variables:

```bash
MECHX_CHAIN_RPC           # Custom RPC endpoint
MECHX_SUBGRAPH_URL        # Custom subgraph URL (optional, defaults provided)
MECHX_GAS_LIMIT           # Custom gas limit
MECHX_TRANSACTION_URL     # Custom transaction explorer URL

MECHX_LEDGER_CHAIN_ID
MECHX_LEDGER_POA_CHAIN
MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY
MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED
```


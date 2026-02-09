## **Overview**

This guide contains practical guidelines for interacting with Mechs.
A requester - whether it is an agent or an application - can choose between two methods for sending service requests:

- On-chain: The request is sent to the Mech contract. For Mechs registered on the [Mech Marketplace](https://stack.olas.network/mech-tools-dev/#the-mech-marketplace), it is relayed via the Mech Marketplace.

- Off-chain: The request is sent directly to the Mech AI agent. The Mech then sends the result (or delivery) to the Mech contract, which is subsequently relayed by the Mech Marketplace if the Mech is registered there.

To send a request, follow these steps:

**1.** Choose a Mech;

**2.** Make an on-chain deposit according to the Mech’s [payment model](https://stack.olas.network/mech-tools-dev/#payment-models).

**3.** Choose a method for sending the request (on-chain or off-chain).

**4.** Send the request.

Detailed instructions for each step are provided below.

## Setup

**Requirements**: [Python](https://www.python.org/) >=3.10, <3.12 (Python 3.10 or 3.11), [Poetry](https://github.com/python-poetry/poetry) == 1.8.4

**1.** Install mech-client:

```bash
pip install mech-client
```

**2.** Setting up an EOA ([Externally Owned Account](https://ethereum.org/en/developers/docs/accounts/)) account:

**a.** Install browser extension of Metamask and open it.

**b.** Click on the account icon, then select “Add account or hardware wallet”, then “Add a new Ethereum account”. Provide a name for the account and click “Add account”.

**c.** Select the newly created account. Open the top-right menu, click “Account details”, then click “Show private key”.

**d.** Copy this key in the file `ethereum_private_key.txt` in your project folder. Make sure the file contains only the private key, with no leading or trailing spaces, tabs, or newlines.

## Supported Chains

**Supported chains:** `gnosis`, `base`, `polygon`, `optimism`

All commands require `--chain-config` with one of these four chain names.

| Chain | Marketplace | Agent Mode | Native Payment | NVM Subscriptions | OLAS Payments | USDC Payments |
|-------|-------------|------------|----------------|-------------------|---------------|---------------|
| Gnosis | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Base | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Polygon | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Optimism | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

**Key:**
- **Marketplace**: All supported chains have marketplace contracts deployed.
- **Agent Mode**: All supported chains support on-chain agent registration via `setup`.
- **Native Payment**: Chains supporting `deposit native` command for prepaid native token deposits.
- **NVM Subscriptions**: Chains supporting `subscription purchase` command for Nevermined subscription-based payments (Gnosis, Base only).
- **OLAS/USDC Payments**: Chains supporting `deposit token` command with OLAS or USDC tokens.

**Important Notes:**
- The `mech list` command works on all marketplace chains (Gnosis, Base, Polygon, Optimism) with default subgraph URLs provided. The `MECHX_SUBGRAPH_URL` environment variable is optional and only needed to override defaults.
- For other marketplace commands (`request`, deposits), subgraph is not required.

## 1. How to Send a request to a Mech (registered on the Mech MarketPlace)

To send a request to a Mech that is accessible through the Mech Marketplace, first complete the [setup](#setup), then follow the [instructions](#1-2-sending-requests) below.

You will need to [choose a Mech](#1-1-choosing-a-mech), and then select one of the following methods to send a request:
- Via the [terminal](#1-2-in-terminal)
- Using a Python [script](#1-3-script-for-automatizing-request-sending)

Follow the instructions in the corresponding section.


### 1. 1. Choosing a Mech

- Use the command mechx in terminal, which is structured as follows.
```bash
mechx mech list --chain-config <chain-config>
```

Replace `<chain-config>` by the chosen network. Supported marketplace chains: gnosis, base, polygon, optimism.

**Note**: Default subgraph URLs are provided for all supported chains. You can optionally override the default:
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

**Finding the price per request**

To determine the Mech's fee in advance:

- Enter the Mech's address into the block explorer of the corresponding network.

- Click on "Contract", then "Read Contract".

- Find and click on the function maxDeliveryRate.

- Divide the displayed number by 10^8 in order to obtain the price per request (in ether or token units, depending on the Mech).

Note: For Mechs using the Nevermined subscription model, this value corresponds to the maximum price per request; actual usage may involve multiple requests per subscription.

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

In all cases above, `<amount>` must be at least the mech's price (as given by maxDeliveryRate).

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

### 1. 2. 2. Finding the response

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

The variable **result** contains the response of the mech.


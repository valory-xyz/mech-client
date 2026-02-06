# Mech Client

A client to interact with Mechs - AI agents providing services - on the [Olas Marketplace](https://olas.network/mech-marketplace). It allows users to post requests for AI tasks on-chain, and get their result delivered.

## Requirements

- Python >=3.10

## Developing, running and deploying Mechs and Mech tools

The easiest way to create, run, deploy and test your own Mech and Mech tools is to follow the Mech and Mech tool docs [here](https://stack.olas.network/mech-tools-dev/). The [Mech tools dev repo](https://github.com/valory-xyz/mech-tools-dev) used in those docs greatly simplifies the development flow and dev experience.

Only continue reading this README if you know what you are doing and you are specifically interested in this repo.

## Quickstart Guide
For a fast and straightforward setup, follow the instructions provided on the website [here](https://build.olas.network/hire). 
This guide will walk you through the essential steps to get up and running without requiring an in-depth understanding of the system.

## Installation

Find the latest available release on [PyPi](https://pypi.org/project/mech-client/).

We recommend that you create a virtual Python environment using [Poetry](https://python-poetry.org/). Set up your virtual environment as follows:

```bash
poetry new my_project
cd my_project
poetry add mech-client
```

Alternatively, you can also install the Mech Client in your local Python installation:

```bash
pip install mech-client
```

If you require to use the Mech Client programmatically, please see [this section](#programmatic-usage) below.

## CLI Usage

Display the available options:

```bash
mechx --help
```

```bash
Usage: mechx [OPTIONS] COMMAND [ARGS]...

  Command-line tool for interacting with mechs.

Options:
  --version      Show the version and exit.
  --client-mode  Enables client mode
  --help         Show this message and exit.

Commands:
  deposit-native                           Deposits Native balance for prepaid marketplace requests
  deposit-token                            Deposits Token balance for prepaid marketplace requests
  fetch-mm-mechs-info                      Fetches info of marketplace mechs
  interact                                 Interact with a mech specifying a prompt and tool
  prompt-to-ipfs                           Upload a prompt and tool to IPFS as metadata
  purchase-nvm-subscription                Allows to purchase Nevermined subscription
  push-to-ipfs                             Upload a file to IPFS
  setup-agent-mode                         Sets up the agent mode for users
  to-png                                   Convert a stability AI API's diffusion model output
  tool-description-for-marketplace-mech    Get the description of a specific tool
  tool-io-schema-for-marketplace-mech      Get the input/output schema of a specific tool
  tools-for-marketplace-mech               List tools available for marketplace mechs

```

## Mech Marketplace

Learn more about mech marketplace [here](https://olas.network/mech-marketplace)

### Supported Chains

**Supported chains:** `gnosis`, `base`, `polygon`, `optimism`

All commands require `--chain-config` with one of these four chain names.

| Chain | Marketplace | Agent Mode | Native Payment | NVM Subscriptions | OLAS Payments | USDC Payments |
|-------|-------------|------------|----------------|-------------------|---------------|---------------|
| Gnosis | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Base | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Polygon | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Optimism | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |

**Notes:**
- **Marketplace**: Chains with marketplace contracts deployed. All supported chains have marketplace support.
- **Agent Mode**: All supported chains support on-chain agent registration via `setup-agent-mode`.
- **Native Payment**: Chains that support `deposit-native` command for prepaid native token deposits.
- **NVM Subscriptions**: Chains that support `purchase-nvm-subscription` command for Nevermined subscription-based payments (Gnosis, Base only).
- **OLAS/USDC Payments**: Chains that support `deposit-token` command with OLAS or USDC tokens.
- **Subgraph**: The `fetch-mm-mechs-info` command requires setting `MECHX_SUBGRAPH_URL` environment variable for any chain.

### Set up agent mode for on-chain interactions

There are two modes you can use the mechx for on-chain interactions. Currently `agent-mode` is supported for all marketplace chains (Gnosis, Base, Polygon, and Optimism).

-   _agent mode_ (Recommended): This allows to register your on-chain interactions as agent on the olas protocol and allows for A2A activity to be reflected on the client
-   _client mode_: Simple on-chain interations using EOA

```bash
cp .example.env .env
```

📝 For better reliability, it is recommended to use a stable third-party RPC provider.

```bash
mechx setup-agent-mode --chain-config <chain_config>
```

⚠️ Note: Run `setup-agent-mode` for each chain you interact with, and ensure your `.env` file has the correct RPC endpoint.

### Generate Mech requests

#### List marketplace mechs

To list the top marketplace mechs based on deliveries, use the `fetch-mm-mechs-info` command. You can specify the chain you want to query. Please note that only the first 20 mechs sorted by number of deliveries will be shown.

⚠️ This command requires a subgraph URL to be set. Configure it with:

```bash
export MECHX_SUBGRAPH_URL=<your-subgraph-url>
```

Supported marketplace chains: gnosis, base, polygon, optimism

```bash
mechx fetch-mm-mechs-info --chain-config gnosis
```

You can also find available Mechs [here](https://marketplace.olas.network/)

#### Usage

The basic usage of the Mech Client is as follows.

```bash
mechx interact --prompts <prompt> --priority-mech <priority mech address> --tools openai-gpt-3.5-turbo --chain-config <chain_config>
```

The Mech Client can also be used to send batch requests. There are couple of different ways to achieve this:

```bash
mechx interact --prompts={<prompt-1>,<prompt-2>} --priority-mech <priority mech address> --tools={<tool-1>,<tool-2>} --chain-config <chain_config>
```

or <br>

```bash
mechx interact --prompts <prompt-1> --prompts <prompt-2> --priority-mech <priority mech address> --tools <tool-1> --tools <tool-2> --chain-config <chain_config>
```

Additionally other options are available and their usage is listed below:

`--use-prepaid <bool>`: use the prepaid method to send requests to a Mech via the Mech Marketplace. Defaults to False. <br>
`--use-offchain <bool>`: use the off-chain method to send requests to a Mech via the Mech Marketplace. Defaults to False.

##### Prepaid Requests

In order to pay for the Mech fees, you can make a deposit before sending requests. The deposit depends on the
payment model of the Mech. For a fixed price Mech receiving payments in native token, use the following:

```bash
mechx deposit-native --chain-config <chain_config> <amount>
```

For a fixed price Mech receiving payments in OLAS, use the following (the amount is in ether):

```bash
mechx deposit-token --chain-config <chain_config> <amount>
```

For a Mech using Nevermined subscriptions, to make requests, it is necessary to buy a subscription. To do that you can use the following command:

```bash
mechx purchase-nvm-subscription --chain-config <chain_config>
```

⚠️ To ensure optimal performance and reliability when using `purchase-nvm-subscription`, it is advisable to use a custom RPC provider as public RPC endpoints may be rate-limited or unreliable under high usage. You can configure your custom RPC URL in your environment variables using

```bash
export MECHX_CHAIN_RPC=
```

##### Offchain Requests

To use offchain requests using `--use-offchain` flag, export the `MECHX_MECH_OFFCHAIN_URL` env variable before sending requests. For example if you want to connect to a mech running locally, you can do the following

```bash
export MECHX_MECH_OFFCHAIN_URL="http://localhost:8000/"
```

If you want to use a Valory mech for offchain requests, below is the list of mechs and their address and offchain urls.

| AI Agent ID |           Priority Mech Address            |                     Offchain URL                      |
| :---------: | :----------------------------------------: | :---------------------------------------------------: |
|    2182     | 0xB3C6319962484602b00d5587e965946890b82101 | https://d19715222af5b940.agent.propel.autonolas.tech/ |

### List tools available for a mech

To list the tools available for a specific marketplace mech, use the `tools-for-marketplace-mech` command. You can specify an AI Agent ID to get tools for a specific mech.

```bash
mechx tools-for-marketplace-mech 1722 --chain-config gnosis
```

```bash
You will see an output like this:
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

### Get Tool Description

To get the description of a specific tool, use the ` tool-description-for-marketplace-mech` command. You need to specify the unique identifier of the tool.

```bash
mechx  tool-description-for-marketplace-mech <unique_identifier> --chain-config <chain_config>
```

Example usage:

```bash
mechx  tool-description-for-marketplace-mech 1722-openai-gpt-4 --chain-config gnosis
```

You will see an output like this:

```bash
Description for tool 1722-openai-gpt-4: Performs a request to OpenAI's GPT-4 model.
```

### Get Tool Input/Output Schema

To get the input/output schema of a specific tool, use the `tool-io-schema-for-marketplace-mech` command. You need to specify the unique identifier of the tool.

```bash
mechx tool-io-schema-for-marketplace-mech <unique_identifier> --chain-config <chain_config>
```

Example usage:

```bash
mechx tool-io-schema-for-marketplace-mech 1722-openai-gpt-4 --chain-config gnosis
```

You will see an output like this:

```bash
Tool Details:
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

### Set up the EOA and private key

To use the Mech Client using client mode, you need an EOA account and its associated private key stored in a text file `ethereum_private_key.txt`. You can set it up in two ways:

-   Use any software of your choice (e.g., [Metamask](https://metamask.io/)) and copy the private key:

    ```bash
    echo -n YOUR_PRIVATE_KEY > ethereum_private_key.txt
    ```

    Do not include any leading or trailing spaces, tabs or newlines, or any other character in the file `ethereum_private_key.txt`.

-   Alternatively, use the Open AEA command `generate-key` (you'll need to install [Open AEA](https://pypi.org/project/open-aea/) and its [Ethereum ledger plugin](https://pypi.org/project/open-aea-ledger-ethereum/)):

    ```bash
    aea generate-key ethereum
    ```

    and display the corresponding EOA:

    ```bash
    python -c "from web3 import Web3; print(Web3().eth.account.from_key(open('ethereum_private_key.txt').read()).address)"
    ```

The EOA you use must have enough funds to pay for the Mech requests, or alternatively, use a Nevermined subscription.

> **:warning: Warning** <br />
>
> -   **If the generated EOA account is for development purposes, make sure it does not contain large amounts of funds.**
>
> -   **If you store the key file in a local Git repository, we recommend that you add it to `.gitignore` in order to avoid publishing it unintentionally:**
>
>     ```bash
>     echo ethereum_private_key.txt >> .gitignore
>     ```

To use client-mode for cli commands, simply supply `--client-mode` flag before the cli commands.

```bash
mechx --client-mode <rest of the cli command>
```


> **:pencil2: Note** <br /> > **If you encounter an "Out of gas" error when executing the Mech Client, you will need to increase the gas limit, e.g.,**
>
> ```bash
> export MECHX_GAS_LIMIT=200000
> ```

### Chain configuration

Default configurations for different chains are stored in the file [configs/mechs.json](./mech_client/configs/mechs.json). If `--chain-config` parameter is not specified, the Mech Client will choose the first configuration on the JSON.

Additionally, you can override any configuration parameter by exporting any of the following environment variables:

```bash
MECHX_CHAIN_RPC
MECHX_GAS_LIMIT
MECHX_TRANSACTION_URL
MECHX_SUBGRAPH_URL

MECHX_LEDGER_CHAIN_ID
MECHX_LEDGER_POA_CHAIN
MECHX_LEDGER_DEFAULT_GAS_PRICE_STRATEGY
MECHX_LEDGER_IS_GAS_ESTIMATION_ENABLED
```

## Programmatic usage

You can also use the Mech Client as a library on your Python project.

1. Set up the private key as specified [above](#set-up-the-private-key). Store the resulting key file (e.g., `ethereum_private_key.txt`) in a convenient and secure location.

2. Create Python script `my_script.py`:

    ```bash
    touch my_script.py
    ```

3. Edit `my_script.py` as follows:

    ```python
    from mech_client.marketplace_interact import marketplace_interact

    PRIORITY_MECH_ADDRESS = "0x77af31De935740567Cf4fF1986D04B2c964A786a"
    PROMPT_TEXT = "Will Gnosis pay reach 100k cards in 2024?"
    TOOL_NAME = "openai-gpt-4o-2024-05-13"
    CHAIN_CONFIG = "gnosis"
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
    print(result)
    ```

You can also use the Mech Client to programmatically fetch tools for marketplace mechs in your Python project, as well as retrieve descriptions and input/output schemas for specific tools given their unique identifier.

1. Set up the private key as specified [above](#set-up-the-private-key). Store the resulting key file (e.g., `ethereum_private_key.txt`) in a convenient and secure location.

2. Create a Python script `fetch_tools_script.py`:

    ```bash
    touch fetch_tools_script.py
    ```

3. Edit `fetch_tools_script.py` as follows:

    ```python
    from mech_client.mech_marketplace_tool_management import (
        get_tools_for_marketplace_mech,
        get_tool_description_for_marketplace_mech,
        get_tool_io_schema_for_marketplace_mech
    )

    # Fetching tools for a specific marketplace mech
    service_id = 1722  # Specify the service ID
    chain_config = "gnosis"  # Specify the chain configuration
    tools = get_tools_for_marketplace_mech(service_id=service_id, chain_config=chain_config)
    print(f"Tools for marketplace mech {service_id}:", tools)

    # Assuming you know the tool name, construct the unique identifier
    tool_name = "openai-gpt-4o-2024-05-13"  # Example tool name
    unique_identifier = f"{service_id}-{tool_name}"  # Construct the unique identifier

    # Fetching description and I/O schema for a specific tool using the unique identifier
    description = get_tool_description_for_marketplace_mech(unique_identifier, chain_config)
    print(f"Description for {unique_identifier}:", description)

    io_schema = get_tool_io_schema_for_marketplace_mech(unique_identifier, chain_config)
    print(f"Input/Output Schema for {unique_identifier}:", io_schema)
    ```

This script will:
- Fetch and print the tools available for a specified marketplace mech.
- Construct the unique identifier for a tool using the format `serviceId-toolName`.
- Retrieve and display the description of a specific tool using its unique identifier.
- Retrieve and display the input and output schema of a specific tool using its unique identifier.

## Architecture & Documentation

### Architecture Overview

Version 0.17.0 introduced a comprehensive architectural refactoring that separates concerns into distinct layers:

```
┌──────────────────────────────────────┐
│         CLI Layer                    │  User interface & command routing
├──────────────────────────────────────┤
│         Service Layer                │  Business workflow orchestration
├──────────────────────────────────────┤
│         Domain Layer                 │  Core business logic & strategies
├──────────────────────────────────────┤
│      Infrastructure Layer            │  External system adapters
└──────────────────────────────────────┘
```

**Key improvements:**
- ✅ **Separation of concerns**: Each layer has a specific responsibility
- ✅ **Strategy pattern**: Flexible payment, execution, and delivery strategies
- ✅ **Dependency injection**: Better testability and modularity
- ✅ **Type safety**: Comprehensive type hints throughout
- ✅ **Comprehensive tests**: 164 unit tests with ~40% coverage

### Documentation

For detailed information about the architecture and development:

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Comprehensive architecture guide
  - Layer descriptions and responsibilities
  - Data flow diagrams
  - Key patterns (Factory, Strategy, Repository)
  - Component reference
  - Best practices

- **[TESTING.md](./TESTING.md)** - Testing guide for contributors
  - Test structure and organization
  - Running tests and coverage reports
  - Writing tests (patterns, fixtures, mocking)
  - Testing async components
  - Best practices

- **[MIGRATION.md](./MIGRATION.md)** - Migration guide from pre-v0.17.0
  - What changed in v0.17.0
  - Module mappings (old → new)
  - Common migration patterns
  - Breaking changes
  - Code examples

- **[CLAUDE.md](./CLAUDE.md)** - Development guidelines for Claude Code
  - Command dependency diagrams
  - Common issues and solutions
  - Environment variables reference
  - Development commands

### For Library Users

If you use mech-client as a library (not just the CLI), see:
- [Programmatic usage](#programmatic-usage) - Basic usage examples
- [MIGRATION.md](./MIGRATION.md) - Migrating from older versions
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Understanding the architecture

### For Contributors

If you want to contribute to mech-client development:
1. Read [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the structure
2. Follow [TESTING.md](./TESTING.md) for writing tests
3. Review [CLAUDE.md](./CLAUDE.md) for development guidelines
4. See [Developer installation](#developer-installation) below

## Developer installation

To setup the development environment for this project, clone the repository and run the following commands:

```bash
poetry install
poetry shell
```

## Release guide

- Bump versions in `pyproject.toml`.`mech_client/__init__.py` and `SECURITY.md`
- `poetry lock`
- `rm -rf dist`
- `autonomy packages sync --update-packages`
- `make dist`
- Then, create a release PR and tag the release.

## FAQ

<details>

<summary><b>On which chains are AI Mechs deployed?</b></summary>

The [Mech repository](https://github.com/valory-xyz/mech?tab=readme-ov-file#examples-of-deployed-mechs) contains the latest information on deployed Mechs.

</details>

<details>

<summary><b>Are AI Mechs deployed on testnets?</b></summary>

No. AI Mechs are currently deployed only on mainnets.

</details>

<details>

<summary><b>Where can I find the agent blueprint ID?</b></summary>

You can find the agent blueprint IDs for each chain on the [Marketplace](https://marketplace.olas.network) or on the [Mech repository](https://github.com/valory-xyz/mech?tab=readme-ov-file#examples-of-deployed-mechs).

</details>

<details>

<summary><b>How do I access an AI Mech on a different chain?</b></summary>

Use the `--chain-config <name>` parameter together with a valid `--priority-mech` address, for example:

```bash
mechx interact --prompts "write a short poem" --priority-mech 0x77af31De935740567Cf4fF1986D04B2c964A786a --key ./ethereum_private_key.txt --tools openai-gpt-4o-2024-05-13 --chain-config gnosis
```

</details>

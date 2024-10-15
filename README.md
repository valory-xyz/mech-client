# Mech Client

A basic client to interact with an AI Mech. [AI Mechs](https://github.com/valory-xyz/mech) allow users to post requests for AI tasks on-chain, and get their result delivered.

> **:warning: Warning** <br />
> **This is a *hacky* alpha version of the client. Don't rely on it as production software.**

## Requirements

- Python >=3.10

## Installation

Find the latest available release on [PyPi](https://pypi.org/project/mech-client/#description).

We recommend that you create a virtual Python environment using [Poetry](https://python-poetry.org/). Set up your virtual environment as follows:

```bash
poetry new my_project
cd my_project
poetry shell
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
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  interact         Interact with a mech specifying a prompt and tool.
  prompt-to-ipfs   Upload a prompt and tool to IPFS as metadata.
  push-to-ipfs     Upload a file to IPFS.
  to-png           Convert a stability AI API's diffusion model output.
  tools-for-agents List tools available for all agents or a specific agent.
  tool-description Get the description of a specific tool.
  tool_io_schema   Get the input/output schema of a specific tool.

 ```

### Set up the EOA and private key

To use the Mech Client you need an EOA account and its associated private key stored in a text file `ethereum_private_key.txt`. You can set it up in two ways:

- Use any software of your choice (e.g., [Metamask](https://metamask.io/)) and copy the private key:

  ```bash
  echo -n YOUR_PRIVATE_KEY > ethereum_private_key.txt
  ```

  Do not include any leading or trailing spaces, tabs or newlines, or any other character in the file `ethereum_private_key.txt`.

- Alternatively, use the Open AEA command `generate-key` (you'll need to install [Open AEA](https://pypi.org/project/open-aea/) and its [Ethereum ledger plugin](https://pypi.org/project/open-aea-ledger-ethereum/)):

  ```bash
  aea generate-key ethereum
  ```

  and display the corresponding EOA:

  ```bash
  python -c "from web3 import Web3; print(Web3().eth.account.from_key(open('ethereum_private_key.txt').read()).address)"
  ```

The EOA you use must have enough funds to pay for the Mech requests, or alternatively, use a Nevermined subscription.

> **:warning: Warning** <br />
> * **If the generated EOA account is for development purposes, make sure it does not contain large amounts of funds.**
>
> * **If you store the key file in a local Git repository, we recommend that you add it to `.gitignore` in order to avoid publishing it unintentionally:**
>
>    ```bash
>    echo ethereum_private_key.txt >> .gitignore
>    ```

### Select the mech you are going to send requests to

Mechs are deployed to several networks. Find the list of supported networks and corresponging mech addresses [here](https://github.com/valory-xyz/mech?tab=readme-ov-file#examples-of-deployed-mechs).

### Generate Mech requests

The basic usage of the Mech Client is as follows:

```bash
mechx interact <prompt> <agent_id>
```

where agent with `<agent_id>` will process `<prompt>` with the default options. Each chain has its own set of Mech agents. You can find the agent IDs for each chain on the [Mech Hub](https://aimechs.autonolas.network/registry) or on the [Mech repository](https://github.com/valory-xyz/mech?tab=readme-ov-file#examples-of-deployed-mechs).

Some useful options:

- `--key <private_key_path>`: Specifies the path of the private key. The default value is `./ethereum_private_key.txt`.
- `--tool  <name>`: Name of the tool to process the prompt. If you are aware about the tools that are provided by an agent you can directly provide its name using this option. If not provided, it will show a list of available tools for the agent so that you can select which one you want to use:

  ```text
  Select prompting tool
  |--------------------------------------------------|
  | ID | Tool                                        |
  |--------------------------------------------------|
  | 0  | openai-text-davinci-002                     |
  | ...| ...                                         |
  |--------------------------------------------------|
  Tool ID >
  ```

- `--chain-config <name>`: Use default chain configuration parameters (RPC, WSS, ...). [See below](#chain-configuration) for more details. Available values are
  - `arbitrum`
  - `base`
  - `celo`
  - `gnosis` (Default)
  - `optimism`
  - `polygon`

- `--confirm <type>`: Specify how to wait for the result of your request:
  - `off-chain`: Wait for the result using the ACN.
  - `on-chain`: Wait for the result using the Subgraph and the Websocket subscription (whichever arrives first).
  - `wait-for-both` (Default): Wait for the result using both `off-chain` and `on-chain` (whichever arrives first).

### Example

Example of a request specifying a key file and tool:

```bash
mechx interact "write a short poem" 6 --key ~/ethereum_private_key.txt --tool openai-gpt-3.5-turbo --chain-config gnosis --confirm on-chain
```

You will see an output like this:

```bash
Chain configuration: gnosis
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f01701220af9e4e8b4bd62d76394064f493081917bcc0b9c34a4aff60f82623b717617279
Transaction sent: https://gnosisscan.io/tx/0x61359f9cc6a1debb07d34ce1038f6aa30d25257c17edeb2b161741805e43e8d0
Waiting for transaction receipt...
Created on-chain request with ID 100407405856633966395081711430940962809568685031934329025999216833965518452765
Data arrived: https://gateway.autonolas.tech/ipfs/f01701220a462120d5bb03f406fa5ef3573df77184a20ab6343d7bade76bd321654aa7251
Data from agent: {'requestId': 100407405856633966395081711430940962809568685031934329025999216833965518452765, 'result': "In a world of chaos and strife,\nThere's beauty in the simplest of life.\nA gentle breeze whispers through the trees,\nAnd birds sing melodies with ease.\n\nThe sun sets in a fiery hue,\nPainting the sky in shades of blue.\nStars twinkle in the darkness above,\nGuiding us with their light and love.\n\nSo take a moment to pause and see,\nThe wonders of this world so free.\nEmbrace the joy that each day brings,\nAnd let your heart soar on gentle wings.", 'prompt': 'write a short poem', 'cost_dict': {}, 'metadata': {'model': None, 'tool': 'openai-gpt-3.5-turbo'}}
```


### List tools available for agents

To list the tools available for a specific agent or for all agents, use the `tools-for-agents` command. You can specify an agent ID to get tools for a specific agent, or omit it to list tools for all agents.

```bash
mechx tools-for-agents
```
```bash
You will see an output like this:
+------------+---------------------------------------------+-----------------------------------------------+
|   Agent ID | Tool Name                                   | UniqueIdentifier                             |
+============+=============================================+===============================================+
|          3 | claude-prediction-offline                   | 3-claude-prediction-offline                   |
+------------+---------------------------------------------+-----------------------------------------------+
|          3 | claude-prediction-online                    | 3-claude-prediction-online                    |
+------------+---------------------------------------------+-----------------------------------------------+
|          3 | deepmind-optimization                       | 3-deepmind-optimization                       |
+------------+---------------------------------------------+-----------------------------------------------+
|          3 | deepmind-optimization-strong                | 3-deepmind-optimization-strong                |
+------------+---------------------------------------------+-----------------------------------------------+
```

```bash
mechx tools-for-agents --agent-id "agent_id"
```
Eaxmple usage 
```bash
mechx tools-for-agents --agent-id 6
```
```bash
You will see an output like this:
+---------------------------------------------+-----------------------------------------------+
| Tool Name                                   | Unique Identifier                             |
+=============================================+===============================================+
| claude-prediction-offline                   | 6-claude-prediction-offline                   |
+---------------------------------------------+-----------------------------------------------+
| claude-prediction-online                    | 6-claude-prediction-online                    |
+---------------------------------------------+-----------------------------------------------+
| deepmind-optimization                       | 6-deepmind-optimization                       |
+---------------------------------------------+-----------------------------------------------+
```

### Get Tool Description

To get the description of a specific tool, use the `tool-description` command. You need to specify the unique identifier of the tool.

```bash
mechx tool-description <unique_identifier> --chain-config <chain_config>
```
Example usage:

```bash
mechx tool-description "6-claude-prediction-offline" --chain-config gnosis
```
You will see an output like this:
```bash
Description for tool 6-claude-prediction-offline: Makes a prediction using Claude
```


### Get Tool Input/Output Schema

To get the input/output schema of a specific tool, use the `tool_io_schema` command. You need to specify the unique identifier of the tool.

```bash
mechx tool-io-schema <unique_identifier> --chain-config <chain_config>
```

Example usage:

```bash
mechx tool-io-schema "6-prediction-offline" --chain-config gnosis
```
You will see an output like this:
```bash
Tool Details:
+---------------------------+-----------------------------------------------+
| Tool Name                 | Tool Description                              |
+===========================+===============================================+
| OpenAI Prediction Offline | Makes a prediction using OpenAI GPT-3.5 Turbo |
+---------------------------+-----------------------------------------------+
Input Schema:
+-------------+----------------------------------+
| Field       | Value                            |
+=============+==================================+
| type        | text                             |
+-------------+----------------------------------+
| description | The text to make a prediction on |
+-------------+----------------------------------+
Output Schema:
+-----------+---------+-----------------------------------------------+
| Field     | Type    | Description                                   |
+===========+=========+===============================================+
| requestId | integer | Unique identifier for the request             |
+-----------+---------+-----------------------------------------------+
| result    | string  | Result information in JSON format as a string |
+-----------+---------+-----------------------------------------------+
| prompt    | string  | Prompt used for probability estimation.       |
+-----------+---------+-----------------------------------------------+
```

> **:pencil2: Note** <br />
> **If you encounter an "Out of gas" error when executing the Mech Client, you will need to increase the gas limit, e.g.,**
>
> ```bash
> export MECHX_GAS_LIMIT=200000
> ```

### Chain configuration

Default configurations for different chains are stored in the file [configs/mechs.json](./mech_client/configs/mechs.json). If `--chain-config` parameter is not specified, the Mech Client will choose the first configuration on the JSON.

Additionally, you can override any configuration parameter by exporting any of the following environment variables:

```bash
MECHX_CHAIN_RPC
MECHX_WSS_ENDPOINT
MECHX_GAS_LIMIT
MECHX_CONTRACT_ABI_URL
MECHX_TRANSACTION_URL
MECHX_SUBGRAPH_URL

MECHX_LEDGER_ADDRESS
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
    from mech_client.interact import interact, ConfirmationType

    prompt_text = 'Will Gnosis pay reach 100k cards in 2024?'
    agent_id = 6
    tool_name = "prediction-online"
    chain_config = "gnosis"
    private_key_path="ethereum_private_key.txt"

    result = interact(
        prompt=prompt_text,
        agent_id=agent_id,
        tool=tool_name,
        chain_config=chain_config,
        confirmation_type=ConfirmationType.ON_CHAIN,
        private_key_path=private_key_path
    )
    print(result)
    ```

You can also use the Mech Client to programmatically fetch tools for agents in your Python project, as well as retrieve descriptions and input/output schemas for specific tools given their unique identifier.

1. Set up the private key as specified [above](#set-up-the-private-key). Store the resulting key file (e.g., `ethereum_private_key.txt`) in a convenient and secure location.

2. Create a Python script `fetch_tools_script.py`:

    ```bash
    touch fetch_tools_script.py
    ```

3. Edit `fetch_tools_script.py` as follows:

    ```python
    from mech_client.mech_tool_management import get_tools_for_agents, get_tool_description, get_tool_io_schema

    # Fetching tools for a specific agent or all agents
    agent_id = 6  # Specify the agent ID or set to None to fetch tools for all agents
    chain_config = "gnosis"  # Specify the chain configuration
    tools = get_tools_for_agents(agent_id=agent_id, chain_config=chain_config)
    print(f"Tools for agent {agent_id}:", tools)

    # Assuming you know the tool name, construct the unique identifier
    tool_name = "claude-prediction-offline"  # Example tool name
    unique_identifier = f"{agent_id}-{tool_name}"  # Construct the unique identifier

    # Fetching description and I/O schema for a specific tool using the unique identifier
    description = get_tool_description(unique_identifier, chain_config)
    print(f"Description for {unique_identifier}:", description)

    io_schema = get_tool_io_schema(unique_identifier, chain_config)
    print(f"Input/Output Schema for {unique_identifier}:", io_schema)
    ```

This script will:
- Fetch and print the tools available for a specified agent or for all agents if `agent_id` is set to `None`.
- Construct the unique identifier for a tool using the format `agentId-toolName`.
- Retrieve and display the description of a specific tool using its unique identifier.
- Retrieve and display the input and output schema of a specific tool using its unique identifier.

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
- `make eject-packages`
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

<summary><b>Where can I find the agent ID?</b></summary>

You can find the agent IDs for each chain on the [Mech Hub](https://aimechs.autonolas.network/registry) or on the [Mech repository](https://github.com/valory-xyz/mech?tab=readme-ov-file#examples-of-deployed-mechs).

</details>

<details>

<summary><b>How do I access an AI Mech on a different chain?</b></summary>

Use the `--chain-config <name>` parameter together with a valid `<agent_id>`, for example:

```bash
mechx interact "write a short poem" 2 --key ./ethereum_private_key.txt --tool openai-gpt-4 --chain-config celo --confirm on-chain
```

</details>

# Mech Client

A basic client to interact with an AI Mech. [AI Mechs](https://github.com/valory-xyz/mech) allow users to post requests for AI tasks on-chain, and get their result delivered.

> **:warning: Warning** <br />
> **This is a *hacky* alpha version of the client. Don't rely on it as production software.**

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
  interact        Interact with a mech specifying a prompt and tool.
  prompt-to-ipfs  Upload a prompt and tool to IPFS as metadata.
  push-to-ipfs    Upload a file to IPFS.
  to-png          Convert a stability AI API's diffusion model output...
 ```

### Set up the EOA and private key

To use the Mech Client you need an EOA account and its associated private key stored in a text file `ethereum_private_key.txt`. You can set it up in two ways:

- Use the Open AEA command `generate-key`:

  ```bash
  aea generate-key ethereum
  ```

  and display the corresponding EOA:

  ```bash
  python -c "from web3 import Web3; print(Web3().eth.account.from_key(open('ethereum_private_key.txt').read()).address)"
  ```

- Alternatively, use any software of your choice (e.g., [Metamask](https://metamask.io/)) and copy the private key:

  ```bash
  echo -n YOUR_PRIVATE_KEY > ethereum_private_key.txt
  ```

Do not include any leading or trailing spaces, tabs or newlines, or any other character in the file `ethereum_private_key.txt`.

The EOA you use must have enough funds to pay for the Mech requests, or alternatively, use a Nevermined subscription.

> **:warning: Warning** <br />
> * **If the generated EOA account is for development purposes, make sure it does not contain large amounts of funds.**
>
> * **If you store the key file in a local Git repository, we recommend that you add it to `.gitignore` in order to avoid publishing it unintentionally:**
>
>    ```bash
>    echo ethereum_private_key.txt >> .gitignore
>    ```

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
mechx interact "write a short poem" 6 --key ~/ethereum_private_key.txt --tool openai-text-davinci-003 --chain-config gnosis --confirm on-chain
```

In your terminal you will see this as an output:

```bash
Chain configuration: gnosis
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f017012205e37f761221a8ba4005e91c36b94153e9432b8888ff2acae6b101dd5a5de6768
Transaction sent: https://gnosisscan.io/tx/0xf1ef63f617717bbb8deb09699af99aa39f10155d33796de2fd7eb61c9c1458b6
Waiting for transaction receipt...
Created on-chain request with ID 81653153529124597849081567361606842861262371002932574194580478443414142139857
Data arrived: https://gateway.autonolas.tech/ipfs/f0170122069b55e077430a00f3cbc3b069347e901396f978ff160eb2b0a947872be1848b7
Data from agent: {'requestId': 81653153529124597849081567361606842861262371002932574194580478443414142139857, 'result': "\n\nA summer breeze, so sweet,\nA gentle reminder of summer's heat.\nThe sky so blue, no cloud in sight,\nA perfect day, a wondrous sight."}
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

<summary><b>How do I access an AI Mech on a different chains?</b></summary>

Use the `--chain-config <name>` parameter together with a valid `<agent_id>`, for example:

```bash
mechx interact "write a short poem" 2 --key ./ethereum_private_key.txt --tool openai-gpt-4 --chain-config celo --confirm on-chain
```

</details>

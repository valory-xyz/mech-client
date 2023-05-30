# mech-client
Basic client to interact with a mech

> **Warning**<br />
> **This is a hacky alpha version of the client - don't rely on it as production software.**

## Installation

```bash
pip install mech-client
```

Then, set a websocket endpoint for Gnosis RPC like so:

```bash
export WEBSOCKET_ENDPOINT=<YOUR ENDPOINT>
```

## CLI:

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
 ```

## Usage:

First, create a private key in file `ethereum_private_key.txt` with this command:

```bash
aea generate-key ethereum
```

Ensure the private key carries funds on Gnosis Chain.

Second, run the following command to instruct the mech with `<prompt>` and `<tool>`:

```bash
mechx interact <prompt> <tool>
```

Example output:
```bash
mechx interact "write a short poem" "openai-text-davinci-003"
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f01701220ad9e2d5698fbd6c3a4ce61f329590e68a23181772669e543e69decdae316423b
Transaction sent: https://gnosisscan.io/tx/0xb3a17ef90da6cc7a86e008a3a91bd367d573b406eae53405a4aa981001a5eaf3
Request on-chain with id: 15263135923206312300456917202469137903009897852865973093832667165921851537677
Data arrived: https://gateway.autonolas.tech/ipfs/f017012205053a4ae3ef0cf4ed7eff0c2d74dbaf3479fbdeb292472560e7bfaa4cfecfcdc
Data: {'requestId': 15263135923206312300456917202469137903009897852865973093832667165921851537677, 'result': "\n\nA sun-filled sky,\nA soft breeze blowing by,\nWhere the trees sway in the wind,\nA peaceful moment I can't rewind."}
```

## Release guide:

Finish edits, bump versions in `pyproject.toml` and `mech_client/__init__.py`, then `poetry lock`, then `rm -rf dist`, then `poetry publish --build --username=<username> --password=<password>`.
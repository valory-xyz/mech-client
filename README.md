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

Second, run the following command to instruct the mech with `<prompt>` and `<agent_id>`:

```bash
mechx interact <prompt> <agent_id>
```

The command will prompt you with all available tools for the agent and you can select which tool you want to use

```
Select prompting tool
|--------------------------------------------------|
| ID | Tool                                        |
|--------------------------------------------------|
| 0  | openai-text-davinci-002                     |
| ...| ...                                         |
|--------------------------------------------------|
Tool ID > 
```

If you are aware about the tools that are provided by an agent you can directly provide tool as a command line argument

```bash
mechx interact <prompt> <agent_id> --tool <tool>
```

If you already have a funded key file on locally you can provide path the key using `--key` flag.

```bash
mechx interact <prompt> <agent_id> --key <key_file>
```

Example output:
```bash
mechx interact "write a short poem" 3 --key ~/gnosis_key --tool openai-text-davinci-003
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f01701220ad773628911d12e28f005e3f249e990d684e5dba07542259195602f9afed30bf
Transaction sent: https://gnosisscan.io/tx/0x0d9209e32e965a820b9e80accfcd71ea3b1174b9758dd251c2e627a60ec426a5
Created on-chain request with ID 111240237160304797537720810617416341148235899500021985333360197012735240803849
Data arrived: https://gateway.autonolas.tech/ipfs/bafybeifk2h35ncszlze7t64rpblfo45rezc33xzbya3cjiyumtaioyat3e
Data from agent: {'requestId': 111240237160304797537720810617416341148235899500021985333360197012735240803849, 'result': "\n\nI am brave and I'm strong\nI don't hide away my song\nI am here and I'm proud\nMy voice will be heard loud!"}
```

By default the client will wait for data to arrive from on-chain using the websocket subscription and off-chain using the ACN and show you the result which arrives first. You can specify the type of confirmation you want using `--confirm` flag like this

```bash
mechx interact "write a short poem" 3 --key ~/gnosis_key --tool openai-text-davinci-003 --confirm on-chain
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f017012205e37f761221a8ba4005e91c36b94153e9432b8888ff2acae6b101dd5a5de6768
Transaction sent: https://gnosisscan.io/tx/0xf1ef63f617717bbb8deb09699af99aa39f10155d33796de2fd7eb61c9c1458b6
Created on-chain request with ID 81653153529124597849081567361606842861262371002932574194580478443414142139857
Data arrived: https://gateway.autonolas.tech/ipfs/f0170122069b55e077430a00f3cbc3b069347e901396f978ff160eb2b0a947872be1848b7
Data from agent: {'requestId': 81653153529124597849081567361606842861262371002932574194580478443414142139857, 'result': "\n\nA summer breeze, so sweet,\nA gentle reminder of summer's heat.\nThe sky so blue, no cloud in sight,\nA perfect day, a wondrous sight."}
```

## Release guide:

- Bump versions in `pyproject.toml` and `mech_client/__init__.py`
- `poetry lock`
- `rm -rf dist`
- `autonomy packages sync --update-packages`
- `make eject-packages`
- then `poetry publish --build --username=<username> --password=<password>`.
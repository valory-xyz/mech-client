# mech-client
Basic client to interact with a mech

> **Warning**<br />
> **This is a hacky alpha version of the client - don't rely on it as production software.**

Add the mech-client ot your python project.

1. [Installation](#installation)
2. [CLI](#cli)
3. [CLI-Usage](#cli-usage)
4. [Programmatic Usage](#programmatic-usage)
5. [Developer installation](#developer-installation)
6. [release guide](#release-guide)

## Installation

In your project set up the python developement like this:

```bash
poetry new my_project
```

Naviagte into your project

```bash
cd my-project
```

And add the `mech-client` to your project.

```bash
poetry add mech-client
```

Then, set a websocket endpoint for the Celo RPC like so:

```bash
export WEBSOCKET_ENDPOINT="https://rpc.ankr.com/celo"
```

You can find all Celo RPCs in [their documentation](https://docs.celo.org/learn/developer-tools#hosted-nodes).

## CLI:

Play around with the mech tool in your command line. Below you can find an example for [how to add the `mech-client` to your python project](#programmatic-usage):

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

## CLI Usage:

First, you will need to store the private key to your ethereum wallet (make sure it's just for development purposes and doesn't hold a lot of funds). 

You can create it in your home directory, e.g., 

```bash
cd ~
```

```bash
printf "<your-private-key>" > private_key
```

In case you add your own, make sure you don't have any extra characters in the file, like newlines or spaces. For developing purposes make sure not to use a wallet with funds (except for testing) in it.

Second, run the following command to instruct the mech with `<prompt>` and `<agent_id>`:

```bash
mechx interact <prompt> <agent_id>
```
If you are using the key file you have to add `---key` and `<key-file-path>`:

```bash
mechx interact <prompt> <agent_id> --key ~/gnosis_key 
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

Example for a full command using the key file

```bash
mechx interact "write a short poem" 3 --key ~/private_key --tool openai-text-davinci-003
```

In your terminal you will see this as an output:

```bash
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f017012205e37f761221a8ba4005e91c36b94153e9432b8888ff2acae6b101dd5a5de6768
Transaction sent: https://gnosisscan.io/tx/0xf1ef63f617717bbb8deb09699af99aa39f10155d33796de2fd7eb61c9c1458b6
Created on-chain request with ID 81653153529124597849081567361606842861262371002932574194580478443414142139857
Data arrived: https://gateway.autonolas.tech/ipfs/f0170122069b55e077430a00f3cbc3b069347e901396f978ff160eb2b0a947872be1848b7
Data from agent: {'requestId': 81653153529124597849081567361606842861262371002932574194580478443414142139857, 'result': "\n\nA summer breeze, so sweet,\nA gentle reminder of summer's heat.\nThe sky so blue, no cloud in sight,\nA perfect day, a wondrous sight."}
```

By default the client will wait for data to arrive from on-chain using the websocket subscription and off-chain using the ACN and show you the result which arrives first. You can specify the type of confirmation you want using `--confirm` flag like this. 

```bash
mechx interact "write a short poem" 3 --key ~/private_key --tool openai-text-davinci-003 --confirm on-chain
```

In your terminal you will see this as an output:

```bash
Prompt uploaded: https://gateway.autonolas.tech/ipfs/f017012205e37f761221a8ba4005e91c36b94153e9432b8888ff2acae6b101dd5a5de6768
Transaction sent: https://gnosisscan.io/tx/0xf1ef63f617717bbb8deb09699af99aa39f10155d33796de2fd7eb61c9c1458b6
Created on-chain request with ID 81653153529124597849081567361606842861262371002932574194580478443414142139857
Data arrived: https://gateway.autonolas.tech/ipfs/f0170122069b55e077430a00f3cbc3b069347e901396f978ff160eb2b0a947872be1848b7
Data from agent: {'requestId': 81653153529124597849081567361606842861262371002932574194580478443414142139857, 'result': "\n\nA summer breeze, so sweet,\nA gentle reminder of summer's heat.\nThe sky so blue, no cloud in sight,\nA perfect day, a wondrous sight."}
```

## Programmatic Usage:
Let's look at how to use the mech-client in your python project.

First let's create our `project.py` file inside of our python project

```bash
touch project.py
```

Now we need to set up the PRIVATE_KEY in our local environment. For that we create a `.env` file. And add our private key there. 

```bash
touch .env
```

It should look like this

```bash
0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcd
```

Before you do anything else, make sure your project has a `.gitignore` file where you add the `.env` file. Even tough you should not be using a wallet with real funds, you don't want to end up pushing your private key to GitHub.

Now we can interact with the mech-client:

```python
from mech_client.interact import interact, ConfirmationType

prompt_text = 'Will gnosis pay reach 100k cards in 2024?'
agent_id = 3
tool_name = "prediction-online"

result = interact(
    prompt=prompt_text,
    agent_id=agent_id,
    tool=tool_name,
    confirmation_type=ConfirmationType.ON_CHAIN,
    private_key_path='./.env'
)
print(result)
```

## Developer installation
To setup the development environment for this project, run the following commands:

```bash
poetry install && poetry shell
```

## Release guide:

- Bump versions in `pyproject.toml` and `mech_client/__init__.py`
- `poetry lock`
- `rm -rf dist`
- `autonomy packages sync --update-packages`
- `make eject-packages`
- then create release PR and tag release

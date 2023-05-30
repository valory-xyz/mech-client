import click

from mech_client import __version__
from mech_client.interact import interact as interact_
from mech_client.prompt_to_ipfs import main as prompt_to_ipfs_main
from mech_client.push_to_ipfs import main as push_to_ipfs_main


@click.group(name="mechx")  # type: ignore
@click.version_option(__version__, prog_name="mechx")
def cli() -> None:
    """Command-line tool for interacting with mechs."""


@click.command()
@click.argument("prompt")
@click.argument("tool")
def interact(prompt: str, tool: str) -> None:
    """Interact with a mech specifying a prompt and tool."""
    interact_(prompt=prompt, tool=tool)


@click.command()
@click.argument("prompt")
@click.argument("tool")
def prompt_to_ipfs(prompt: str, tool: str) -> None:
    """Upload a prompt and tool to IPFS as metadata."""
    prompt_to_ipfs_main(prompt=prompt, tool=tool)


@click.command()
@click.argument("file_path")
def push_to_ipfs(file_path: str) -> None:
    """Upload a file to IPFS."""
    push_to_ipfs_main(file_path=file_path)


cli.add_command(interact)
cli.add_command(prompt_to_ipfs)
cli.add_command(push_to_ipfs)


if __name__ == "__main__":
    cli()

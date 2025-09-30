from typing import Optional

from safe_eth.eth import EthereumClient  # pylint:disable=import-error
from safe_eth.safe import Safe  # pylint:disable=import-error
from web3.constants import ADDRESS_ZERO


def send_safe_tx(
    ethereum_client: EthereumClient,
    tx_data: str,
    to_adress: str,
    safe_address: str,
    signer_pkey: str,
    value: int = 0,
) -> Optional[str]:
    """Send a Safe transaction"""
    # Get the safe
    safe = Safe(  # pylint:disable=abstract-class-instantiated
        safe_address, ethereum_client
    )

    estimated_gas = safe.estimate_tx_gas_with_safe(
        to=to_adress, value=value, data=bytes.fromhex(tx_data[2:]), operation=0
    )

    # Build, sign and send the safe transaction
    safe_tx = safe.build_multisig_tx(
        to=to_adress,
        value=value,
        data=bytes.fromhex(tx_data[2:]),
        operation=0,
        safe_tx_gas=estimated_gas,
        base_gas=0,
        gas_price=0,
        gas_token=ADDRESS_ZERO,
        refund_receiver=ADDRESS_ZERO,
    )
    safe_tx.sign(signer_pkey)
    try:
        tx_hash, _ = safe_tx.execute(signer_pkey)
        return tx_hash
    except Exception as e:
        print(f"Exception while sending a safe transaction: {e}")
        return False


def get_safe_nonce(ethereum_client: EthereumClient, safe_address: str) -> int:
    """Get the Safe nonce"""
    safe = Safe(  # pylint:disable=abstract-class-instantiated
        safe_address, ethereum_client
    )
    return safe.retrieve_nonce()

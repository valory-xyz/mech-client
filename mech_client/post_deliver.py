# -*- coding: utf-8 -*-

"""Deliver via Gnosis Safe using RRS logic, adapted for the mech client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.contract import Contract as Web3Contract

import base64
from multibase import multibase
from multicodec import multicodec

from mech_client.interact import get_mech_config


REGISTRY_ADD_URL = "https://registry.autonolas.tech/api/v0/add"


def _load_abi_file(abi_path: Path) -> Optional[list]:
    try:
        with open(abi_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "abi" in data:
            return data["abi"]
        if isinstance(data, list):
            return data
    except Exception:
        return None
    return None


def _extract_sha256_digest_from_cid(cid_str: str) -> bytes:
    """Extract sha256 digest from CID (supports CIDv0 and CIDv1)."""
    if cid_str.startswith("Qm"):
        # CIDv0 base58
        try:
            import base58  # type: ignore
        except ImportError as e:
            raise ValueError("base58 library required for CIDv0 support. Install with: pip install base58") from e
        multihash_bytes = base58.b58decode(cid_str)
    else:
        # CIDv1 base32 (starts with 'b')
        b32 = cid_str.lower()
        if b32.startswith('b'):
            b32 = b32[1:]
        pad_len = (-len(b32)) % 8
        b32_padded = b32.upper() + ('=' * pad_len)
        cid_bytes = base64.b32decode(b32_padded)

        # Skip CIDv1 prefix (0x01) and consume varint codec
        idx = 0
        if idx < len(cid_bytes) and cid_bytes[idx] == 0x01:
            idx += 1
        while idx < len(cid_bytes):
            byte = cid_bytes[idx]
            idx += 1
            if (byte & 0x80) == 0:
                break
        if idx >= len(cid_bytes):
            raise ValueError("CID too short after skipping prefixes")
        multihash_bytes = cid_bytes[idx:]

    if len(multihash_bytes) < 34:
        raise ValueError("Multihash too short")
    code = multihash_bytes[0]
    length = multihash_bytes[1]
    if code != 0x12 or length != 32:
        raise ValueError(f"Unexpected multihash code/length: code=0x{code:02x} len={length}")
    return multihash_bytes[2:34]


def _upload_to_autonolas_registry(content: Dict[str, Any], request_id_for_log: str) -> Optional[str]:
    """Upload JSON content to Autonolas registry IPFS (wrap-with-directory) and return directory CID."""
    files = {"file": (request_id_for_log, json.dumps(content, ensure_ascii=False).encode("utf-8"), "application/json")}
    params = {"pin": "true", "cid-version": "1", "wrap-with-directory": "true"}
    resp = requests.post(REGISTRY_ADD_URL, files=files, params=params, timeout=60)
    if resp.status_code != 200:
        return None
    # Response is NDJSON, last line has directory CID
    last_hash = None
    for line in resp.text.strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            last_hash = entry.get("Hash") or last_hash
        except json.JSONDecodeError:
            continue
    return last_hash


def _to_bytes32_from_int(value: int) -> bytes:
    return value.to_bytes(32, byteorder="big")


def _normalize_request_id_to_int(request_id: str) -> int:
    request_id = request_id.strip()
    if request_id.startswith("0x") or request_id.startswith("0X"):
        return int(request_id, 16)
    return int(request_id, 10)


def _get_web3_http(chain_config: str, rpc_http_url: Optional[str] = None) -> Web3:
    mech_config = get_mech_config(chain_config)
    rpc_url = rpc_http_url or mech_config.rpc_url
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Failed to connect to RPC {rpc_url}")
    return w3


def _get_agent_mech_contract(w3: Web3, target_mech_address: str) -> Web3Contract:
    # Only use the mech_client ABI location
    abi_path = Path(__file__).parent / "abis" / "AgentMech.json"
    abi = _load_abi_file(abi_path)
    if not abi:
        raise RuntimeError("AgentMech ABI not found or invalid at mech_client/abis/AgentMech.json")
    try:
        names = {entry.get("name") for entry in abi if isinstance(entry, dict)}
    except Exception:
        names = set()
    if "deliverToMarketplace" not in names:
        raise RuntimeError("AgentMech ABI does not contain deliverToMarketplace function")
    return w3.eth.contract(address=Web3.to_checksum_address(target_mech_address), abi=abi)


def _get_gnosis_safe_contract(w3: Web3, safe_address: str) -> Web3Contract:
    abi_path = Path(__file__).parent / "abis" / "GnosisSafe_v1.3.0.json"
    abi = _load_abi_file(abi_path)
    if not abi:
        raise RuntimeError("Gnosis Safe ABI not found or invalid")
    return w3.eth.contract(address=Web3.to_checksum_address(safe_address), abi=abi)


def _encode_agent_mech_deliver_call(agent_mech: Web3Contract, request_id_dec_str: str, result_digest_bytes: bytes) -> bytes:
    request_id_int = _normalize_request_id_to_int(request_id_dec_str)
    request_id_bytes32 = _to_bytes32_from_int(request_id_int)
    data_hex = agent_mech.functions.deliverToMarketplace([request_id_bytes32], [result_digest_bytes])._encode_transaction_data()  # type: ignore
    return Web3.to_bytes(hexstr=data_hex)


def deliver_via_safe(
    *,
    chain_config: str,
    request_id: str,
    result_content: Dict[str, Any],
    target_mech_address: str,
    safe_address: str,
    private_key_path: Optional[str] = None,
    private_key: Optional[str] = None,
    rpc_http_url: Optional[str] = None,
    wait: bool = True,
) -> Dict[str, Any]:
    """Upload result to registry IPFS, then submit AgentMech.deliverToMarketplace via Gnosis Safe."""

    # Upload to IPFS registry
    cid = _upload_to_autonolas_registry(result_content, request_id_for_log=request_id)
    if not cid:
        raise RuntimeError("IPFS registry upload failed")
    # Include CID in result for downstream consumers/tests and for parity with TS client logs

    # Derive raw digest bytes from CID
    digest_bytes = _extract_sha256_digest_from_cid(cid)

    # Web3 setup
    w3 = _get_web3_http(chain_config, rpc_http_url)
    chain_id = w3.eth.chain_id

    # Contracts
    agent_mech = _get_agent_mech_contract(w3, target_mech_address)
    safe = _get_gnosis_safe_contract(w3, safe_address)

    # Build AgentMech call data
    inner_call_data = _encode_agent_mech_deliver_call(agent_mech, request_id, digest_bytes)

    # Prepare Safe getTransactionHash params
    params_for_hash = {
        "to": Web3.to_checksum_address(target_mech_address),
        "value": 0,
        "data": inner_call_data,
        "operation": 0,  # CALL
        "safeTxGas": 0,
        "baseGas": 0,
        "gasPrice": 0,
        "gasToken": Web3.to_checksum_address("0x0000000000000000000000000000000000000000"),
        "refundReceiver": Web3.to_checksum_address("0x0000000000000000000000000000000000000000"),
        "_nonce": safe.functions.nonce().call(),
    }

    # Compute hash to sign
    tx_hash_to_sign: bytes = safe.functions.getTransactionHash(
        params_for_hash["to"],
        params_for_hash["value"],
        params_for_hash["data"],
        params_for_hash["operation"],
        params_for_hash["safeTxGas"],
        params_for_hash["baseGas"],
        params_for_hash["gasPrice"],
        params_for_hash["gasToken"],
        params_for_hash["refundReceiver"],
        params_for_hash["_nonce"],
    ).call()

    # Sign with EOA private key (eth_sign semantics)
    if private_key is not None:
        pk = private_key.strip()
    elif private_key_path is not None:
        with open(private_key_path, "r", encoding="utf-8") as f:
            pk = f.read().strip()
    else:
        raise RuntimeError("Either private_key or private_key_path must be provided")
    signer: LocalAccount = Account.from_key(pk)
    checksum_sender = Web3.to_checksum_address(signer.address)

    signed_msg = signer.sign_message(encode_defunct(primitive=tx_hash_to_sign))
    v_adjusted = signed_msg.v + 4  # Safe expects eth_sign marker
    signature = (
        signed_msg.r.to_bytes(32, "big")
        + signed_msg.s.to_bytes(32, "big")
        + v_adjusted.to_bytes(1, "big")
    )

    # Encode execTransaction
    exec_data_hex = safe.functions.execTransaction(
        params_for_hash["to"],
        params_for_hash["value"],
        params_for_hash["data"],
        params_for_hash["operation"],
        params_for_hash["safeTxGas"],
        params_for_hash["baseGas"],
        params_for_hash["gasPrice"],
        params_for_hash["gasToken"],
        params_for_hash["refundReceiver"],
        signature,
    )._encode_transaction_data()  # type: ignore

    tx_payload: Dict[str, Any] = {
        "to": safe.address,
        "from": checksum_sender,
        "value": 0,
        "data": Web3.to_bytes(hexstr=exec_data_hex),
        "chainId": chain_id,
    }

    # Nonce, gas, fees
    tx_payload["nonce"] = w3.eth.get_transaction_count(checksum_sender)

    # Estimate gas
    gas_estimate = w3.eth.estimate_gas(tx_payload)
    tx_payload["gas"] = gas_estimate

    latest_block = w3.eth.get_block("latest")
    base_fee = latest_block.get("baseFeePerGas")
    if base_fee is not None:
        try:
            priority = w3.eth.max_priority_fee
        except Exception:
            priority = int(1.5e9)
        tx_payload["maxPriorityFeePerGas"] = priority
        tx_payload["maxFeePerGas"] = base_fee * 2 + priority
    else:
        tx_payload["gasPrice"] = w3.eth.gas_price

    # Sign & send
    signed_tx = w3.eth.account.sign_transaction(tx_payload, private_key=pk)
    tx_hash = w3.eth.send_raw_transaction(getattr(signed_tx, "raw_transaction", getattr(signed_tx, "rawTransaction")))

    result: Dict[str, Any] = {"tx_hash": tx_hash.hex(), "status": "submitted", "cid": cid}
    if wait:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        if receipt and receipt.status == 1:
            result.update({"status": "confirmed", "block_number": receipt.blockNumber, "gas_used": receipt.gasUsed})
        elif receipt:
            result.update({"status": "reverted", "block_number": receipt.blockNumber, "gas_used": receipt.gasUsed})
        else:
            result.update({"status": "unknown"})
    return result



from web3 import Web3
from eth_account._utils.legacy_transactions import Transaction

raw = "0x02f901926481ac8459682f008459682f22835b8d8094735faab1c4ec41128c367afb5c3bac73509f70bb01b90124f6938b0900000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000002386f26fc10000ba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1000000000000000000000000601024e27f1c67b28209e24272ced8a31fc8151f000000000000000000000000000000000000000000000000000000000000012c00000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000000020fb609758a77f2daa652c8c16388bb06aacc30eda67aa4678c4e4f4066129ad8c0000000000000000000000000000000000000000000000000000000000000000c001a0566a523f94289282edd93dc717ff10a0270f4befda0282c3907b4f7e7a4df3f6a069d7718a33b8332bc75174059ee0efdeff901c69cefb85cafd6b5c2c01ad39cf"  # your full hex here

# 1) Strip the 0x and turn into bytes
raw_bytes = bytes.fromhex(raw[2:])

# 2) Parse it
tx = Transaction.deserialize(raw_bytes)

# 3) Pretty‑print
print(f"Type:            {tx.type}")                                # 2
print(f"Chain ID:        {tx.chainId}")                            # e.g. 100 for Gnosis
print(f"Nonce:           {tx.nonce}")
print(f"MaxFeePerGas:    {tx.maxFeePerGas}")
print(f"MaxPriorityFee:  {tx.maxPriorityFeePerGas}")
print(f"Gas Limit:       {tx.gas}")
print(f"To:              {tx.to.hex()}")
print(f"Value:           {tx.value}")
print(f"Data (length):   {len(tx.data)} bytes")
print(f"v, r, s:         {tx.v}, {tx.r}, {tx.s}")

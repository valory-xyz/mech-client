payment_data # unused variable (mech_client/interact.py:111)
principal_chain # unused variable (mech_client/cli.py:201)
configure_local_config # unused variable (mech_client/cli.py:306)
verify_tools # unused function
get_native_balance_tracker_contract # unused function (mech_client/marketplace_interact.py:1149) - used by deposits.py
get_token_balance_tracker_contract # used by deposits.py
get_token_contract # used by deposits.py
get_abi # unused function (mech_client/interact.py:154) - kept for potential future use

# CLI command functions (used via Click decorators)
request # CLI command function
mech_list # CLI command function
tool_list # CLI command function
tool_describe # CLI command function
tool_schema # CLI command function
subscription_purchase # CLI command function
ipfs_upload # CLI command function
ipfs_upload_prompt # CLI command function
ipfs_to_png # CLI command function

# Existing entries...
send_marketplace_request_nonblocking  # used in tests/locustfile.py
delivery_consumer_loop_status_only    # used in tests/locustfile.py

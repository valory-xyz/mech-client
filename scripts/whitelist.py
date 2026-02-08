# Vulture whitelist for mech-client
# This file contains intentional "unused" code that should not be flagged

# CLI command parameters (reserved for future functionality)
retries  # CLI parameter in request_cmd.py - reserved for retry logic
sleep  # CLI parameter in request_cmd.py - reserved for retry delay

# Public API methods (service layer interfaces)
watch_for_data_urls  # OnchainDeliveryWatcher method - used in specific delivery scenarios
ToolSchema  # Data model class - used for type hints and validation
fetch_ipfs_hash  # IPFS utility - public API for external use
get_abi_path  # ABI loader utility - public API for path resolution
estimate_gas  # SafeClient method - reserved for gas estimation feature
is_native  # PaymentConfig helper method - payment type checking
is_nvm  # PaymentConfig helper method - payment type checking
download  # IPFSClient method - reserved for direct download functionality
is_initialized  # OperateManager method - state checking utility
SubscriptionService  # Service class - subscription management interface
purchase_subscription  # SubscriptionService method - NVM subscription purchase

# Validation utilities (now used in CLI commands)
validate_payment_type  # Payment type validator - public validation API
validate_chain_support  # Chain support validator - public validation API
validate_ipfs_hash  # IPFS hash validator - public validation API

# CLI command functions (invoked via Click decorators)
ipfs_upload  # IPFS upload command
ipfs_upload_prompt  # IPFS prompt upload command
mech_list  # List mechs command
subscription_purchase  # Purchase subscription command
tool_list  # List tools command
tool_describe  # Describe tool command
tool_schema  # Tool schema command

# Service methods (public API)
principal_chain  # SetupService attribute - chain configuration
get_description  # ToolService method - tool description getter
get_schema  # ToolService method - tool schema getter
get_tools_info  # ToolService method - complete tool info getter
format_input_schema  # ToolService method - input schema formatter
format_output_schema  # ToolService method - output schema formatter

# Infrastructure utilities
payment_data  # ChainConfig attribute - payment configuration data

# NVM Config dataclass fields (used by dataclass, marked as unused by vulture)
network_name  # NVMConfig field - network identifier
receiver_plan  # NVMConfig field - plan receiver address
web3_provider_uri  # NVMConfig field - Web3 provider URI (overridden by MECHX_CHAIN_RPC)
marketplace_uri  # NVMConfig field - NVM marketplace URI
nevermined_node_uri  # NVMConfig field - Nevermined node URI
nevermined_node_address  # NVMConfig field - Nevermined node address
etherscan_url  # NVMConfig field - block explorer URL
native_token  # NVMConfig field - native token symbol
get_marketplace_fee  # NeverminedConfigContract method - reserved for marketplace fee query

# Constants (configuration and infrastructure)
TRANSACTION_CONFIRMATION_BLOCKS  # Blocks to wait for confirmation
IPFS_CID_V0_PREFIX  # IPFS CIDv0 format prefix
IPFS_CID_V1_PREFIX  # IPFS CIDv1 format prefix
IPFS_HEX_PREFIX  # IPFS hex format prefix
DELIVERY_DATA_INDEX  # Index for delivery data in contract events
SUPPORTED_MARKETPLACE_CHAINS  # List of supported marketplace chains
NVM_SUPPORTED_CHAINS  # List of NVM-supported chains
CHAIN_ID_TO_NAME  # Mapping from chain ID to chain name
CHAIN_NAME_TO_ID  # Mapping from chain name to chain ID
SAFE_VERSION  # Safe multisig version
SAFE_TX_GAS_BUFFER  # Gas buffer for Safe transactions
REQUEST_TYPE_SINGLE  # Single request type constant
REQUEST_TYPE_BATCH  # Batch request type constant
PAYMENT_METHOD_NAMES  # Mapping of payment types to display names
TOOL_FIELD_NAME  # Tool metadata field: name
TOOL_FIELD_DESCRIPTION  # Tool metadata field: description
TOOL_FIELD_INPUT  # Tool metadata field: input schema
TOOL_FIELD_OUTPUT  # Tool metadata field: output schema
TOOL_FIELD_TOOLS  # Tool metadata field: tools list
TOOL_FIELD_TOOL_NAME  # Tool metadata field: tool name
METADATA_FIELD_HASH  # Metadata field: IPFS hash
METADATA_FIELD_SERVICE_ID  # Metadata field: service ID
METADATA_FIELD_DELIVERIES  # Metadata field: delivery count
EVENT_DELIVER  # Contract event: Deliver
EVENT_REQUEST  # Contract event: Request
EVENT_DEPOSIT  # Contract event: Deposit

# Error message methods (error formatting utilities)
missing_env_var  # ErrorMessages method - missing environment variable formatter
chain_not_supported  # ErrorMessages method - unsupported chain formatter
insufficient_balance  # ErrorMessages method - insufficient balance formatter
agent_mode_not_setup  # ErrorMessages method - agent mode setup formatter
tool_not_found  # ErrorMessages method - tool not found formatter
delivery_timeout  # ErrorMessages method - delivery timeout formatter
private_key_error  # ErrorMessages method - private key error formatter

# ANSI color constants (terminal output styling)
BLACK  # ANSI color code
BLUE  # ANSI color code
MAGENTA  # ANSI color code
CYAN  # ANSI color code
BG_BLACK  # ANSI background color code
BG_RED  # ANSI background color code
BG_GREEN  # ANSI background color code
BG_YELLOW  # ANSI background color code
BG_BLUE  # ANSI background color code

# Reserved attributes (not yet implemented)
delivery_rate  # ChainConfig attribute - reserved for rate limiting
response_timeout  # ChainConfig attribute - reserved for timeout configuration
ipfs_client  # MarketplaceService attribute - reserved for future IPFS operations

# Infrastructure constants (configuration and utilities)
IPFS_GATEWAY_URL  # IPFS gateway URL for retrieving files
DEFAULT_MAX_RETRIES  # Default retry count for operations
DEFAULT_GAS_LIMIT  # Default gas limit for transactions
TEMPLATES_DIR_NAME  # Directory name for templates
TEMPLATE_GNOSIS  # Template name for Gnosis chain
TEMPLATE_BASE  # Template name for Base chain
TEMPLATE_POLYGON  # Template name for Polygon chain
TEMPLATE_OPTIMISM  # Template name for Optimism chain

# Logger utilities (public API)
get_logger  # Logger factory - public API for module loggers
set_log_level  # Logger configuration - public API for log level control
log_transaction  # Transaction logger - public API for transaction logging
log_request  # Request logger - public API for request logging
log_delivery  # Delivery logger - public API for delivery logging

# Test/stress test utilities
send_marketplace_request_nonblocking  # Used in stress_tests/locustfile.py
delivery_consumer_loop_status_only  # Used in stress_tests/locustfile.py

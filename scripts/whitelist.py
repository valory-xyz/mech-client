# Vulture whitelist for mech-client
# This file contains intentional "unused" code that should not be flagged

# CLI command parameters (reserved for future functionality)
retries  # CLI parameter in request_cmd.py - reserved for retry logic
sleep  # CLI parameter in request_cmd.py - reserved for retry delay

# Public API methods (service layer interfaces)
get_from_ipfs  # IPFSClient helper - used by converters.ipfs_to_png()
watch_for_data_urls  # OnchainDeliveryWatcher method - used in specific delivery scenarios
ToolSchema  # Data model class - used for type hints and validation
fetch_ipfs_hash  # IPFS utility - public API for external use
get_abi_path  # ABI loader utility - public API for path resolution
estimate_gas  # SafeClient method - reserved for gas estimation feature
send_safe_tx  # Safe transaction helper - used by agent executor
get_safe_nonce  # Safe nonce helper - used by agent executor
delivery_rate  # ChainConfig attribute - reserved for rate limiting
response_timeout  # ChainConfig attribute - reserved for timeout configuration
IPFS_GATEWAY_URL  # Config constant - alternative IPFS gateway
is_native  # PaymentConfig helper method - payment type checking
is_nvm  # PaymentConfig helper method - payment type checking
download  # IPFSClient method - reserved for direct download functionality
is_initialized  # OperateManager method - state checking utility
ipfs_client  # MarketplaceService attribute - reserved for future IPFS operations
SubscriptionService  # Service class - subscription management interface
purchase_subscription  # SubscriptionService method - NVM subscription purchase
check_subscription_status  # SubscriptionService method - subscription status checking
list_tools  # ToolService method - public API for tool listing

# Validation utilities (public API for input validation)
validate_payment_type  # Payment type validator - public validation API
validate_service_id  # Service ID validator - public validation API
validate_ipfs_hash  # IPFS hash validator - public validation API
validate_chain_support  # Chain support validator - public validation API
validate_batch_sizes_match  # Batch size validator - public validation API
validate_timeout  # Timeout validator - public validation API
validate_extra_attributes  # Extra attributes validator - public validation API

# Logging utilities (public API for structured logging)
BG_BLUE  # ANSI color constant - reserved for future colored output
get_logger  # Logger getter - public API for getting named loggers
set_log_level  # Log level setter - public logging configuration API
log_transaction  # Transaction logger - public logging API
log_request  # Request logger - public logging API
log_delivery  # Delivery logger - public logging API

# CLI command functions (invoked via Click decorators)
ipfs_upload  # IPFS upload command
ipfs_upload_prompt  # IPFS prompt upload command
ipfs_to_png  # IPFS to PNG conversion command
mech_list  # List mechs command
subscription_purchase  # Purchase subscription command
tool_list  # List tools command
tool_describe  # Describe tool command
tool_schema  # Tool schema command

# Service methods (public API)
configure_local_config  # SetupService method - configuration helper
principal_chain  # SetupService attribute - chain configuration
get_description  # ToolService method - tool description getter
get_schema  # ToolService method - tool schema getter
get_tools_info  # ToolService method - complete tool info getter
format_input_schema  # ToolService method - input schema formatter
format_output_schema  # ToolService method - output schema formatter

# Infrastructure utilities
payment_data  # ChainConfig attribute - payment configuration data
ipfs_to_png  # IPFSConverters function - IPFS to PNG converter

# Constants (configuration and infrastructure)
CLI_NAME  # Application name constant
DEFAULT_WAIT_SLEEP  # Default sleep interval for polling
DEFAULT_MAX_RETRIES  # Default maximum retry attempts
DEFAULT_GAS_LIMIT  # Default gas limit for transactions
TRANSACTION_CONFIRMATION_BLOCKS  # Blocks to wait for confirmation
IPFS_CID_V0_PREFIX  # IPFS CIDv0 format prefix
IPFS_CID_V1_PREFIX  # IPFS CIDv1 format prefix
IPFS_HEX_PREFIX  # IPFS hex format prefix
DELIVERY_DATA_INDEX  # Index for delivery data in contract events
DECIMALS_18  # 18-decimal token precision
DECIMALS_6  # 6-decimal token precision
ADDRESS_DISPLAY_LENGTH  # Display length for addresses
IPFS_HASH_DISPLAY_LENGTH  # Display length for IPFS hashes
TX_HASH_DISPLAY_LENGTH  # Display length for transaction hashes
SUCCESS_SYMBOL  # Success output symbol
ERROR_SYMBOL  # Error output symbol
WARNING_SYMBOL  # Warning output symbol
INFO_SYMBOL  # Info output symbol
SUPPORTED_MARKETPLACE_CHAINS  # List of supported marketplace chains
NVM_SUPPORTED_CHAINS  # List of NVM-supported chains
ENV_CHAIN_RPC  # Environment variable name for RPC URL
ENV_SUBGRAPH_URL  # Environment variable name for subgraph URL
ENV_MECH_OFFCHAIN_URL  # Environment variable name for offchain URL
ENV_GAS_LIMIT  # Environment variable name for gas limit
ENV_OPERATE_PASSWORD  # Environment variable name for operate password
CONFIG_DIR_NAME  # Configuration directory name
ABI_DIR_NAME  # ABI directory name
TEMPLATES_DIR_NAME  # Templates directory name
TEMPLATE_GNOSIS  # Gnosis service template path
TEMPLATE_BASE  # Base service template path
TEMPLATE_POLYGON  # Polygon service template path
TEMPLATE_OPTIMISM  # Optimism service template path
MIN_SERVICE_ID  # Minimum valid service ID
MAX_TOOL_ID_LENGTH  # Maximum tool ID string length
MIN_AMOUNT  # Minimum transaction amount
MAX_BATCH_SIZE  # Maximum batch request size
HTTP_REQUEST_TIMEOUT  # HTTP request timeout in seconds
HTTP_DOWNLOAD_TIMEOUT  # HTTP download timeout in seconds
DEFAULT_LOG_LEVEL  # Default logging level
VALID_LOG_LEVELS  # List of valid log levels
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
HINT_CHECK_RPC  # Error hint: check RPC endpoint
HINT_CHECK_BALANCE  # Error hint: check balance
HINT_CHECK_APPROVAL  # Error hint: check token approval
HINT_CHECK_NETWORK  # Error hint: check network connection
HINT_CHECK_ADDRESS  # Error hint: check address format
HINT_SET_ENV_VAR  # Error hint: set environment variable
HINT_RUN_SETUP  # Error hint: run setup command

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

# Test/stress test utilities
send_marketplace_request_nonblocking  # Used in stress_tests/locustfile.py
delivery_consumer_loop_status_only  # Used in stress_tests/locustfile.py

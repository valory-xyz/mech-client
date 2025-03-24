from scripts.nvm_subscription.manager import NVMSubscriptionManager
import os

def main():
    PLAN_DID = os.environ.get('PLAN_DID')
    NETWORK=os.environ.get('NETWORK_NAME', 'GNOSIS')
    WALLET_PVT_KEY = os.environ.get('WALLET_PVT_KEY')
    CHAIN_ID = int(os.environ.get('CHAIN_ID', 100))

    if not WALLET_PVT_KEY:
        raise ValueError("WALLET_PVT_KEY environment variable is not set")
    if not PLAN_DID:
        raise ValueError("PLAN_DID environment variable is not set")

    manager = NVMSubscriptionManager(NETWORK)
    tx_receipt = manager.create_subscription(PLAN_DID, WALLET_PVT_KEY, CHAIN_ID)

    print("Subscription created successfully")
    print(tx_receipt)

if __name__ == '__main__':
    main()

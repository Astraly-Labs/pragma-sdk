"""
Taken from starknet_py tests :
https://github.com/software-mansion/starknet.py/blob/0243f05ebbefc59e1e71d4aee3801205a7783645/starknet_py/tests/e2e/contract_interaction/v1_interaction_test.py
"""

from typing import Tuple

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair

from tests.integration.constants import (
    DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
    DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
    TESTNET_ACCOUNT_ADDRESS,
    TESTNET_ACCOUNT_PRIVATE_KEY,
)

load_dotenv()


@pytest_asyncio.fixture(scope="function")
async def address_and_private_key(
    pytestconfig,
) -> Tuple[str, str]:
    """
    Returns address and private key of an account, depending on the network.
    """
    net = pytestconfig.getoption("--net")

    account_details = {
        "devnet": (
            DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
            DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        ),
        "sepolia": (
            TESTNET_ACCOUNT_ADDRESS,
            TESTNET_ACCOUNT_PRIVATE_KEY,
        ),
    }
    return account_details[net]


@pytest.fixture(scope="function")
def account(address_and_private_key: Tuple[str, str], client: FullNodeClient) -> Account:
    """
    Returns a new Account created with FullNodeClient.
    """

    address, private_key = address_and_private_key

    return Account(
        address=address,
        client=client,
        key_pair=KeyPair.from_private_key(int(private_key, 0)),
        chain=StarknetChainId.MAINNET,
    )


@pytest.fixture(scope="function")
def pre_deployed_account_with_validate_deploy(pytestconfig, network: str) -> Account:
    """
    Returns an Account pre-deployed on specified network. Used to deploy other accounts.
    """
    address_and_priv_key = {
        "devnet": (
            DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
            DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        ),
        "sepolia": (
            TESTNET_ACCOUNT_ADDRESS,
            TESTNET_ACCOUNT_PRIVATE_KEY,
        ),
    }

    net = pytestconfig.getoption("--net")
    address, private_key = address_and_priv_key[net]
    return Account(
        address=address,
        client=FullNodeClient(node_url=network),
        key_pair=KeyPair.from_private_key(int(private_key, 16)),
        chain=StarknetChainId.MAINNET,
    )

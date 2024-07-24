import pytest
import pytest_asyncio

from typing import Tuple, Dict, Any
from urllib.parse import urlparse

from starknet_py.contract import Contract
from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.onchain.types import (
    ContractAddresses,
)

from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


@pytest.fixture(
    scope="function",
)
def client(network: str) -> FullNodeClient:
    """
    Returns Client instances.
    """
    return FullNodeClient(node_url=network)


@pytest.fixture(scope="function")
def network_config(request: pytest.FixtureRequest) -> Dict[str, Any]:
    """
    Fixture to provide network configuration.
    """
    return {
        "network": getattr(request, "param", {}).get("network", "mainnet"),
        "account_address": getattr(request, "param", {}).get(
            "account_address",
            "0x02356b628D108863BAf8644c945d97bAD70190AF5957031f4852d00D0F690a77",
        ),
        "block_number": getattr(request, "param", {}).get("block_number", None),
    }


@pytest_asyncio.fixture(scope="function", name="pragma_client")
async def pragma_client(
    deploy_oracle_contracts: Tuple[Contract, Contract],
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaOnChainClient:
    (oracle, publisher_registry) = deploy_oracle_contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    client = PragmaOnChainClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=publisher_registry.address,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=0x0,
        ),
        port=port,
    )
    return client

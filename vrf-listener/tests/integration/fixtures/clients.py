import pytest
import pytest_asyncio

from typing import Tuple, Dict, Any
from urllib.parse import urlparse

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.onchain.abis.abi import get_erc20_abi
from pragma_sdk.onchain.types import (
    ContractAddresses,
)
from tests.integration.constants import (
    FEE_TOKEN_ADDRESS,
)

# from pragma_sdk.onchain.client import PragmaOnChainClient
from tests.integration.utils import ExtendedPragmaClient
from tests.integration.utils import read_contract

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


@pytest_asyncio.fixture(scope="function")
async def declare_deploy_randomness(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract = read_contract("pragma_Randomness.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Randomness.casm.json", directory=None)

    compiled_example_contract = read_contract(
        "pragma_ExampleRandomness.sierra.json", directory=None
    )
    compiled_example_contract_casm = read_contract(
        "pragma_ExampleRandomness.casm.json", directory=None
    )

    compiled_oracle_mock_contract = read_contract("pragma_MockOracle.sierra.json", directory=None)
    compiled_oracle_mock_contract_casm = read_contract(
        "pragma_MockOracle.casm.json", directory=None
    )
    # Declare Randomness
    declare_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Declare Randomness Example
    declare_example_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_example_contract,
        compiled_contract_casm=compiled_example_contract_casm,
        auto_estimate=True,
    )
    await declare_example_result.wait_for_acceptance()

    # Declare Mock Oracle
    declare_mock_oracle_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_oracle_mock_contract,
        compiled_contract_casm=compiled_oracle_mock_contract_casm,
        auto_estimate=True,
    )
    await declare_mock_oracle_result.wait_for_acceptance()

    # Deploy Mock Oracle
    deploy_oracle_result = await declare_mock_oracle_result.deploy_v1(
        constructor_args=[], auto_estimate=True
    )
    await deploy_oracle_result.wait_for_acceptance()

    # Deploy Randomness
    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            account.address,
            account.signer.public_key,
            int(FEE_TOKEN_ADDRESS, 16),
            deploy_oracle_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await declare_example_result.deploy_v1(
        constructor_args=[
            deploy_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_example_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_example_result, deploy_oracle_result


@pytest_asyncio.fixture(scope="function")
async def randomness_contracts(
    declare_deploy_randomness,
) -> (Contract, Contract, Contract):
    (
        _,
        deploy_result,
        deploy_example_result,
        deploy_oracle_result,
    ) = declare_deploy_randomness
    return (
        deploy_result.deployed_contract,
        deploy_example_result.deployed_contract,
        deploy_oracle_result.deployed_contract,
    )


@pytest_asyncio.fixture(scope="function", name="vrf_pragma_client")
async def vrf_pragma_client(
    randomness_contracts: (Contract, Contract, Contract),
    network,
    address_and_private_key: Tuple[str, str],
) -> ExtendedPragmaClient:
    (randomness, example, oracle) = randomness_contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    client = ExtendedPragmaClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=0x0,
        ),
        port=port,
    )
    client.init_randomness_contract(randomness.address)
    client.init_example_randomness_contract(example.address)
    erc20_contract = Contract(
        address=FEE_TOKEN_ADDRESS,
        abi=get_erc20_abi(),
        provider=client.account,
        cairo_version=0,
    )
    # Approve randomness contract to transfer fee tokens
    await erc20_contract.functions["approve"].invoke_v1(
        randomness.address, 0xFFFFFFFFFFFFFFFFFFFFFFFF, auto_estimate=True
    )
    return client

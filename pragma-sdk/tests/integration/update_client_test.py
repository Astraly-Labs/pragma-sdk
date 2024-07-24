from typing import List

import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult
from starknet_py.net.client_errors import ClientError

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.utils import str_to_felt
from tests.integration.utils import get_deployments, read_contract
from pragma_sdk.common.types.pair import Pair
from tests.integration.constants import USD_PAIRS

logger = get_pragma_sdk_logger()

MAX_FEE = 3700000000000000
PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = str_to_felt("ETH/USD")
BTC_PAIR = str_to_felt("BTC/USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"


@pytest_asyncio.fixture(scope="module")
@pytest.mark.parametrize(
    "network_config",
    [
        {
            "network": "mainnet",
            "block_number": None,
            "account_address": "0x02356b628D108863BAf8644c945d97bAD70190AF5957031f4852d00D0F690a77",
        },
    ],
    indirect=True,
)
async def declare_oracle(forked_client: PragmaOnChainClient) -> DeclareResult:
    try:
        compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
        compiled_contract_casm = read_contract(
            "pragma_Oracle.casm.json", directory=None
        )
        # Declare Oracle
        declare_result = await Contract.declare_v2(
            account=forked_client.account,
            compiled_contract=compiled_contract,
            compiled_contract_casm=compiled_contract_casm,
            auto_estimate=True,
        )
        await declare_result.wait_for_acceptance()
        return declare_result

    except ClientError as err:
        if "is already declared" in err.message:
            logger.info("Contract already declared with this class hash")
        else:
            logger.info("An error occured during the declaration: %s", err)
            raise err
        return None


@pytest.mark.asyncio
async def test_update_oracle(
    forked_client: PragmaOnChainClient, declare_oracle: DeclareResult
):
    deployments = get_deployments(forked_client.network)
    if declare_oracle is None:
        pytest.skip("oracle_declare failed. Skipping this test...")

    # Retrieve old state

    publishers = await forked_client.get_all_publishers()
    initial_prices = await retrieve_spot_prices(forked_client, USD_PAIRS)
    oracle_admin = await forked_client.get_admin_address()
    assert oracle_admin == forked_client.account_address()

    # Determine new implementation hash
    declare_result = declare_oracle
    logger.info("Contract declared with hash: %s", declare_result.class_hash)

    # Update oracle
    update_invoke = await forked_client.update_oracle(
        declare_result.class_hash, MAX_FEE
    )
    update_invoke.wait_for_acceptance()
    logger.info("Contract upgraded with tx %s", hex(update_invoke.hash))

    # Check that the class hash was updated
    class_hash = await forked_client.full_node_client.get_class_hash_at(
        deployments["pragma_Oracle"]["address"]
    )
    # assert class_hash['result'] == declare_result.class_hash
    assert class_hash == declare_result.class_hash
    # Retrieve new state
    new_publishers = await forked_client.get_all_publishers()
    post_treatment_prices = await retrieve_spot_prices(forked_client, USD_PAIRS)

    # Check that state is the same
    assert publishers == new_publishers
    assert initial_prices == post_treatment_prices


async def retrieve_spot_prices(client: PragmaOnChainClient, pairs: List[Pair]):
    prices = {}
    for pair in pairs:
        price = await client.get_spot(pair.id)
        prices[pair] = price
    return prices

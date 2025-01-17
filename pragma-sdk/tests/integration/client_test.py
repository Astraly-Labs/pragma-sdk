import time
import pytest
import pytest_asyncio

from typing import Tuple
from urllib.parse import urlparse

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account
from starknet_py.net.client_errors import ClientError
from starknet_py.transaction_errors import TransactionRevertedError

from pragma_sdk.common.types.entry import FutureEntry, SpotEntry, GenericEntry
from pragma_sdk.common.types.asset import Asset
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import str_to_felt, felt_to_str

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import ContractAddresses, Network
from pragma_sdk.onchain.constants import DERIBIT_MERKLE_FEED_KEY

from tests.integration.constants import CURRENCIES, USD_PAIRS
from tests.integration.utils import read_contract, wait_for_acceptance


pytestmark = pytest.mark.asyncio

PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = Pair.from_tickers("ETH", "USD")
BTC_PAIR = Pair.from_tickers("BTC", "USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"


@pytest_asyncio.fixture(scope="module")
async def declare_deploy_oracle(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract_registry = read_contract(
        "pragma_PublisherRegistry.sierra.json", directory=None
    )
    compiled_contract_registry_casm = read_contract(
        "pragma_PublisherRegistry.casm.json", directory=None
    )

    compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)

    # Declare Publisher Registry
    declare_result_registry = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract_registry,
        compiled_contract_casm=compiled_contract_registry_casm,
        auto_estimate=True,
    )
    await declare_result_registry.wait_for_acceptance()

    # Deploy Publisher Registry
    deploy_result_registry = await declare_result_registry.deploy_v1(
        constructor_args=[account.address], auto_estimate=True
    )
    await deploy_result_registry.wait_for_acceptance()

    # Declare Oracle
    declare_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Deploy Oracle
    all_currencies = CURRENCIES[:40]
    all_pairs = USD_PAIRS[:20]

    currencies = [currency.to_dict() for currency in all_currencies]
    pairs = [pair.to_dict() for pair in all_pairs]

    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            account.address,
            deploy_result_registry.deployed_contract.address,
            currencies,
            pairs,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_result_registry


@pytest_asyncio.fixture(scope="module", name="contracts")
async def oracle_contract(declare_deploy_oracle) -> Tuple[Contract, Contract]:
    _, deploy_result, deploy_result_registry = declare_deploy_oracle
    return (deploy_result.deployed_contract, deploy_result_registry.deployed_contract)


@pytest_asyncio.fixture(scope="module", name="pragma_client")
async def pragma_client(
    contracts: Tuple[Contract, Contract],
    network: Network,
    address_and_private_key: Tuple[str, str],
) -> PragmaOnChainClient:
    oracle, registry = contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    return PragmaOnChainClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=registry.address,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=0x0,
        ),
        port=port,
    )


@pytest.mark.asyncio
async def test_deploy_contract(contracts):
    oracle, registry = contracts
    assert isinstance(oracle, Contract)
    assert isinstance(registry, Contract)


@pytest.mark.asyncio
async def test_client_setup(pragma_client: PragmaOnChainClient, account: Account):
    assert pragma_client.account_address == account.address

    account_balance = await account.get_balance()
    assert await pragma_client.get_balance(account.address) == account_balance

    assert pragma_client.oracle is not None
    assert pragma_client.publisher_registry is not None


@pytest.mark.asyncio
async def test_client_publisher_mixin(pragma_client: PragmaOnChainClient):
    publishers = await pragma_client.get_all_publishers()
    assert publishers == []

    publisher_name = "PUBLISHER_1"

    expected_publisher_address = 123

    await wait_for_acceptance(
        await pragma_client.add_publisher(publisher_name, expected_publisher_address)
    )

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(publisher_name)]

    publisher_address = await pragma_client.get_publisher_address(publisher_name)
    assert expected_publisher_address == publisher_address

    await wait_for_acceptance(
        await pragma_client.add_source_for_publisher(publisher_name, SOURCE_1)
    )
    sources = await pragma_client.get_publisher_sources(publisher_name)
    assert sources == [str_to_felt(SOURCE_1)]

    await wait_for_acceptance(
        await pragma_client.add_sources_for_publisher(
            publisher_name, [SOURCE_2, SOURCE_3]
        )
    )
    sources = await pragma_client.get_publisher_sources(publisher_name)
    assert sources == [str_to_felt(source) for source in (SOURCE_1, SOURCE_2, SOURCE_3)]


@pytest.mark.asyncio
async def test_client_oracle_mixin_spot(pragma_client: PragmaOnChainClient):
    # Add PRAGMA as Publisher
    publisher_name = "PRAGMA"
    publisher_address = pragma_client.account_address

    assert await pragma_client.is_currency_registered(
        BTC_PAIR.base_currency.id, "pending"
    )
    assert await pragma_client.is_currency_registered(
        BTC_PAIR.quote_currency.id, "pending"
    )
    assert not (await pragma_client.is_currency_registered("DONOTEXIST", "pending"))

    await wait_for_acceptance(
        await pragma_client.add_publisher(publisher_name, publisher_address)
    )
    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    # Add PRAGMA as Source for PRAGMA Publisher
    await wait_for_acceptance(
        await pragma_client.add_source_for_publisher(publisher_name, SOURCE_1)
    )
    # Publish SPOT Entry
    timestamp = int(time.time())
    await wait_for_acceptance(
        await pragma_client.publish_spot_entry(
            BTC_PAIR.id,
            1000000000000,
            timestamp,
            SOURCE_1,
            publisher_name,
            volume=int(200 * 100 * 1e8),
        )
    )
    entries = await pragma_client.get_spot_entries(BTC_PAIR.id, sources=[])
    assert entries == [
        SpotEntry(
            BTC_PAIR.id,
            1000000000000,
            timestamp,
            SOURCE_1,
            publisher_name,
            volume=2000000000000,
        )
    ]

    # Get SPOT
    res = await pragma_client.get_spot(BTC_PAIR.id)
    assert res.price == 1000000000000
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp
    assert res.decimals == 8

    # Get Decimals
    decimals = await pragma_client.get_decimals(
        Asset(DataTypes.SPOT, BTC_PAIR.id, None)
    )
    assert decimals == 8

    # Publish many SPOT entries
    spot_entry_1 = SpotEntry(
        ETH_PAIR.id, 1000000000000, timestamp, SOURCE_1, publisher_name, volume=10
    )
    spot_entry_2 = SpotEntry(
        ETH_PAIR.id, 2000000000000, timestamp + 10, SOURCE_1, publisher_name, volume=20
    )

    invocations = await pragma_client.publish_many(
        [spot_entry_1, spot_entry_2],
    )
    await invocations[len(invocations) - 1].wait_for_acceptance()
    # Fails for UNKNOWN source
    unknown_source = "UNKNOWN"
    try:
        await pragma_client.get_spot_entries(
            ETH_PAIR.id, sources=[str_to_felt(unknown_source)]
        )
    except ClientError as err:
        err_msg = "Contract error"  # TODO(#000): check error message 04e6f206461746120656e74727920666f756e64
        if err_msg not in err.message:
            raise err

    # Returns correct entries
    entries = await pragma_client.get_spot_entries(ETH_PAIR.id, sources=[])

    assert entries == [spot_entry_2]

    # Return correct price aggregated
    res = await pragma_client.get_spot(ETH_PAIR.id)
    assert res.price == 2000000000000
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp + 10
    assert res.decimals == 8

    # Fails if timestamp too far in the future (>7min)
    spot_entry_future = SpotEntry(
        ETH_PAIR.id,
        1000000000000,
        timestamp + 450,
        SOURCE_1,
        publisher_name,
        volume=100000000000,
    )
    try:
        invocations = await pragma_client.publish_many(
            [spot_entry_future],
        )
        await invocations[-1].wait_for_acceptance()
    except TransactionRevertedError as err:
        err_msg = "Timestamp is in the future"
        if err_msg not in err.message:
            raise err

    # Add new source and check aggregation
    await wait_for_acceptance(
        await pragma_client.add_source_for_publisher(publisher_name, SOURCE_2)
    )
    spot_entry_1 = SpotEntry(
        ETH_PAIR.id, 1000000000000, timestamp + 20, SOURCE_1, publisher_name, volume=10
    )
    spot_entry_2 = SpotEntry(
        ETH_PAIR.id, 2000000000000, timestamp + 30, SOURCE_2, publisher_name, volume=20
    )

    invocations = await pragma_client.publish_many(
        [spot_entry_1, spot_entry_2],
    )
    await invocations[len(invocations) - 1].wait_for_acceptance()
    res = await pragma_client.get_spot(ETH_PAIR.id)
    assert res.price == 1500000000000
    assert res.num_sources_aggregated == 2
    assert res.last_updated_timestamp == timestamp + 30
    assert res.decimals == 8


@pytest.mark.asyncio
async def test_client_oracle_mixin_future(pragma_client: PragmaOnChainClient):
    # Checks
    publisher_name = "PRAGMA"
    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    timestamp = int(time.time())
    expiry_timestamp = timestamp + 1000
    future_entry_1 = FutureEntry(
        BTC_PAIR.id,
        10000000000000,
        timestamp,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=10000,
    )
    future_entry_2 = FutureEntry(
        BTC_PAIR.id,
        20000000000000,
        timestamp + 100,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=20000,
    )

    invocations = await pragma_client.publish_many(
        [future_entry_1, future_entry_2],
    )
    await invocations[len(invocations) - 1].wait_for_acceptance()
    # Check entries
    entries = await pragma_client.get_future_entries(
        BTC_PAIR.id, expiry_timestamp, sources=[]
    )
    assert entries == [future_entry_2]

    # Get FUTURE
    res = await pragma_client.get_future(BTC_PAIR.id, expiry_timestamp)
    assert res.price == 20000000000000
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp + 100
    assert res.decimals == 8
    assert res.expiration_timestamp == expiry_timestamp

    # Add new source and check aggregation
    timestamp = int(time.time())
    future_entry_1 = FutureEntry(
        ETH_PAIR.id,
        1000000000000,
        timestamp,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=10,
    )
    future_entry_2 = FutureEntry(
        ETH_PAIR.id,
        2000000000000,
        timestamp + 10,
        SOURCE_2,
        publisher_name,
        expiry_timestamp,
        volume=20,
    )

    invocations = await pragma_client.publish_many(
        [future_entry_1, future_entry_2],
    )
    await invocations[-1].wait_for_acceptance()
    res = await pragma_client.get_future(ETH_PAIR.id, expiry_timestamp)
    assert res.price == 1500000000000
    assert res.num_sources_aggregated == 2
    assert res.last_updated_timestamp == timestamp + 10
    assert res.decimals == 8

    # Fails if timestamp too far in the future (>2min)
    future_entry_future = FutureEntry(
        ETH_PAIR.id,
        1000000000000,
        timestamp + 1000,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=10,
    )
    try:
        invocations = await pragma_client.publish_many(
            [future_entry_future],
        )
        await invocations[-1].wait_for_acceptance()
    except TransactionRevertedError as err:
        err_msg = "Timestamp is in the future"
        if err_msg not in err.message:
            raise err


@pytest.mark.asyncio
async def test_client_oracle_mixin_generic(pragma_client: PragmaOnChainClient):
    # Checks
    publisher_name = "PRAGMA"
    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    timestamp = int(time.time())
    generic_entry = GenericEntry(
        DERIBIT_MERKLE_FEED_KEY,
        424242,
        timestamp,
        SOURCE_1,
        publisher_name,
    )

    invocations = await pragma_client.publish_many([generic_entry])
    await invocations[len(invocations) - 1].wait_for_acceptance()

    # Get GENERIC
    res = await pragma_client.get_generic(DERIBIT_MERKLE_FEED_KEY)
    assert res.key == DERIBIT_MERKLE_FEED_KEY
    assert res.value == 424242
    assert res.base.timestamp == timestamp
    assert felt_to_str(res.base.source) == SOURCE_1
    assert felt_to_str(res.base.publisher) == publisher_name


@pytest.mark.asyncio
async def test_client_oracle_mixin_get_entry(pragma_client: PragmaOnChainClient):
    # Checks
    publisher_name = "PRAGMA"
    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    timestamp = int(time.time())
    spot_entry = SpotEntry(
        ETH_PAIR.id, 1000000000000, timestamp + 40, SOURCE_1, publisher_name, volume=0
    )
    future_entry = FutureEntry(
        ETH_PAIR.id,
        2000000000000,
        timestamp + 20,
        SOURCE_1,
        publisher_name,
        expiry_timestamp=0,
        volume=20,
    )

    invocations = await pragma_client.publish_many([spot_entry, future_entry])
    await invocations[len(invocations) - 1].wait_for_acceptance()

    # Get spot entry
    published_entry = await pragma_client.get_entry(
        ETH_PAIR.id, DataTypes.SPOT, publisher_name, SOURCE_1
    )
    assert published_entry.pair_id == ETH_PAIR.id
    assert published_entry.price == 1000000000000
    assert published_entry.volume == 0
    assert published_entry.base.timestamp == timestamp + 40
    assert felt_to_str(published_entry.base.source) == SOURCE_1
    assert felt_to_str(published_entry.base.publisher) == publisher_name

    # Get future entry
    published_entry = await pragma_client.get_entry(
        ETH_PAIR.id, DataTypes.FUTURE, publisher_name, SOURCE_1
    )
    assert published_entry.pair_id == ETH_PAIR.id
    assert published_entry.price == 2000000000000
    assert published_entry.volume == 20
    assert published_entry.base.timestamp == timestamp + 20
    assert felt_to_str(published_entry.base.source) == SOURCE_1
    assert felt_to_str(published_entry.base.publisher) == publisher_name
    assert published_entry.expiry_timestamp == 0


def test_client_with_http_network():
    client_with_chain_name = PragmaOnChainClient(
        network="http://test.rpc/rpc", chain_name="sepolia"
    )
    assert client_with_chain_name.network == "sepolia"

    client_with_chain_name_only = PragmaOnChainClient(chain_name="sepolia")
    # default value of network is sepolia
    assert client_with_chain_name_only.network == "sepolia"

    with pytest.raises(Exception) as exception:
        _ = PragmaOnChainClient(network="http://test.rpc/rpc")
        assert "`chain_name` is not provided" in str(exception)

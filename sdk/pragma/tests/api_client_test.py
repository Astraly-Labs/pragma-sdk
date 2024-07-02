# pylint: disable=redefined-outer-name

import json
import os
import random
import subprocess
import time
from unittest import mock

import pytest
from aioresponses import aioresponses
from starknet_py.net.client import Client

from pragma.onchain.client import PragmaOnChainClient
from pragma.common.types import RPC_URLS
from pragma.publisher.client import PragmaAPIClient, PragmaAPIError
from pragma.tests.constants import MOCK_DIR, SAMPLE_ASSETS
from pragma.tests.fixtures.devnet import get_available_port

JEDISWAP_POOL = "0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0"

ACCOUNT_ADDRESS = os.getenv("TESTNET_ACCOUNT_ADDRESS")
ACCOUNT_PRIVATE_KEY = os.getenv("TESTNET_PRIVATE_KEY")
# %% SPOT


@pytest.fixture(scope="module")
def forked_client(request, module_mocker, pytestconfig) -> Client:
    """
    This module-scope fixture prepares a forked starknet
    client for e2e testing.

    :return: a starknet Client
    """
    # net = pytestconfig.getoption("--net")
    port = get_available_port()
    block_number = request.param.get("block_number", None)
    network = request.param.get("network", "mainnet")

    rpc_url = RPC_URLS[network][random.randint(0, len(RPC_URLS[network]) - 1)]
    command = [
        "starknet-devnet",
        "--fork-network",
        str(rpc_url),
        "--chain-id",
        "MAINNET",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
    ]
    if block_number is not None:
        print(f"forking starknet at block {block_number}")
        command.extend(["--fork-block-number", str(block_number)])
    subprocess.Popen(command)  # pylint: disable=consider-using-with
    time.sleep(10)
    pragma_client = PragmaOnChainClient(
        f"http://127.0.0.1:{port}/rpc", chain_name=network
    )
    return pragma_client


API_CLIENT_CONFIGS = {
    "get_spot_data": {
        "function": "get_entry",
        "url": "https://api.dev.pragma.build/node/v1/data/",
        "mock_file": MOCK_DIR / "responses" / "api_client" / "get_spot.json",
        "expected_result": {
            "BTC": {
                "num_sources_aggregated": 8,
                "pair_id": "BTC/USD",
                "price": "0x5a768fa96ac",
                "timestamp": 1709238600000,
                "decimals": 8,
            },
            "ETH": {
                "num_sources_aggregated": 8,
                "pair_id": "ETH/USD",
                "price": "0x4f6d61001d",
                "timestamp": 1709238600000,
                "decimals": 8,
            },
        },
    },
    "get_ohlc_data": {
        "function": "api_get_ohlc",
        "url": "https://api.dev.pragma.build/node/v1/aggregation/candlestick/",
        "mock_file": MOCK_DIR / "responses" / "api_client" / "get_ohlc.json",
        "expected_result": {
            "BTC": [
                {
                    "time": "2024-02-29T14:00:00",
                    "open": "6287600000000",
                    "low": "6258656956761",
                    "high": "6306870000000",
                    "close": "6258656956761",
                },
                {
                    "time": "2024-02-29T13:30:00",
                    "open": "6259600000000",
                    "low": "6237130000000",
                    "high": "6275705000017",
                    "close": "6255363757538",
                },
                {
                    "time": "2024-02-29T13:00:00",
                    "open": "6265500000000",
                    "low": "6251390000000",
                    "high": "6275025999982",
                    "close": "6275025999982",
                },
                {
                    "time": "2024-02-29T12:30:00",
                    "open": "6273500000000",
                    "low": "6250000000000",
                    "high": "6273500000000",
                    "close": "6255421941903",
                },
            ],
            "ETH": [
                {
                    "time": "2024-02-29T21:30:00",
                    "open": "333873000000",
                    "low": "331695000000",
                    "high": "343495227969",
                    "close": "332000000000",
                },
                {
                    "time": "2024-02-29T21:00:00",
                    "open": "339030000000",
                    "low": "335363000000",
                    "high": "343932180566",
                    "close": "335814999999",
                },
                {
                    "time": "2024-02-29T20:30:00",
                    "open": "341090000000",
                    "low": "340498000000",
                    "high": "344132236518",
                    "close": "340757000000",
                },
                {
                    "time": "2024-02-29T20:00:00",
                    "open": "340152000000",
                    "low": "339706000000",
                    "high": "344222173320",
                    "close": "339920000000",
                },
            ],
        },
    },
    "get_volatility": {
        "function": "get_volatility",
        "url": "https://api.dev.pragma.build/node/v1/volatility/",
        "mock_file": MOCK_DIR / "responses" / "api_client" / "get_volatility.json",
        "expected_result": {
            "BTC": {
                "num_sources_aggregated": 8,
                "pair_id": "BTC/USD",
                "price": "0x5a768fa96ac",
                "timestamp": 1709238600000,
                "decimals": 8,
            },
            "ETH": {
                "num_sources_aggregated": 8,
                "pair_id": "ETH/USD",
                "price": "0x4f6d61001d",
                "timestamp": 1709238600000,
                "decimals": 8,
            },
        },
    },
}


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_async_api_client_spot(forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            if asset["type"] == "INDEX":
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = (
                API_CLIENT_CONFIGS["get_spot_data"]["url"]
                + f"{quote_asset}/{base_asset}"
            )
            with open(
                [
                    config["mock_file"]
                    for config in API_CLIENT_CONFIGS.values()
                    if config["function"] == "get_entry"
                ][0],
                "r",
                encoding="utf-8",
            ) as filepath:
                mock_data = json.load(filepath)
            mock.get(
                url,
                payload=mock_data[quote_asset],
            )
            result = await api_client.get_entry(
                f'{asset["pair"][0]}/{asset["pair"][1]}'
            )
            expected_result = [
                config["expected_result"]
                for config in API_CLIENT_CONFIGS.values()
                if config["function"] == "get_entry"
            ]
            assert result.assert_attributes_equal(expected_result[0][quote_asset])


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_async_api_client_spot_404_error(forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            if asset["type"] == "INDEX":
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = (
                API_CLIENT_CONFIGS["get_spot_data"]["url"]
                + f"{quote_asset}/{base_asset}"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.get_entry(f"{quote_asset}/{base_asset}")

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Unable to GET /v1/data for pair {quote_asset}/{base_asset}"
            )


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_async_api_client_ohlc(forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            if asset["type"] == "INDEX":
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = (
                API_CLIENT_CONFIGS["get_ohlc_data"]["url"]
                + f"{quote_asset}/{base_asset}"
            )
            with open(
                [
                    config["mock_file"]
                    for config in API_CLIENT_CONFIGS.values()
                    if config["function"] == "api_get_ohlc"
                ][0],
                "r",
                encoding="utf-8",
            ) as filepath:
                mock_data = json.load(filepath)
            print(mock_data[quote_asset])
            mock.get(
                url,
                payload=mock_data[quote_asset],
            )
            result = await api_client.api_get_ohlc(
                f'{asset["pair"][0]}/{asset["pair"][1]}'
            )

            expected_result = [
                config["expected_result"]
                for config in API_CLIENT_CONFIGS.values()
                if config["function"] == "api_get_ohlc"
            ]
            assert result.data == expected_result[0][quote_asset]


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_async_api_client_ohlc_404_error(forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            if asset["type"] == "INDEX":
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = (
                API_CLIENT_CONFIGS["get_ohlc_data"]["url"]
                + f"{quote_asset}/{base_asset}"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.api_get_ohlc(f'{asset["pair"][0]}/{asset["pair"][1]}')

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Failed to get OHLC data for pair {quote_asset}/{base_asset}"
            )


# @mock.patch("time.time", mock.MagicMock(return_value=12345))
# @pytest.mark.parametrize(
#     "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
# )
# @pytest.mark.asyncio
# async def test_async_api_client_volatility(forked_client):
#     # we only want to mock the external fetcher APIs and not the RPC
#     with aioresponses(passthrough=[forked_client.client.url]) as mock:
#         api_client = PragmaAPIClient(ACCOUNT_ADDRESS, ACCOUNT_PRIVATE_KEY,'https://api.dev.pragma.build', 'dummy_key')
#         # Mocking the expected call for assets
#         for asset in SAMPLE_ASSETS:
#   if asset["type"] == "INDEX":
#     continue
#             quote_asset = asset["pair"][0]
#             base_asset = asset["pair"][1]
#             url = API_CLIENT_CONFIGS["get_volatility"]["url"] + f"{quote_asset}/{base_asset}"
#             with open([config["mock_file"] for config in API_CLIENT_CONFIGS.values() if config['function'] == 'get_volatility'][0], "r", encoding="utf-8") as filepath:
#                 mock_data = json.load(filepath)
#             mock.get(
#                     url,
#                     payload=mock_data[quote_asset],
#             )
#             result = await api_client.get_volatility(f'{asset["pair"][0]}/{asset["pair"][1]}')

#             expected_result  = [config["expected_result"] for config in API_CLIENT_CONFIGS.values() if config['function'] == 'get_volatility']
#             assert result == expected_result[0][quote_asset]


# @mock.patch("time.time", mock.MagicMock(return_value=12345))
# @pytest.mark.parametrize(
#     "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
# )
# @pytest.mark.asyncio
# async def test_async_api_client_volatility(forked_client):
#     # we only want to mock the external fetcher APIs and not the RPC
#     with aioresponses(passthrough=[forked_client.client.url]) as mock:
#         api_client = PragmaAPIClient(ACCOUNT_ADDRESS, ACCOUNT_PRIVATE_KEY,'https://api.dev.pragma.build', 'dummy_key')
#         # Mocking the expected call for assets
#         for asset in SAMPLE_ASSETS:
# if asset["type"] == "INDEX":
# continue
#             quote_asset = asset["pair"][0]
#             base_asset = asset["pair"][1]
#             url = API_CLIENT_CONFIGS["get_volatility"]["url"] + f"{quote_asset}/{base_asset}"
#             mock.get(
#                     url,
#                     status=404,
#             )
#             result = await api_client.get_volatility(f'{asset["pair"][0]}/{asset["pair"][1]}')
#             assert result == Nones

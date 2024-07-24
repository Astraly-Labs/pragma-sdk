# pylint: disable=redefined-outer-name

import json
import os

import pytest
from aioresponses import aioresponses

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.offchain.client import PragmaAPIClient
from pragma_sdk.offchain.exceptions import PragmaAPIError
from pragma_sdk.common.types.pair import Pair
from tests.integration.constants import MOCK_DIR, SAMPLE_PAIRS

JEDISWAP_POOL = "0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0"

ACCOUNT_ADDRESS = os.getenv("TESTNET_ACCOUNT_ADDRESS")
ACCOUNT_PRIVATE_KEY = os.getenv("TESTNET_PRIVATE_KEY")


logger = get_pragma_sdk_logger()


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
    "get_future_data": {
        "function": "get_future_entry",
        "url": "https://api.dev.pragma.build/node/v1/data/",
        "mock_file": MOCK_DIR / "responses" / "api_client" / "get_future.json",
        "expected_result": {
            "BTC": {
                "num_sources_aggregated": 8,
                "pair_id": "BTC/USD",
                "price": "0x52bd9a0154d",
                "timestamp": 1720274400000,
                "decimals": 8,
            },
            "ETH": {
                "num_sources_aggregated": 8,
                "pair_id": "ETH/USD",
                "price": "0x45d8ad9ae4",
                "timestamp": 1720274400000,
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
    "get_expiries_list": {
        "function": "get_expiries_list",
        "url": "https://api.dev.pragma.build/node/v1/data/",
        "mock_file": MOCK_DIR / "responses" / "api_client" / "get_expiries_list.json",
        "expected_result": ["2024-09-27T08:00:00", "2024-12-27T08:00:00"],
    },
}


@pytest.mark.asyncio
async def test_async_api_client_spot():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_spot_data"]["url"]
                + f"{base_asset}/{quote_asset}"
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
                payload=mock_data[base_asset],
            )
            result = await api_client.get_entry(
                f"{asset.base_currency.id}/{asset.quote_currency.id}"
            )
            expected_result = [
                config["expected_result"]
                for config in API_CLIENT_CONFIGS.values()
                if config["function"] == "get_entry"
            ]
            assert result.assert_attributes_equal(expected_result[0][base_asset])


@pytest.mark.asyncio
async def test_async_api_client_spot_404_error():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_spot_data"]["url"]
                + f"{base_asset}/{quote_asset}"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.get_entry(f"{base_asset}/{quote_asset}")

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Unable to GET /v1/data for pair {base_asset}/{quote_asset}"
            )


@pytest.mark.asyncio
async def test_async_api_client_ohlc():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_ohlc_data"]["url"]
                + f"{base_asset}/{quote_asset}"
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
            mock.get(
                url,
                payload=mock_data[base_asset],
            )
            result = await api_client.get_ohlc(
                f"{asset.base_currency.id}/{asset.quote_currency.id}"
            )

            expected_result = [
                config["expected_result"]
                for config in API_CLIENT_CONFIGS.values()
                if config["function"] == "api_get_ohlc"
            ]
            assert result.data == expected_result[0][base_asset]


@pytest.mark.asyncio
async def test_async_api_client_ohlc_404_error():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_ohlc_data"]["url"]
                + f"{base_asset}/{quote_asset}"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.get_ohlc(
                    f"{asset.base_currency.id}/{asset.quote_currency.id}"
                )

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Failed to get OHLC data for pair {base_asset}/{quote_asset}"
            )


@pytest.mark.asyncio
async def test_async_api_client_future():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_future_data"]["url"]
                + f"{base_asset}/{quote_asset}"
                + "?entry_type=future"
            )
            with open(
                [
                    config["mock_file"]
                    for config in API_CLIENT_CONFIGS.values()
                    if config["function"] == "get_future_entry"
                ][0],
                "r",
                encoding="utf-8",
            ) as filepath:
                mock_data = json.load(filepath)
            mock.get(
                url,
                payload=mock_data[base_asset],
            )
            result = await api_client.get_future_entry(
                f"{asset.base_currency.id}/{asset.quote_currency.id}"
            )
            expected_result = [
                config["expected_result"]
                for config in API_CLIENT_CONFIGS.values()
                if config["function"] == "get_future_entry"
            ]

            assert result.assert_attributes_equal(expected_result[0][base_asset])


@pytest.mark.asyncio
async def test_async_api_client_future_404_error():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_future_data"]["url"]
                + f"{base_asset}/{quote_asset}"
                + "?entry_type=future"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.get_future_entry(f"{base_asset}/{quote_asset}")

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Unable to GET /v1/data for pair {base_asset}/{quote_asset}"
            )


@pytest.mark.asyncio
async def test_async_api_client_expiries_list():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_expiries_list"]["url"]
                + f"{base_asset}/{quote_asset}"
                + "/future_expiries"
            )
            with open(
                [
                    config["mock_file"]
                    for config in API_CLIENT_CONFIGS.values()
                    if config["function"] == "get_expiries_list"
                ][0],
                "r",
                encoding="utf-8",
            ) as filepath:
                mock_data = json.load(filepath)
            mock.get(
                url,
                payload=mock_data,
            )
            result = await api_client.get_expiries_list(
                Pair.from_tickers(
                    f"{asset.base_currency.id}", f"{asset.quote_currency.id}"
                )
            )
            expected_result = API_CLIENT_CONFIGS["get_expiries_list"]["expected_result"]
            assert expected_result == result


@pytest.mark.asyncio
async def test_async_api_client_expiries_list_404_error():
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses() as mock:
        api_client = PragmaAPIClient(
            ACCOUNT_ADDRESS,
            ACCOUNT_PRIVATE_KEY,
            "https://api.dev.pragma.build",
            "dummy_key",
        )
        # Mocking the expected call for assets
        for asset in SAMPLE_PAIRS:
            base_asset = asset.base_currency.id
            quote_asset = asset.quote_currency.id
            url = (
                API_CLIENT_CONFIGS["get_expiries_list"]["url"]
                + f"{base_asset}/{quote_asset}"
                + "/future_expiries"
            )
            mock.get(url, status=404)
            # Use pytest.raises to capture the exception
            with pytest.raises(PragmaAPIError) as exc_info:
                await api_client.get_expiries_list(
                    Pair.from_tickers(
                        f"{asset.base_currency.id}", f"{asset.quote_currency.id}"
                    )
                )

            # Assert the error message or other details if needed
            assert (
                str(exc_info.value)
                == f"Unable to GET future_expiries for pair {base_asset}/{quote_asset}"
            )

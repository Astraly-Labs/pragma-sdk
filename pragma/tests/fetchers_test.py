import json
from unittest import mock

import aiohttp
import pytest
import requests_mock
from aioresponses import aioresponses

from pragma.core.entry import SpotEntry
from pragma.publisher.assets import PRAGMA_ALL_ASSETS
from pragma.publisher.fetchers import (
    AscendexFetcher,
    BitstampFetcher,
    CexFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    KaikoFetcher,
    OkxFetcher,
)
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import MOCK_DIR, SAMPLE_ASSETS

PUBLISHER_NAME = "TEST_PUBLISHER"

# Define fetcher configurations
FETCHER_CONFIGS = {
    "CexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "cex.json",
        "fetcher_class": CexFetcher,
        "name": "CEX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601210000000,
                1692717096,
                "CEX",
                PUBLISHER_NAME,
                volume=181043893,
            ),
            SpotEntry(
                "ETH/USD",
                163921000000,
                1692724899,
                "CEX",
                PUBLISHER_NAME,
                volume=5654796900,
            ),
        ],
    },
    "DefillamaFetcher": {
        "mock_file": MOCK_DIR / "responses" / "defillama.json",
        "fetcher_class": DefillamaFetcher,
        "name": "Defillama",
        "expected_result": [
            SpotEntry(
                "BTC/USD", 2604800000000, 1692779346, "DEFILLAMA", PUBLISHER_NAME
            ),
            SpotEntry("ETH/USD", 164507000000, 1692779707, "DEFILLAMA", PUBLISHER_NAME),
        ],
    },
    "BitstampFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bitstamp.json",
        "fetcher_class": BitstampFetcher,
        "name": "Bitstamp",
        "expected_result": [
            SpotEntry("BTC/USD", 2602100000000, 1692781034, "BITSTAMP", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164250000000, 1692780986, "BITSTAMP", PUBLISHER_NAME),
        ],
    },
    "CoinbaseFetcher": {
        "mock_file": MOCK_DIR / "responses" / "coinbase.json",
        "fetcher_class": CoinbaseFetcher,
        "name": "Coinbase",
        "expected_result": [
            SpotEntry("BTC/USD", 2602820500003, 12345, "COINBASE", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164399499999, 12345, "COINBASE", PUBLISHER_NAME),
        ],
    },
    "AscendexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "ascendex.json",
        "fetcher_class": AscendexFetcher,
        "name": "Ascendex",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2602650000000,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=978940000,
            ),
            SpotEntry(
                "ETH/USD",
                164369999999,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=12318800000,
            ),
        ],
    },
    "OkxFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx.json",
        "fetcher_class": OkxFetcher,
        "name": "OKX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2640240000000,
                1692829724112,
                "OKX",
                PUBLISHER_NAME,
                volume=1838238980000,
            ),
            SpotEntry(
                "ETH/USD",
                167372000000,
                1692829751109,
                "OKX",
                PUBLISHER_NAME,
                volume=18534136460000,
            ),
        ],
    },
    "KaikoFetcher": {
        "mock_file": MOCK_DIR / "responses" / "kaiko.json",
        "fetcher_class": KaikoFetcher,
        "name": "Kaiko",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601601000000,
                1692782303,
                "KAIKO",
                PUBLISHER_NAME,
                volume=414884,
            ),
            SpotEntry(
                "ETH/USD",
                164315580431,
                1692782453,
                "KAIKO",
                PUBLISHER_NAME,
                volume=4504710943,
            ),
        ],
    },
}


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r") as f:
        return json.load(f)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_fetcher(fetcher_config, mock_data):
    with aioresponses() as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=200, payload=mock_data[quote_asset])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        assert result == fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_async_fetcher_404_error(mock_data, fetcher_config):
    with aioresponses() as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
            )
            for asset in SAMPLE_ASSETS
        ]

        assert result == expected_result


@mock.patch("time.time", mock.MagicMock(return_value=12345))
def test_fetcher_sync_success(fetcher_config, mock_data):
    with requests_mock.Mocker() as m:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, json=mock_data[quote_asset])

        result = fetcher.fetch_sync()

        assert result == fetcher_config["expected_result"]


def test_fetcher_sync_404(fetcher_config, mock_data):
    with requests_mock.Mocker() as m:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, status_code=404)

        result = fetcher.fetch_sync()

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
            )
            for asset in SAMPLE_ASSETS
        ]

        assert result == expected_result
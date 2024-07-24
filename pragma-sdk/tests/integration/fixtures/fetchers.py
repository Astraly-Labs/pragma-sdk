import json

import pytest
from pragma_sdk.common.logging import get_pragma_sdk_logger
from tests.integration.fetchers.fetcher_configs import (
    FETCHER_CONFIGS,
    FUTURE_FETCHER_CONFIGS,
    ONCHAIN_FETCHER_CONFIGS,
    PUBLISHER_NAME,
)
from tests.integration.constants import SAMPLE_PAIRS

logger = get_pragma_sdk_logger()


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_future_data(future_fetcher_config):
    with open(future_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture(params=FUTURE_FETCHER_CONFIGS.values())
def future_fetcher_config(request):
    return request.param


@pytest.fixture(params=ONCHAIN_FETCHER_CONFIGS.values())
def onchain_fetcher_config(request):
    return request.param


@pytest.fixture
def onchain_mock_data(onchain_fetcher_config):
    with open(onchain_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture
def other_mock_endpoints(future_fetcher_config):
    # fetchers such as OkxFutureFetcher and BinanceFutureFetcher
    # have other API endpoints that must be mocked
    fetcher = future_fetcher_config["fetcher_class"](SAMPLE_PAIRS, PUBLISHER_NAME)
    other_mock_fns = future_fetcher_config.get("other_mock_fns", {})
    if not other_mock_fns:
        return []

    responses = []
    for asset in SAMPLE_PAIRS:
        base_asset = asset.base_currency.id
        for mock_fn in other_mock_fns:
            [*fn], [*val] = zip(*mock_fn.items())
            fn, val = fn[0], val[0]
            url = getattr(fetcher, fn)(**val["kwargs"][base_asset])
            with open(val["mock_file"], "r", encoding="utf-8") as filepath:
                mock_file = json.load(filepath)
            responses.append({"url": url, "json": mock_file[base_asset]})
    return responses

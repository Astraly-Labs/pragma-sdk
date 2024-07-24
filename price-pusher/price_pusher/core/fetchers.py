import logging
import os

from typing import List, Set

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from price_pusher.configs.price_config import (
    PriceConfig,
    get_unique_spot_pairs_from_config_list,
    get_unique_future_pairs_from_config_list,
)
from price_pusher.configs.fetchers import (
    ALL_FUTURE_FETCHERS,
    ALL_SPOT_FETCHERS,
    FETCHERS_WITH_API_KEY,
)

logger = logging.getLogger(__name__)


def add_all_fetchers(
    fetcher_client: FetcherClient,
    publisher_name: str,
    price_configs: List[PriceConfig],
) -> FetcherClient:
    """
    Add fetchers to the FetcherClient based on the provided configuration.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        publisher_name: The name of the publisher.
        price_configs: List of PriceConfig configurations.

    Returns:
        FetcherClient
    """
    spot_pairs = get_unique_spot_pairs_from_config_list(price_configs)
    future_pairs = get_unique_future_pairs_from_config_list(price_configs)
    _add_fetchers(fetcher_client, ALL_SPOT_FETCHERS, spot_pairs, publisher_name)
    _add_fetchers(fetcher_client, ALL_FUTURE_FETCHERS, future_pairs, publisher_name)
    return fetcher_client


def _add_fetchers(
    fetcher_client: FetcherClient,
    fetchers: List[FetcherInterfaceT],
    pairs: Set[Pair],
    publisher_name: str,
) -> None:
    """
    Add multiple fetchers to the FetcherClient.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        fetchers: List of fetcher classes to instantiate and add.
        pairs: List of pairs for the fetchers.
        publisher_name: The name of the publisher.
    """
    for fetcher in fetchers:
        _add_one_fetcher(
            fetcher=fetcher,
            fetcher_client=fetcher_client,
            pairs=pairs,
            publisher_name=publisher_name,
        )


def _add_one_fetcher(
    fetcher: FetcherInterfaceT,
    fetcher_client: FetcherClient,
    pairs: Set[Pair],
    publisher_name: str,
):
    config = FETCHERS_WITH_API_KEY.get(fetcher, None)
    if config is None:
        fetcher_client.add_fetcher(fetcher(list(pairs), publisher_name))
        return

    api_key = os.getenv(config.env_api_key)
    if api_key or config.optional:
        fetcher_client.add_fetcher(fetcher(list(pairs), publisher_name, api_key))
    else:
        logger.warning(
            f"⚠️ API key for {fetcher.__name__} is missing. "
            f"You need to set {config.env_api_key} as an env variable. "
            "Skipping it."
        )
        return

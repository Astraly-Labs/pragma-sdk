import asyncio
from typing import List
import logging

import aiohttp

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.utils import add_sync_methods
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.exceptions import PublisherFetchError

logger = logging.getLogger(__name__)


@add_sync_methods
class FetcherClient:
    """
    This client extends the pragma client with functionality for fetching from our third party sources.
    It can be used to synchronously or asynchronously fetch assets.

    The client works by setting up fetchers that are provided the assets to fetch and the publisher name.

    Example usage:

    .. code-block:: python

        pairs = [
            Pair.from_tickers("BTC", "USD"),
            Pair.from_tickers("ETH", "USD"),
        ]

        bitstamp_fetcher = BitstampFetcher(pairs, "publisher_test")
        gateio_fetcher = GateIOFetcher(pairs, "publisher_test")

        fetchers = [
            bitstamp_fetcher,
            gateio_fetcher,
        ]

        fc = FetcherClient()
        fc.add_fetchers(fetchers)

        await fc.fetch()
        fc.fetch_sync()

    You can also set a custom timeout duration as followed:

    .. code-block:: python

        await fc.fetch(timeout_duration=20)  # Denominated in seconds (default=10)
    """

    __fetchers: List[FetcherInterfaceT] = []

    @property
    def fetchers(self) -> List[FetcherInterfaceT]:
        return self.__fetchers

    @fetchers.setter
    def fetchers(self, value: List[FetcherInterfaceT]) -> None:
        if len(value) > 0:
            self.__fetchers = value
        else:
            raise ValueError("Fetcher list cannot be empty")

    def add_fetchers(self, fetchers: List[FetcherInterfaceT]) -> None:
        """
        Add fetchers to the supported fetchers list.
        """
        self.fetchers.extend(fetchers)

    def add_fetcher(self, fetcher: FetcherInterfaceT) -> None:
        """
        Add a single fetcher to the supported fetchers list.
        """
        self.fetchers.append(fetcher)

    async def fetch(
        self,
        filter_exceptions: bool = True,
        return_exceptions: bool = True,
        timeout_duration: int = 20,
    ) -> List[Entry | PublisherFetchError | Exception]:
        """
        Fetch data from all fetchers asynchronously.
        Fetching is done in parallel for all fetchers.

        :param filter_exceptions: If True, filters out exceptions from the result list
        :param return_exceptions: If True, returns exceptions in the result list
        :param timeout_duration: Timeout duration for each fetcher
        :return: List of fetched data
        """
        tasks = []
        timeout = aiohttp.ClientTimeout(
            total=timeout_duration
        )  # 20 seconds per request
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for fetcher in self.fetchers:
                data = fetcher.fetch(session)
                tasks.append(data)
            result = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
            result = [val for subl in result for val in subl]  # type: ignore[misc,union-attr]
            if filter_exceptions:
                result = [
                    subl for subl in result if not isinstance(subl, BaseException)
                ]
            return result  # type: ignore[union-attr, misc, return-value]

import logging

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable

from pragma_sdk.common.types.entry import Entry, FutureEntry
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient


from pragma_utils.retries import retry_async

logger = logging.getLogger(__name__)

FnUpdatePrices = Callable[[List[Entry]], None]


class IPricePoller(ABC):
    fetcher_client: FetcherClient
    update_prices_callback: Optional[FnUpdatePrices]

    @abstractmethod
    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None: ...

    @abstractmethod
    async def poll_prices(self) -> None: ...


class PricePoller(IPricePoller):
    def __init__(self, fetcher_client: FetcherClient) -> Dict:
        self.fetcher_client = fetcher_client
        self.update_prices_callback = None

        # If we're requesting some onchain fetchers, we allow for requests
        # retry in case of a small RPC down time etc...
        self._is_requesting_onchain = any(
            getattr(getattr(fetcher, "client", None), "full_node_client", None)
            is not None
            for fetcher in self.fetcher_client.fetchers
        )

    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None:
        self.update_prices_callback = callback

    async def poll_prices(self) -> None:
        """
        Poll in parallel every fetchers for the required pairs and send them
        to the orchestrator using the callback function.
        The orchestrator will be responsible of handling the entries.
        """
        if self.update_prices_callback is None:
            raise ValueError("Update callback must be set.")

        try:
            new_entries = await self._fetch_action()
            new_entries = self._filter_zeros_and_non_perp_from_entries(new_entries)
            logger.info(
                f"🔄 POLLER: Successfully fetched {len(new_entries)} new entries!"
            )
            self.update_prices_callback(new_entries)
        except Exception as e:
            logger.error(f"🔄 POLLER: ⛔ error while fetching new prices: {e}")
            if not self._is_requesting_onchain:
                raise e
            try:
                logger.warning("🤔 POLLER fetching prices failed. Retrying...")
                new_entries = await retry_async(
                    self._fetch_action, retries=5, delay_in_s=5, logger=logger
                )
                self.update_prices_callback(new_entries)
            except Exception as e:
                raise ValueError(
                    f"🔄 POLLERS: Retries for fetching new prices still failed: {e}"
                )

    async def _fetch_action(self) -> None:
        """
        Call the fetcher client `fetch` function to try to retrieve all entries from fetchers.
        """
        new_entries = await self.fetcher_client.fetch(
            filter_exceptions=True, return_exceptions=True, timeout_duration=3, configuration_decimals=18
        )
        return new_entries

    def _filter_zeros_and_non_perp_from_entries(
        self, entries: List[Entry]
    ) -> List[Entry]:
        """
        Some fetchers sometimes bug and return 0 as the price for an Entry.
        We use this function to filter them out.
        """
        return [
            entry
            for entry in entries
            if (entry.price > 0)
            and ((not isinstance(entry, FutureEntry)) or (entry.expiry_timestamp == 0))
        ]

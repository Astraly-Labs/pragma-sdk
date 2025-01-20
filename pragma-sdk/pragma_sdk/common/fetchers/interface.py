import abc
from typing import List, Optional, Dict, Any

from aiohttp import ClientSession

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.onchain.types import Network
from pragma_sdk.common.utils import add_sync_methods, str_to_felt
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.exceptions import PublisherFetchError


# TODO(akhercha): FetcherInterfaceT should take as parameter the client instead of creating it
# Abstract base class for all fetchers
@add_sync_methods
class FetcherInterfaceT(abc.ABC):
    pairs: List[Pair]
    publisher: str
    headers: Dict[Any, Any]
    hop_handler: Optional[HopHandler] = None

    _client = None

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        self.pairs = pairs
        self.publisher = publisher
        self.client = self.get_client(network)
        self.headers = {"Accepts": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    @abc.abstractmethod
    async def fetch(
        self, session: ClientSession, configuration_decimals: Optional[int] = None
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        ...

    @abc.abstractmethod
    async def fetch_pair(
        self,
        pair: Pair,
        session: ClientSession,
        configuration_decimals: Optional[int] = None,
    ) -> Entry | PublisherFetchError:
        """
        Fetches the data for a specific pair from the fetcher and returns a SpotEntry object.
        """
        ...

    @abc.abstractmethod
    def format_url(self, pair: Pair) -> str:
        """Formats the URL for the fetcher, used in `fetch_pair` to get the data."""
        ...

    def get_client(self, network: Network = "mainnet") -> PragmaOnChainClient:
        if self._client is None:
            self._client = PragmaOnChainClient(network=network)
        return self._client

    async def get_stable_price(self, stable_asset: str) -> float:
        """
        Query the PragmaOnChainClient for the price of the stable asset in USD
        e.g get_stable_price("USDT") returns the price of USDT in USD
        """

        usdt_str = str_to_felt(stable_asset + "/USD")
        usdt_entry = await self.client.get_spot(usdt_str)
        return int(usdt_entry.price) / int(10 ** int(usdt_entry.decimals))

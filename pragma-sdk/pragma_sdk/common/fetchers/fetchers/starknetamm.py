import asyncio
import time
from typing import List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

SUPPORTED_ASSETS = [
    ("ETH", "STRK"),
    ("STRK", "USD"),
    ("STRK", "USDT"),
    ("LORDS", "USD"),
    ("LUSD", "USD"),
    ("WBTC", "USD"),
    ("ETH", "LORDS"),
    ("ZEND", "USD"),
    ("ZEND", "USDC"),
    ("ZEND", "USDT"),
    ("ETH", "ZEND"),
    ("NSTR", "USD"),
    ("NSTR", "USDC"),
    ("NSTR", "USDT"),
    ("ETH", "NSTR"),
]


class StarknetAMMFetcher(FetcherInterfaceT):
    EKUBO_PUBLIC_API: str = "https://mainnet-api.ekubo.org"
    SOURCE = "STARKNET"

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDC",
        }
    )

    async def off_fetch_ekubo_price(
        self, pair: Pair, session: ClientSession, timestamp=None
    ) -> SpotEntry | PublisherFetchError:
        url = self.format_url(pair, timestamp)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Starknet")
            if resp.status == 200:
                result_json = await resp.json()
                return self._construct(pair, float(result_json["price"]))
            return PublisherFetchError(f"Failed to fetch data for {pair} from Starknet")

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        return await self.off_fetch_ekubo_price(pair, session)

    def format_url(self, pair: Pair, timestamp: Optional[int] = None) -> str:
        new_pair = self.hop_handler.get_hop_pair(pair) or pair
        if timestamp:
            return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{new_pair}?atTime={timestamp}&period=3600"

        return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{new_pair}?period=3600"

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = []
        for pair in self.pairs:
            if pair.to_tuple() in SUPPORTED_ASSETS:
                entries.append(self.fetch_pair(pair, session))
            else:
                logger.debug(f"Skipping StarknetAMM for non supported pair: {pair}")

        return list(await asyncio.gather(*entries, return_exceptions=True))  # type: ignore[call-overload]

    def _construct(self, pair: Pair, result: float) -> SpotEntry:
        price_int = int(result * (10 ** pair.decimals()))
        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=0,
        )

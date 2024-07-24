import asyncio
import time
from typing import Any, List

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class CoinbaseFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.coinbase.com/v2/exchange-rates?currency="
    SOURCE: str = "COINBASE"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Coinbase")
            result = await resp.json()
            return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = self.BASE_URL + pair.base_currency.id
        return url

    def _construct(self, pair: Pair, result: Any) -> SpotEntry | PublisherFetchError:
        if pair.base_currency.id in result["data"]["rates"]:
            rate = float(result["data"]["rates"][pair.base_currency.id])
            price = 1 / rate
            price_int = int(price * (10 ** pair.decimals()))
            timestamp = int(time.time())

            logger.debug("Fetched price %d for %s from Coinbase", price, pair)

            return SpotEntry(
                pair_id=pair.id,
                price=price_int,
                timestamp=timestamp,
                source=self.SOURCE,
                publisher=self.publisher,
            )

        return PublisherFetchError(f"No entry found for {pair.id} from Coinbase")

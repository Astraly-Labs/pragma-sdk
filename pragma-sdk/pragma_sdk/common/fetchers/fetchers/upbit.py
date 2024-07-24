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


class UpbitFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://sg-api.upbit.com/v1/ticker"
    SOURCE: str = "UPBIT"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Upbit")
            result = await resp.json()
            return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = (
            f"{self.BASE_URL}?markets={pair.base_currency.id}-{pair.quote_currency.id}"
        )
        return url

    def _construct(self, pair: Pair, result: Any) -> SpotEntry:
        data = result[0]
        timestamp = int(time.time())
        price = float(data["trade_price"])
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(data["trade_volume"])

        logger.debug("Fetched  price %d for %s from Upbit", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

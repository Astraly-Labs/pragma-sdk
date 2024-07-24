import asyncio
from typing import Any, List

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class BitstampFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://www.bitstamp.net/api/v2/ticker"
    SOURCE: str = "BITSTAMP"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Bitstamp")

            return self._construct(pair, await resp.json())

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}/{pair.base_currency.id.lower()}{pair.quote_currency.id.lower()}"
        return url

    def _construct(self, pair: Pair, result: Any) -> SpotEntry:
        timestamp = int(result["timestamp"])
        price = float(result["last"])
        price_int = int(price * (10 ** pair.decimals()))

        logger.debug("Fetched price %d for %s from Bitstamp", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

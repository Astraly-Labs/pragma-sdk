import asyncio
import json
from typing import Any, List

from aiohttp import ClientSession

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class OkxFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://okx.com/api/v5/market/ticker"
    SOURCE: str = "OKX"

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDT",
        }
    )

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price: float = 1
    ) -> SpotEntry | PublisherFetchError:
        new_pair = self.hop_handler.get_hop_pair(pair) or pair
        url = self.format_url(new_pair)

        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from OKX")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"OKX: Unexpected content type: {content_type}")

            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from OKX")

            return self._construct(pair, result, usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            entries.append(
                asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
            )
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}?instId={pair.base_currency.id}-{pair.quote_currency.id}-SWAP"
        return url

    def _construct(self, pair: Pair, result: Any, usdt_price: float = 1) -> SpotEntry:
        data = result["data"][0]

        timestamp = int(int(data["ts"]) / 1000)
        price = float(data["last"]) / usdt_price
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(data["volCcy24h"])

        logger.debug("Fetched  price %d for %s from OKX", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

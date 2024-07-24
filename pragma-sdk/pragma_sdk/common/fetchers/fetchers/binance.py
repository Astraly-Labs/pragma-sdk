import asyncio
import time
from typing import List, Optional, Any

from aiohttp import ClientSession

from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import SpotEntry, Entry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

# TODO: add exception list
EXCEPTION_LIST: List[Pair] = []


class BinanceFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.binance.com/api/v3/ticker/24hr"
    SOURCE: str = "BINANCE"

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDT",
        }
    )

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price: float = 1
    ) -> Entry | PublisherFetchError:
        new_pair = self.hop_handler.get_hop_pair(pair) or pair
        url = self.format_url(new_pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Binance")

            result = await resp.json()
            if "code" in result:
                return await self.operate_usdt_hop(pair, session)
            return self._construct(pair=pair, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            if pair not in EXCEPTION_LIST:
                entries.append(
                    asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
                )
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id}{pair.quote_currency.id}"
        return url

    async def operate_usdt_hop(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        url_pair1 = self.format_url(
            Pair(
                pair.base_currency,
                Currency.from_asset_config(AssetConfig.from_ticker("USDT")),
            )
        )
        async with session.get(url_pair1) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from Binance - hop failed for {pair.base_currency.id}"
                )
            pair1_usdt = await resp.json()
            if "code" in pair1_usdt:
                return PublisherFetchError(
                    f"No data found for {pair} from Binance - hop failed for {pair.base_currency.id}"
                )

        url_pair2 = self.format_url(
            Pair(
                pair.quote_currency,
                Currency.from_asset_config(AssetConfig.from_ticker("USDT")),
            )
        )
        async with session.get(url_pair2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from Binance - hop failed for {pair.quote_currency.id}"
                )
            pair2_usdt = await resp.json()
            if "code" in pair2_usdt:
                return PublisherFetchError(
                    f"No data found for {pair} from Binance - hop failed for {pair.quote_currency.id}"
                )

        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self,
        pair: Pair,
        result: Any,
        hop_result: Optional[Any] = None,
        usdt_price: float = 1,
    ) -> SpotEntry:
        bid = float(result["bidPrice"])
        ask = float(result["askPrice"])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["bidPrice"])
            hop_ask = float(hop_result["askPrice"])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(time.time())
        price_int = int(price * (10 ** pair.decimals()))

        logger.debug("Fetched price %d for %s from Binance", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

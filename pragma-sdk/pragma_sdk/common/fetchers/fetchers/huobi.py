import asyncio
from typing import List, Optional, Any

from aiohttp import ClientSession

from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class HuobiFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.huobi.pro/market/detail/merged"
    SOURCE: str = "HUOBI"

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
                return PublisherFetchError(f"No data found for {pair} from Huobi")
            result = await resp.json()
            if result["status"] != "ok":
                return await self.operate_usdt_hop(pair, session)
            return self._construct(pair=pair, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        usdt_price = await self.get_stable_price("USDT")
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
            for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id.lower()}{pair.quote_currency.id.lower()}"
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
                    f"No data found for {pair} from Huobi - hop failed for {pair.base_currency}"
                )
            pair1_usdt = await resp.json()
            if pair1_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {pair} from Huobi - hop failed for {pair.base_currency}"
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
                    f"No data found for {pair} from Huobi - hop failed for {pair.quote_currency}"
                )
            pair2_usdt = await resp.json()
            if pair2_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {pair} from Huobi - hop failed for {pair.quote_currency}"
                )
        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self,
        pair: Pair,
        result: Any,
        hop_result: Optional[Any] = None,
        usdt_price: float = 1,
    ) -> SpotEntry:
        bid = float(result["tick"]["bid"][0])
        ask = float(result["tick"]["ask"][0])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["tick"]["bid"][0])
            hop_ask = float(hop_result["tick"]["ask"][0])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(result["ts"] / 1000)
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(result["tick"]["vol"]) if hop_result is None else 0
        logger.debug("Fetched  price %d for %s from Bybit", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=int(volume),
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

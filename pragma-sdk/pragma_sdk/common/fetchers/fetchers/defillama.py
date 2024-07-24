import asyncio
from typing import Any, List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class DefillamaFetcher(FetcherInterfaceT):
    BASE_URL: str = (
        "https://coins.llama.fi/prices/current/coingecko:{pair_id}" "?searchWidth=15m"
    )
    SOURCE: str = "DEFILLAMA"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        pair_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair.base_currency.id}"
            )
        if pair.quote_currency.id != "USD":
            return await self.operate_usd_hop(pair, session)

        url = self.format_url(pair)
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Defillama")
            result = await resp.json()
            if not result["coins"]:
                return PublisherFetchError(f"No data found for {pair} from Defillama")
        return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        coingecko_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        url = self.BASE_URL.format(pair_id=coingecko_id)
        return url

    async def operate_usd_hop(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        coingecko_id_1 = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        coingeck_id_2 = AssetConfig.get_coingecko_id_from_ticker(pair.quote_currency.id)
        if coingeck_id_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair.quote_currency.id} - hop failed"
            )
        url_pair_1 = self.BASE_URL.format(pair_id=coingecko_id_1)
        async with session.get(url_pair_1, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from Defillama - hop failed for {pair.base_currency.id}"
                )
            result_base = await resp.json()
            if not result_base["coins"]:
                return PublisherFetchError(
                    f"No data found for {pair} from Defillama - hop failed for {pair.base_currency.id}"
                )
        url_pair_2 = self.BASE_URL.format(pair_id=coingeck_id_2)
        async with session.get(url_pair_2, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from Defillama - usd hop failed for {pair.quote_currency.id}"
                )
            result_quote = await resp.json()
            if not result_quote["coins"]:
                return PublisherFetchError(
                    f"No data found for {pair} from Defillama -  usd hop failed for {pair.quote_currency.id}"
                )
        return self._construct(pair, result_base, result_quote)

    def _construct(
        self, pair: Pair, result: Any, hop_result: Optional[Any] = None
    ) -> SpotEntry:
        base_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        timestamp = int(result["coins"][f"coingecko:{base_id}"]["timestamp"])
        decimals = pair.decimals()
        if hop_result is not None:
            quote_id = AssetConfig.get_coingecko_id_from_ticker(pair.quote_currency.id)
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            hop_price = hop_result["coins"][f"coingecko:{quote_id}"]["price"]
            price_int = int((price / hop_price) * (10**decimals))
        else:
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            price_int = int(price * (10**decimals))

        logger.debug("Fetched  price %d for %s from Coingecko", price, pair)

        entry = SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry

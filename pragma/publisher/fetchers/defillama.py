import asyncio
import logging
from typing import Dict, List

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

ASSET_MAPPING: Dict[str, str] = {
    "ETH": "ethereum",
    "BTC": "bitcoin",
    "WBTC": "wrapped-bitcoin",
    "SOL": "solana",
    "AVAX": "avalanche-2",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "TEMP": "tempus",
    "DAI": "dai",
    "USDT": "tether",
    "USDC": "usd-coin",
    "TUSD": "true-usd",
    "BUSD": "binance-usd",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "XRP": "ripple",
    "MATIC": "matic-network",
    "AAVE": "aave",
    "R": "r",
    "LORDS": "lords",
    "WSTETH": "wrapped-steth",
    "UNI": "uniswap",
    "LUSD": "liquity-usd",
    "STRK": "starknet",
}


class DefillamaFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://coins.llama.fi/prices/current/coingecko:{pair_id}" "?searchWidth=5m"
    )

    SOURCE: str = "DEFILLAMA"
    headers = {
        "Accepts": "application/json",
    }

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        pair_id = ASSET_MAPPING.get(pair[0])
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair[1] != "USD": 
            return await self.operate_usd_hop(asset, session)

        url = self.BASE_URL.format(pair_id=pair_id)
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )
            result = await resp.json()
            if not result["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )

        return self._construct(
            asset=asset, result=result
        )

    def _fetch_pair_sync(self, asset: PragmaSpotAsset) -> SpotEntry:
        pair = asset["pair"]
        pair_id = ASSET_MAPPING.get(pair[0])
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair[1] != "USD":
             return self.operate_usd_hop_sync(asset)
        url = self.BASE_URL.format(pair_id=pair_id)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama"
            )
        result = resp.json()
        if not result["coins"]:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama"
            )
        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        pair_id = ASSET_MAPPING.get(quote_asset)
        url = self.BASE_URL.format(pair_id=pair_id)
        return url
    
    async def operate_usd_hop(self, asset, session) -> SpotEntry:
        pair = asset["pair"]
        pair_id_1 = ASSET_MAPPING.get(pair[0])
        pair_id_2 = ASSET_MAPPING.get(pair[1])
        if pair_id_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[1]} - hop failed"
            )
        url_pair_1 = self.BASE_URL.format(pair_id=pair_id_1)
        async with session.get(url_pair_1, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
                )
            result_base = await resp.json()
            if not result_base["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
                )
        url_pair_2 = self.BASE_URL.format(pair_id=pair_id_2)
        async with session.get(url_pair_2, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - usd hop failed for {pair[1]}"
                )
            result_quote= await resp.json()
            print(result_quote)
            if not result_quote["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama -  usd hop failed for {pair[1]}"
                )
        return self._construct(asset, result_base,result_quote)
    
    def operate_usd_hop_sync(self, asset) -> SpotEntry:
        pair = asset["pair"]
        pair_id_1 = ASSET_MAPPING.get(pair[0])
        pair_id_2 = ASSET_MAPPING.get(pair[1])
        if pair_id_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[1]} - hop failed"
            )
        url_pair_1 = self.BASE_URL.format(pair_id=pair_id_1)
        resp = requests.get(url_pair_1, headers=self.headers)
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
            )
        result_base = resp.json()
        if not result_base["coins"]:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
            )
        url_pair_2 = self.BASE_URL.format(pair_id=pair_id_2)
        resp = requests.get(url_pair_2, headers=self.headers)
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama - usd hop failed for {pair[1]}"
            )
        result_quote = resp.json()
        if not result_quote["coins"]:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama -  usd hop failed for {pair[1]}"
            )
        return self._construct(asset, result_base,result_quote)

    def _construct(self, asset, result, hop_result = None) -> SpotEntry:
        pair = asset["pair"]
        base_id= ASSET_MAPPING.get(pair[0])
        quote_id = ASSET_MAPPING.get(pair[1])
        pair_id = currency_pair_to_pair_id(*pair)
        timestamp = int(result["coins"][f"coingecko:{base_id}"]["timestamp"])
        if hop_result is not None: 
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            hop_price = hop_result["coins"][f"coingecko:{quote_id}"]["price"]
            price_int = int((price / hop_price) * (10 ** asset["decimals"]))
        else: 
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            price_int = int(price * (10 ** asset["decimals"]))

        logger.info("Fetched price %d for %s from Coingecko", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

import asyncio
import json
import logging
import time
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import try_get_asset_config_from_ticker
from pragma.core.types import Pair
from pragma.publisher.client import PragmaOnChainClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.fetchers.index import AssetQuantities
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)

SUPPORTED_INDEXES = {
    "DPI": "0x1494CA1F11D487c2bBe4543E90080AeBa4BA3C2b",
    "MVI": "0x72e364F2ABdC788b7E918bc238B21f109Cd634D7",
}


class IndexCoopFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.indexcoop.com"
    SOURCE: str = "INDEXCOOP"
    client: PragmaOnChainClient
    publisher: str

    def __init__(self, pairs: List[Pair], publisher, client=None):
        self.pairs = pairs
        self.publisher = publisher
        self.client = client or PragmaOnChainClient(network="mainnet")

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = pair["pair"]
        url = self.format_url(pair[0].lower())
        async with session.get(url) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                response_text = await resp.text()
                if not response_text:
                    return PublisherFetchError(
                        f"No index found for {pair[0]} from IndexCoop"
                    )
                parsed_data = json.loads(response_text)
                logger.warning("Unexpected content type received: %s", content_type)

            return self._construct(pair, parsed_data)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_pair, base_pair=None):
        url = f"{self.BASE_URL}/{quote_pair}/analytics"
        return url

    def fetch_quantities(self, index_address) -> List[AssetQuantities]:
        url = f"{self.BASE_URL}/components?chainId=1&isPerpToken=false&address={index_address}"
        response = requests.get(url)
        response.raise_for_status()
        json_response = response.json()

        components = json_response["components"]
        quantities = {
            component["symbol"]: float(component["quantity"])
            for component in components
        }

        return [
            AssetQuantities(
                pair=Pair(
                    try_get_asset_config_from_ticker(symbol).get_currency(),
                    try_get_asset_config_from_ticker("USD").get_currency(),
                ),
                quantities=quantities,
            )
            for symbol, quantities in quantities.items()
        ]

    def _construct(self, pair: Pair, result) -> SpotEntry:
        timestamp = int(time.time())
        price = result["navPrice"]
        decimals = pair.decimals()
        price_int = int(price * (10**decimals))
        volume = int(float(result["volume24h"]) * (10**decimals))

        logger.info("Fetched price %d for %s from IndexCoop", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

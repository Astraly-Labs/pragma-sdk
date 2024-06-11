import json
import logging
from datetime import datetime, timezone
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaFutureAsset
from pragma.core.entry import FutureEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class BinancePerpFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://dapi.binance.com/dapi/v1/premiumIndex"
    VOLUME_URL: str = "https://dapi.binance.com/dapi/v1/ticker/24hr"
    SOURCE: str = "BINANCE"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_volume(self, asset, session):
        pair = asset["pair"]
        url = f"{self.VOLUME_URL}"
        selection = f"{pair[0]}{pair[1]}_PERP"
        volume_arr = []
        queried_url = f"{url}?symbol={selection}"
        async with session.get(queried_url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance"
                )
            result = await resp.json(content_type="application/json")
            for element in result:
                volume_arr.append((element["pair"], element["volume"]))
            return volume_arr

    async def _fetch_pair(
        self, asset: PragmaFutureAsset, session: ClientSession
    ) -> Union[FutureEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}"
        selection = f"{pair[0]}{pair[1]}_PERP"
        queried_url = f"{url}?symbol={selection}"
        async with session.get(queried_url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"Binance: Unexpected content type: {content_type}")

            volume_arr = await self.fetch_volume(asset, session)
            return self._construct(asset, result, volume_arr)

    async def fetch(self, session: ClientSession):
        entries = []
        for asset in self.assets:
            if asset["type"] != "FUTURE":
                logger.debug("Skipping Binance for non-future asset %s", asset)
                continue
            future_entries = await self._fetch_pair(asset, session)
            if isinstance(future_entries, list):
                entries.extend(future_entries)
            else:
                entries.append(future_entries)
        return entries

    def format_url(self, quote_asset, base_asset):
        return self.BASE_URL

    def retrieve_volume(self, asset, volume_arr):  # pylint: disable=no-self-use
        for list_asset, list_vol in volume_arr:
            if asset == list_asset:
                return list_vol
        return 0

    def _construct(self, asset, result, volume_arr) -> List[FutureEntry]:
        pair = asset["pair"]
        result_arr = []
        for data in result:
            timestamp = int(data["time"])
            price = float(data["markPrice"])
            price_int = int(price * (10 ** asset["decimals"]))
            pair_id = currency_pair_to_pair_id(*pair)
            volume = float(self.retrieve_volume(data["pair"], volume_arr)) / (
                10 ** asset["decimals"]
            )
            expiry_timestamp = 0
            if data["pair"] != f"{pair[0]}{pair[1]}":
                date_arr = data["symbol"].split("_")
                expiry_timestamp = int(date_arr)
                if expiry_timestamp > 0:
                    # log error
                    logger.error(
                        "Expiry timestamp should always be zero for perps. %s is ignored.",
                        data["symbol"],
                    )
                    continue
            result_arr.append(
                FutureEntry(
                    pair_id=pair_id,
                    price=price_int,
                    volume=int(volume),
                    timestamp=int(timestamp / 1000),
                    source=self.SOURCE,
                    publisher=self.publisher,
                    expiry_timestamp=expiry_timestamp,
                    autoscale_volume=True,
                )
            )
        return result_arr

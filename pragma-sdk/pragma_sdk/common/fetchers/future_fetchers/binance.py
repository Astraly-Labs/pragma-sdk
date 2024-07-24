import json
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, FutureEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class BinanceFutureFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://fapi.binance.com/fapi/v1/premiumIndex"
    VOLUME_URL: str = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    SOURCE: str = "BINANCE"

    async def _fetch_volume(
        self, pair: Pair, session: ClientSession
    ) -> List[Tuple[str, int]] | PublisherFetchError:
        url = f"{self.VOLUME_URL}"
        selection = f"{pair.base_currency.id}{pair.quote_currency.id}"
        volume_arr = []
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Binance")
            result = await resp.json(content_type="application/json")
            for element in result:
                if selection in element["symbol"]:
                    volume_arr.append(
                        (element["symbol"], int(float(element["quoteVolume"])))
                    )
            return volume_arr

    async def fetch_pair(  # type: ignore[override]
        self, pair: Pair, session: ClientSession
    ) -> List[FutureEntry] | PublisherFetchError:
        filtered_data = []
        url = self.format_url()
        selection = str(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Binance")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"Binance: Unexpected content type: {content_type}")

            for element in result:
                if selection in element["symbol"]:
                    filtered_data.append(element)
            volume_arr = await self._fetch_volume(pair, session)
            return self._construct(pair, filtered_data, volume_arr)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries: List[Entry | PublisherFetchError | BaseException] = []
        for pair in self.pairs:
            future_entries = await self.fetch_pair(pair, session)
            if isinstance(future_entries, list):
                entries.extend(future_entries)
            else:
                entries.append(future_entries)
        return entries

    def format_url(self, pair: Optional[Pair] = None) -> str:
        return self.BASE_URL

    def _retrieve_volume(
        self, pair: Pair, volume_arr: List[Tuple[str, int]] | PublisherFetchError
    ) -> int:
        if isinstance(volume_arr, PublisherFetchError):
            return 0
        for list_pair, list_vol in volume_arr:
            if pair == list_pair:
                return list_vol
        return 0

    def _construct(
        self,
        pair: Pair,
        result: Any,
        volume_arr: List[Tuple[str, int]] | PublisherFetchError,
    ) -> List[FutureEntry]:
        result_arr = []
        decimals = pair.decimals()
        for data in result:
            timestamp = int(data["time"])
            price = float(data["markPrice"])
            price_int = int(price * (10**decimals))
            volume = float(self._retrieve_volume(data["symbol"], volume_arr)) / (
                10**decimals
            )
            if data["symbol"] == f"{pair.base_currency.id}{pair.quote_currency.id}":
                expiry_timestamp = 0
            else:
                date_arr = data["symbol"].split("_")
                if len(date_arr) > 1:
                    date_part = date_arr[1]
                    expiry_date = datetime.strptime(date_part, "%y%m%d")
                    expiry_date = expiry_date.replace(
                        hour=8, minute=0, second=0, tzinfo=timezone.utc
                    )
                    expiry_timestamp = int(expiry_date.timestamp())
                else:
                    expiry_timestamp = int(0)
            result_arr.append(
                FutureEntry(
                    pair_id=pair.id,
                    price=price_int,
                    volume=int(volume),
                    timestamp=int(timestamp / 1000),
                    source=self.SOURCE,
                    publisher=self.publisher,
                    expiry_timestamp=expiry_timestamp * 1000,
                )
            )
        return result_arr

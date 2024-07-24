import json
from typing import Any, List, Union

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import FutureEntry, Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class OkxFutureFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://okx.com/api/v5/market/tickers"
    SOURCE: str = "OKX"
    TIMESTAMP_URL: str = "https://www.okx.com/api/v5/public/instruments"

    async def fetch_expiry_timestamp(
        self, pair: Pair, instrument_id: str, session: ClientSession
    ) -> Union[int, PublisherFetchError]:
        url = self.format_expiry_timestamp_url(instrument_id)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from OKX")
            result = await resp.json(content_type="application/json")
            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from OKX")
            return int(result["data"][0]["expTime"])

    def format_expiry_timestamp_url(self, instrument_id: str) -> str:
        return f"{self.TIMESTAMP_URL}?instType=FUTURES&instId={instrument_id}"

    async def fetch_pair(  # type: ignore[override]
        self, pair: Pair, session: ClientSession
    ) -> PublisherFetchError | List[Entry]:
        url = self.format_url(pair)
        future_entries: List[Entry] = []
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
            result_len = len(result["data"])
            if result_len > 1:
                for i in range(0, result_len):
                    expiry_timestamp = await self.fetch_expiry_timestamp(
                        pair, result["data"][i]["instId"], session
                    )
                    if not isinstance(expiry_timestamp, PublisherFetchError):
                        future_entries.append(
                            self._construct(pair, result["data"][i], expiry_timestamp)
                        )
            return future_entries

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

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}?instType=FUTURES&uly={pair.base_currency.id}-{pair.quote_currency.id}"
        return url

    def _construct(self, pair: Pair, data: Any, expiry_timestamp: int) -> FutureEntry:
        timestamp = int(int(data["ts"]) / 1000)
        decimals = pair.decimals()
        price = float(data["last"])
        price_int = int(price * (10**decimals))
        volume = float(data["volCcy24h"])

        logger.debug("Fetched  future for %s from OKX", pair.id)

        return FutureEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            expiry_timestamp=int(expiry_timestamp),
        )

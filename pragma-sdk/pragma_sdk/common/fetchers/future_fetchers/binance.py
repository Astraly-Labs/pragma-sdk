import asyncio
import json
import time

from datetime import datetime, timezone
from typing import Any, List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, FutureEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class BinanceFutureFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://fapi.binance.com/fapi/v1/premiumIndex"
    SOURCE: str = "BINANCE"

    async def fetch_pair(  # type: ignore[override]
        self,
        pair: Pair,
        session: ClientSession,
        configuration_decimals: Optional[int] = None,
    ) -> FutureEntry | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Binance")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"Binance: Unexpected content type: {content_type}")

            if "code" in result:
                return PublisherFetchError(f"No data found for {pair} from Binance")

            return self._construct(pair, result, configuration_decimals=configuration_decimals)

    async def fetch(
        self, session: ClientSession, configuration_decimals: Optional[int] = None
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = []
        for pair in self.pairs:
            entries.append(
                asyncio.ensure_future(
                    self.fetch_pair(pair, session, configuration_decimals)
                )
            )
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        return (
            self.BASE_URL + "?symbol=" + pair.base_currency.id + pair.quote_currency.id
        )

    def _construct(
        self,
        pair: Pair,
        data: Any,
        configuration_decimals: Optional[int] = None,
    ) -> list[FutureEntry] | PublisherFetchError:
        decimals = (
            pair.decimals()
            if configuration_decimals is None
            else configuration_decimals
        )
        price = float(data["markPrice"])
        price_int = int(price * (10**decimals))
        volume = 0  # TODO: Implement volume
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

        return FutureEntry(
            pair_id=pair.id,
            price=price_int,
            volume=int(volume),
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            expiry_timestamp=expiry_timestamp * 1000,
        )

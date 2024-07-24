import asyncio
import time
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


ASSET_MAPPING: Dict[str, Any] = {
    "LORDS": (
        "starknet-alpha",
        "0x124aeb495b947201f5fac96fd1138e326ad86195b98df6dec9009158a533b49",
    ),
    "R": ("eth", "0x183015a9ba6ff60230fdeadc3f43b3d788b13e21"),
    "WBTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "BTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "WSTETH": ("eth", "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"),
    "ETH": ("eth", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
    "UNI": ("eth", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"),
    "LUSD": ("eth", "0x5f98805a4e8be255a32880fdec7f6728c6568ba0"),
    "STRK": (
        "starknet-alpha",
        "0x4718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d",
    ),
    "ZEND": (
        "starknet-alpha",
        "0x00585c32b625999e6e5e78645ff8df7a9001cf5cf3eb6b80ccdd16cb64bd3a34",
    ),
    "YFI": (
        "eth",
        "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e",
    ),
    "COMP": ("eth", "0xc00e94Cb662C3520282E6f5717214004A7f26888"),
    "SNX": ("eth", "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F"),
    "MKR": ("eth", "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2"),
    "BAL": ("eth", "0xba100000625a3754423978a60c9317c58a424e3D"),
    "AAVE": ("eth", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
    "LDO": ("eth", "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32"),
    "RPL": ("eth", "0xD33526068D116cE69F19A9ee46F0bd304F21A51f"),
    "WETH": ("eth", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    "MC": ("eth", "0x949d48eca67b17269629c7194f4b727d4ef9e5d6"),
    "RNDR": ("eth", "0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24"),
    "FET": ("eth", "0xaea46A60368A7bD060eec7DF8CBa43b7EF41Ad85"),
    "IMX": ("eth", "0xf57e7e7c23978c3caec3c3548e3d615c346e79ff"),
    "GALA": ("eth", "0xd1d2Eb1B1e90B638588728b4130137D262C87cae"),
    "ILV": ("eth", "0x767fe9edc9e0df98e07454847909b5e959d7ca0e"),
    "SAND": ("eth", "0x3845badAde8e6dFF049820680d1F14bD3903a5d0"),
    "AXS": ("eth", "0xbb0e17ef65f82ab018d8edd776e8dd940327b28b"),
    "MANA": ("eth", "0x0f5d2fb29fb7d3cfee444a200298f468908cc942"),
    "ENS": ("eth", "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72"),
    "BLUR": ("eth", "0x5283d291dbcf85356a21ba090e6db59121208b44"),
    "DPI": ("eth", "0x1494ca1f11d487c2bbe4543e90080aeba4ba3c2b"),
    "MVI": ("eth", "0x72e364f2abdc788b7e918bc238b21f109cd634d7"),
    "NSTR": ("eth", "0x610dbd98a28ebba525e9926b6aaf88f9159edbfd"),
}


class GeckoTerminalFetcher(FetcherInterfaceT):
    BASE_URL: str = (
        "https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}"
    )
    SOURCE: str = "GECKOTERMINAL"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        if pair.quote_currency.id != "USD":
            return await self.operate_usd_hop(pair, session)
        pool = ASSET_MAPPING.get(pair.base_currency.id)
        if pool is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query GeckoTerminal for {pair.base_currency}"
            )
        url = self.BASE_URL.format(network=pool[0], token_address=pool[1])
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )
            result = await resp.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )

        return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        pool = ASSET_MAPPING[pair.base_currency.id]
        url = self.BASE_URL.format(network=pool[0], token_address=pool[1])
        return url

    async def operate_usd_hop(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        pool_1 = ASSET_MAPPING.get(pair.base_currency.id)
        pool_2 = ASSET_MAPPING.get(pair.quote_currency.id)
        if pool_1 is None or pool_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query GeckoTerminal for hop {pair.base_currency} to {pair.quote_currency}"
            )

        pair1_url = self.format_url(
            Pair(
                pair.base_currency,
                Currency.from_asset_config(AssetConfig.from_ticker("USD")),
            )
        )

        async with session.get(pair1_url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )
            result = await resp.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )

        pair2_url = self.format_url(
            Pair(
                pair.quote_currency,
                Currency.from_asset_config(AssetConfig.from_ticker("USD")),
            )
        )
        async with session.get(pair2_url, headers=self.headers) as resp2:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )
            hop_result = await resp2.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {pair} from GeckoTerminal"
                )
        return self._construct(pair, result, hop_result)

    def _construct(
        self, pair: Pair, result: Any, hop_result: Optional[Any] = None
    ) -> SpotEntry:
        data = result["data"]["attributes"]
        price = float(data["price_usd"])
        decimals = pair.decimals()
        if hop_result is not None:
            hop_price = float(hop_result["data"]["attributes"]["price_usd"])
            price_int = int(hop_price / price * 10**decimals)
        else:
            price_int = int(price * (10**decimals))

        volume = float(data["volume_usd"]["h24"])

        timestamp = int(time.time())

        logger.debug("Fetched  price %d for %s from GeckoTerminal", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=int(volume),
        )

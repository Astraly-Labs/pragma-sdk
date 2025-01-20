import time

from typing import List, Optional, Dict, Tuple
from enum import IntEnum
from aiohttp import ClientSession

from starknet_py.net.client_models import Call
from starknet_py.hash.selector import get_selector_from_name

from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.utils import uint256_to_int

from pragma_sdk.onchain.types.types import Network

logger = get_pragma_sdk_logger()

# Below is the list of parameters related to the Price Fetcher contract from Ekubo, i.e:
#   * the contract,
#   * the selector,
#   * the period, i.e now() - period_as_seconds = the data we consider for the price
#   * min tokens, i.e the minimum liquidity accepted for a pair

PRICE_FETCHER_CONTRACT: Dict[Network, str] = {
    "sepolia": "0x04613bee55d8a37adfa249b24c6b13451dedf7cf4f02d01de859579119de3add",
    "mainnet": "0x04946fb4ad5237d97bbb1256eba2080c4fe1de156da6a7f83e3b4823bb6d7da1",
}
GET_PRICES_SELECTOR = get_selector_from_name("get_prices")
PERIOD = 3600  # one hour
MIN_TOKENS = int(1e18)


class EkuboStatus(IntEnum):
    NOT_INITIALIZED = 0
    INSUFFICIENT_LIQUIDITY = 1
    PERIOD_TOO_LONG = 2
    PRICE_AVAILABLE = 3


class EkuboFetcher(FetcherInterfaceT):
    SOURCE: str = "EKUBO"

    pairs: List[Pair]
    publisher: str
    price_fetcher_contract: int
    hop_handler: HopHandler = HopHandler(
        hopped_currencies={"USD": "USDC", "USDPLUS": "USDC"}
    )

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        price_fetcher_contract = PRICE_FETCHER_CONTRACT.get(network)
        if price_fetcher_contract is None:
            raise ValueError(f"Ekubo Price Fetcher not available for {network}")
        self.price_fetcher_contract = int(price_fetcher_contract, 16)
        super().__init__(pairs, publisher, api_key, network)

    async def fetch(
        self, session: ClientSession, configuration_decimals: Optional[int] = None
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        pairs: List[Tuple[Pair, bool]] = self._get_pairs_after_hop()
        hop_prices = (
            await self.hop_handler.get_hop_prices(self.client)
            if any([has_been_hopped for _, has_been_hopped in pairs])
            else None
        )

        # We make N calls per N unique quote assets. To do so, we group
        # the pairs by their quote currencies.
        groupped_pairs = self._group_pairs_by_quote(pairs)

        entries = []
        for quote, base_currencies in groupped_pairs.items():
            if quote[0].starknet_address == 0:
                entries.extend(self._get_no_quote_errors(quote, base_currencies))
                continue
            response = await self._call_get_prices(quote, base_currencies)
            new_entries = await self._parse_response_into_entries(
                quote=quote,
                bases=base_currencies,
                res=response,
                hop_prices=hop_prices,
                configuration_decimals=configuration_decimals,
            )
            entries.extend(new_entries)

        return entries  # type: ignore[call-overload]

    def _get_no_quote_errors(
        self, quote: Tuple[Currency, bool], base_currencies: List[Currency]
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Returns errors for the pairs that have a Quote currency without address.
        """
        return [
            PublisherFetchError(
                f"No data found for {Pair(base, quote[0])} from Ekubo:"
                f' no onchain starknet address for "{quote[0].id}"'
            )
            for base in base_currencies
        ]

    async def _call_get_prices(
        self,
        quote: Tuple[Currency, bool],
        bases: List[Currency],
    ) -> List[int]:
        """
        Calls the get_prices function from the Price Fetcher contract and returns
        the response.
        """
        call = Call(
            to_addr=self.price_fetcher_contract,
            selector=GET_PRICES_SELECTOR,
            calldata=[
                quote[0].starknet_address,
                len(bases),
                *[c.starknet_address for c in bases],
                PERIOD,
                MIN_TOKENS,
            ],
        )
        response: list[int] = await self.client.full_node_client.call_contract(
            call=call,
            block_hash="pending",
        )
        return response

    async def _parse_response_into_entries(
        self,
        quote: Tuple[Currency, bool],
        bases: List[Currency],
        res: List[int],
        hop_prices: Optional[Dict[Pair, float]],
        configuration_decimals: Optional[int] = None,
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Parse response data into a list of entries or errors.
        First element is the number of responses.
        Following elements are either:
            - Status (0: NotInitialized, 1: InsufficientLiquidity, 2: PeriodTooLong, 3: Price)
            - If status is 3 (PRICE_AVAILABLE), next two elements are price (low, high)
        """
        num_responses = res[0]
        if num_responses > len(bases):
            return [
                BaseException(
                    f"Got {num_responses} price responses but only {len(bases)} base assets."
                )
            ]

        entries: List[Entry | PublisherFetchError | BaseException] = []

        current_idx = 1
        current_base_idx = 0
        while current_base_idx < num_responses and current_idx < len(res):
            base = bases[current_base_idx]
            pair = Pair.from_tickers(base.id, quote[0].id)
            status = EkuboStatus(res[current_idx])

            match status:
                case EkuboStatus.PRICE_AVAILABLE:
                    if current_idx + 2 >= len(res):
                        return [
                            BaseException(
                                "Incomplete price data in the Price Fetcher response."
                            )
                        ]

                    entry, idx_increment = await self._handle_price_status(
                        current_idx=current_idx,
                        res=res,
                        pair=pair,
                        is_hopped_pair=quote[1],
                        hop_prices=hop_prices,
                        configuration_decimals=configuration_decimals,
                    )
                    entries.append(entry)

                case _:
                    publisher_error, idx_increment = self._handle_error_status(
                        status=status,
                        pair=pair,
                    )
                    entries.append(publisher_error)

            current_idx += idx_increment
            current_base_idx += 1

        return entries

    async def _handle_price_status(
        self,
        current_idx: int,
        res: List[int],
        pair: Pair,
        is_hopped_pair: bool,
        hop_prices: Optional[Dict[Pair, float]],
        configuration_decimals: Optional[int] = None,
    ) -> Tuple[SpotEntry, int]:
        """
        Handle the sub-array of the Ekubo Response when the response was 3, i.e
        PRICE_AVAILABLE.

        The steps are:
            * 1. Convert the UINT256 price from Ekubo to int,
            * 2. Convert this cairo price to a correct price for the pair,
            * 3. If the pair has been hopped, convert it back to the original pair,
            * 4. Create the new Entry.

        At the end, we return the created Entry and the number of elements used
        in the Cairo response.
        """
        raw_price = uint256_to_int(low=res[current_idx + 1], high=res[current_idx + 2])
        price = self._convert_raw_cairo_price(pair, raw_price)

        if is_hopped_pair:
            if hop_prices is None:
                raise ValueError("Hopped prices are None. Should never happen.")
            pair, price = await self._adapt_back_hopped_pair(hop_prices, pair, price)

        price_int = (
            int(price * 10 ** pair.decimals())
            if configuration_decimals is None
            else int(price * 10**configuration_decimals)
        )
        logger.debug("Fetched price %d for %s from Ekubo", price_int, pair)

        entry = SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry, 3

    async def _adapt_back_hopped_pair(
        self,
        hop_prices: Dict[Pair, float],
        pair: Pair,
        price: float,
    ) -> Tuple[Pair, float]:
        """
        If a hop occured for the given pair, we enter this function.

        For example, if we just fetched the price of the pair BTC/USDC
        but we know that a hop occured with USD, we convert it back
        to BTC/USD.

        To do so, we use the hop_prices of USDC/USD and compute
        the conversion between the two pairs.

        At the end, we return the original Pair before hop and the price.
        """
        # For USDPLUS, use USD prices directly
        requested_quote = self.pairs[0].quote_currency.id
        lookup_quote = "USD" if requested_quote == "USDPLUS" else requested_quote

        hop_quote_pair = Pair.from_tickers(pair.quote_currency.id, lookup_quote)
        hop_price = hop_prices.get(hop_quote_pair)

        if hop_price is None:
            # Try reverse pair
            reverse_pair = Pair.from_tickers(lookup_quote, pair.quote_currency.id)
            reverse_price = hop_prices.get(reverse_pair)
            if reverse_price:
                hop_price = 1 / reverse_price
            else:
                raise ValueError(
                    f"No valid hop price found for {hop_quote_pair} or {reverse_pair}"
                )

        # Create the final pair with the originally requested quote currency
        new_pair = Pair.from_tickers(pair.base_currency.id, requested_quote)
        final_price = price * hop_price

        return (new_pair, final_price)

    def _handle_error_status(
        self, status: EkuboStatus, pair: Pair
    ) -> Tuple[PublisherFetchError, int]:
        """
        Handle error statuses (0, 1, 2) - i.e, return the correct PublisherFetchError
        with the right message.
        """
        error_messages = {
            EkuboStatus.NOT_INITIALIZED: f"Price feed not initialized for {pair} in Ekubo",
            EkuboStatus.INSUFFICIENT_LIQUIDITY: f"Insufficient liquidity for {pair} in Ekubo",
            EkuboStatus.PERIOD_TOO_LONG: f"Period too long for {pair}",
        }
        return PublisherFetchError(error_messages[status]), 1

    def _convert_raw_cairo_price(self, pair: Pair, raw_price: int) -> float:
        """
        Converts a Raw price returned from the Ekubo Price Fetcher contract to
        a price with the right decimals depending on the pair.
        """
        decimals = abs(pair.quote_currency.decimals - pair.base_currency.decimals)
        price: float = (raw_price / (2**128)) * (10**decimals)
        return price

    def _get_pairs_after_hop(self) -> List[Tuple[Pair, bool]]:
        """
        Returns the Fetcher pairs after the work of the Hop Handler.
        Each pair is associated with a boolean flag allowing us to know if
        the pair has been hopped.

        This flag is used later when grouping currencies, so we can attach this
        boolean to each hopped quote currencies and after reconstruct the original pair.
        """
        new_pairs = []
        for pair in self.pairs:
            hopped_pair = self.hop_handler.get_hop_pair(pair)
            if hopped_pair is None:
                new_pairs.append((pair, False))
            else:
                new_pairs.append((hopped_pair, True))
        return new_pairs

    def _group_pairs_by_quote(
        self,
        pairs: List[Tuple[Pair, bool]],
    ) -> Dict[Tuple[Currency, bool], List[Currency]]:
        """
        Groups a list of Pair by their quote currency.

        Example, with this set of pairs:
            - Pair(BTC, USD)
            - Pair(ETH, USD)
            - Pair(DOGE, ETH)

        We will get:
        {
            (USD, false): [BTC, ETH],
            (ETH, false): [DOGE]
        }

        all elements being of type `Currency`.

        The boolean in the key will be True if the quote currency was hopped,
        else false.
        """
        grouped_pairs: Dict[Tuple[Currency, bool], List[Currency]] = {}
        for pair, is_hopped in pairs:
            quote_currency = pair.quote_currency
            key = (quote_currency, is_hopped)
            if key not in grouped_pairs:
                grouped_pairs[key] = []
            if pair.base_currency != key[0]:
                grouped_pairs[key].append(pair.base_currency)
        return grouped_pairs

    async def fetch_pair(
        self,
        pair: Pair,
        session: ClientSession,
    ) -> Entry | PublisherFetchError:
        raise NotImplementedError("`fetch_pair` is not needed for the Ekubo Fetcher.")

    def format_url(self, pair: Pair) -> str:
        raise NotImplementedError("`format_url` is not needed for the Ekubo Fetcher.")

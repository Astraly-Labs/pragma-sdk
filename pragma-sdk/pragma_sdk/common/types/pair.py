from typing import Tuple, Optional, Dict


from pragma_sdk.common.utils import currency_pair_to_pair_id, str_to_felt
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.configs.asset_config import AssetConfig


class Pair:
    """
    Pair class to represent a trading pair.

    :param id: Corresponds to the felt representation of the pair e.g str_to_felt("ETH/USD")
    :param base_currency: Base currency
    :param quote_currency: Quote currency
    """

    id: int
    base_currency: Currency
    quote_currency: Currency

    def __init__(self, base_currency: Currency, quote_currency: Currency):
        self.id = str_to_felt(
            currency_pair_to_pair_id(base_currency.id, quote_currency.id)
        )
        self.base_currency = base_currency
        self.quote_currency = quote_currency

    def serialize(self) -> Tuple[int, Currency, Currency]:
        return (self.id, self.base_currency, self.quote_currency)

    def to_dict(self) -> Dict[str, int | str]:
        return {
            "id": self.id,
            "base_currency_id": self.base_currency.id,
            "quote_currency_id": self.quote_currency.id,
        }

    def __str__(self) -> str:
        return f"{self.base_currency.id}/{self.quote_currency.id}"

    def __repr__(self) -> str:
        return f"{self.base_currency.id}/{self.quote_currency.id}"

    def __hash__(self) -> int:
        return hash((self.id, self.base_currency, self.quote_currency))

    def to_tuple(self) -> Tuple[str, str]:
        return (self.base_currency.id, self.quote_currency.id)

    def decimals(self) -> int:
        """
        Returns the decimals of the pair.
        Corresponds to the minimum of both currencies' decimals.
        """
        return min(self.base_currency.decimals, self.quote_currency.decimals)

    @classmethod
    def from_asset_configs(
        cls, base_asset: AssetConfig, quote_asset: AssetConfig
    ) -> Optional["Pair"]:
        """
        Return a Pair from two AssetConfigs.
        Return None if the base and quote assets are the same.

        :param base_asset: Base asset
        :param quote_asset: Quote asset
        :return: Pair
        """

        if base_asset == quote_asset:
            return None

        return cls(
            base_currency=Currency.from_asset_config(base_asset),
            quote_currency=Currency.from_asset_config(quote_asset),
        )

    @staticmethod
    def from_tickers(base_ticker: str, quote_ticker: str) -> Optional["Pair"]:
        """
        Return a Pair from two tickers.
        Return None if the base and quote tickers are the same.

        :param base_ticker: Base ticker
        :param quote_ticker: Quote ticker
        :return: Pair
        """

        base_asset = AssetConfig.from_ticker(base_ticker)
        quote_asset = AssetConfig.from_ticker(quote_ticker)
        return Pair.from_asset_configs(base_asset, quote_asset)

import yaml

from typing import List, Optional, Self

from pydantic import BaseModel

from pragma_sdk.common.types.types import Decimals
from pragma_sdk.common.exceptions import UnsupportedAssetError

from pathlib import Path

SUPPORTED_ASSETS_FILE_PATH = (
    Path(__file__).parent.parent.parent / "supported_assets.yaml"
)


class AssetConfig(BaseModel):
    name: str
    decimals: Decimals
    ticker: str
    coingecko_id: Optional[str] = None
    abstract: Optional[bool] = False

    @classmethod
    def from_yaml(cls, path: Path) -> List[Self]:
        with open(path, "r") as file:
            assets_configs = yaml.safe_load(file)
        list_configs = [cls(**config) for config in assets_configs]
        return list_configs

    @classmethod
    def from_ticker(cls, ticker: str) -> "AssetConfig":
        """
        Return a AssetConfig from a ticker.
        Raise UnsupportedAssetError if the ticker is not supported.

        :param ticker: Ticker
        :return: AssetConfig
        """

        assets = filter(lambda x: x.ticker == ticker, ALL_ASSETS_CONFIGS)
        try:
            asset = next(assets)
            return asset
        except StopIteration:
            raise UnsupportedAssetError(f"Asset with ticker {ticker} is not supported.")

    @staticmethod
    def get_coingecko_id_from_ticker(ticker: str) -> str:
        """
        Return the coingecko id from a ticker.
        Raise UnsupportedAssetError if the ticker is not supported.

        :param ticker: Ticker
        :return: Coingecko id
        """

        asset = AssetConfig.from_ticker(ticker)
        if asset.coingecko_id is None:
            raise ValueError(f"{ticker} does not have any coingecko id.")
        return asset.coingecko_id


ALL_ASSETS_CONFIGS: List[AssetConfig] = AssetConfig.from_yaml(
    SUPPORTED_ASSETS_FILE_PATH
)

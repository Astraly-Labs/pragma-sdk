from typing import Dict, List, Optional, Set

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated

from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.types.pair import Pair


class PairConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    spot: Optional[List[Pair]] = None
    future: Optional[List[Pair]] = None


class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs: PairConfig
    time_difference: Annotated[int, Field(strict=True, gt=0)]
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator("pairs", mode="before")
    def validate_pairs(cls, value: PairConfig) -> PairConfig:
        if "spot" in value:
            value["spot"] = cls.validate_asset_pairs(value["spot"])
        if "future" in value:
            value["future"] = cls.validate_asset_pairs(value["future"])
        return value

    @staticmethod
    def validate_asset_pairs(pairs: List[str]) -> List:
        assets = []
        for pair in pairs:
            pair = pair.replace(" ", "").upper()
            base, quote = pair.split("/")
            assets.append(Pair.from_tickers(base, quote))
        return list(set(assets))

    @classmethod
    def from_yaml(cls, path: str) -> List["PriceConfig"]:
        with open(path, "r") as file:
            price_configs = yaml.safe_load(file)
        list_configs = [cls(**config) for config in price_configs]
        return list_configs

    def get_all_assets(self) -> Dict[DataTypes, List[Pair]]:
        """
        Get all spot and future assets from the configuration.

        Returns:
            Dict from DataTypes to List of Pairs.
        """
        pair_dict_by_type = {}
        if self.pairs.spot:
            pair_dict_by_type[DataTypes.SPOT] = self.pairs.spot
        if self.pairs.future:
            pair_dict_by_type[DataTypes.FUTURE] = self.pairs.future
        return pair_dict_by_type


def get_unique_pairs_from_config_list(
    price_configs: List[PriceConfig], pair_type: DataTypes
) -> Set[Pair]:
    """
    Extract unique pairs from a list of PriceConfig objects.

    Args:
        price_configs: List of PriceConfig objects.
        pair_type: Type of pair to extract (DataTypes.SPOT or DataTypes.FUTURE).

    Returns:
        Set of unique Pairs.
    """
    if pair_type not in [DataTypes.SPOT, DataTypes.FUTURE]:
        raise ValueError("pair_type must be either DataTypes.SPOT or DataTypes.FUTURE")

    return {pair for config in price_configs for pair in config.get_all_assets().get(pair_type, [])}


def get_unique_spot_pairs_from_config_list(
    price_configs: List[PriceConfig],
) -> Set[Pair]:
    return get_unique_pairs_from_config_list(price_configs, DataTypes.SPOT)


def get_unique_future_pairs_from_config_list(
    price_configs: List[PriceConfig],
) -> Set[Pair]:
    return get_unique_pairs_from_config_list(price_configs, DataTypes.FUTURE)

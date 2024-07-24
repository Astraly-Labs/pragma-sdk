import yaml
from typing import List, Optional, Tuple, Union
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, field_validator

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import str_to_felt


@dataclass(frozen=True)
class SpotPairConfig:
    pair: Pair


@dataclass(frozen=True)
class FuturePairConfig:
    pair: Pair
    expiry: datetime = field(default_factory=lambda: datetime.fromtimestamp(0, ZoneInfo("UTC")))


class PairsConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    spot: List[SpotPairConfig] = field(default_factory=list)
    future: List[FuturePairConfig] = field(default_factory=list)

    @field_validator("spot", "future", mode="before")
    def validate_pairs(
        cls, value: Optional[List[dict]], info
    ) -> List[SpotPairConfig | FuturePairConfig]:
        if not value:
            return []

        pairs: List[Union[SpotPairConfig, FuturePairConfig]] = []
        for raw_pair in value:
            pair_str = raw_pair["pair"].replace(" ", "").upper()
            base, quote = pair_str.split("/")
            if len(base) == 0 or len(quote) == 0:
                raise ValueError("Pair should be formatted as 'BASE/QUOTE'")

            pair = Pair.from_tickers(base, quote)
            if pair is None:
                raise ValueError(f"⛔ Could not create Pair object for {base}/{quote}")

            if info.field_name == "future":
                expiry = datetime.fromtimestamp(raw_pair.get("expiry", 0), tz=ZoneInfo("UTC"))
                pairs.append(FuturePairConfig(pair=pair, expiry=expiry))
            else:
                pairs.append(SpotPairConfig(pair=pair))

        return list(set(pairs))

    @classmethod
    def from_yaml(cls, path: str) -> "PairsConfig":
        with open(path, "r") as file:
            pairs_config = yaml.safe_load(file)
        config = cls(**pairs_config)

        if not config.spot and not config.future:
            raise ValueError(
                "⛔ No pair found: you need to specify at least one spot/future pair in the configuration file."
            )
        return config

    def get_spot_ids(self) -> List[int]:
        return [str_to_felt(str(pair_config.pair)) for pair_config in self.spot]

    def get_future_ids_and_expiries(self) -> Tuple[List[int], List[int]]:
        pair_ids = [str_to_felt(str(pair_config.pair)) for pair_config in self.future]
        expiries = [int(pair_config.expiry.timestamp()) for pair_config in self.future]
        return pair_ids, expiries

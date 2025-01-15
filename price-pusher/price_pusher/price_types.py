from typing import Dict, Literal, Union

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import DataTypes

DurationInSeconds = int

PairId = str
SourceName = str
ExpiryTimestamp = str
FuturePrices = Dict[ExpiryTimestamp, Entry]
LatestOrchestratorPairPrices = Dict[
    PairId,
    Dict[DataTypes, Union[Dict[SourceName, Entry], Dict[SourceName, FuturePrices]]],
]
LatestOraclePairPrices = Dict[PairId, Dict[DataTypes, Entry]]
Target = Literal["onchain", "offchain"]
Network = Literal["mainnet", "sepolia", "pragma_devnet"]

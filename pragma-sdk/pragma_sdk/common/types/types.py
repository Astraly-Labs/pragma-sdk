from enum import StrEnum, unique
from typing import Dict

Address = int
HexStr = str
Decimals = int
UnixTimestamp = int


@unique
class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"


@unique
class AggregationMode(StrEnum):
    MEDIAN = "Median"
    AVERAGE = "Mean"
    ERROR = "Error"

    def serialize(self) -> Dict[str, None]:
        return {self.value: None}


@unique
class DataTypes(StrEnum):
    SPOT = "Spot"
    FUTURE = "Future"

    def __repr__(self):
        return f"'{self.value}'"

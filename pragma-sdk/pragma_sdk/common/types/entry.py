from __future__ import annotations

import abc

from datetime import datetime
from pydantic.dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from pragma_sdk.common.types.types import DataTypes, UnixTimestamp
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.onchain.types.types import OracleResponse


FUTURE_ENTRY_EXPIRIES_FORMAT = "%Y-%m-%dT%H:%M:%S"


class Entry(abc.ABC):
    """
    Abstract class that represents an Entry.
    All entries must implement this class.
    """

    @abc.abstractmethod
    def to_tuple(self) -> Tuple[Any]: ...

    @abc.abstractmethod
    def serialize(self) -> Dict[str, object]: ...

    @abc.abstractmethod
    def offchain_serialize(self) -> Dict[str, object]: ...

    @abc.abstractmethod
    def get_timestamp(self) -> int: ...

    @abc.abstractmethod
    def get_expiry(self) -> Optional[str]: ...

    @abc.abstractmethod
    def get_pair_id(self) -> str: ...

    @abc.abstractmethod
    def get_source(self) -> str: ...

    @abc.abstractmethod
    def get_asset_type(self) -> DataTypes: ...

    @staticmethod
    def serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        serialized_entries = [entry.serialize() for entry in entries]
        return list(filter(lambda item: item is not None, serialized_entries))  # type: ignore[arg-type]

    @staticmethod
    def offchain_serialize_entries(entries: List[Entry]) -> List[Dict[str, int]]:
        serialized_entries = [entry.offchain_serialize() for entry in entries]
        return list(filter(lambda item: item is not None, serialized_entries))  # type: ignore[arg-type]

    @staticmethod
    def flatten_entries(entries: List[Entry]) -> List[int]:
        """This flattens entriees to tuples. Useful when you need the raw felt array"""

        expanded = [entry.to_tuple() for entry in entries]
        flattened = [x for entry in expanded for x in entry]
        return [len(entries)] + flattened


@dataclass
class BaseEntry:
    """
    BaseEntry is a dataclass that represents the common fields between SpotEntry and FutureEntry.
    """

    timestamp: UnixTimestamp
    source: int
    publisher: int

    def __init__(
        self,
        timestamp: UnixTimestamp,
        source: str | int,
        publisher: str | int,
    ):
        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.timestamp = timestamp
        self.source = source
        self.publisher = publisher

    def __hash__(self) -> int:
        return hash((self.timestamp, self.source, self.publisher))


class SpotEntry(Entry):
    """
    Represents a Spot Entry.
    """

    base: BaseEntry
    pair_id: int
    price: int
    volume: int

    def __init__(
        self,
        pair_id: str | int,
        price: int,
        timestamp: UnixTimestamp,
        source: str | int,
        publisher: str | int,
        volume: Optional[int | float] = None,
    ) -> None:
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)

        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.base = BaseEntry(timestamp, source, publisher)
        self.pair_id = pair_id
        self.price = price

        if volume is None:
            volume = 0
        if isinstance(volume, float):
            volume = int(volume)
        self.volume = volume

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SpotEntry):
            return all(
                [
                    self.pair_id == other.pair_id,
                    self.price == other.price,
                    self.base.timestamp == other.base.timestamp,
                    self.base.source == other.base.source,
                    self.base.publisher == other.base.publisher,
                    self.volume == other.volume,
                ]
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, tuple) and len(other) == 4:
            return all(
                [
                    self.pair_id == other[0],
                    self.price == other[1],
                    self.base == other[2],
                    self.volume == other[3],
                ]
            )
        return False

    def to_tuple(self) -> Tuple[int, int, int, int, int, int]:  # type: ignore[explicit-override, override]
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.volume,
        )

    def serialize(self) -> Dict[str, object]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": self.base.source,
                "publisher": self.base.publisher,
            },
            "pair_id": self.pair_id,
            "price": self.price,
            "volume": self.volume,
        }

    def offchain_serialize(self) -> Dict[str, object]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": felt_to_str(self.base.source),
                "publisher": felt_to_str(self.base.publisher),
            },
            "pair_id": felt_to_str(self.pair_id),
            "price": self.price,
            "volume": self.volume,
        }

    def set_publisher(self, publisher: int) -> "SpotEntry":
        self.base.publisher = publisher
        return self

    def get_timestamp(self) -> int:
        return self.base.timestamp

    def get_expiry(self) -> Optional[str]:
        return None

    def get_pair_id(self) -> str:
        return felt_to_str(self.pair_id)

    def get_source(self) -> str:
        return felt_to_str(self.base.source)

    def get_asset_type(self) -> DataTypes:
        return DataTypes.SPOT

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> "SpotEntry":
        """
        Builds a SpotEntry object from a Pair and an OracleResponse.
        Method primarly used by our price pusher package when we're retrieving
        lastest oracle prices for comparisons with the latest prices of
        various APIs (binance etc).
        """

        return SpotEntry(
            pair.id,
            oracle_response.price,
            oracle_response.last_updated_timestamp,
            publisher_name,
            source_name,
            0,
        )

    @staticmethod
    def from_dict(entry_dict: Any) -> "SpotEntry":
        base = dict(entry_dict["base"])
        return SpotEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            volume=entry_dict["volume"],
        )

    def __repr__(self) -> str:
        return (
            f'SpotEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}, volume={self.volume})")'
        )

    def __hash__(self) -> int:
        return hash((self.base, self.pair_id, self.price, self.volume))


class FutureEntry(Entry):
    """
    Represents a Future Entry.

    Also used to represent a Perp Entry - the only difference is that a perpetual future has no
    expiry timestamp.
    """

    base: BaseEntry
    pair_id: int
    price: int
    expiry_timestamp: int
    volume: int

    def __init__(
        self,
        pair_id: str | int,
        price: int,
        timestamp: int,
        source: str | int,
        publisher: str | int,
        expiry_timestamp: Optional[int] = None,
        volume: Optional[float | int] = None,
    ):
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)

        if isinstance(publisher, str):
            publisher = str_to_felt(publisher)

        if isinstance(source, str):
            source = str_to_felt(source)

        self.base = BaseEntry(timestamp, source, publisher)
        self.pair_id = pair_id
        self.price = price
        if expiry_timestamp is None:
            expiry_timestamp = 0
        self.expiry_timestamp = expiry_timestamp

        if volume is None:
            volume = 0
        if isinstance(volume, float):
            volume = int(volume)
        self.volume = volume

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FutureEntry):
            return all(
                [
                    self.pair_id == other.pair_id,
                    self.price == other.price,
                    self.base.timestamp == other.base.timestamp,
                    self.base.source == other.base.source,
                    self.base.publisher == other.base.publisher,
                    self.expiry_timestamp == other.expiry_timestamp,
                    self.volume == other.volume,
                ]
            )
        # This supports comparing against entries that are returned by starknet.py,
        # which will be namedtuples.
        if isinstance(other, tuple) and len(other) == 5:
            return all(
                [
                    self.pair_id == other[0],
                    self.price == other[1],
                    self.base == other[2],
                    self.expiry_timestamp == other[3],
                    self.volume == other[4],
                ]
            )
        return False

    def to_tuple(self) -> Tuple[int, int, int, int, int, int, int]:  # type: ignore[explicit-override, override]
        return (
            self.base.timestamp,
            self.base.source,
            self.base.publisher,
            self.pair_id,
            self.price,
            self.expiry_timestamp,
            self.volume,
        )

    def serialize(self) -> Dict[str, object]:
        return {
            "base": {
                "timestamp": self.base.timestamp,
                "source": self.base.source,
                "publisher": self.base.publisher,
            },
            "pair_id": self.pair_id,
            "price": self.price,
            "expiration_timestamp": self.expiry_timestamp,
            "volume": self.volume,
        }

    def offchain_serialize(self) -> Dict[str, object]:
        serialized = {
            "base": {
                "timestamp": self.base.timestamp,
                "source": felt_to_str(self.base.source),
                "publisher": felt_to_str(self.base.publisher),
            },
            "pair_id": felt_to_str(self.pair_id),
            "price": self.price,
            "volume": self.volume,
            "expiration_timestamp": self.expiry_timestamp,
        }
        return serialized

    def __repr__(self) -> str:
        return (
            f'FutureEntry(pair_id="{felt_to_str(self.pair_id)}", '
            f"price={self.price}, "
            f"timestamp={self.base.timestamp}, "
            f'source="{felt_to_str(self.base.source)}", '
            f'publisher="{felt_to_str(self.base.publisher)}, '
            f"volume={self.volume}, "
            f'expiry_timestamp={self.expiry_timestamp})")'
        )

    def __hash__(self) -> int:
        return hash(
            (self.base, self.pair_id, self.price, self.expiry_timestamp, self.volume)
        )

    def get_timestamp(self) -> UnixTimestamp:
        return self.base.timestamp

    def get_expiry(self) -> Optional[str]:
        return datetime.utcfromtimestamp(self.expiry_timestamp).strftime(
            FUTURE_ENTRY_EXPIRIES_FORMAT
        )

    def get_pair_id(self) -> str:
        return felt_to_str(self.pair_id)

    def get_source(self) -> str:
        return felt_to_str(self.base.source)

    def get_asset_type(self) -> DataTypes:
        return DataTypes.FUTURE

    @staticmethod
    def from_dict(entry_dict: Any) -> "FutureEntry":
        base = dict(entry_dict["base"])
        return FutureEntry(
            entry_dict["pair_id"],
            entry_dict["price"],
            base["timestamp"],
            base["source"],
            base["publisher"],
            entry_dict["expiration_timestamp"],
            volume=entry_dict["volume"],
        )

    @staticmethod
    def from_oracle_response(
        pair: Pair,
        oracle_response: OracleResponse,
        publisher_name: str,
        source_name: str,
    ) -> "FutureEntry":
        """
        Builds a SpotEntry object from a PragmaAsset and an OracleResponse.
        Method primarly used by our price pusher package when we're retrieving
        lastest oracle prices for comparisons with the latest prices of
        various APIs (binance etc).
        """
        return FutureEntry(
            pair.id,
            oracle_response.price,
            oracle_response.last_updated_timestamp,
            publisher_name,
            source_name,
            oracle_response.expiration_timestamp,
            0,
        )

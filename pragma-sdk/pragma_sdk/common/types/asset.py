from typing import Optional, Dict, Tuple, Union


from pragma_sdk.common.types.types import DataTypes, UnixTimestamp
from pragma_sdk.common.utils import str_to_felt


class Asset:
    data_type: DataTypes
    pair_id: int
    expiration_timestamp: Optional[UnixTimestamp]

    def __init__(
        self,
        data_type: DataTypes,
        pair_id: str | int,
        expiration_timestamp: Optional[UnixTimestamp] = None,
    ):
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        self.pair_id = pair_id
        self.data_type = data_type
        self.expiration_timestamp = expiration_timestamp

    def serialize(self) -> Dict[str, Union[int | Tuple[int, Optional[int]]]]:
        """
        Serialize method used to interact with Cairo contracts.
        """
        match self.data_type:
            case DataTypes.SPOT:
                return {"SpotEntry": self.pair_id}
            case DataTypes.FUTURE:
                return {"FutureEntry": (self.pair_id, self.expiration_timestamp)}

    def to_dict(self) -> Dict[str, Union[int, str, None]]:
        return {
            "pair_id": self.pair_id,
            "expiration_timestamp": self.expiration_timestamp,
            "data_type": self.data_type.name,
        }

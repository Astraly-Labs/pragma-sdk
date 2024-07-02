from typing import List


from pragma.common.utils import felt_to_str
from pragma.common.types.types import ADDRESS, DECIMALS


class Currency:
    id: str
    decimals: DECIMALS
    is_abstract_currency: bool
    starknet_address: ADDRESS
    ethereum_address: ADDRESS

    def __init__(
        self,
        id_: str,
        decimals: DECIMALS,
        is_abstract_currency: bool,
        starknet_address: ADDRESS = None,
        ethereum_address: ADDRESS = None,
    ):
        self.id = id_

        self.decimals = decimals

        if isinstance(is_abstract_currency, int):
            is_abstract_currency = bool(is_abstract_currency)
        self.is_abstract_currency = is_abstract_currency

        if starknet_address is None:
            starknet_address = 0
        self.starknet_address = starknet_address

        if ethereum_address is None:
            ethereum_address = 0
        self.ethereum_address = ethereum_address

    def serialize(self) -> List[str]:
        return [
            self.id,
            self.decimals,
            self.is_abstract_currency,
            self.starknet_address,
            self.ethereum_address,
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "decimals": self.decimals,
            "is_abstract_currency": self.is_abstract_currency,
            "starknet_address": self.starknet_address,
            "ethereum_address": self.ethereum_address,
        }

    def __repr__(self):
        return (
            f"Currency({felt_to_str(self.id)}, {self.decimals}, "
            f"{self.is_abstract_currency}, {self.starknet_address},"
            f" {self.ethereum_address})"
        )
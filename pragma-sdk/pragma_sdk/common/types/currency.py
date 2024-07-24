from typing import Tuple, Optional, Self, Dict

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.common.types.types import Address, Decimals
from pragma_sdk.common.configs.asset_config import AssetConfig


class Currency:
    id: str
    decimals: Decimals
    is_abstract_currency: bool
    starknet_address: Address
    ethereum_address: Address

    def __init__(
        self,
        currency_id: str,
        decimals: Decimals,
        is_abstract_currency: bool,
        starknet_address: Optional[Address] = None,
        ethereum_address: Optional[Address] = None,
    ):
        self.id = currency_id
        self.decimals = decimals

        if isinstance(is_abstract_currency, int):
            is_abstract_currency = bool(is_abstract_currency)
        self.is_abstract_currency = is_abstract_currency

        self.starknet_address = self._validate_address(starknet_address)
        self.ethereum_address = self._validate_address(ethereum_address)

    def _validate_address(self, address: Optional[Address]) -> int:
        if address is None:
            return 0
        if isinstance(address, str):
            return int(address, 16)
        return address

    @classmethod
    def from_asset_config(cls, config: AssetConfig) -> Self:
        return cls(
            currency_id=config.ticker,
            decimals=config.decimals,
            is_abstract_currency=config.abstract or False,
        )

    def serialize(self) -> Tuple[str, int, bool, int, int]:
        return (
            self.id,
            self.decimals,
            self.is_abstract_currency,
            self.starknet_address,
            self.ethereum_address,
        )

    def to_dict(self) -> Dict[str, int | str | bool]:
        return {
            "id": self.id,
            "decimals": self.decimals,
            "is_abstract_currency": self.is_abstract_currency,
            "starknet_address": self.starknet_address,
            "ethereum_address": self.ethereum_address,
        }

    def __repr__(self) -> str:
        return (
            f"Currency({str_to_felt(self.id)}, {self.decimals}, "
            f"{self.is_abstract_currency}, {self.starknet_address},"
            f" {self.ethereum_address})"
        )

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Currency):
            return False
        return (
            self.id == value.id
            and self.decimals == value.decimals
            and self.is_abstract_currency == value.is_abstract_currency
            and self.starknet_address == value.starknet_address
            and self.ethereum_address == value.ethereum_address
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.id,
                self.decimals,
                self.is_abstract_currency,
                self.starknet_address,
                self.ethereum_address,
            )
        )

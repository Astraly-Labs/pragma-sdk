from typing import List

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class AssetQuantities:
    def __init__(self, pair: Pair, quantities: float):
        self.pair = pair
        self.quantities = quantities


class IndexAggregation:
    spot_entries: List[SpotEntry]
    pair_quantities: List[AssetQuantities]

    def __init__(
        self, spot_entries: List[SpotEntry], pair_quantities: List[AssetQuantities]
    ):
        self.spot_entries = spot_entries
        self.pair_quantities = pair_quantities

    def get_index_value(self):
        self.standardize_decimals()

        total = sum(
            entry.price * quantities.quantities
            for entry, quantities in zip(self.spot_entries, self.pair_quantities)
        )
        return total

    def standardize_decimals(self):
        decimals = self.pair_quantities[0].pair.decimals()
        for i, pair_quantity in enumerate(self.pair_quantities):
            pair = pair_quantity.pair
            exponent = abs(pair.decimals() - decimals)
            if pair.decimals() > decimals:
                for j in range(0, i):
                    self.spot_entries[j].price *= 10**exponent
                    self.spot_entries[j].volume *= 10**exponent
            elif pair.decimals() < decimals:
                self.spot_entries[i].price *= 10**exponent
                self.spot_entries[i].volume *= 10**exponent
            else:
                continue

            decimals = pair.decimals()

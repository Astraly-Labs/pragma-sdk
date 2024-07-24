from typing import List, Union
from abc import ABC, abstractmethod

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.utils import add_sync_methods

from pragma_sdk.offchain.types import PublishEntriesAPIResult
from pragma_sdk.onchain.types import PublishEntriesOnChainResult


@add_sync_methods
class PragmaClient(ABC):
    @abstractmethod
    async def publish_entries(
        self, entries: List[Entry]
    ) -> Union[PublishEntriesAPIResult, PublishEntriesOnChainResult]:
        """
        Publish entries to some destination.

        :param entries: List of Entry objects
        :param execution_config: ExecutionConfig object. Only used for on-chain publishing.
        :return: Tuple of responses for spot and future entries
        """

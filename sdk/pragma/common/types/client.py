from typing import List, Optional
from abc import ABC, abstractmethod

from pragma.common.types.entry import Entry
from pragma.common.types.types import ExecutionConfig
from pragma.common.utils import add_sync_methods


@add_sync_methods
class PragmaClient(ABC):
    @abstractmethod
    async def publish_entries(
        self, entries: List[Entry], execution_config: Optional[ExecutionConfig] = None
    ) -> any:
        """
        Publish entries to some destination.

        :param entries: List of Entry objects
        :param execution_config: ExecutionConfig object. Only used for on-chain publishing.
        :return: Tuple of responses for spot and future entries
        """

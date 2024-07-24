from typing import List

from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client

from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.common.utils import str_to_felt


class PublisherRegistryMixin:
    client: Client
    account: Account
    publisher_registry: Contract
    execution_config: ExecutionConfig

    async def get_all_publishers(self) -> List[int]:
        """
        Returns all publishers registered in the publisher registry.

        :return: List of publishers. (as felt integers)
        """

        (publishers,) = await self.publisher_registry.functions[
            "get_all_publishers"
        ].call()

        return publishers  # type: ignore[no-any-return]

    async def get_publisher_address(self, publisher: str) -> int:
        """
        Returns the address of a publisher.

        :param publisher: The publisher to get the address of.
        :return: The address of the publisher. (as a felt integer)
        """

        (address,) = await self.publisher_registry.functions[
            "get_publisher_address"
        ].call(publisher)

        return address  # type: ignore[no-any-return]

    async def get_publisher_sources(self, publisher: str) -> List[int]:
        """
        Returns the sources of a publisher.

        :param publisher: The publisher to get the sources of.
        :return: The sources of the publisher. (as felt integers)
        """

        (sources,) = await self.publisher_registry.functions[
            "get_publisher_sources"
        ].call(publisher)

        return sources  # type: ignore[no-any-return]

    async def add_publisher(
        self,
        publisher: str,
        publisher_address: int,
    ) -> InvokeResult:
        """
        Add a publisher to the publisher registry.
        Can only be called by the owner of the publisher registry.

        :param publisher: The publisher to add.
        :param publisher_address: The address of the publisher.
        :param execution_config: The execution config to use.
        :return: The invocation result.
        """
        invocation = await self.publisher_registry.functions["add_publisher"].invoke(
            str_to_felt(publisher),
            publisher_address,
            execution_config=self.execution_config,
        )
        return invocation  # type: ignore[no-any-return]

    async def add_source_for_publisher(
        self,
        publisher: str,
        source: str,
    ) -> InvokeResult:
        """
        Add a source for a publisher.
        Can only be called by the owner of the publisher registry.

        :param publisher: The publisher to add the source to.
        :param source: The source to add.
        :param execution_config: The execution config to use.
        :return: The invocation result.
        """
        invocation = await self.publisher_registry.functions[
            "add_source_for_publisher"
        ].invoke(
            str_to_felt(publisher),
            str_to_felt(source),
            execution_config=self.execution_config,
        )
        return invocation  # type: ignore[no-any-return]

    async def add_sources_for_publisher(
        self,
        publisher: str,
        sources: List[str],
    ) -> InvokeResult:
        """
        Add multiple sources for a publisher.
        Can only be called by the owner of the publisher registry.

        :param publisher: The publisher to add the sources to.
        :param sources: The sources to add.
        :param execution_config: The execution config to use.
        :return: The invocation result.
        """
        invocation = await self.publisher_registry.functions[
            "add_sources_for_publisher"
        ].invoke(
            str_to_felt(publisher),
            [str_to_felt(source) for source in sources],
            execution_config=self.execution_config,
        )
        return invocation  # type: ignore[no-any-return]

    async def update_publisher_address(
        self,
        publisher: str,
        publisher_address: int,
    ) -> InvokeResult:
        """
        Update the address of a publisher.
        Can only be called by the owner of the publisher registry.

        :param publisher: The publisher to update the address of.
        :param publisher_address: The new address of the publisher.
        :param execution_config: The execution config to use.
        :return: The invocation result.
        """
        invocation = await self.publisher_registry.functions[
            "update_publisher_address"
        ].invoke(
            str_to_felt(publisher),
            publisher_address,
            execution_config=self.execution_config,
        )
        return invocation  # type: ignore[no-any-return]

import time
from typing import Callable, Coroutine, Dict, List, Optional, Sequence, cast

from deprecated import deprecated
from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.common.types.entry import Entry, FutureEntry, SpotEntry, GenericEntry
from pragma_sdk.common.types.types import AggregationMode
from pragma_sdk.common.types.asset import Asset
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import (
    DataTypes,
    Address,
    Decimals,
    UnixTimestamp,
)

from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.types import (
    OracleResponse,
    Checkpoint,
    Contract,
    BlockId,
)

logger = get_pragma_sdk_logger()


class OracleMixin:
    publisher_registry: Contract
    client: Client
    account: Account
    execution_config: ExecutionConfig
    oracle: Contract
    is_user_client: bool = False
    track_nonce: Callable[[object, int, int], Coroutine[None, None, None]]

    @deprecated
    async def publish_spot_entry(
        self,
        pair_id: int,
        value: int,
        timestamp: UnixTimestamp,
        source: int,
        publisher: int,
        volume: int = 0,
    ) -> InvokeResult:
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.oracle.functions["publish_data"].invoke(
            new_entry={
                "Spot": {
                    "base": {
                        "timestamp": timestamp,
                        "source": source,
                        "publisher": publisher,
                    },
                    "price": value,
                    "pair_id": pair_id,
                    "volume": volume,
                }
            },
            execution_config=self.execution_config,
        )
        return invocation

    async def publish_many(self, entries: List[Entry]) -> List[InvokeResult]:
        if not entries:
            logger.warning("publish_many received no entries to publish. Skipping")
            return []

        # Pre-allocate lists with approximate sizes
        spot_entries = []
        future_entries = []
        generic_entries = []

        DECIMAL_ADJUSTMENT = 10**10  # Constant for 18 -> 8 decimal conversion
        for entry in entries:
            if isinstance(entry, SpotEntry):
                spot_entries.append(
                    SpotEntry(
                        pair_id=entry.pair_id,
                        price=entry.price // DECIMAL_ADJUSTMENT,
                        timestamp=entry.base.timestamp,
                        source=entry.base.source,
                        publisher=entry.base.publisher,
                        volume=entry.volume,
                    )
                )
            elif isinstance(entry, FutureEntry):
                future_entries.append(
                    FutureEntry(
                        pair_id=entry.pair_id,
                        price=entry.price // DECIMAL_ADJUSTMENT,
                        timestamp=entry.base.timestamp,
                        source=entry.base.source,
                        publisher=entry.base.publisher,
                        expiry_timestamp=entry.expiry_timestamp,
                    )
                )
            else:  # GenericEntry does not requires conversion
                generic_entries.append(entry)

        # Batch publish all entries
        invocations = []
        if spot_entries:
            invocations.extend(
                await self._publish_entries(
                    cast(List[Entry], spot_entries), DataTypes.SPOT
                )
            )
        if future_entries:
            invocations.extend(
                await self._publish_entries(
                    cast(List[Entry], future_entries), DataTypes.FUTURE
                )
            )
        if generic_entries:
            invocations.extend(
                await self._publish_entries(generic_entries, DataTypes.GENERIC)
            )

        return invocations

    async def _publish_entries(
        self, entries: List[Entry], data_type: DataTypes
    ) -> List[InvokeResult]:
        if len(entries) == 0:
            return []

        invocations = []
        match data_type:
            case DataTypes.SPOT:
                serialized_entries = SpotEntry.serialize_entries(entries)
            case DataTypes.FUTURE:
                serialized_entries = FutureEntry.serialize_entries(entries)
            case DataTypes.GENERIC:
                serialized_entries = GenericEntry.serialize_entries(entries)

        pagination = self.execution_config.pagination
        if pagination:
            for i in range(0, len(serialized_entries), pagination):
                entries_subset = serialized_entries[i : i + pagination]
                invocation = await self._invoke_publish(entries_subset, data_type)
                invocations.append(invocation)
                self._log_transaction(invocation, len(entries_subset), data_type)
        else:
            invocation = await self._invoke_publish(serialized_entries, data_type)
            invocations.append(invocation)
            self._log_transaction(invocation, len(serialized_entries), data_type)

        return invocations

    async def _invoke_publish(
        self, entries: List[Dict], data_type: DataTypes
    ) -> InvokeResult:
        return await self.oracle.functions["publish_data_entries"].invoke(
            new_entries=[{data_type: entry} for entry in entries],
            execution_config=self.execution_config,
            callback=self.track_nonce,
        )

    def _log_transaction(
        self, invocation: InvokeResult, entry_count: int, data_type: DataTypes
    ):
        logger.debug(
            f"Sent {entry_count} updated {data_type.name.lower()} entries with transaction {hex(invocation.hash)}"
        )

    @deprecated
    async def get_spot_entries(
        self,
        pair_id,
        sources=None,
        block_id: Optional[BlockId] = "latest",
    ) -> List[SpotEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            Asset(DataTypes.SPOT, pair_id, None).serialize(),
            sources,
            block_number=block_id,
        )
        entries = response[0]
        return [SpotEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_all_sources(
        self,
        asset: Asset,
        block_id: Optional[BlockId] = "latest",
    ) -> List[str]:
        """
        Query on-chain all sources used for a given asset.

        :param asset: Asset
        :param block_id: Block number or Block Tag
        :return: List of sources
        """
        (response,) = await self.oracle.functions["get_all_sources"].call(
            asset.serialize(), block_number=block_id
        )

        return [felt_to_str(source) for source in response]

    @deprecated
    async def get_future_entries(
        self,
        pair_id: str | int,
        expiration_timestamp: UnixTimestamp,
        sources: Optional[List[str | int]] = None,
        block_id: Optional[BlockId] = "latest",
    ) -> List[FutureEntry]:
        if sources is None:
            sources = []
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        (response,) = await self.oracle.functions["get_data_entries_for_sources"].call(
            Asset(DataTypes.FUTURE, pair_id, expiration_timestamp).serialize(),
            sources,
            block_number=block_id,
        )
        entries = response[0]
        return [FutureEntry.from_dict(dict(entry.value)) for entry in entries]

    async def get_spot(
        self,
        pair_id: str | int,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources: Optional[List[str | int]] = None,
        block_id: Optional[BlockId] = "latest",
    ) -> OracleResponse:
        """
        Query the Oracle contract for the data of a spot asset.

        :param pair_id: Pair ID
        :param aggregation_mode: AggregationMode
        :param sources: List of sources, if None will use all sources
        :param block_id: Block number or Block Tag
        :return: OracleResponse
        """
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )
        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                Asset(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
                block_number=block_id,
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                Asset(DataTypes.SPOT, pair_id, None).serialize(),
                aggregation_mode.serialize(),
                sources,
                block_number=block_id,
            )

        response = dict(response)

        return OracleResponse(
            response["price"],
            response["decimals"],
            response["last_updated_timestamp"],
            response["num_sources_aggregated"],
            response["expiration_timestamp"],
        )

    async def get_entry(
        self,
        pair_id: str | int,
        data_type: DataTypes,
        publisher: str | int,
        source: str | int,
        expiration_timestamp: Optional[int] = None,
        block_id: Optional[BlockId] = "latest",
    ) -> Entry:
        """
        Query the Oracle contract for the entry of a publisher for a source.

        :param pair_id: Pair ID
        :param data_type: DataTypes
        :param publisher: Publisher to check entry for
        :param source: Source to check
        :param expiration_timestamp: Optional, expiration timestamp for futures. Defaults to 0.
        :param block_id: Block number or Block Tag
        :return: Entry
        """
        if data_type == DataTypes.FUTURE and expiration_timestamp is None:
            expiration_timestamp = 0

        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        match data_type:
            case DataTypes.SPOT | DataTypes.GENERIC:
                asset = Asset(data_type, pair_id, None)
            case DataTypes.FUTURE:
                asset = Asset(data_type, pair_id, expiration_timestamp)

        (response,) = await self.oracle.functions["get_data_entry"].call(
            asset.serialize(),
            source,
            publisher,
            block_number=block_id,
        )

        response = response.as_dict()
        response = dict(response["value"])
        entry: Entry
        match data_type:
            case DataTypes.SPOT:
                entry = SpotEntry.from_dict(response)
            case DataTypes.FUTURE:
                entry = FutureEntry.from_dict(response)
            case DataTypes.GENERIC:
                entry = GenericEntry.from_dict(response)
        return entry

    async def get_future(
        self,
        pair_id: str | int,
        expiry_timestamp: UnixTimestamp,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources: Optional[List[str | int]] = None,
        block_id: Optional[BlockId] = "latest",
    ) -> OracleResponse:
        """
        Query the Oracle contract for the data of a future asset.

        :param pair_id: Pair ID
        :param expiry_timestamp: Expiry timestamp of the future contract
        :param aggregation_mode: AggregationMode
        :param sources: List of sources, if None will use all sources
        :param block_id: Block number or Block Tag
        :return: OracleResponse
        """
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id.upper())
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        if sources is None:
            (response,) = await self.oracle.functions["get_data"].call(
                Asset(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
                block_number=block_id,
            )
        else:
            (response,) = await self.oracle.functions["get_data_for_sources"].call(
                Asset(DataTypes.FUTURE, pair_id, expiry_timestamp).serialize(),
                aggregation_mode.serialize(),
                sources,
                block_number=block_id,
            )

        response = dict(response)

        return OracleResponse(
            response["price"],
            response["decimals"],
            response["last_updated_timestamp"],
            response["num_sources_aggregated"],
            response["expiration_timestamp"],
        )

    async def get_generic(
        self,
        key: str | int,
        sources: Optional[List[str | int]] = None,
        block_id: Optional[BlockId] = "latest",
    ) -> GenericEntry:
        """
        Query the Oracle contract to retrieve the

        :param key: Key ID of the generic entry
        :param block_id: Block number or Block Tag
        :return: GenericEntry
        """
        if isinstance(key, str):
            key = str_to_felt(key.upper())
        elif not isinstance(key, int):
            raise TypeError(
                "Generic entry key must be string (will be converted to felt) or integer"
            )

        if sources is None:
            (response,) = await self.oracle.functions["get_data_entries"].call(
                Asset(DataTypes.GENERIC, key, None).serialize(),
                block_number=block_id,
            )
        else:
            (response,) = await self.oracle.functions[
                "get_data_entries_for_sources"
            ].call(
                Asset(DataTypes.GENERIC, key, None).serialize(),
                sources,
                block_number=block_id,
            )

        # NOTE: We only return the latest entry because there shouldn't more
        # than one entry with the same key.
        response = response[-1].as_dict()
        entry = dict(response["value"])

        return GenericEntry(
            key=entry["key"],
            value=entry["value"],
            timestamp=entry["base"]["timestamp"],
            source=entry["base"]["source"],
            publisher=entry["base"]["publisher"],
        )

    async def get_decimals(
        self,
        asset: Asset,
        block_id: Optional[BlockId] = "latest",
    ) -> Decimals:
        """
        Query on-chain the decimals for a given asset

        :param asset: Asset
        :param block_id: Block number or Block Tag
        :return: Decimals
        """
        (response,) = await self.oracle.functions["get_decimals"].call(
            asset.serialize(),
            block_number=block_id,
        )

        return response  # type: ignore[no-any-return]

    async def set_future_checkpoints(
        self,
        pair_ids: Sequence[int],
        expiry_timestamps: Sequence[int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
    ) -> InvokeResult:
        assert len(pair_ids) == len(expiry_timestamps)
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = None

        pagination = self.execution_config.pagination
        if pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[index : index + pagination]
                expiries_subset = expiry_timestamps[index : index + pagination]
                invocation = await self.oracle.set_checkpoints.invoke(
                    [
                        Asset(DataTypes.FUTURE, pair_id, expiry).serialize()
                        for pair_id, expiry in zip(pair_ids_subset, expiries_subset)
                    ],
                    aggregation_mode.serialize(),
                    max_fee=self.execution_config.max_fee,
                    callback=self.track_nonce,
                )
                index += pagination
                logger.info(
                    "Set future checkpoints for %d pair IDs with transaction %s",
                    len(pair_ids_subset),
                    hex(invocation.hash),
                )
        else:
            invocation = await self.oracle.set_checkpoints.invoke(
                [
                    Asset(DataTypes.FUTURE, pair_id, expiry).serialize()
                    for pair_id, expiry in zip(pair_ids, expiry_timestamps)
                ],
                aggregation_mode.serialize(),
                max_fee=self.execution_config.max_fee,
                callback=self.track_nonce,
            )

        return invocation

    async def set_checkpoints(
        self,
        pair_ids: Sequence[str | int],
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
    ) -> InvokeResult:
        """
        Set checkpoints for a list of pair IDs.

        :param pair_ids: List of pair IDs
        :param aggregation_mode: AggregationMode
        :return: InvokeResult
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = None
        pagination = self.execution_config.pagination
        if pagination:
            index = 0
            while index < len(pair_ids):
                pair_ids_subset = pair_ids[index : index + pagination]
                invocation = await self.oracle.set_checkpoints.invoke(
                    [
                        Asset(DataTypes.SPOT, pair_id, None).serialize()
                        for pair_id in pair_ids_subset
                    ],
                    aggregation_mode.serialize(),
                    max_fee=self.execution_config.max_fee,
                    callback=self.track_nonce,
                )
                index += pagination
                logger.info(
                    "Set spot checkpoints for %d pair IDs with transaction %s",
                    len(pair_ids_subset),
                    hex(invocation.hash),
                )
        else:
            invocation = await self.oracle.set_checkpoints.invoke(
                [
                    Asset(DataTypes.SPOT, pair_id, None).serialize()
                    for pair_id in pair_ids
                ],
                aggregation_mode.serialize(),
                max_fee=self.execution_config.max_fee,
                callback=self.track_nonce,
            )

        return invocation

    async def get_latest_checkpoint(
        self,
        pair_id: str | int,
        data_type: DataTypes,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        expiration_timestamp: Optional[UnixTimestamp] = None,
    ) -> Checkpoint:
        if expiration_timestamp is not None and data_type == DataTypes.SPOT:
            raise ValueError("expiration_timestamp for SPOT should be None.")
        (response,) = await self.oracle.functions["get_latest_checkpoint"].call(
            Asset(data_type, pair_id, expiration_timestamp).serialize(),
            aggregation_mode.serialize(),
        )
        return Checkpoint(  # type: ignore[no-any-return]
            timestamp=response["timestamp"],
            value=response["value"],
            aggregation_mode=AggregationMode(response["aggregation_mode"].variant),
            num_sources_aggregated=response["num_sources_aggregated"],
        )

    async def get_last_checkpoint_before(
        self,
        pair_id: str | int,
        data_type: DataTypes,
        timestamp: UnixTimestamp,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        expiration_timestamp: Optional[UnixTimestamp] = None,
    ) -> Checkpoint:
        if expiration_timestamp is not None and data_type == DataTypes.SPOT:
            raise ValueError("expiration_timestamp for SPOT should be None.")
        (response,) = await self.oracle.functions["get_last_checkpoint_before"].call(
            Asset(data_type, pair_id, expiration_timestamp).serialize(),
            timestamp,
            aggregation_mode.serialize(),
        )
        return Checkpoint(  # type: ignore[no-any-return]
            timestamp=response["timestamp"],
            value=response["value"],
            aggregation_mode=AggregationMode(response["aggregation_mode"].variant),
            num_sources_aggregated=response["num_sources_aggregated"],
        )

    async def get_admin_address(self) -> Address:
        """
        Return the admin address of the Oracle contract.
        """

        (response,) = await self.oracle.functions["get_admin_address"].call()
        return response  # type: ignore[no-any-return]

    async def update_oracle(
        self,
        implementation_hash: int,
    ) -> InvokeResult:
        """
        Update the Oracle contract to a new implementation.

        :param implementation_hash: New implementation hash
        :return: InvokeResult
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. "
                "You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.oracle.functions["upgrade"].invoke(
            implementation_hash,
            max_fee=self.execution_config.max_fee,
        )
        return invocation

    async def get_time_since_last_published_spot(
        self,
        pair: Pair,
        publisher: str,
        block_id: Optional[BlockId] = "latest",
    ) -> int:
        """
        Get the time since the last published spot entry by a publisher for a given pair.
        Will return a large number if no entry is found.

        :param pair: Pair
        :param publisher: Publisher name e.g "PRAGMA"
        :param block_id: Block number or Block Tag
        :return: Time since last published entry
        """
        all_entries = await self.get_spot_entries(pair.id, block_id=block_id)

        entries = [
            entry
            for entry in all_entries
            if entry.base.publisher == str_to_felt(publisher)
        ]

        if len(entries) == 0:
            return 1000000000  # arbitrary large number

        max_timestamp = max(entry.base.timestamp for entry in entries)

        diff = int(time.time()) - max_timestamp

        return diff

    async def is_currency_registered(
        self,
        currency_id: str,
        block_id: Optional[BlockId] = "latest",
    ) -> bool:
        """
        Check if a currency is registered on the Oracle.
        """
        (currency_info,) = await self.oracle.functions["get_currency"].call(
            str_to_felt(currency_id),
            block_number=block_id,
        )
        return bool(currency_info["id"] != 0)

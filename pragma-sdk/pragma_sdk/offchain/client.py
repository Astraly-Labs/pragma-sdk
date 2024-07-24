import asyncio
import time
from typing import Dict, List, Optional, Union, Any
import logging

import aiohttp
from pragma_sdk.onchain.types.types import PublishEntriesOnChainResult
from requests import HTTPError
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner

from pragma_sdk.common.types.entry import Entry, FutureEntry, SpotEntry
from pragma_sdk.common.types.types import AggregationMode, DataTypes
from pragma_sdk.common.utils import add_sync_methods, get_cur_from_pair
from pragma_sdk.offchain.signer import OffchainSigner
from pragma_sdk.offchain.types import Interval, PublishEntriesAPIResult
from pragma_sdk.common.types.pair import Pair

from pragma_sdk.common.types.client import PragmaClient

from pragma_sdk.offchain.exceptions import PragmaAPIError

logger = logging.getLogger(__name__)


@add_sync_methods
class PragmaAPIClient(PragmaClient):
    """
    Client for interacting with the Pragma API.
    see https://docs.pragma.build/Resources/PragmApi/overview

    An API Key is required to interact with the API.
    """

    api_base_url: str
    api_key: str
    account_private_key: Optional[int] = None
    offchain_signer: Optional[OffchainSigner] = None

    def __init__(
        self,
        account_private_key: Optional[str | int],
        account_contract_address: Optional[str | int],
        api_base_url: str,
        api_key: str,
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key

        if account_private_key is not None and account_contract_address is not None:
            if isinstance(account_private_key, str):
                account_private_key = int(account_private_key, 16)
            if isinstance(account_contract_address, str):
                account_contract_address = int(account_contract_address, 16)

            signer = StarkCurveSigner(
                account_contract_address,
                KeyPair.from_private_key(account_private_key),
                StarknetChainId.MAINNET,  # not used anyway
            )
            self.offchain_signer = OffchainSigner(signer=signer)

    async def get_ohlc(
        self,
        pair: str,
        timestamp: Optional[int] = None,
        interval: Optional[Interval] = None,
        aggregation: Optional[AggregationMode] = None,
    ) -> "EntryResult":
        """
        Retrieve OHLC data from the Pragma API.

        :param pair: Pair to get data for
        :param timestamp: Timestamp to get data for, defaults to now
        :param interval: Interval on which data is aggregated, defaults to 1m
        :param aggregation: Aggregation method, defaults to Median

        :return: [EntryResult] result data
        """
        base_asset, quote_asset = get_cur_from_pair(pair)

        endpoint = f"/node/v1/aggregation/candlestick/{base_asset}/{quote_asset}"

        path_params = {
            key: value
            for key, value in {
                "timestamp": timestamp,
                "interval": interval,
                "aggregation": (
                    aggregation.value.lower() if aggregation is not None else None
                ),
            }.items()
            if value is not None
        }

        url = f"{self.api_base_url}{endpoint}"

        headers = {
            "x-api-key": self.api_key,
        }

        # Create connection
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, params=path_params
            ) as response_raw:
                status_code: int = response_raw.status
                response: Dict = await response_raw.json()
                if status_code == 200:
                    logger.debug(f"Success: {response}")
                    logger.info(f"Get {base_asset}/{quote_asset} Ohlc successful")
                else:
                    logger.error(f"Status Code: {status_code}")
                    raise PragmaAPIError(f"Failed to get OHLC data for pair {pair}")

        return EntryResult(pair_id=response["pair_id"], data=response["data"])

    async def publish_entries(
        self, entries: List[Entry]
    ) -> Union[PublishEntriesAPIResult, PublishEntriesOnChainResult]:
        """
        Publishes spot and future entries to the Pragma API.
        This function accepts both type of entries - but they need to be sent through
        different endpoints & signed differently, so we split them in two separate
        lists.

        :param entries: List of SpotEntry objects
        """
        # We accept both types of entries - but they need to be sent through
        # different endpoints & signed differently, so we split them here.
        spot_entries: List[Entry] = []
        future_entries: List[Entry] = []

        for entry in entries:
            if isinstance(entry, SpotEntry):
                spot_entries.append(entry)
            elif isinstance(entry, FutureEntry):
                future_entries.append(entry)

        # execute both in parralel
        spot_response, future_response = await asyncio.gather(
            self._create_entries(spot_entries, DataTypes.SPOT),
            self._create_entries(future_entries, DataTypes.FUTURE),
        )
        return spot_response, future_response

    async def _create_entries(
        self, entries: List[Entry], data_type: DataTypes = DataTypes.SPOT
    ) -> Optional[Dict]:
        """
        Publishes entries to the Pragma API & returns the http response.

        We can only publish entries of the same type at once - if we have a mix of
        types, the function will raise an error.
        """
        if self.offchain_signer is None:
            raise PragmaAPIError("No offchain signer set")

        if len(entries) == 0:
            return None

        assert all(isinstance(entry, type(entries[0])) for entry in entries)

        now = int(time.time())
        expiry = now + 24 * 60 * 60
        endpoint = get_endpoint_publish_offchain(data_type)
        url = f"{self.api_base_url}{endpoint}"

        headers: Dict = {
            "PRAGMA-TIMESTAMP": str(now),
            "PRAGMA-SIGNATURE-EXPIRATION": str(expiry),
            "x-api-key": self.api_key,
        }

        sig, _ = self.offchain_signer.sign_publish_message(entries, data_type)
        # Convert entries to JSON string
        data = {
            "signature": [str(s) for s in sig],
            "entries": Entry.offchain_serialize_entries(entries),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response_raw:
                status_code: int = response_raw.status
                response: Dict = await response_raw.json()
                if status_code == 200:
                    logger.debug(f"Success: {response}")
                    logger.debug("Publish successful")
                    return response
                logger.debug(f"Status Code: {status_code}")
                logger.debug(f"Response Text: {response}")
                raise PragmaAPIError("Unable to POST /v1/data")

    async def get_entry(
        self,
        pair: str,
        timestamp: Optional[int] = None,
        interval: Optional[Interval] = None,
        aggregation: Optional[AggregationMode] = None,
        routing: Optional[bool] = None,
    ) -> "EntryResult":
        """
        Get data aggregated on the Pragma API.

        :param pair: Pair to get data for
        :param timestamp: Timestamp to get data for, defaults to now
        :param interval: Interval on which data is aggregated, defaults to 2h
        :param routing: If we want to route data for unexisting pair, defaults to False
        :param aggregation: Aggregation method, defaults to TWAP

        :return: [EntryResult] result data
        """
        base_asset, quote_asset = get_cur_from_pair(pair)
        endpoint = f"/node/v1/data/{base_asset}/{quote_asset}"
        url = f"{self.api_base_url}{endpoint}"
        # Construct query parameters based on provided arguments
        params = {
            key: value
            for key, value in {
                "routing": routing,
                "timestamp": timestamp,
                "interval": interval.value if interval else None,
                "aggregation": aggregation.value.lower() if aggregation else None,
            }.items()
            if value is not None
        }

        headers = {
            "x-api-key": self.api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response_raw:
                status_code: int = response_raw.status
                response: Dict = await response_raw.json()
                if status_code == 200:
                    logger.debug(f"Success: {response}")
                    logger.debug(f"Get {base_asset}/{quote_asset} Data successful")
                else:
                    logger.debug(f"Status Code: {status_code}")
                    logger.debug(f"Response Text: {response}")
                    raise PragmaAPIError(f"Unable to GET /v1/data for pair {pair}")

        return EntryResult(
            pair_id=response["pair_id"],
            data=response["price"],
            num_sources_aggregated=response["num_sources_aggregated"],
            timestamp=response["timestamp"],
            decimals=response["decimals"],
        )

    async def get_future_entry(
        self,
        pair: str,
        timestamp: Optional[int] = None,
        interval: Optional[Interval] = None,
        aggregation: Optional[AggregationMode] = None,
        routing: Optional[bool] = None,
        expiry: Optional[str] = None,
    ) -> "EntryResult":
        """
        Get data aggregated on the Pragma API.

        :param pair: Pair to get data for
        :param timestamp: Timestamp to get data for, defaults to now
        :param interval: Interval on which data is aggregated, defaults to 2h
        :param routing: If we want to route data for unexisting pair, defaults to False
        :param aggregation: Aggregation method, defaults to TWAP

        :return: [EntryResult] result data
        """
        base_asset, quote_asset = get_cur_from_pair(pair)
        endpoint = f"/node/v1/data/{base_asset}/{quote_asset}"
        url = f"{self.api_base_url}{endpoint}"
        # Construct query parameters based on provided arguments
        params = {
            key: value
            for key, value in {
                "routing": routing,
                "timestamp": timestamp,
                "interval": interval.value if interval else None,
                "aggregation": aggregation.value.lower() if aggregation else None,
                "entry_type": "future",
                "expiry": expiry if expiry else None,
            }.items()
            if value is not None
        }

        headers = {
            "x-api-key": self.api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                status_code: int = response.status
                json_response: Dict = await response.json()
                if status_code == 200:
                    logger.debug(f"Success: {json_response}")
                    logger.debug(
                        f"Get {base_asset}/{quote_asset} future Data successful"
                    )
                else:
                    logger.debug(f"Status Code: {status_code}")
                    logger.debug(f"Response Text: {response}")
                    raise PragmaAPIError(f"Unable to GET /v1/data for pair {pair}")

        return EntryResult(
            pair_id=json_response["pair_id"],
            data=json_response["price"],
            num_sources_aggregated=json_response["num_sources_aggregated"],
            timestamp=json_response["timestamp"],
            decimals=json_response["decimals"],
            expiry=expiry,
        )

    async def get_volatility(self, pair: str, start: int, end: int):
        """
        Get volatility data for a pair in a given time range on the Pragma API.

        :param pair: Pair to get data for
        :param start: Start timestamp
        :param end: End timestamp
        """

        base_asset, quote_asset = get_cur_from_pair(pair)

        endpoint = f"/node/v1/volatility/{base_asset}/{quote_asset}"

        headers = {
            "x-api-key": self.api_key,
        }

        params = {
            "start": start,
            "end": end,
        }

        # Construct URL with parameters
        url = f"{self.api_base_url}{endpoint}"
        # Send GET request with headers
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response_raw:
                status_code: int = response_raw.status
                response: Dict = await response_raw.json()
                if status_code == 200:
                    logger.debug(f"Success: {response}")
                    logger.info("Get Volatility successful")
                else:
                    logger.debug(f"Status Code: {status_code}")
                    logger.debug(f"Response Text: {response}")
                    raise HTTPError(f"Unable to GET /v1/volatility for pair {pair} ")

        return EntryResult(pair_id=response["pair_id"], data=response["volatility"])

    async def get_expiries_list(self, pair: Pair):
        """
        Get volatility data for a pair in a given time range on the Pragma API.

        :param pair: Pair to get data for
        :param start: Start timestamp
        :param end: End timestamp
        """

        base_asset, quote_asset = get_cur_from_pair(f"{pair}")

        endpoint = f"/node/v1/data/{base_asset}/{quote_asset}/future_expiries"

        headers = {
            "x-api-key": self.api_key,
        }

        # Construct URL with parameters
        url = f"{self.api_base_url}{endpoint}"
        # Send GET request with headers
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                status_code: int = response.status
                json_response: Dict = await response.json()
                if status_code == 200:
                    logger.debug(f"Success: {json_response}")
                    logger.debug(f"Get {base_asset}/{quote_asset} expiry successful")
                else:
                    logger.debug(f"Status Code: {status_code}")
                    logger.debug(f"Response Text: {response}")
                    raise PragmaAPIError(
                        f"Unable to GET future_expiries for pair {pair}"
                    )
                return json_response


def get_endpoint_publish_offchain(data_type: DataTypes):
    """
    Returns the correct publish endpoint for the given data type.
    """
    endpoint = "/node/v1/data/publish"
    if data_type == DataTypes.FUTURE:
        endpoint += "_future"
    return endpoint


class EntryResult:
    def __init__(
        self,
        pair_id: str,
        data: Any,
        num_sources_aggregated: int = 0,
        timestamp: Optional[int] = None,
        decimals: Optional[int] = None,
        expiry: Optional[str] = None,
    ):
        self.pair_id = pair_id
        self.data = data
        self.num_sources_aggregated = num_sources_aggregated
        self.timestamp = timestamp
        self.decimals = decimals
        self.expiry = expiry

    def __str__(self):
        return (
            f"Pair ID: {self.pair_id}, "
            "Data: {self.data}, "
            "Num Sources Aggregated: {self.num_sources_aggregated}, "
            "Timestamp: {self.timestamp}, "
            "Decimals: {self.decimals},"
            "Expiry: {self.expiry}"
        )

    def assert_attributes_equal(self, expected_dict):
        """
        Asserts that the attributes of the class object are equal to the values in the dictionary.
        """
        for key, value in expected_dict.items():
            if key == "price":
                if getattr(self, "data") != value:
                    return False
            elif getattr(self, key) != value:
                return False
        return True

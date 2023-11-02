import collections
import logging
from typing import List, Dict
import time
import aiohttp
import ssl
import io

from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.utils.typed_data import TypedData

from pragma.core.entry import SpotEntry
from pragma.core.types import AggregationMode

logger = logging.getLogger(__name__)

GetDataResponse = collections.namedtuple(
    "GetDataResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)

"""
{'base': 
{'publisher': 88314212732225, 
'source': 5787760245619121969, 'timestamp': 1697147959}, 
'pair_id': 19514442401534788, '
price': 1000, 
'volume': 0}
"""
def build_publish_message(entries: List[SpotEntry]) -> TypedData:
    message = {
        "domain": {"name": "Pragma", "version": "1"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": SpotEntry.serialize_entries(entries),
        },
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Request": [
                {"name": "action", "type": "felt"},
                {"name": "entries", "type": "Entry*"},
            ],
            "Entry": [
                { "name": "base", "type": "Base" },
                { "name": "pair_id", "type": "felt" },
                { "name": "price", "type": "felt" },
                { "name": "volume", "type": "felt" },
            ],
            "Base": [
                { "name": "publisher", "type": "felt" },
                { "name": "source", "type": "felt" },
                { "name": "timestamp", "type": "felt" },
            ],
        },
    }

    return message


class OffchainMixin:
    client: Client
    account: Account
    api_url: str
    ssl_context: ssl.SSLContext
    api_key: str

    def sign_publish_message(self, entries: List[SpotEntry]) -> (List[int], int):
        """
        Sign a publish message
        """

        message = build_publish_message(entries)
        hash_ = TypedData.from_dict(message).message_hash(self.account.address)
        sig = self.account.sign_message(message)

        return sig, hash_

    def load_ssl_context(self, client_cert, client_key):
        """
        Load SSL context from client cert and key
        """

        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_cert_chain(certfile=io.StringIO(client_cert), keyfile=io.StringIO(client_key))
        self.ssl_context = ssl_context

    async def publish_data(
        self,
        entries: List[SpotEntry],
    ):
        """
        Publish data to PragmAPI

        Args:
            entries (List[SpotEntry]): List of SpotEntry to publish
        """

        # Sign message
        sig, _ = self.sign_publish_message(entries)

        now = int(time.time())
        expiry = now + 24 * 60 * 60

        # Add headers
        headers: Dict = {
            "PRAGMA-TIMESTAMP": str(now),
            "PRAGMA-SIGNATURE-EXPIRATION": str(expiry),
            "x-api-key": self.api_key,
        }

        body = {
            "signature": [str(s) for s in sig],
            "entries": SpotEntry.offchain_serialize_entries(entries),
        }

        url = self.api_url + '/v1/data/publish'

        logging.info(f"POST {url}")
        logging.info(f"Headers: {headers}")
        logging.info(f"Body: {body}")

        # Call Pragma API
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl_context=self.ssl_context)) as session:
            async with session.post(url, headers=headers, json=body) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Publish successful")
                    return response

                logging.error(f"Status Code: {status_code}")
                logging.error(f"Response Text: {response}")
                logging.error("Unable to POST /v1/data")

        return response

    # pylint: disable=no-self-use
    async def get_spot_data(
        self,
        quote_asset,
        base_asset,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ):
        """
        Get spot data from PragmaAPI

        Args:
            quote_asset (str): Quote asset
            base_asset (str): Base asset
            aggregation_mode (AggregationMode): Aggregation mode
            sources (List[str]): List of sources to fetch from
        """
        url = self.api_url + f"/v1/data/{quote_asset}/{base_asset}"

        headers = {
            "x-api-key": self.api_key,
        }

        logging.info(f"GET {url}")

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl_context=self.ssl_context)) as session:
            async with session.get(url, headers=headers) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Get Data successful")

                logging.error(f"Status Code: {status_code}")
                logging.error(f"Response Text: {response}")
                logging.error("Unable to GET /v1/data")

        return response

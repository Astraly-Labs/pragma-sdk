import logging
from typing import List, Optional, Union

from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.client import Client
from starknet_py.net.signer.stark_curve_signer import KeyPair, StarkCurveSigner
from starknet_py.net.models import StarknetChainId

from pragma_sdk.common.exceptions import ClientException
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import Address
from pragma_sdk.common.types.client import PragmaClient

from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.onchain.constants import CHAIN_IDS, CONTRACT_ADDRESSES
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.types import (
    PrivateKey,
    Contract,
    NetworkName,
    ContractAddresses,
    Network,
    PublishEntriesOnChainResult,
)
from pragma_sdk.onchain.mixins import (
    NonceMixin,
    OracleMixin,
    PublisherRegistryMixin,
    RandomnessMixin,
)
from pragma_sdk.onchain.utils import get_full_node_client_from_network

from pragma_sdk.offchain.types import PublishEntriesAPIResult


logger = get_pragma_sdk_logger()
logger.setLevel(logging.INFO)


class PragmaOnChainClient(  # type: ignore[misc]
    PragmaClient,
    NonceMixin,
    OracleMixin,
    PublisherRegistryMixin,
    RandomnessMixin,
):
    """
    Client for interacting with Pragma on Starknet.

    :param network: Target network for the client. Can be a URL string, or one of
                    ``"mainnet"``, ``"sepolia"`` or ``"devnet"``
    :param account_private_key: Optional private key for requests. Not necessary if not making
                                network updates.
                                Can be either an hexadecimal string 0x prefixed, an integer or
                                a KeyStore type.
                                The KeyStore is a tuple of two string [str, str], which are
                                ["path/to/the/keystore", "password_to_unlock_the_keystore"].
    :param account_contract_address: Optional account contract address.  Not necessary if not
                                     making network updates.
                                     Can either be an integer or an hexadecimal string 0x prefixed.
    :param contract_addresses_config: Optional Contract Addresses for Pragma contracts.
                                      Will default to the provided network but must be set if using
                                      non standard contracts.
    :param port: Optional port to interact with local node. Will default to 5050.
    :param chain_name: A str-representation of the chain if a URL string is given for `network`.
                       Must be one of ``"mainnet"``, ``"sepolia"`` or ``"devnet"``.
    """

    is_user_client: bool = False
    account_contract_address: Optional[Address] = None
    account: Account = None
    full_node_client: FullNodeClient = None
    client: Client = None
    execution_config: ExecutionConfig

    def __init__(
        self,
        network: Network = "sepolia",
        account_private_key: Optional[PrivateKey] = None,
        account_contract_address: Optional[int | str] = None,
        contract_addresses_config: Optional[ContractAddresses] = None,
        port: Optional[int] = None,
        chain_name: Optional[NetworkName] = None,
        execution_config: Optional[ExecutionConfig] = None,
    ):
        full_node_client: FullNodeClient = get_full_node_client_from_network(
            network, port=port
        )
        self.full_node_client = full_node_client
        self.client = full_node_client

        if network.startswith("http") and chain_name is None:  # type: ignore[union-attr]
            raise ClientException(
                f"Network provided is a URL: {network} but `chain_name` is not provided."
            )

        self.network = (
            network if not (network.startswith("http") and chain_name) else chain_name  # type: ignore[union-attr]
        )

        if execution_config is not None:
            self.execution_config = execution_config
        else:
            self.execution_config = ExecutionConfig(auto_estimate=True)

        if account_contract_address and account_private_key:
            self._setup_account_client(
                CHAIN_IDS[self.network],
                account_private_key,
                account_contract_address,
            )

        if not contract_addresses_config:
            contract_addresses_config = CONTRACT_ADDRESSES[self.network]  # type: ignore[index]

        self.contract_addresses_config = contract_addresses_config
        self._setup_contracts()

    async def publish_entries(
        self, entries: List[Entry]
    ) -> Union[PublishEntriesAPIResult, PublishEntriesOnChainResult]:
        """
        Publish entries on-chain.

        :param entries: List of Entry objects
        :return: List of InvokeResult objects
        """
        return await self.publish_many(entries)

    def _setup_contracts(self):
        """
        Setup the contracts for the client.
        For now, this includes the Oracle and PublisherRegistry contracts.
        """

        provider = self.account if self.account else self.client
        self.oracle = Contract(
            address=self.contract_addresses_config.oracle_proxy_addresss,
            abi=ABIS["pragma_Oracle"],
            provider=provider,
            cairo_version=1,
        )
        self.publisher_registry = Contract(
            address=self.contract_addresses_config.publisher_registry_address,
            abi=ABIS["pragma_PublisherRegistry"],
            provider=provider,
            cairo_version=1,
        )

    async def get_balance(self, account_contract_address, token_address=None) -> int:
        """
        Get the balance of an account given the account contract address and token address.

        :param account_contract_address: The account contract address.
        :param token_address: The token address. If None, will use ETH as the token address.
        :return: The balance of the account.
        """

        client = Account(
            address=account_contract_address,
            client=self.client,
            key_pair=KeyPair.from_private_key(1),
            chain=CHAIN_IDS[self.network],
        )
        return await client.get_balance(token_address)  # type: ignore[no-any-return]

    def _process_secret_key(self, private_key: PrivateKey) -> KeyPair:
        """Converts a Private Key to a KeyPair."""
        if isinstance(private_key, int):
            return KeyPair.from_private_key(private_key)
        elif isinstance(private_key, tuple):
            path, password = private_key
            return KeyPair.from_keystore(path, password)
        elif isinstance(private_key, str):
            return KeyPair.from_private_key(int(private_key, 16))

    def _setup_account_client(
        self,
        chain_id: StarknetChainId,
        private_key: PrivateKey,
        account_contract_address: int | str,
    ):
        self.signer = StarkCurveSigner(
            account_contract_address,
            self._process_secret_key(private_key),
            chain_id,
        )
        self.account = Account(
            address=account_contract_address,
            client=self.client,
            signer=self.signer,
        )
        self.client = self.account.client
        self.account.get_nonce = self._get_nonce  # pylint: disable=protected-access
        self.is_user_client = True
        if isinstance(account_contract_address, str):
            account_contract_address = int(account_contract_address, 16)
        self.account_contract_address = account_contract_address

    @property
    def account_address(self) -> Address:
        """
        Return the account address.
        """

        return self.account.address  # type: ignore[no-any-return]

    def init_stats_contract(
        self,
        stats_contract_address: Address,
    ):
        """
        Initialize the Summary Stats contract.
        """
        provider = self.account if self.account else self.client
        self.stats = Contract(
            address=stats_contract_address,
            abi=ABIS["pragma_SummaryStats"],
            provider=provider,
            cairo_version=1,
        )

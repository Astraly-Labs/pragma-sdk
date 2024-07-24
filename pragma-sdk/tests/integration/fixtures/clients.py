import pytest
import requests
import random
import subprocess
import time

from typing import Any, Dict
from starknet_py.net.full_node_client import FullNodeClient

from pragma_sdk.onchain.constants import RPC_URLS
from pragma_sdk.onchain.client import PragmaOnChainClient

from tests.integration.fixtures.devnet import get_available_port

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


@pytest.fixture(
    scope="module",
)
def client(network: str) -> FullNodeClient:
    """
    Returns Client instances.
    """
    return FullNodeClient(node_url=network)


@pytest.fixture(scope="module")
def network_config(request: pytest.FixtureRequest) -> Dict[str, Any]:
    """
    Fixture to provide network configuration.
    """
    return {
        "network": getattr(request, "param", {}).get("network", "mainnet"),
        "account_address": getattr(request, "param", {}).get(
            "account_address",
            "0x02356b628D108863BAf8644c945d97bAD70190AF5957031f4852d00D0F690a77",
        ),
        "block_number": getattr(request, "param", {}).get("block_number", None),
    }


@pytest.fixture(scope="module")
def forked_client(network_config: Dict[str, Any]) -> PragmaOnChainClient:
    """
    This package-scope fixture prepares a forked starknet
    client for e2e testing.

    :param network_config: Configuration for the network
    :return: a starknet Client
    """
    port = get_available_port()

    network = network_config["network"]
    account_address = network_config["account_address"]
    block_number = network_config["block_number"]

    rpc_url = random.choice(RPC_URLS[network])
    command = [
        "starknet-devnet",
        "--fork-network",
        str(rpc_url),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
        "--chain-id",
        network.upper(),
    ]
    if block_number is not None:
        command.extend(["--fork-block-number", str(block_number)])

    subprocess.Popen(command)
    time.sleep(10)

    devnet_url = f"http://127.0.0.1:{port}/rpc"

    pragma_client = PragmaOnChainClient(
        devnet_url,
        chain_name=network,
        account_contract_address=account_address,
        account_private_key="0x"
        + "1" * 62,  # Dummy private key as it will use account impersonation
    )

    impersonate_account(account_address, devnet_url)

    return pragma_client


def impersonate_account(account_address: str, rpc_url: str):
    """
    Impersonates the account on the running devnet.
    see https://0xspaceshard.github.io/starknet-devnet-rs/docs/account-impersonation#devnet_impersonateaccount

    :param account_address: The account address to impersonate
    :param rpc_url: The RPC URL of the devnet
    """

    impersonate_payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "devnet_impersonateAccount",
        "params": {"account_address": account_address},
    }

    response = requests.post(rpc_url, json=impersonate_payload)

    if response.status_code != 200:
        raise Exception(f"Failed to impersonate account: {response.text}")

    result = response.json()
    if "error" in result:
        raise Exception(f"Failed to impersonate account: {result['error']}")

    logger.info(f"Successfully impersonated account: {account_address}")

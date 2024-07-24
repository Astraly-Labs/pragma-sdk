import asyncio
import pytest
import logging

from urllib.parse import urlparse
from starknet_py.contract import Contract
from pragma_utils.logger import setup_logging
from pragma_sdk.onchain.types import (
    VRFRequestParams,
    RequestStatus,
)

from vrf_listener.main import main
from tests.integration.utils import ExtendedPragmaClient

logger = logging.getLogger(__name__)


def spawn_main_in_parallel_thread(
    network,
    vrf_address: int,
    admin_address: int,
    private_key: str,
    check_requests_interval: int = 1,
) -> asyncio.Task:
    """
    Spawns the main function in a parallel thread and return the task.
    The task can later be cancelled using the .cancel function.
    """
    port = urlparse(network).port
    main_task = asyncio.create_task(
        main(
            network="devnet",
            rpc_url=f"http://localhost:{port}",
            vrf_address=hex(vrf_address),
            admin_address=hex(admin_address),
            private_key=private_key,
            check_requests_interval=check_requests_interval,
        )
    )
    return main_task


@pytest.mark.asyncio
async def test_vrf_listener(
    vrf_pragma_client: ExtendedPragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
    network,
):
    setup_logging(logger, "DEBUG")

    _, private_key = address_and_private_key
    (randomness, example, oracle) = randomness_contracts
    caller_address = vrf_pragma_client.account_address

    main_task = spawn_main_in_parallel_thread(
        network=network,
        vrf_address=randomness.address,
        admin_address=caller_address,
        private_key=private_key,
    )

    # Spams VRF requests...
    last_request_id = 10
    for _ in range(last_request_id):
        invocation = await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=1,
                callback_address=example.address,
                callback_fee_limit=2855600000000000000,
                publish_delay=1,
                num_words=1,
                calldata=[0x1234, 0x1434, 314141, 13401234],
            )
        )
        await invocation.wait_for_acceptance()

    # ... and check that they're all fullfilled by the VRF listener
    for id_to_check in range(0, last_request_id):
        status = await vrf_pragma_client.get_request_status(caller_address, id_to_check)
        assert status == RequestStatus.FULFILLED

    main_task.cancel()


@pytest.mark.asyncio
async def test_vrf_listener_miss_with_large_interval(
    vrf_pragma_client: ExtendedPragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
    network,
):
    setup_logging(logger, "DEBUG")

    _, private_key = address_and_private_key
    (randomness, example, oracle) = randomness_contracts
    caller_address = vrf_pragma_client.account_address

    main_task = spawn_main_in_parallel_thread(
        network=network,
        vrf_address=randomness.address,
        admin_address=caller_address,
        private_key=private_key,
        # Very big check interval request so we're sure it does not catch the request
        check_requests_interval=10000,
    )

    await asyncio.sleep(5)

    # Send a VRF request...
    last_request_id = 0
    invocation = await vrf_pragma_client.request_random(
        VRFRequestParams(
            seed=1,
            callback_address=example.address,
            callback_fee_limit=2855600000000000000,
            publish_delay=1,
            num_words=1,
            calldata=[0x1234, 0x1434, 314141, 13401234],
        )
    )
    await invocation.wait_for_acceptance()

    # ... and check that its status is still pending
    status = await vrf_pragma_client.get_request_status(caller_address, last_request_id)
    assert status == RequestStatus.RECEIVED
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [last_request_id]

    main_task.cancel()

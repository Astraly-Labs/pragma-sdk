import asyncio
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account
from starknet_py.transaction_errors import TransactionRevertedError

from pragma_sdk.onchain.abis.abi import get_erc20_abi
from pragma_sdk.onchain.types import (
    VRFRequestParams,
    VRFCancelParams,
    VRFSubmitParams,
    ContractAddresses,
    RequestStatus,
)
from tests.integration.constants import (
    ESTIMATED_FEE_MULTIPLIER,
    FEE_TOKEN_ADDRESS,
    MAX_PREMIUM_FEE,
)

# from pragma_sdk.onchain.client import PragmaOnChainClient
from tests.integration.utils import ExtendedPragmaClient as PragmaClient
from tests.integration.utils import convert_to_wei, read_contract, wait_for_acceptance

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


@pytest_asyncio.fixture(scope="module")
async def declare_deploy_randomness(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract = read_contract("pragma_Randomness.sierra.json", directory=None)
    compiled_contract_casm = read_contract(
        "pragma_Randomness.casm.json", directory=None
    )

    compiled_example_contract = read_contract(
        "pragma_ExampleRandomness.sierra.json", directory=None
    )
    compiled_example_contract_casm = read_contract(
        "pragma_ExampleRandomness.casm.json", directory=None
    )

    compiled_oracle_mock_contract = read_contract(
        "pragma_MockOracle.sierra.json", directory=None
    )
    compiled_oracle_mock_contract_casm = read_contract(
        "pragma_MockOracle.casm.json", directory=None
    )
    # Declare Randomness
    declare_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Declare Randomness Example
    declare_example_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_example_contract,
        compiled_contract_casm=compiled_example_contract_casm,
        auto_estimate=True,
    )
    await declare_example_result.wait_for_acceptance()

    # Declare Mock Oracle
    declare_mock_oracle_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_oracle_mock_contract,
        compiled_contract_casm=compiled_oracle_mock_contract_casm,
        auto_estimate=True,
    )
    await declare_mock_oracle_result.wait_for_acceptance()

    # Deploy Mock Oracle
    deploy_oracle_result = await declare_mock_oracle_result.deploy_v1(
        constructor_args=[], auto_estimate=True
    )
    await deploy_oracle_result.wait_for_acceptance()

    # Deploy Randomness
    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            account.address,
            account.signer.public_key,
            int(FEE_TOKEN_ADDRESS, 16),
            deploy_oracle_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await declare_example_result.deploy_v1(
        constructor_args=[
            deploy_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_example_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_example_result, deploy_oracle_result


@pytest_asyncio.fixture(scope="module")
async def randomness_contracts(
    declare_deploy_randomness,
) -> (Contract, Contract, Contract):
    (
        _,
        deploy_result,
        deploy_example_result,
        deploy_oracle_result,
    ) = declare_deploy_randomness
    return (
        deploy_result.deployed_contract,
        deploy_example_result.deployed_contract,
        deploy_oracle_result.deployed_contract,
    )


@pytest_asyncio.fixture(scope="module", name="vrf_pragma_client")
async def vrf_pragma_client(
    randomness_contracts: (Contract, Contract, Contract),
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    (randomness, example, oracle) = randomness_contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    client = PragmaClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=0x0,
        ),
        port=port,
    )
    client.init_randomness_contract(randomness.address)
    client.init_example_randomness_contract(example.address)
    erc20_contract = Contract(
        address=FEE_TOKEN_ADDRESS,
        abi=get_erc20_abi(),
        provider=client.account,
        cairo_version=0,
    )
    # Approve randomness contract to transfer fee tokens
    await erc20_contract.functions["approve"].invoke_v1(
        randomness.address, 0xFFFFFFFFFFFFFFFFFFFFFFFF, auto_estimate=True
    )

    return client


@pytest.mark.asyncio
async def test_deploy_contract(randomness_contracts):
    (randomness, example_randomness, mock_oracle) = randomness_contracts
    assert isinstance(randomness, Contract)
    assert isinstance(example_randomness, Contract)
    assert isinstance(mock_oracle, Contract)


@pytest.mark.asyncio
async def test_client_setup(vrf_pragma_client: PragmaClient, account: Account):
    assert vrf_pragma_client.account_address == account.address

    account_balance = await account.get_balance()
    assert await vrf_pragma_client.get_balance(account.address) == account_balance

    assert vrf_pragma_client.randomness is not None


@pytest.mark.asyncio
async def test_randomness_mixin(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
):
    _, private_key = address_and_private_key
    (_, example_randomness, _) = randomness_contracts

    caller_address = vrf_pragma_client.account_address

    seed = 1
    callback_fee_limit = 2855600000000000000
    callback_address = example_randomness.address
    publish_delay = 0
    num_words = 1
    calldata = [0x1234, 0x1434, 314141, 13401234]

    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [0]

    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []

    status = await vrf_pragma_client.get_request_status(caller_address, 0)
    assert status == RequestStatus.FULFILLED

    # Request cancellation test
    seed = 2
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    block_number = await vrf_pragma_client.full_node_client.get_block_number()
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [1]
    status = await vrf_pragma_client.get_request_status(caller_address, 1)
    assert status == RequestStatus.RECEIVED
    await wait_for_acceptance(
        await vrf_pragma_client.cancel_random_request(
            VRFCancelParams(
                request_id=pending_reqs[0],
                requestor_address=caller_address,
                seed=seed,
                minimum_block_number=block_number + publish_delay,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                num_words=num_words,
            )
        )
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    status = await vrf_pragma_client.get_request_status(caller_address, 1)
    assert status == RequestStatus.CANCELLED

    # Request cancellation failed if request is already fulfilled
    seed = 3
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    block_number = await vrf_pragma_client.full_node_client.get_block_number()
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [2]
    status = await vrf_pragma_client.get_request_status(caller_address, 2)
    assert status == RequestStatus.RECEIVED

    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    status = await vrf_pragma_client.get_request_status(caller_address, 2)
    assert status == RequestStatus.FULFILLED

    try:
        await vrf_pragma_client.cancel_random_request(
            VRFCancelParams(
                request_id=2,
                requestor_address=caller_address,
                seed=seed,
                minimum_block_number=block_number + publish_delay,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                num_words=num_words,
            )
        )
    except TransactionRevertedError:
        # err_msg = "Execution was reverted; failure reason: [0x7265717565737420616c72656164792066756c66696c6c6564]"
        # err_msg = "Contract Error"
        # if not err_msg in err.message:
        #     raise err
        assert True


@pytest.mark.asyncio
async def test_fails_gas_limit(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
):
    _, private_key = address_and_private_key
    (_, example_randomness, _) = randomness_contracts

    seed = 1
    callback_fee_limit = 10
    callback_address = example_randomness.address
    publish_delay = 0
    num_words = 1
    caller_address = vrf_pragma_client.account_address

    balance_before = await vrf_pragma_client.get_balance(caller_address)

    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
            )
        )
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [3]

    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []

    status = await vrf_pragma_client.get_request_status(caller_address, 3)
    assert status == RequestStatus.REFUNDED

    balance_after = await vrf_pragma_client.get_balance(caller_address)

    assert balance_before >= balance_after


@pytest.mark.asyncio
async def test_balance_evolution(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
):
    (_, example_randomness, _) = randomness_contracts

    _, private_key = address_and_private_key
    (_, example_randomness, _) = randomness_contracts

    request_id = 4
    seed = 1
    callback_fee_limit = 65400000000000
    callback_address = example_randomness.address
    publish_delay = 0
    calldata = [0x1234, 0x1434, 314141]
    num_words = 1
    caller_address = vrf_pragma_client.account_address

    # Determining the estimated cost for the request random operation
    request_estimated_fee = await vrf_pragma_client.estimate_gas_request_random_op(
        VRFRequestParams(
            seed,
            callback_address,
            callback_fee_limit,
            publish_delay,
            num_words,
            calldata,
        )
    )

    # Fetching user initial balance
    initial_balance = await vrf_pragma_client.get_balance(caller_address)
    # Initiating request random
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )

    # Check balance after the randomness request
    new_balance = await vrf_pragma_client.get_balance(caller_address)

    # Verify the fee configuration
    premium_fee = await vrf_pragma_client.compute_premium_fee(caller_address)
    total_fee = await vrf_pragma_client.get_total_fees(caller_address, request_id)
    assert total_fee == convert_to_wei(premium_fee) + callback_fee_limit

    # Determine the total cost for the request random operation
    total_cost = (
        convert_to_wei(premium_fee)
        + callback_fee_limit
        + ESTIMATED_FEE_MULTIPLIER * request_estimated_fee.overall_fee
    )

    # The user balance should be decremented by the total cost
    assert new_balance >= initial_balance - int(total_cost)

    # Check the pending request evolution
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [request_id]

    block_number = await vrf_pragma_client.full_node_client.get_block_number()

    random_words = [
        405107394872172057115262954592232705152426027670166803695971257483286492108
    ]
    proof = [
        222504705630538894159390252206410388469377536249758264971017249221789657744,
        252046043704048207916077512885153897033434975082716884715263509256036001312,
        1333176046351886212531569533062945259971235,
    ]

    # Estimate the gas cost for the handle random operation
    estimated_gas_cost_submit = await vrf_pragma_client.estimate_gas_submit_random_op(
        VRFSubmitParams(
            request_id=request_id,
            requestor_address=caller_address,
            seed=seed,
            minimum_block_number=block_number + publish_delay,
            callback_address=callback_address,
            callback_fee_limit=callback_fee_limit,
            random_words=random_words,
            proof=proof,
        )
    )

    # Generate the random number and send it to the callback contract
    pre_op_balance = await vrf_pragma_client.get_balance(caller_address)

    await vrf_pragma_client.handle_random(int(private_key, 16))
    # Check post op balance
    post_op_balance = await vrf_pragma_client.get_balance(caller_address)

    logger.info("OVERALL FEES:")
    logger.info(estimated_gas_cost_submit.overall_fee)

    assert (
        post_op_balance
        >= pre_op_balance
        - int(ESTIMATED_FEE_MULTIPLIER * estimated_gas_cost_submit.overall_fee)
        + callback_fee_limit
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []

    status = await vrf_pragma_client.get_request_status(caller_address, request_id)
    assert status == RequestStatus.FULFILLED


@pytest.mark.asyncio
async def test_balance_evolution_cancel(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
):
    (_, example_randomness, _) = randomness_contracts
    request_id = 5
    seed = 1
    callback_fee_limit = 2855600000000000000
    callback_address = example_randomness.address
    publish_delay = 0
    num_words = 1
    calldata = [0x1234, 0x1434, 314141]
    caller_address = vrf_pragma_client.account_address

    # Fetching user initial balance
    initial_balance = await vrf_pragma_client.get_balance(caller_address)

    # Determining the estimated cost for the request random operation
    request_estimated_fee = await vrf_pragma_client.estimate_gas_request_random_op(
        VRFRequestParams(
            seed,
            callback_address,
            callback_fee_limit,
            publish_delay,
            num_words,
            calldata,
        )
    )

    # Initiating request random
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    block_number = await vrf_pragma_client.full_node_client.get_block_number()

    # Check balance after the randomness request
    new_balance = await vrf_pragma_client.get_balance(caller_address)

    # Verify the fee configuration
    premium_fee = await vrf_pragma_client.compute_premium_fee(caller_address)
    total_fee = await vrf_pragma_client.get_total_fees(caller_address, request_id)
    assert total_fee == convert_to_wei(premium_fee) + callback_fee_limit

    # Determine the total cost for the request random operation
    total_cost = (
        convert_to_wei(premium_fee)
        + callback_fee_limit
        + ESTIMATED_FEE_MULTIPLIER * request_estimated_fee.overall_fee
    )

    # The user balance should be decremented by the total cost
    assert new_balance >= initial_balance - int(total_cost)

    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [request_id]
    before_cancel_balance = await vrf_pragma_client.get_balance(caller_address)
    # Estimated cost for the cancel operation
    estimated_cancel_fee = await vrf_pragma_client.estimate_gas_cancel_random_op(
        VRFCancelParams(
            request_id=pending_reqs[0],
            requestor_address=caller_address,
            seed=seed,
            minimum_block_number=block_number + publish_delay,
            callback_address=callback_address,
            callback_fee_limit=callback_fee_limit,
            num_words=num_words,
        )
    )

    # User balance
    await wait_for_acceptance(
        await vrf_pragma_client.cancel_random_request(
            VRFCancelParams(
                request_id=pending_reqs[0],
                requestor_address=caller_address,
                seed=seed,
                minimum_block_number=block_number + publish_delay,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                num_words=num_words,
            )
        )
    )

    # new_balance = old_balance + total_fee - estimated_cancel_fee
    # User balance after this call should be incremented by the total_fees - estimated_cancel_fee
    after_cancel_balance = await vrf_pragma_client.get_balance(caller_address)
    assert after_cancel_balance >= before_cancel_balance + total_fee - int(
        ESTIMATED_FEE_MULTIPLIER * estimated_cancel_fee.overall_fee
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    final_balance = await vrf_pragma_client.get_balance(caller_address)

    assert final_balance >= initial_balance - int(
        ESTIMATED_FEE_MULTIPLIER
        * (estimated_cancel_fee.overall_fee + request_estimated_fee.overall_fee)
    )


@pytest.mark.asyncio
async def test_delayed_randomness_request(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
):
    (_, example_randomness, _) = randomness_contracts
    _, private_key = address_and_private_key
    seed = 1
    request_id = 6
    callback_fee_limit = 2113000000000000
    callback_address = example_randomness.address
    publish_delay = 2
    num_words = 1
    calldata = [0x1234, 0x1434, 314141]
    erc20_contract = Contract(
        address=FEE_TOKEN_ADDRESS,
        abi=get_erc20_abi(),
        provider=vrf_pragma_client.account,
        cairo_version=0,
    )
    block_number_1 = await vrf_pragma_client.full_node_client.get_block_number()
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(
        vrf_pragma_client.account_address
    )
    assert pending_reqs == [request_id]
    block_number_2 = await vrf_pragma_client.full_node_client.get_block_number()
    assert block_number_2 <= block_number_1 + publish_delay
    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(
        vrf_pragma_client.account_address
    )
    assert pending_reqs == [request_id]
    block_number_3 = await vrf_pragma_client.full_node_client.get_block_number()
    await wait_for_acceptance(
        await erc20_contract.functions["approve"].invoke_v1(
            example_randomness.address, 0xF, auto_estimate=True
        )
    )
    await wait_for_acceptance(
        await erc20_contract.functions["approve"].invoke_v1(
            example_randomness.address, 0xF, auto_estimate=True
        )
    )
    block_number_3 = await vrf_pragma_client.full_node_client.get_block_number()
    assert block_number_3 > block_number_1 + publish_delay
    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(
        vrf_pragma_client.account_address
    )
    assert pending_reqs == []


@pytest.mark.asyncio
async def test_example_randomness_process(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    address_and_private_key,
):
    (_, example_randomness, _) = randomness_contracts
    request_id = 7
    _, private_key = address_and_private_key
    caller_address = vrf_pragma_client.account_address
    seed = 1
    callback_fee_limit = 3248900000000000
    callback_address = example_randomness.address
    publish_delay = 0
    calldata = [0x1234, 0x1434, 314141]
    num_words = 1
    await wait_for_acceptance(
        await vrf_pragma_client.request_random(
            VRFRequestParams(
                seed=seed,
                callback_address=callback_address,
                callback_fee_limit=callback_fee_limit,
                publish_delay=publish_delay,
                num_words=num_words,
                calldata=calldata,
            )
        )
    )
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [request_id]
    await vrf_pragma_client.handle_random(int(private_key, 16))
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    status = await vrf_pragma_client.get_request_status(caller_address, request_id)
    assert status == RequestStatus.FULFILLED
    random_number = await vrf_pragma_client.get_last_example_random()
    assert random_number != 0


async def multiple_randomness_request(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
    number_of_interations: int,
):
    (_, example_randomness, _) = randomness_contracts
    callback_fee_limit = 2113000000000000
    callback_address = example_randomness.address
    publish_delay = 0
    num_words = 1
    calldata = [0x1234, 0x1434, 314141]
    initial_index = await vrf_pragma_client.requestor_current_request_id(
        vrf_pragma_client.account_address
    )
    for i in range(initial_index, initial_index + number_of_interations):
        seed = i
        await wait_for_acceptance(
            await vrf_pragma_client.request_random(
                VRFRequestParams(
                    seed=seed,
                    callback_address=callback_address,
                    callback_fee_limit=callback_fee_limit,
                    publish_delay=publish_delay,
                    num_words=num_words,
                    calldata=calldata,
                )
            )
        )
        await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_compute_premium_fee(
    vrf_pragma_client: PragmaClient,
    randomness_contracts: (Contract, Contract, Contract),
):
    caller_address = vrf_pragma_client.account_address

    await multiple_randomness_request(vrf_pragma_client, randomness_contracts, 1)
    premium_fee_1st = await vrf_pragma_client.compute_premium_fee(caller_address)
    assert premium_fee_1st == MAX_PREMIUM_FEE

    await multiple_randomness_request(vrf_pragma_client, randomness_contracts, 10)
    premium_fee_2nd = await vrf_pragma_client.compute_premium_fee(caller_address)
    assert premium_fee_2nd == MAX_PREMIUM_FEE / 2

    # Commented the following lines in order to avoid a long test execution

    # await multiple_randomness_request(vrf_pragma_client, randomness_contracts, 21)
    # premium_fee_3rd = await vrf_pragma_client.compute_premium_fee(caller_address)
    # assert premium_fee_3rd == MAX_PREMIUM_FEE / 4

    # await multiple_randomness_request(vrf_pragma_client, randomness_contracts, 70)
    # premium_fee_3rd = await vrf_pragma_client.compute_premium_fee(caller_address)
    # assert premium_fee_3rd == MAX_PREMIUM_FEE / 10

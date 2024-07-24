import asyncio
import sys
from typing import List, Optional

from starknet_py.contract import InvokeResult
from starknet_py.net.client import Client
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import EstimatedFee, EventsChunk
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.account.account import Account

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.randomness.utils import (
    create_randomness,
    felt_to_secret_key,
)
from pragma_sdk.common.types.types import Address

from pragma_sdk.onchain.types import RequestStatus, RandomnessRequest, ExecutionConfig
from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.onchain.constants import RANDOMNESS_REQUEST_EVENT_SELECTOR
from pragma_sdk.onchain.types import Contract
from pragma_sdk.onchain.types import (
    VRFCancelParams,
    VRFRequestParams,
    VRFSubmitParams,
)

logger = get_pragma_sdk_logger()


class RandomnessMixin:
    client: Client
    randomness: Contract
    account: Optional[Account] = None
    is_user_client: bool = False
    full_node_client: FullNodeClient
    execution_config: ExecutionConfig

    def init_randomness_contract(self, contract_address: Address):
        provider = self.account if self.account else self.client
        self.randomness = Contract(
            address=contract_address,
            abi=ABIS["pragma_Randomness"],
            provider=provider,
            cairo_version=1,
        )

    async def request_random(
        self,
        request_params: VRFRequestParams,
    ) -> InvokeResult:
        """
        Request randomness from the VRF contract.
        Must set account. You may do this by invoking self._setup_account_client(private_key, account_contract_address)

        :param request_params: VRFRequestParams object containing the request parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if request_params.calldata is None:
            request_params.calldata = []

        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by invoking "
                "self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["request_random"].invoke(
            *request_params.to_list(),
            execution_config=self.execution_config,
        )
        return invocation

    async def estimate_gas_request_random_op(
        self,
        vrf_request_params: VRFRequestParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the request_random operation.

        :param vrf_request_params: VRFRequestParams object containing the request parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if vrf_request_params.calldata is None:
            vrf_request_params.calldata = []

        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )
        prepared_call = self.randomness.functions["request_random"].prepare_invoke_v1(
            *vrf_request_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def submit_random(
        self,
        vrf_submit_params: VRFSubmitParams,
    ) -> InvokeResult:
        """
        Submit randomness to the VRF contract.
        If fee estimation fails, the status of the request is updated to OUT_OF_GAS.
        Then, the remaining gas is refunded to the requestor address.

        Fee estimation is used to set the callback fee parameter in the VRFSubmitParams object.

        :param vrf_submit_params: VRFSubmitParams object containing the submit parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        prepared_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            *vrf_submit_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )

        try:
            estimate_fee = await prepared_call.estimate_fee()
        except ClientError as e:
            logger.error("Error while estimating fee: ", e)
            return None

        if estimate_fee.overall_fee > vrf_submit_params.callback_fee_limit:
            logger.error(
                "OUT OF GAS %s > %s",
                estimate_fee.overall_fee,
                vrf_submit_params.callback_fee_limit,
            )
            invocation = await self.randomness.functions["update_status"].invoke(
                vrf_submit_params.requestor_address,
                vrf_submit_params.request_id,
                RequestStatus.OUT_OF_GAS.serialize(),
                execution_config=self.execution_config,
            )

            # Refund gas
            await self.refund_operation(
                vrf_submit_params.request_id, vrf_submit_params.requestor_address
            )
            return invocation

        vrf_submit_params.callback_fee = estimate_fee.overall_fee

        invocation = await self.randomness.functions["submit_random"].invoke(
            *vrf_submit_params.to_list(),
            execution_config=self.execution_config,
        )
        logger.info("Sumbitted random %s", invocation.hash)

        return invocation

    async def estimate_gas_submit_random_op(
        self,
        vrf_submit_params: VRFSubmitParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the submit_random operation.

        :param vrf_submit_params: VRFSubmitParams object containing the submit parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        vrf_submit_params.callback_fee = vrf_submit_params.callback_fee_limit

        prepared_call = self.randomness.functions["submit_random"].prepare_invoke_v1(
            *vrf_submit_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee

    async def get_request_status(
        self,
        caller_address: Address,
        request_id: int,
    ) -> RequestStatus:
        """
        Query the status of a request given the caller address and request ID.

        :param caller_address: The caller address.
        :param request_id: The request ID.
        :return: The status of the request.
        """
        (response,) = await self.randomness.functions["get_request_status"].call(
            caller_address,
            request_id,
        )
        return RequestStatus(response.variant)

    async def get_total_fees(self, caller_address: Address, request_id: int) -> int:
        """
        Query the total fees of a request given the caller address and request ID.
        Total fees correspond to the sum of the callback fee and the premium fee.

        :param caller_address: The caller address.
        :param request_id: The request ID.
        :return: The total fees of the request.
        """
        (response,) = await self.randomness.functions["get_total_fees"].call(
            caller_address, request_id
        )

        return response  # type: ignore[no-any-return]

    async def compute_premium_fee(self, caller_address: Address) -> int:
        """
        Query the premium fee for a request given the caller address.
        see https://docs.pragma.build/Resources/Cairo%201/randomness/randomness#pricing

        :param caller_address: The caller address.
        :return: The premium fee.
        """
        (response,) = await self.randomness.functions["compute_premium_fee"].call(
            caller_address
        )

        return response  # type: ignore[no-any-return]

    async def requestor_current_request_id(self, caller_address: Address) -> int:
        """
        Query the request id of the latest request made by the caller address.

        :param caller_address: The caller address.
        :return: The request id of the latest request.
        """
        (response,) = await self.randomness.functions["requestor_current_index"].call(
            caller_address
        )

        return response  # type: ignore[no-any-return]

    async def get_pending_requests(
        self,
        requestor_address: Address,
        offset: int = 0,
        max_len: int = 100,
    ) -> List[int]:
        """
        Query the pending requests of a requestor address.

        :param requestor_address: The requestor address.
        :param offset: Request id from which to start the query.
        :param max_len: Maximum number of requests to query.
        :return: The pending requests of the requestor address.
        """
        (response,) = await self.randomness.functions["get_pending_requests"].call(
            requestor_address,
            offset,
            max_len,
        )

        return response  # type: ignore[no-any-return]

    async def cancel_random_request(
        self,
        vrf_cancel_params: VRFCancelParams,
    ) -> InvokeResult:
        """
        Cancel a random request given the request parameters.
        see more info https://docs.pragma.build/Resources/Cairo%201/randomness/randomness#function-cancel_random_request

        :param vrf_cancel_params: VRFCancelParams object containing the cancel parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["cancel_random_request"].invoke(
            *vrf_cancel_params.to_list(),
            execution_config=self.execution_config,
        )
        return invocation

    async def estimate_gas_cancel_random_op(
        self,
        vrf_cancel_params: VRFCancelParams,
    ) -> EstimatedFee:
        """
        Estimate the gas for the cancel_random_request operation.

        :param vrf_cancel_params: VRFCancelParams object containing the cancel parameters.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: The estimated gas for the operation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account.  You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        prepared_call = self.randomness.functions[
            "cancel_random_request"
        ].prepare_invoke_v1(
            *vrf_cancel_params.to_list(),
            max_fee=self.execution_config.max_fee,
        )
        estimate_fee = await prepared_call.estimate_fee()
        return estimate_fee  # type: ignore[no-any-return]

    async def refund_operation(
        self,
        request_id: int,
        requestor_address: int,
    ) -> InvokeResult:
        """
        Refund the remaining gas to the requestor address.
        Only requests with status OUT_OF_GAS can be refunded.

        :param request_id: The request ID.
        :param requestor_address: The requestor address.
        :param execution_config: ExecutionConfig object containing the execution parameters.
        :return: InvokeResult object containing the result of the invocation.
        """
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by "
                "invoking self._setup_account_client(private_key, account_contract_address)"
            )

        invocation = await self.randomness.functions["refund_operation"].invoke(
            requestor_address, request_id, execution_config=self.execution_config
        )

        return invocation

    async def handle_random(
        self,
        private_key: int,
        ignore_request_threshold: int = 3,
    ):
        """
        Handle randomness requests.
        Will submit randomness for requests that are not too old and have not been handled yet.

        :param private_key: The private key of the account that will sign the randomness.
        :param ignore_request_threshold: The number of blocks we ignore requests that are older than.
        """

        block_number = await self.full_node_client.get_block_number()

        min_block = max(block_number - ignore_request_threshold, 0)
        logger.info(f"Handle random job running with min_block: {min_block}")

        sk = felt_to_secret_key(private_key)

        more_pages = True
        continuation_token = None

        while more_pages:
            event_list = await self._get_randomness_requests_events(
                min_block, continuation_token
            )

            # Remove the calldata length from the event data
            for event in event_list.events:
                index_to_split = 7
                event.data = event.data[:index_to_split] + [
                    event.data[index_to_split + 1 :]
                ]

            events = [RandomnessRequest(*r.data) for r in event_list.events]
            continuation_token = event_list.continuation_token
            more_pages = continuation_token is not None

            statuses = await asyncio.gather(
                *[
                    self.get_request_status(event.caller_address, event.request_id)
                    for event in events
                ]
            )

            for event in events:
                minimum_block_number = event.minimum_block_number
                # Skip if block_number is less than minimum_block_number
                # Take into account pending block
                # Ignore requests that are too old
                if (
                    minimum_block_number > block_number + 1
                    or minimum_block_number < block_number - ignore_request_threshold
                ):
                    logger.info(
                        f"Skipping event: {event.request_id} with min_block: {minimum_block_number}"
                    )
                    continue

                status = statuses.pop(0)
                if status != RequestStatus.RECEIVED:
                    logger.info(
                        f"Skipping event: {event.request_id} with status: {status.value}"
                    )
                    continue

                logger.info(f"Found event: {event}")

                is_pending = minimum_block_number == block_number + 1

                block = (
                    await self.full_node_client.get_block(block_number="pending")
                    if is_pending
                    else await self.full_node_client.get_block(block_number="latest")
                )
                block_hash = block.parent_hash

                seed = self._build_request_seed(event, block_hash)

                beta_string, pi_string, _ = create_randomness(sk, seed)  # type: ignore[arg-type]
                beta_string = int.from_bytes(beta_string, sys.byteorder)  # type: ignore[arg-type, assignment]
                proof = [
                    int.from_bytes(p, sys.byteorder)  # type: ignore[arg-type]
                    for p in [pi_string[:31], pi_string[31:62], pi_string[62:]]
                ]

                random_words: List[int] = [beta_string]  # type: ignore[list-item]

                vrf_submit_params = VRFSubmitParams(
                    request_id=event.request_id,
                    requestor_address=event.caller_address,
                    seed=event.seed,
                    minimum_block_number=event.minimum_block_number,
                    callback_address=event.callback_address,
                    callback_fee_limit=event.callback_fee_limit,
                    random_words=random_words,
                    proof=proof,
                    calldata=event.calldata,
                )

                invocation = await self.submit_random(vrf_submit_params)

                if invocation is None:
                    logger.error("Failed to submit randomness")
                    continue

                logger.info(f"Submitted tx: {hex(invocation.hash)}\n\n")

    async def _get_randomness_requests_events(
        self, min_block: int, continuation_token=None
    ) -> EventsChunk:
        """
        Get randomness requests events.
        Queries from the min_block to the pending block.

        :return: The randomness requests events.
        """
        event_list = await self.full_node_client.get_events(
            self.randomness.address,
            keys=[[RANDOMNESS_REQUEST_EVENT_SELECTOR]],
            from_block_number=min_block,
            to_block_number="pending",
            continuation_token=continuation_token,
            chunk_size=500,
        )
        logger.info(f"Got {len(event_list.events)} events")
        return event_list

    def _build_request_seed(self, event: RandomnessRequest, block_hash: int) -> int:
        """
        Build the request seed.
        The seed is the hash of the request id, the block hash, the event seed and the caller address.

        :param event: The event data.
        :param block_hash: The block hash.
        :return: The generated seed.
        """
        return (
            event.request_id.to_bytes(8, sys.byteorder)  # type: ignore[return-value]
            + block_hash.to_bytes(32, sys.byteorder)
            + event.seed.to_bytes(32, sys.byteorder)
            + event.caller_address.to_bytes(32, sys.byteorder)
        )

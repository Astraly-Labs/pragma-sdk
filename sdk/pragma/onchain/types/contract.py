from typing import Awaitable, Callable, Optional

from starknet_py.contract import Contract as StarknetContract
from starknet_py.contract import ContractFunction, InvokeResult
from starknet_py.net.client_models import SentTransactionResponse

from pragma.common.types.types import ExecutionConfig


class Contract(StarknetContract):
    def __getattr__(self, attr):
        if attr in self._functions:
            return self._functions[attr]

        if attr in dir(self):
            return getattr(self, attr)

        raise AttributeError("Invalid Attribute")


async def invoke_(
    self,
    *args,
    execution_config: Optional[ExecutionConfig] = None,
    callback: Optional[Callable[[SentTransactionResponse, str], Awaitable[None]]] = None,
    **kwargs,
) -> InvokeResult:
    """
    Allows for a callback in the invocation of a contract method.
    This is useful for tracking the nonce changes
    """
    if execution_config is None :
        raise AttributeError("Invalid Attribute")

    prepared_call = (
        self.prepare_invoke_v3(*args, **kwargs)
        if execution_config.enable_strk_fees
        else self.prepare_invoke_v1(*args, **kwargs)
    )

    # transfer ownership to the prepared call
    self = prepared_call
    if execution_config.max_fee is not None:
        self.max_fee = execution_config.max_fee

    transaction = (
        await self.get_account.sign_invoke_v3(
            calls=self,
            l1_resource_bounds=execution_config.l1_resource_bounds,
            auto_estimate=execution_config.auto_estimate,
        )
        if execution_config.enable_strk_fees
        else await self.get_account.sign_invoke_v1(
            calls=self, max_fee=execution_config.max_fee
        )
    )

    transaction = None


    response = await self._client.send_transaction(transaction)
    if callback:
        await callback(transaction.nonce, response.transaction_hash)

    invoke_result = InvokeResult(
        hash=response.transaction_hash,
        _client=self._client,
        contract=self._contract_data,
        invoke_transaction=transaction,
    )

    # don't return invoke result until it is received or errors
    # await invoke_result.wait_for_acceptance()

    return invoke_result


# patch contract function to use new invoke function
ContractFunction.invoke = invoke_

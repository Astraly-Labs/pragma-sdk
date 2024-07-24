from typing import Tuple

import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account

from tests.integration.constants import CURRENCIES, USD_PAIRS
from tests.integration.utils import read_contract


@pytest_asyncio.fixture(scope="function")
async def declare_deploy_oracle(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract_registry = read_contract(
        "pragma_PublisherRegistry.sierra.json", directory=None
    )
    compiled_contract_registry_casm = read_contract(
        "pragma_PublisherRegistry.casm.json", directory=None
    )

    compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)

    # Declare Publisher Registry
    declare_result_registry = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract_registry,
        compiled_contract_casm=compiled_contract_registry_casm,
        auto_estimate=True,
    )
    await declare_result_registry.wait_for_acceptance()

    # Deploy Publisher Registry
    deploy_result_registry = await declare_result_registry.deploy_v1(
        constructor_args=[account.address], auto_estimate=True
    )
    await deploy_result_registry.wait_for_acceptance()

    # Declare Oracle
    declare_result = await Contract.declare_v2(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Deploy Oracle
    currencies = [currency.to_dict() for currency in CURRENCIES]
    pairs = [pair.to_dict() for pair in USD_PAIRS]

    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            account.address,
            deploy_result_registry.deployed_contract.address,
            currencies,
            pairs,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_result_registry


@pytest_asyncio.fixture(scope="function", name="deploy_oracle_contracts")
async def deploy_oracle_contracts(declare_deploy_oracle) -> Tuple[Contract, Contract]:
    _, deploy_result, deploy_result_registry = declare_deploy_oracle
    return (deploy_result.deployed_contract, deploy_result_registry.deployed_contract)

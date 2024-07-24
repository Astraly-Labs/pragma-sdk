import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal, Tuple

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from pragma_sdk.common.types.types import AggregationMode, DataTypes
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import ContractAddresses

from checkpointer.configs.pairs_config import PairsConfig

logger = logging.getLogger(__name__)


async def main(
    pairs_config: PairsConfig,
    network: Literal["mainnet", "sepolia"],
    oracle_address: str,
    admin_address: str,
    private_key: str | Tuple[str, str],
    set_checkpoint_interval: int,
    rpc_url: Optional[HttpUrl] = None,
) -> None:
    pragma_client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=admin_address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=int(oracle_address, 16),
            summary_stats_address=0x0,
        ),
    )
    _log_handled_pairs(pairs_config, set_checkpoint_interval)
    logger.info("🧩 Starting Checkpointer...")
    try:
        while True:
            tasks = []
            if pairs_config.spot:
                tasks.append(_set_checkpoints(pragma_client, pairs_config, DataTypes.SPOT))
            if pairs_config.future:
                tasks.append(_set_checkpoints(pragma_client, pairs_config, DataTypes.FUTURE))
            await asyncio.gather(*tasks)
            await asyncio.sleep(set_checkpoint_interval)
    except asyncio.CancelledError:
        logger.info("... Checkpointer service stopped! 👋")
        return


async def _set_checkpoints(
    client: PragmaOnChainClient,
    pairs_config: PairsConfig,
    pairs_type: DataTypes,
) -> None:
    try:
        match pairs_type:
            case DataTypes.SPOT:
                pair_ids = pairs_config.get_spot_ids()
                tx = await client.set_checkpoints(
                    pair_ids=pair_ids,
                    aggregation_mode=AggregationMode.MEDIAN,
                )
            case DataTypes.FUTURE:
                pair_ids, expiries = pairs_config.get_future_ids_and_expiries()
                tx = await client.set_future_checkpoints(
                    pair_ids=pair_ids,
                    expiry_timestamps=expiries,
                    aggregation_mode=AggregationMode.MEDIAN,
                )
        await tx.wait_for_acceptance()
        logger.info(f"✅ Successfully set {pairs_type} checkpoints")
    except Exception as e:
        logger.error(f"⛔ Error while setting {pairs_type} checkpoint: {e}")


def _log_handled_pairs(pairs_config: PairsConfig, set_checkpoint_interval: int) -> None:
    log_message = (
        "👇 New checkpoints will automatically be set every "
        f"{set_checkpoint_interval} seconds for those pairs:"
    )
    for pair_type, pairs in pairs_config:
        if pairs:
            log_message += f"\n{pair_type.upper()}: {pairs}"
    logger.info(log_message)


@click.command()
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to YAML configuration file.",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    default="sepolia",
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="On which networks the checkpoints will be set. Defaults to SEPOLIA.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "--oracle-address",
    type=click.STRING,
    required=True,
    help="Address of the Pragma Oracle",
)
@click.option(
    "--admin-address",
    type=click.STRING,
    required=True,
    help="Address of the Admin contract for the Oracle.",
)
@click.option(
    "-p",
    "--private-key",
    "raw_private_key",
    type=click.STRING,
    required=True,
    help=(
        "Private key of the signer. Format: "
        "aws:secret_name, "
        "plain:private_key, "
        "env:ENV_VAR_NAME, "
        "or keystore:PATH/TO/THE/KEYSTORE:PASSWORD"
    ),
)
@click.option(
    "-t",
    "--set-checkpoint-interval",
    type=click.IntRange(min=0),
    required=False,
    default=3600,
    help="Delay in seconds between each new checkpoints. Defaults to 1 hour (3600s).",
)
def cli_entrypoint(
    config_file: str,
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    oracle_address: str,
    admin_address: str,
    raw_private_key: str,
    set_checkpoint_interval: int,
) -> None:
    """
    Checkpointer entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)
    pairs_config = PairsConfig.from_yaml(config_file)
    asyncio.run(
        main(
            pairs_config=pairs_config,
            network=network,
            rpc_url=rpc_url,
            oracle_address=oracle_address,
            admin_address=admin_address,
            private_key=private_key,
            set_checkpoint_interval=set_checkpoint_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()

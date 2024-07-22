import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg
from pragma_sdk.onchain.types import ContractAddresses

from pragma_sdk.onchain.client import PragmaOnChainClient

logger = logging.getLogger(__name__)


async def main(
    network: Literal["mainnet", "sepolia"],
    oracle_address: str,
    vrf_address: str,
    admin_address: str,
    private_key: str,
    start_block: int,
    check_requests_interval: int,
    rpc_url: Optional[HttpUrl] = None,
) -> None:
    logger.info("🧩 Starting VRF listener...")
    client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=int(admin_address, 16),
        account_private_key=int(private_key, 16),
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=int(oracle_address, 16),
            summary_stats_address=0x0,
        ),
    )
    client.init_randomness_contract(int(vrf_address, 16))

    logger.info("👂 Listening for randomness requests!")
    while True:
        try:
            await client.handle_random(int(private_key, 16), start_block)
        except Exception as e:
            logger.error(f"⛔ Error while handling randomness request: {e}")
        await asyncio.sleep(check_requests_interval)


@click.command()
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
    help="Which network to listen. Defaults to SEPOLIA.",
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
    "--vrf-address",
    type=click.STRING,
    required=True,
    help="Address of the VRF contract",
)
@click.option(
    "--admin-address",
    type=click.STRING,
    required=True,
    help="Address of the Admin contract",
)
@click.option(
    "-p",
    "--private-key",
    type=click.STRING,
    required=True,
    help="Secret key of the signer. Format: aws:secret_name, plain:secret_key, or env:ENV_VAR_NAME",
)
@click.option(
    "-b",
    "--start-block",
    type=click.IntRange(min=0),
    required=False,
    default=0,
    help="At which block to start listening for VRF requests. Defaults to 0.",
)
@click.option(
    "-t",
    "--check-requests-interval",
    type=click.IntRange(min=0),
    required=False,
    default=10,
    help="Delay in seconds between checks for VRF requests. Defaults to 10 seconds.",
)
def cli_entrypoint(
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    oracle_address: str,
    vrf_address: str,
    admin_address: str,
    private_key: str,
    start_block: int,
    check_requests_interval: int,
) -> None:
    """
    VRF Listener entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(private_key)
    asyncio.run(
        main(
            network=network,
            rpc_url=rpc_url,
            oracle_address=oracle_address,
            vrf_address=vrf_address,
            admin_address=admin_address,
            private_key=private_key,
            start_block=start_block,
            check_requests_interval=check_requests_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()

import asyncio
import click
import logging

from typing import Optional, List, Tuple

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.offchain.client import PragmaAPIClient
from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import PriceListener
from price_pusher.core.request_handlers import REQUEST_HANDLER_REGISTRY
from price_pusher.core.pusher import PricePusher
from price_pusher.core.fetchers import add_all_fetchers
from price_pusher.configs.price_config import (
    PriceConfig,
)
from price_pusher.orchestrator import Orchestrator
from price_pusher.types import Target, Network

logger = logging.getLogger(__name__)


async def main(
    price_configs: List[PriceConfig],
    target: Target,
    network: Network,
    private_key: str | Tuple[str, str],
    publisher_name: str,
    publisher_address: str,
    rpc_url: Optional[str] = None,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    max_fee: Optional[int] = None,
    pagination: Optional[int] = None,
    enable_strk_fees: Optional[bool] = None,
) -> None:
    """
    Main function of the price pusher.
    Create the parts that are then fed to the orchestrator for the main loop.
    """
    logger.info("🔨 Creating Pragma client...")
    pragma_client = _create_client(
        target=target,
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        rpc_url=rpc_url,
        api_base_url=api_base_url,
        api_key=api_key,
        max_fee=max_fee,
        pagination=pagination,
        enable_strk_fees=enable_strk_fees,
    )

    logger.info("🪚 Creating Fetcher client & adding fetchers...")
    fetcher_client = add_all_fetchers(
        fetcher_client=FetcherClient(),
        publisher_name=publisher_name,
        price_configs=price_configs,
    )

    logger.info("⏳ Starting orchestration...")
    poller = PricePoller(fetcher_client=fetcher_client)
    pusher = PricePusher(client=pragma_client)
    orchestrator = Orchestrator(
        poller=poller,
        listeners=_create_listeners(price_configs, target, pragma_client),
        pusher=pusher,
    )

    logger.info("🚀 Orchestration starting 🚀")
    await orchestrator.run_forever()


def _create_listeners(
    price_configs: List[PriceConfig],
    target: str,
    pragma_client: PragmaClient,
) -> List[PriceListener]:
    """
    Create a listener for each price configuration. They will be used to monitor a group
    of pairs during the orchestration.
    """
    listeners: List[PriceListener] = []
    for price_config in price_configs:
        new_listener = PriceListener(
            request_handler=REQUEST_HANDLER_REGISTRY[target](client=pragma_client),
            price_config=price_config,
            polling_frequency_in_s=20,
        )
        listeners.append(new_listener)
    return listeners


def _create_client(
    target: Target,
    network: Network,
    publisher_address: str,
    private_key: str | Tuple[str, str],
    rpc_url: Optional[str] = None,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    max_fee: Optional[int] = None,
    pagination: Optional[int] = None,
    enable_strk_fees: Optional[bool] = None,
) -> PragmaClient:
    """
    Create the appropriate client based on the target.

    Args:
        target: The target type ('onchain' or 'offchain').
        network: The network type.
        publisher_address: The publisher's address.
        private_key: The private key for the account.
        api_base_url: The API base URL for offchain publishing.
        api_key: The API key for offchain publishing.

    Returns:
        PragmaClient
    """
    if target == "onchain":
        execution_config = ExecutionConfig(
            pagination=pagination if pagination is not None else ExecutionConfig.pagination,
            max_fee=max_fee if max_fee is not None else ExecutionConfig.max_fee,
            enable_strk_fees=enable_strk_fees
            if enable_strk_fees is not None
            else ExecutionConfig.enable_strk_fees,
            auto_estimate=True,
        )
        return PragmaOnChainClient(
            chain_name=network,
            network=network if rpc_url is None else rpc_url,
            account_contract_address=publisher_address,
            account_private_key=private_key,
            execution_config=execution_config,
        )
    elif target == "offchain":
        if not api_key:
            raise click.BadParameter("Argument api-key can't be None if offchain is selected")
        if not api_base_url:
            raise click.BadParameter("Argument api-base-url can't be None if offchain is selected")
        return PragmaAPIClient(
            account_contract_address=publisher_address,
            account_private_key=private_key,
            api_key=api_key,
            api_base_url=api_base_url,
        )
    else:
        raise ValueError(f"Invalid target: {target}")


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
    "-t",
    "--target",
    required=True,
    type=click.Choice(["onchain", "offchain"], case_sensitive=False),
    help="Where the prices will be published.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="At which network the price corresponds.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used to interact with the chain.",
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
    "--publisher-name",
    type=click.STRING,
    required=True,
    help="Your publisher name.",
)
@click.option(
    "--publisher-address",
    type=click.STRING,
    required=True,
    help="Your publisher address.",
)
@click.option("--api-base-url", type=click.STRING, required=False, help="Pragma API base URL")
@click.option(
    "--api-key",
    type=click.STRING,
    required=False,
    help="Pragma API key used to publish offchain",
)
@click.option(
    "--max-fee",
    type=click.IntRange(min=0),
    required=False,
    help="Max fee used when using the onchain client",
)
@click.option(
    "--pagination",
    type=click.IntRange(min=0),
    required=False,
    help="Number of elements per page returned from the onchain client",
)
@click.option(
    "--enable-strk-fees",
    type=click.BOOL,
    required=False,
    help="enable_strk_fees option for the onchain client",
)
def cli_entrypoint(
    config_file: str,
    log_level: str,
    target: str,
    network: str,
    rpc_url: Optional[str],
    raw_private_key: str,
    publisher_name: str,
    publisher_address: str,
    api_base_url: Optional[str],
    api_key: Optional[str],
    max_fee: Optional[int],
    pagination: Optional[int],
    enable_strk_fees: Optional[bool],
) -> None:
    if target == "offchain":
        if not api_key or not api_base_url:
            raise click.UsageError(
                '⛔ "api-key" and "api-base-url" are required when the destination is "offchain".'
            )
        if rpc_url:
            logger.error(
                '🤔 "rpc-url" option has no use when the target is "offchain". Ignoring it.'
            )
        if max_fee:
            logger.warning(
                '🤔 "max_fee" option has no use when the target is "offchain". Ignoring it.'
            )
        if pagination:
            logger.warning(
                '🤔 "pagination" option has no use when the target is "offchain". Ignoring it.'
            )
        if enable_strk_fees:
            logger.warning(
                '🤔 "enable_strk_fees" option has no use when the target is "offchain". Ignoring it.'
            )

    if target == "onchain":
        if rpc_url and not rpc_url.startswith("http"):
            raise click.UsageError('⛔ "rpc_url" format is incorrect. It must start with http(...)')

    # Update the logger level of the pragma_sdk package
    sdk_logger = get_pragma_sdk_logger()
    sdk_logger.setLevel(log_level)

    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)
    price_configs: List[PriceConfig] = PriceConfig.from_yaml(config_file)

    # Make sure that the API base url does not ends with /
    if api_base_url is not None and api_base_url.endswith("/"):
        api_base_url = api_base_url.rstrip()[:-1]

    asyncio.run(
        main(
            price_configs=price_configs,
            target=target,
            network=network,
            private_key=private_key,
            publisher_name=publisher_name,
            publisher_address=publisher_address,
            api_base_url=api_base_url,
            api_key=api_key,
            rpc_url=rpc_url,
            max_fee=max_fee,
            pagination=pagination,
            enable_strk_fees=enable_strk_fees,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()

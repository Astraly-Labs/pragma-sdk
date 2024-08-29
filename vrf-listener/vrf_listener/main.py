import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal, List

from grpc import ssl_channel_credentials
from grpc.aio import secure_channel
from apibara.protocol import StreamAddress, StreamService, credentials_with_auth_token
from apibara.protocol.proto.stream_pb2 import DataFinality
from apibara.starknet import Block, EventFilter, Filter, felt, starknet_cursor

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg
from pragma_sdk.onchain.types import ContractAddresses, RandomnessRequest
from pragma_sdk.onchain.constants import RANDOMNESS_REQUEST_EVENT_SELECTOR
from pragma_sdk.onchain.client import PragmaOnChainClient

logger = logging.getLogger(__name__)

EVENT_INDEX_TO_SPLIT = 7


async def main(
    network: Literal["mainnet", "sepolia"],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    check_requests_interval: int,
    ignore_request_threshold: int,
    rpc_url: Optional[HttpUrl] = None,
    index_with_apibara: bool = False,
    apibara_api_key: Optional[str] = None,
) -> None:
    logger.info("🧩 Starting VRF listener...")
    client = _create_pragma_client(
        network=network,
        vrf_address=vrf_address,
        admin_address=admin_address,
        private_key=private_key,
        rpc_url=rpc_url,
    )

    if index_with_apibara:
        logger.info("👩‍💻 Indexing VRF requests using apibara...")
        stream = await _create_apibara_stream(
            client=client,
            network=network,
            apibara_api_key=apibara_api_key,
            vrf_address=vrf_address,
        )
        requests_queue: asyncio.Queue = asyncio.Queue()
        asyncio.create_task(_index_using_apibara(stream, requests_queue))

    logger.info("👂 Listening for VRF requests!")
    while True:
        if index_with_apibara:
            events = await _consume_full_queue(requests_queue)
        try:
            await client.handle_random(
                private_key=int(private_key, 16),
                ignore_request_threshold=ignore_request_threshold,
                requests_events=events if index_with_apibara else None,
            )
            events = []
        except Exception as e:
            logger.error(f"⛔ Error while handling randomness request: {e}")
            raise e
        await asyncio.sleep(check_requests_interval)


def _create_pragma_client(
    network: Literal["mainnet", "sepolia"],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    rpc_url: Optional[HttpUrl] = None,
) -> PragmaOnChainClient:
    """
    Creates the Pragma Client & init the VRF contract.
    """
    client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=admin_address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=0x0,
            summary_stats_address=0x0,
        ),
    )
    client.init_randomness_contract(int(vrf_address, 16))
    return client


async def _create_apibara_stream(
    client: PragmaOnChainClient,
    network: Literal["mainnet", "sepolia"],
    apibara_api_key: Optional[str],
    vrf_address: str,
) -> StreamService:
    """
    Creates an apibara stream filter that will index VRF requests events.
    """
    if apibara_api_key is None:
        raise ValueError("--apibara-api-key not provided.")

    channel = secure_channel(
        StreamAddress.StarkNet.Sepolia if network == "sepolia" else StreamAddress.StarkNet.Mainnet,
        credentials_with_auth_token(apibara_api_key, ssl_channel_credentials()),
    )
    filter = (
        Filter()
        .with_header(weak=False)
        .add_event(
            EventFilter()
            .with_from_address(felt.from_hex(vrf_address))
            .with_keys([felt.from_hex(RANDOMNESS_REQUEST_EVENT_SELECTOR)])
            .with_include_receipt(False)
            .with_include_transaction(False)
        )
        .encode()
    )
    current_block = await client.get_block_number()
    return StreamService(channel).stream_data_immutable(
        filter=filter,
        finality=DataFinality.DATA_STATUS_PENDING,
        batch_size=1,
        cursor=starknet_cursor(current_block),
    )


async def _index_using_apibara(
    stream: StreamService,
    requests_queue: asyncio.Queue,
) -> None:
    """
    Consumes the apibara stream until empty and extract found vrf requests.
    """
    block = Block()
    async for message in stream:
        if message.data is None:
            continue
        else:
            for batch in message.data.data:
                block.ParseFromString(batch)
                if len(block.events) == 0:
                    continue
                events = block.events
                for event in events:
                    from_data = list(map(felt.to_int, event.event.data))
                    from_data = from_data[:EVENT_INDEX_TO_SPLIT] + [
                        from_data[EVENT_INDEX_TO_SPLIT + 1 :]
                    ]
                    await requests_queue.put(RandomnessRequest(*from_data))


async def _consume_full_queue(requests_queue: asyncio.Queue) -> List[RandomnessRequest]:
    """
    Consume the whole requests_queue and return the requests.
    """
    events = []
    while not requests_queue.empty():
        try:
            e = requests_queue.get_nowait()
            events.append(e)
        except asyncio.QueueEmpty:
            break
    return events


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
    "raw_private_key",
    type=click.STRING,
    required=True,
    help=(
        "Private key of the signer. Format: "
        "aws:secret_name, "
        "plain:private_key, "
        "or env:ENV_VAR_NAME"
    ),
)
@click.option(
    "-t",
    "--check-requests-interval",
    type=click.IntRange(min=0),
    required=False,
    default=10,
    help="Delay in seconds between checks for VRF requests. Defaults to 10 seconds.",
)
@click.option(
    "--ignore-request-threshold",
    type=click.IntRange(min=0),
    required=False,
    default=3,
    help="Blocks to ignore before the current block for the handling.",
)
@click.option(
    "--index-with-apibara",
    type=click.BOOL,
    is_flag=True,
    required=False,
    default=False,
    help="Self index the VRF requests using Apibara instead of using Starknet.py",
)
@click.option(
    "--apibara-api-key",
    type=click.STRING,
    required=False,
    help="Apibara API key. Needed when indexing with Apibara.",
)
def cli_entrypoint(
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    vrf_address: str,
    admin_address: str,
    raw_private_key: str,
    check_requests_interval: int,
    ignore_request_threshold: int,
    index_with_apibara: bool,
    apibara_api_key: Optional[str],
) -> None:
    """
    VRF Listener entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)

    if isinstance(private_key, tuple):
        raise click.UsageError("⛔ KeyStores aren't supported as private key for the vrf-listener!")

    if index_with_apibara and apibara_api_key is None:
        raise click.UsageError(
            "⛔ Apibara API Key is needed when --index-with-apibara is provided."
        )

    asyncio.run(
        main(
            network=network,
            rpc_url=rpc_url,
            vrf_address=vrf_address,
            admin_address=admin_address,
            private_key=private_key,
            check_requests_interval=check_requests_interval,
            ignore_request_threshold=ignore_request_threshold,
            index_with_apibara=index_with_apibara,
            apibara_api_key=apibara_api_key,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()

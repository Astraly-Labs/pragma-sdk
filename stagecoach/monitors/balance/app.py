import asyncio
import json
import os

import boto3
import requests
import telegram

from pragma.core.client import PragmaClient
from pragma.core.logger import get_stream_logger
from pragma.core.utils import felt_to_str

logger = get_stream_logger()

# Inputs
# [Optional]: Publisher names; if empty, query for all
# [Optional]: Balance threshold; if empty, defaults to 0.1 * 10**18 Wei

# Behavior: Ping betteruptime if all is good

SECRET_NAME = os.environ.get("SECRET_NAME")


def handler(event, context):
    asyncio.run(_handler())
    return {"success": True}


def _get_telegram_bot_oauth_token_from_aws():
    region_name = "eu-west-3"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=SECRET_NAME)
    return json.loads(get_secret_value_response["SecretString"])[
        "TELEGRAM_BOT_USER_OAUTH_TOKEN"
    ]


async def _handler():
    chat_id = os.environ.get("CHAT_ID")
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_USER_OAUTH_TOKEN")
    if telegram_bot_token is None:
        telegram_bot_token = _get_telegram_bot_oauth_token_from_aws()
    network = os.environ.get("NETWORK")
    ignore_publishers_str = os.environ.get("IGNORE_PUBLISHERS", "")
    ignore_publishers = ignore_publishers_str.split(",")
    threshold_wei = int(os.environ.get("THRESHOLD_WEI", 0.5 * 10**18))
    bot = telegram.Bot(token=telegram_bot_token)
    client = PragmaClient(network)

    publishers = [
        publisher
        for publisher in await client.get_all_publishers()
        if publisher not in ignore_publishers
    ]

    all_above_threshold = True

    for publisher in publishers:
        address = await client.get_publisher_address(publisher)

        token_address = None
        if network == "testnet2":
            token_address = (
                0x049D36570D4E46F48E99674BD3FCC84644DDD6B96F7C741B1562B82F9E004DC7
            )
        balance = await client.get_balance(address, token_address)

        if balance < threshold_wei:
            error_message = f"Balance below threshold for publisher: {felt_to_str(publisher)}, address: {hex(address)}, balance in ETH: {balance/(10**18)}"
            logger.warning(error_message)
            all_above_threshold = False
            await bot.send_message(chat_id, text=error_message)

        else:
            logger.info(
                f"Balance above threshold for publisher: {felt_to_str(publisher)}, address: {hex(address)}, balance in ETH: {balance/(10**18)}"
            )

    if all_above_threshold:
        betteruptime_id = os.environ.get("BETTERUPTIME_ID")
        requests.get(f"https://betteruptime.com/api/v1/heartbeat/{betteruptime_id}")


if __name__ == "__main__":
    handler(None, None)

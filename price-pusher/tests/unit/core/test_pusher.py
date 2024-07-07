import pytest
import logging
from unittest.mock import AsyncMock, MagicMock
from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry
from price_pusher.core.pusher import PricePusher


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=PragmaClient)
    return client


@pytest.fixture
def price_pusher(mock_client):
    return PricePusher(client=mock_client)


@pytest.mark.asyncio
async def test_update_price_feeds_success(price_pusher, mock_client, caplog):
    caplog.set_level(logging.INFO)
    mock_entry = MagicMock(spec=Entry)
    mock_client.publish_entries.return_value = {"status": "success"}

    entries = [mock_entry]

    response = await price_pusher.update_price_feeds(entries)

    assert response == {"status": "success"}
    mock_client.publish_entries.assert_called_once_with(entries)

    assert any(
        "processing 1 new asset(s) to push..." in record.message for record in caplog.records
    )
    assert any("published 1 entrie(s)" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_update_price_feeds_failure(price_pusher, mock_client, caplog):
    caplog.set_level(logging.INFO)
    mock_entry = MagicMock(spec=Entry)
    mock_client.publish_entries.side_effect = Exception("Test Exception")

    entries = [mock_entry]

    response = await price_pusher.update_price_feeds(entries)

    assert response is None
    mock_client.publish_entries.assert_called_once_with(entries)

    assert any(
        "processing 1 new asset(s) to push..." in record.message for record in caplog.records
    )
    assert any(
        "could not publish entrie(s): Test Exception" in record.message for record in caplog.records
    )

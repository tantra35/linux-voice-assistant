"""Unit tests for the peripheral WebSocket API client mode (PeripheralAPIClient)."""

import asyncio
import json
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linux_voice_assistant.peripheral_api import LVAEvent, PeripheralAPIClient
from tests.unit.conftest import make_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(state=None, url: str = "ws://speaker:6055") -> PeripheralAPIClient:
    """Return a PeripheralAPIClient, optionally attached to a ServerState."""
    client = PeripheralAPIClient(url=url)
    if state is not None:
        client.set_state(state)
    return client


class FakeConnection:
    """Minimal async context-manager websocket standing in for websockets' client."""

    def __init__(self, incoming: Optional[List[str]] = None):
        self.incoming: List[str] = list(incoming or [])
        self.send = AsyncMock()
        self.closed = False

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.closed = True

    def __aiter__(self) -> "FakeConnection":
        return self

    async def __anext__(self) -> str:
        if self.incoming:
            return self.incoming.pop(0)
        # A real open websocket just waits for the next frame — block forever.
        await asyncio.Event().wait()
        raise StopAsyncIteration  # pragma: no cover - unreachable

    async def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# __init__ / start() / stop()
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_stores_url(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        assert client._url == "ws://speaker:6055"  # pylint: disable=protected-access

    def test_default_volume_step(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        assert client._volume_step == 0.05  # pylint: disable=protected-access

    def test_no_connection_on_init(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        assert client._ws is None  # pylint: disable=protected-access
        assert client._task is None  # pylint: disable=protected-access


class TestClientStartStop:
    @pytest.mark.asyncio
    async def test_start_uses_configured_url_and_sets_loop(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        connection = FakeConnection()
        factory = MagicMock(return_value=connection)

        with patch("websockets.client.connect", factory):
            await client.start()

        # The reconnect task dials asynchronously; give it a chance to run.
        await asyncio.sleep(0.05)
        factory.assert_called_once_with("ws://speaker:6055")
        assert client._loop is asyncio.get_running_loop()  # pylint: disable=protected-access
        assert client._task is not None  # pylint: disable=protected-access
        assert client._ws is connection  # pylint: disable=protected-access
        await client.stop()

    @pytest.mark.asyncio
    async def test_stop_closes_connection_and_cancels_task(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        connection = FakeConnection()

        with patch("websockets.client.connect", MagicMock(return_value=connection)):
            await client.start()
        await asyncio.sleep(0.05)
        task = client._task  # pylint: disable=protected-access

        await client.stop()

        assert connection.closed is True
        assert client._ws is None  # pylint: disable=protected-access
        assert client._task is None  # pylint: disable=protected-access
        assert task is not None
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.done()

    @pytest.mark.asyncio
    async def test_stop_without_start_does_not_raise(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        await client.stop()  # should not raise


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestClientRun:
    @pytest.mark.asyncio
    async def test_connect_sends_snapshot(self, tmp_path):
        state = make_state(tmp_path, volume=0.3, muted=False, connected=True)
        client = make_client(state)
        connection = FakeConnection()
        client._connect_factory = MagicMock(return_value=connection)  # pylint: disable=protected-access

        task = asyncio.get_running_loop().create_task(client._run())  # pylint: disable=protected-access
        for _ in range(10):
            await asyncio.sleep(0)

        assert connection.send.await_count >= 1
        snapshot = json.loads(connection.send.call_args_list[0].args[0])
        assert snapshot["event"] == "snapshot"
        assert snapshot["data"]["volume"] == pytest.approx(0.3)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_dispatches_commands_from_endpoint(self, tmp_path):
        state = make_state(tmp_path, muted=False)
        satellite = MagicMock()
        state.satellite = satellite
        client = make_client(state)
        connection = FakeConnection(incoming=[json.dumps({"command": "start_listening"})])
        client._connect_factory = MagicMock(return_value=connection)  # pylint: disable=protected-access

        task = asyncio.get_running_loop().create_task(client._run())  # pylint: disable=protected-access
        for _ in range(10):
            await asyncio.sleep(0)

        satellite.start_listening.assert_called_once()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_reconnects_after_connection_failure(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        connection = FakeConnection()
        factory = MagicMock(side_effect=[OSError("down"), connection])
        client._connect_factory = factory  # pylint: disable=protected-access

        task = asyncio.get_running_loop().create_task(client._run())  # pylint: disable=protected-access
        await asyncio.sleep(1.5)

        assert client._ws is connection  # pylint: disable=protected-access
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Event sending
# ---------------------------------------------------------------------------


class TestClientSendToPeers:
    @pytest.mark.asyncio
    async def test_emit_event_sends_to_endpoint(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        connection = AsyncMock()
        client._ws = connection  # pylint: disable=protected-access

        await client.emit_event(LVAEvent.IDLE)

        connection.send.assert_awaited_once()
        assert json.loads(connection.send.await_args.args[0])["event"] == "idle"

    @pytest.mark.asyncio
    async def test_emit_event_without_connection_does_not_raise(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        await client.emit_event(LVAEvent.IDLE)  # should not raise

    @pytest.mark.asyncio
    async def test_send_failure_does_not_raise(self):
        client = PeripheralAPIClient(url="ws://speaker:6055")
        connection = AsyncMock()
        connection.send.side_effect = ConnectionError
        client._ws = connection  # pylint: disable=protected-access

        await client.emit_event(LVAEvent.IDLE)  # should not raise

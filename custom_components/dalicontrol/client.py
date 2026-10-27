"""Transport for DCBM line controllers (UDP or TCP)."""

from __future__ import annotations

import asyncio
import logging

from .const import PROTOCOL_TCP
from .protocol import GROUP_ACK

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 3
# A controller allows 4 TCP sockets in total, so never hold one open.
SEND_GAP = 0.05


class DaliControlError(Exception):
    """Raised when a frame could not be delivered."""


class _UdpProtocol(asyncio.DatagramProtocol):
    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP error: %s", exc)


class DaliControlClient:
    """Sends frames to one host/port. Commands are serialised."""

    def __init__(self, host: str, port: int, protocol: str) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol
        self._lock = asyncio.Lock()

    async def async_send(self, frame: str) -> None:
        """Send one frame and wait for the controller's ack where one exists."""
        async with self._lock:
            _LOGGER.debug("TX %s:%s %s", self.host, self.port, frame)
            if self.protocol == PROTOCOL_TCP:
                await self._send_tcp(frame)
            else:
                await self._send_udp(frame)
            await asyncio.sleep(SEND_GAP)

    async def _send_udp(self, frame: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            transport, _ = await loop.create_datagram_endpoint(
                _UdpProtocol, remote_addr=(self.host, self.port), allow_broadcast=True
            )
        except OSError as err:
            raise DaliControlError(f"UDP send to {self.host}:{self.port} failed: {err}") from err
        try:
            transport.sendto(frame.encode("ascii"))
        finally:
            transport.close()

    async def _send_tcp(self, frame: str) -> None:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), TIMEOUT
            )
        except (OSError, TimeoutError) as err:
            raise DaliControlError(f"TCP connect to {self.host}:{self.port} failed: {err}") from err
        try:
            writer.write(frame.encode("ascii"))
            await asyncio.wait_for(writer.drain(), TIMEOUT)
            # Group Type commands (015) are acknowledged; DALI Type (014) are not.
            if frame[4:7] == "015":
                try:
                    reply = await asyncio.wait_for(reader.readuntil(b"*"), TIMEOUT)
                except (TimeoutError, asyncio.IncompleteReadError):
                    _LOGGER.debug("No ack for %s", frame)
                else:
                    if reply.decode("ascii", "replace") != GROUP_ACK:
                        _LOGGER.warning("Unexpected reply to %s: %r", frame, reply)
        except OSError as err:
            raise DaliControlError(f"TCP send to {self.host}:{self.port} failed: {err}") from err
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


async def async_test_connection(host: str, port: int, protocol: str) -> None:
    """Check reachability. UDP is connectionless, so only TCP is really tested."""
    if protocol != PROTOCOL_TCP:
        return
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), TIMEOUT)
    except (OSError, TimeoutError) as err:
        raise DaliControlError(str(err)) from err
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass



"""Transport tests against local UDP/TCP listeners (no Home Assistant needed)."""

import asyncio
import importlib.util
import pathlib
import sys
import types
import unittest

_pkg_dir = pathlib.Path(__file__).parent.parent / "custom_components" / "dalicontrol"
# Register a stub package so client.py's relative imports work without
# running the integration's __init__ (which needs Home Assistant).
_pkg = types.ModuleType("dalicontrol_stub")
_pkg.__path__ = [str(_pkg_dir)]
sys.modules["dalicontrol_stub"] = _pkg
for _name in ("const", "protocol", "client"):
    _spec = importlib.util.spec_from_file_location(
        f"dalicontrol_stub.{_name}", _pkg_dir / f"{_name}.py"
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"dalicontrol_stub.{_name}"] = _mod
    _spec.loader.exec_module(_mod)
client = sys.modules["dalicontrol_stub.client"]


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_udp(self):
        got = asyncio.Queue()

        class P(asyncio.DatagramProtocol):
            def datagram_received(self, data, addr):
                got.put_nowait(data)

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            P, local_addr=("127.0.0.1", 0)
        )
        port = transport.get_extra_info("sockname")[1]
        try:
            c = client.DaliControlClient("127.0.0.1", port, "udp")
            await c.async_send("$011014010010051000500*")
            self.assertEqual(
                await asyncio.wait_for(got.get(), 2), b"$011014010010051000500*"
            )
        finally:
            transport.close()

    async def test_tcp_group_ack(self):
        got = []

        async def handle(reader, writer):
            got.append(await reader.readuntil(b"*"))
            writer.write(b"$0000150000300000*")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            c = client.DaliControlClient("127.0.0.1", port, "tcp")
            await c.async_send("$011015007005800500*")
        self.assertEqual(got, [b"$011015007005800500*"])

    async def test_tcp_refused(self):
        c = client.DaliControlClient("127.0.0.1", 1, "tcp")
        with self.assertRaises(client.DaliControlError):
            await c.async_send("$011014010010051000500*")


if __name__ == "__main__":
    unittest.main()

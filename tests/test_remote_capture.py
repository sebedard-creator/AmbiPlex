import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from led_engine import LedEngine
from remote_capture import FRAME_BYTES, RemoteCapture


CONFIG = {"wled_ip": "192.0.2.1", "leds_top": 64, "leds_side": 36,
          "led_depth": 8, "led_smoothing": 0, "disable_autocrop": True}


class Socket:
    def __init__(self, messages=()):
        self.client = SimpleNamespace(host="127.0.0.1")
        self.url = "ws://localhost:5777/api/remote/frames"
        self.headers = {"origin": "http://localhost:5777"}
        self.messages = iter(messages)
        self.accept = AsyncMock()
        self.close = AsyncMock()
        self.send_json = AsyncMock()

    async def receive(self):
        return next(self.messages, {"type": "websocket.disconnect"})


class RemoteCaptureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = LedEngine()
        self.engine.send_ddp = Mock()
        self.engine.close = Mock(wraps=self.engine.close)
        self.broadcast = AsyncMock()
        self.capture = RemoteCapture(lambda: CONFIG.copy(), self.broadcast, lambda: self.engine)

    def tearDown(self):
        self.engine.sock.close()

    async def test_rgb_matches_existing_engine_and_ack_follows_ddp(self):
        rgba = np.random.default_rng(42).integers(0, 256, (90, 160, 4), dtype=np.uint8)
        with patch.object(LedEngine, "send_ddp"):
            reference = LedEngine()
            expected = reference.calculate_colors(rgba[:, :, :3], CONFIG)
            reference.close()
        socket = Socket([{"type": "websocket.receive", "bytes": rgba.tobytes()}])
        async def ack(data):
            if data["type"] == "frame":
                self.engine.send_ddp.assert_called_once_with(CONFIG["wled_ip"], expected)
                self.assertTrue(self.capture.active)
        socket.send_json.side_effect = ack
        await self.capture.receive(socket)
        self.assertFalse(self.capture.active)
        self.engine.close.assert_called_once()
        self.assertEqual(self.broadcast.call_args.args[0]["colors"], expected)

    async def test_invalid_frames_release_owner_without_ddp(self):
        for message in [{"bytes": b""}, {"bytes": b"x" * (FRAME_BYTES + 1)}, {"text": "hello"}]:
            socket = Socket([{"type": "websocket.receive", **message}])
            await self.capture.receive(socket)
            self.assertEqual(socket.close.call_args.kwargs["code"], 1003)
            self.assertFalse(self.capture.active)
        self.engine.send_ddp.assert_not_called()

    async def test_second_capture_cannot_take_ownership(self):
        owner = object()
        self.capture.owner = owner
        socket = Socket()
        await self.capture.receive(socket)
        self.assertIs(self.capture.owner, owner)
        self.assertEqual(socket.close.call_args.kwargs["code"], 1008)
        self.engine.close.assert_not_called()

    async def test_remote_or_cross_origin_connections_rejected(self):
        for host, origin in [("192.168.1.20", "http://localhost:5777"),
                             ("127.0.0.1", "https://evil.example"),
                             ("127.0.0.1", "http://localhost:9999"),
                             ("127.0.0.1", ""),
                             ("127.0.0.1", "http://localhost:bad")]:
            socket = Socket()
            socket.client.host = host
            socket.headers["origin"] = origin
            await self.capture.receive(socket)
            socket.accept.assert_not_called()
            self.assertFalse(self.capture.active)

    async def test_missing_wled_releases_ownership(self):
        self.capture.load_config = lambda: {}
        socket = Socket()
        await self.capture.receive(socket)
        self.assertFalse(self.capture.active)
        self.assertEqual(socket.close.call_args.kwargs["code"], 1008)
        self.engine.send_ddp.assert_not_called()

    async def test_silent_client_times_out_and_releases_ownership(self):
        socket = Socket()
        socket.receive = lambda: asyncio.sleep(10)
        self.capture.timeout = 0.01
        await self.capture.receive(socket)
        self.assertFalse(self.capture.active)
        self.engine.close.assert_called_once()

    async def test_heartbeat_keeps_static_source_connected_without_ddp(self):
        socket = Socket()
        calls = 0
        async def receive():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            if calls <= 6:
                return {"type": "websocket.receive", "text": "ping"}
            return {"type": "websocket.disconnect", "code": 1000}
        socket.receive = receive
        self.capture.timeout = 0.04
        await self.capture.receive(socket)
        socket.close.assert_not_called()
        self.assertEqual(socket.send_json.await_count, 7)
        self.engine.send_ddp.assert_not_called()
        self.assertFalse(self.capture.active)

    async def test_cancellation_releases_ownership(self):
        socket = Socket()
        socket.receive = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.capture.receive(socket)
        self.assertFalse(self.capture.active)
        self.engine.close.assert_called_once()

    async def test_engine_failure_releases_ownership(self):
        self.engine.calculate_colors = Mock(side_effect=ValueError("test"))
        socket = Socket([{"type": "websocket.receive", "bytes": bytes(FRAME_BYTES)}])
        with self.assertRaises(ValueError):
            await self.capture.receive(socket)
        self.assertFalse(self.capture.active)
        self.engine.close.assert_called_once()

    def test_plex_ddp_suppressed_only_during_capture(self):
        colors = [[20, 40, 60]]
        self.capture.owner = object()
        self.capture.send_plex_colors(self.engine, CONFIG["wled_ip"], colors)
        self.engine.send_ddp.assert_not_called()
        self.capture.owner = None
        self.capture.send_plex_colors(self.engine, CONFIG["wled_ip"], colors)
        self.engine.send_ddp.assert_called_once_with(CONFIG["wled_ip"], colors)

    async def test_capture_started_during_subtitle_load_prevents_plex_send(self):
        import web
        sync = SimpleNamespace(is_playing=True, current_media_path="movie.mkv",
                               current_view_offset=1000, connect=Mock(), start_websocket_listener=Mock())
        reader = Mock()
        reader.is_active.return_value = False
        reader.needs_check.return_value = True
        async def ensure(*args):
            self.capture.owner = object()
            return True
        reader.ensure_compatible = ensure
        async def sleep(seconds):
            if seconds == 0.01:
                raise asyncio.CancelledError
        engine = Mock()
        with patch.object(web, "remote_capture", self.capture), \
                patch.object(web, "load_config", return_value=CONFIG), \
                patch.object(web, "PlexSynchronizer", return_value=sync), \
                patch.object(web, "WledSubtitleReader", return_value=reader), \
                patch.object(web, "LedEngine", return_value=engine), \
                patch.object(web, "broadcast", AsyncMock()), \
                patch.object(web.asyncio, "sleep", side_effect=sleep):
            with self.assertRaises(asyncio.CancelledError):
                await web.background_sync_loop()
        engine.send_ddp.assert_not_called()
        self.capture.owner = None


def serve_fixture(port):
    """Browser test server: no Plex, real config file or physical DDP output."""
    import uvicorn
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    app = FastAPI()
    stats = {"frames": 0, "colors": []}

    def engine_factory():
        engine = LedEngine()
        def record(ip, colors):
            stats["frames"] += 1
            stats["colors"] = colors
        engine.send_ddp = record
        return engine

    capture = RemoteCapture(lambda: CONFIG.copy(), AsyncMock(), engine_factory)
    app.include_router(capture.router)
    app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parents[1] / "static"))

    @app.get("/test-stats")
    def test_stats():
        return {**stats, "active": capture.active}

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning",
                ws_max_size=65536, ws_max_queue=1, ws_per_message_deflate=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve_fixture(int(sys.argv[2]))
    else:
        unittest.main()

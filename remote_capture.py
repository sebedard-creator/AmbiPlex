"""Local, user-selected browser capture feeding the existing LED engine."""

import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from led_engine import LedEngine

WIDTH, HEIGHT = 160, 90
FRAME_BYTES = WIDTH * HEIGHT * 4
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
logger = logging.getLogger("RemoteCapture")


class RemoteCapture:
    def __init__(self, load_config, broadcast, engine_factory=LedEngine):
        self.load_config = load_config
        self.broadcast = broadcast
        self.engine_factory = engine_factory
        self.owner = None
        self.timeout = 15.0
        self.router = APIRouter()
        self.router.add_api_route("/remote", self.page, methods=["GET"])
        self.router.add_api_websocket_route("/api/remote/frames", self.receive)

    @property
    def active(self):
        return self.owner is not None

    def send_plex_colors(self, engine, ip, colors):
        # No await between ownership check and UDP send: both sources share a loop.
        if not self.active:
            engine.send_ddp(ip, colors)

    def page(self):
        return FileResponse(Path(__file__).parent / "static" / "remote.html")

    @staticmethod
    def is_local(websocket):
        try:
            origin = urlsplit(websocket.headers.get("origin", ""))
            target = urlsplit(str(websocket.url))
            return (websocket.client is not None
                    and websocket.client.host in LOCAL_HOSTS
                    and origin.hostname in LOCAL_HOSTS
                    and origin.hostname == target.hostname
                    and origin.port == target.port
                    and origin.scheme == ("https" if target.scheme == "wss" else "http"))
        except ValueError:
            return False

    async def receive(self, websocket: WebSocket):
        if not self.is_local(websocket):
            await websocket.close(code=1008, reason="Local same-origin capture only")
            return
        await websocket.accept()
        if self.active:
            await websocket.close(code=1008, reason="Une capture est deja active")
            return

        token = object()
        self.owner = token
        engine = None
        frames = 0
        try:
            config = self.load_config()
            if not config.get("wled_ip"):
                await websocket.close(code=1008, reason="Adresse WLED absente de la configuration")
                return
            engine = self.engine_factory()
            loaded_at = time.monotonic()
            logger.info("Capture locale ouverte")
            await websocket.send_json({"type": "ready"})
            while True:
                message = await asyncio.wait_for(websocket.receive(), timeout=self.timeout)
                if message["type"] == "websocket.disconnect":
                    logger.info("Capture fermee par le navigateur: code=%s, images=%s",
                                message.get("code"), frames)
                    break
                if message.get("text") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                payload = message.get("bytes")
                if payload is None or len(payload) != FRAME_BYTES:
                    await websocket.close(code=1003, reason="Expected 160x90 RGBA8")
                    break
                started = time.perf_counter()
                if time.monotonic() - loaded_at >= 1:
                    config = self.load_config()
                    loaded_at = time.monotonic()
                frame = np.frombuffer(payload, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)[:, :, :3]
                colors = engine.calculate_colors(frame, config)
                engine.send_ddp(config.get("wled_ip"), colors)
                frames += 1
                elapsed_ms = (time.perf_counter() - started) * 1000
                # Acknowledgment allows exactly one outstanding frame in the browser.
                await websocket.send_json({"type": "frame", "processing_ms": elapsed_ms})
                await self.broadcast({
                    "type": "monitoring", "state": "playing (remote)",
                    "offset": 0, "local_offset": 0, "action": "REMOTE",
                    "dropped_frames": 0, "loop_time_ms": round(elapsed_ms, 2),
                    "colors": colors,
                    "crop_box": [int(engine.crop_top), int(engine.crop_bottom)],
                })
        except asyncio.TimeoutError:
            logger.warning("Capture expiree: aucun message depuis %ss, images=%s", self.timeout, frames)
            await websocket.close(code=1000, reason="Connexion de capture inactive depuis 15 secondes")
        except WebSocketDisconnect:
            pass
        finally:
            if engine is not None:
                engine.close()
            if self.owner is token:
                self.owner = None

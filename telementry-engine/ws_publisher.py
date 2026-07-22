# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.


from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Deque, Optional

from telemetry_schema import TelemetryFrame

logger = logging.getLogger("telemetry_engine.ws_publisher")

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:  # pragma: no cover
    websockets = None
    WEBSOCKETS_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    aiohttp = None
    AIOHTTP_AVAILABLE = False


class WSPublisher:


    def __init__(
        self,
        mode: str = "websocket",
        ws_uri: Optional[str] = None,
        http_endpoint: Optional[str] = None,
        batch_hz: float = 30.0,
        max_buffer_frames: int = 600,
        reconnect_backoff_start_s: float = 0.5,
        reconnect_backoff_max_s: float = 10.0,
    ):
        if mode not in ("websocket", "http"):
            raise ValueError(f"Unsupported mode: {mode}")
        if mode == "websocket" and not ws_uri:
            raise ValueError("ws_uri is required for websocket mode")
        if mode == "http" and not http_endpoint:
            raise ValueError("http_endpoint is required for http mode")

        self.mode = mode
        self.ws_uri = ws_uri
        self.http_endpoint = http_endpoint
        self.batch_hz = batch_hz
        self.reconnect_backoff_start_s = reconnect_backoff_start_s
        self.reconnect_backoff_max_s = reconnect_backoff_max_s

        self._buffer: Deque[TelemetryFrame] = deque(maxlen=max_buffer_frames)
        self._lock = asyncio.Lock()
        self._running = False
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def publish(self, frame: TelemetryFrame) -> None:

        async with self._lock:
            if len(self._buffer) == self._buffer.maxlen:
                logger.warning(
                    "ws_publisher buffer full (%d frames); dropping oldest frame. "
                    "Downstream consumer may be too slow or disconnected.",
                    self._buffer.maxlen,
                )
            self._buffer.append(frame)

    async def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        if self.mode == "websocket":
            await self._run_websocket()
        else:
            await self._run_http()

  


    async def _run_websocket(self) -> None:
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("`websockets` package not installed. pip install websockets")

        backoff = self.reconnect_backoff_start_s
        period = 1.0 / self.batch_hz

        while self._running:
            try:
                async with websockets.connect(self.ws_uri, ping_interval=20, ping_timeout=20) as ws:
                    self._connected = True
                    backoff = self.reconnect_backoff_start_s
                    logger.info("ws_publisher connected to %s", self.ws_uri)

                    while self._running:
                        batch = await self._drain_batch()
                        for f in batch:
                            await ws.send(f.to_json())
                        await asyncio.sleep(period)

            except (
                getattr(websockets, "exceptions", None) and websockets.exceptions.WebSocketException,
                OSError,
                asyncio.TimeoutError,
            ) as e:
                self._connected = False
                logger.warning(
                    "ws_publisher disconnected (%s); retrying in %.1fs. "
                    "Frames are buffering (max %d) in the meantime.",
                    e, backoff, self._buffer.maxlen,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.reconnect_backoff_max_s)

        self._connected = False

    async def _drain_batch(self) -> list:
        async with self._lock:
            batch = list(self._buffer)
            self._buffer.clear()
        return batch

  

    async def _run_http(self) -> None:
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("`aiohttp` package not installed. pip install aiohttp")

        period = 1.0 / self.batch_hz
        backoff = self.reconnect_backoff_start_s

        async with aiohttp.ClientSession() as session:
            while self._running:
                batch = await self._drain_batch()
                if batch:
                    payload = [f.to_dict() for f in batch]
                    try:
                        async with session.post(self.http_endpoint, json=payload, timeout=5) as resp:
                            self._connected = resp.status < 400
                            if not self._connected:
                                logger.warning(
                                    "ws_publisher HTTP POST got status %d", resp.status
                                )
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        self._connected = False
                        logger.warning(
                            "ws_publisher HTTP POST failed (%s); retrying in %.1fs.", e, backoff
                        )
                     
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, self.reconnect_backoff_max_s)
                        continue
                    else:
                        backoff = self.reconnect_backoff_start_s

                await asyncio.sleep(period)
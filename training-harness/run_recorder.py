
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Optional

from event_schema import TrainingEvent

try:
    import websockets
    _WEBSOCKETS_AVAILABLE = True
except ImportError:
    _WEBSOCKETS_AVAILABLE = False


class RunRecorder:
    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.output_path.open("w", encoding="utf-8")
        self._seq = 0
        self._telemetry_task: Optional[asyncio.Task] = None

    

    def record_training_event(self, event: TrainingEvent) -> None:
        self._write({"stream": "training", **event.to_dict()})

    
    def record_telemetry_frame(self, frame: dict[str, Any]) -> None:
        self._write({"stream": "telemetry", "received_at": time.time(), "frame": frame})

    async def attach_telemetry(self, stream_server_ws_url: str) -> None:
      
        if not _WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets package not installed — pip install websockets")

        async def _consume():
            async with websockets.connect(stream_server_ws_url) as ws:
                await ws.send(json.dumps({"type": "subscribe_live"}))
                async for raw in ws:
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    self.record_telemetry_frame(frame)

        self._telemetry_task = asyncio.create_task(_consume())

    async def stop(self) -> None:
        if self._telemetry_task is not None:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
        self._fh.close()


    def _write(self, record: dict[str, Any]) -> None:
        record["seq"] = self._seq
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()
        self._seq += 1  
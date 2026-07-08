# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.

"""
main.py

Entry point for telemetry-engine. Wires the poller, kernel tracer, and
memory tracker together as coordinated async tasks, assembles their
latest output into fixed-rate TelemetryFrames, and either streams them
live (via ws_publisher) or records them to a local file.

CLI:
    python main.py --gpu-index 0 --tick-rate 30 --output-mode live  --ws-uri ws://localhost:8765/telemetry --kernel-mode auto

    python main.py --list-gpus
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from telemetry_schema import MemorySnapshot, SMState, TelemetryFrame, TrainingMetrics, new_frame
from nvml_poller import NVMLPoller, NVMLUnavailableError
from kernel_tracer import KernelTracer, KernelTracerMode
from memory_tracker import MemoryTracker
from ws_publisher import WSPublisher

logging.basicConfig(
    level=os.environ.get("TELEMETRY_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("telemetry_engine.main")


class FrameAssembler:
    """Holds the latest known state from each producer and stitches them
    into a TelemetryFrame at a fixed output rate, independent of each
    producer's own (possibly irregular) tick rate. This is the
    'Buffering & Interpolation' piece from the roadmap: producers can be
    choppy, but the assembler always emits smooth, fixed-rate frames."""

    def __init__(self, tick_rate_hz: float):
        self.tick_rate_hz = tick_rate_hz
        self._latest_sm: Optional[SMState] = None
        self._pending_kernel_events = []
        self._latest_memory: Optional[MemorySnapshot] = None
        self._frame_id = 0

    def on_sm_state(self, sample: SMState) -> None:
        self._latest_sm = sample

    def on_kernel_event(self, event) -> None:
        self._pending_kernel_events.append(event)

    def set_memory_snapshot(self, snapshot: MemorySnapshot) -> None:
        self._latest_memory = snapshot

    def build_frame(self) -> TelemetryFrame:
        events, self._pending_kernel_events = self._pending_kernel_events, []
        frame = new_frame(
            frame_id=self._frame_id,
            tick_rate_hz=self.tick_rate_hz,
            sm_state=self._latest_sm,
            kernel_events=events,
            memory_snapshot=self._latest_memory,
            training_metrics=None,  # wired up once a training harness forwards metrics
        )
        self._frame_id += 1
        return frame


async def assembler_loop(
    assembler: FrameAssembler,
    tick_rate_hz: float,
    memory_tracker: Optional[MemoryTracker],
    sink,  # coroutine function: async def sink(frame) -> None
    stop_event: asyncio.Event,
) -> None:
    period = 1.0 / tick_rate_hz
    loop = asyncio.get_event_loop()
    next_tick = loop.time()

    while not stop_event.is_set():
        if memory_tracker is not None:
            assembler.set_memory_snapshot(memory_tracker.poll())

        frame = assembler.build_frame()
        await sink(frame)

        next_tick += period
        delay = next_tick - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        else:
            next_tick = loop.time()


async def run(args: argparse.Namespace) -> None:
    stop_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal) if hasattr(loop, "add_signal_handler") else None
        except (NotImplementedError, AttributeError):
            pass
    try:
        loop.add_signal_handler(signal.SIGINT, _handle_signal)
        loop.add_signal_handler(signal.SIGTERM, _handle_signal)
    except (NotImplementedError, AttributeError):
        # Not supported on this platform (e.g. some Windows setups) -
        # KeyboardInterrupt will still work via the outer try/except.
        pass

    assembler = FrameAssembler(tick_rate_hz=args.tick_rate)

    poller = NVMLPoller(
        gpu_index=args.gpu_index,
        poll_hz=args.tick_rate,
        on_sample=assembler.on_sm_state,
    )

    try:
        await poller.start()
    except NVMLUnavailableError as e:
        logger.error("Cannot start: %s", e)
        sys.exit(1)

    tracer = KernelTracer(
        on_event=assembler.on_kernel_event,
        mode=KernelTracerMode(args.kernel_mode),
        nvml_util_getter=lambda: (assembler._latest_sm.sm_utilization_pct if assembler._latest_sm else 0.0),
    )
    await tracer.start()

    memory_tracker = MemoryTracker(pid=os.getpid(), nvml_handle=poller._handle)

    # -- output sink: live stream or record-to-file -----------------------
    publisher: Optional[WSPublisher] = None
    record_file = None

    if args.output_mode == "live":
        publisher = WSPublisher(
            mode="websocket" if args.ws_uri else "http",
            ws_uri=args.ws_uri,
            http_endpoint=args.http_endpoint,
            batch_hz=args.tick_rate,
        )

        async def sink(frame: TelemetryFrame) -> None:
            await publisher.publish(frame)

    else:  # record
        record_file = open(args.record_path, "w", buffering=1)
        logger.info("Recording telemetry frames to %s", args.record_path)

        async def sink(frame: TelemetryFrame) -> None:
            record_file.write(frame.to_json() + "\n")

    tasks = [
        asyncio.create_task(poller.run(), name="nvml_poller"),
        asyncio.create_task(tracer.run(), name="kernel_tracer"),
        asyncio.create_task(
            assembler_loop(assembler, args.tick_rate, memory_tracker, sink, stop_event),
            name="assembler_loop",
        ),
    ]
    if publisher is not None:
        tasks.append(asyncio.create_task(publisher.run(), name="ws_publisher"))

    def _on_task_done(task: asyncio.Task) -> None:
        # Without this, a task that dies from an uncaught exception just
        # vanishes - asyncio logs a quiet "exception was never retrieved"
        # warning at best, and every other task (including the assembler)
        # keeps running forever on whatever stale data that task last
        # produced. That's how a dead poller silently produces a
        # recording that *looks* fine but is frozen after frame N.
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Task '%s' died unexpectedly: %r", task.get_name(), exc, exc_info=exc)
            stop_event.set()  # bring the whole pipeline down together, not limp on partially

    for t in tasks:
        t.add_done_callback(_on_task_done)

    logger.info(
        "telemetry-engine running: gpu=%d tick_rate=%.1fHz kernel_mode=%s output=%s",
        args.gpu_index, args.tick_rate, tracer.active_mode, args.output_mode,
    )

    await stop_event.wait()

    logger.info("Shutting down...")
    await tracer.stop()
    await poller.stop()
    if publisher is not None:
        await publisher.stop()
    if record_file is not None:
        record_file.close()

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete.")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pyrosilica telemetry engine")
    p.add_argument("--gpu-index", type=int, default=0, help="Target GPU index (default: 0)")
    p.add_argument("--tick-rate", type=float, default=25.0, help="Poll/output rate in Hz (default: 25)")
    p.add_argument(
        "--kernel-mode", choices=["auto", "cupti", "sampled"], default="auto",
        help="'auto' probes for CUPTI and falls back to sampling; 'cupti' fails hard if unavailable.",
    )
    p.add_argument("--output-mode", choices=["live", "record"], default="live")
    p.add_argument("--ws-uri", default=None, help="e.g. ws://localhost:8765/telemetry (live mode)")
    p.add_argument("--http-endpoint", default=None, help="Used instead of --ws-uri for HTTP POST mode")
    p.add_argument("--record-path", default="telemetry_recording.jsonl", help="Output path for record mode")
    p.add_argument("--list-gpus", action="store_true", help="List visible GPUs and exit")
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.list_gpus:
        for d in NVMLPoller.enumerate_devices():
            print(f"[{d.index}] {d.name}  ({d.uuid})")
        return

    if args.output_mode == "live" and not args.ws_uri and not args.http_endpoint:
        parser.error("--output-mode live requires --ws-uri or --http-endpoint")

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
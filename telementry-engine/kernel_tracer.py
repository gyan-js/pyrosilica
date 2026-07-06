# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.

"""
kernel_tracer.py

The abstraction layer main.py actually talks to for kernel-level activity.
Decides once, at startup, whether to use the real CUPTI bridge or the
sampling fallback, based on a capability probe. Normalizes both sources
into one KernelEvent schema (telemetry_schema.KernelEvent) so nothing
downstream ever needs to know which mode is active.

Fallback mode note: without CUPTI, there is no way to observe individual
kernel launches. The fallback instead periodically snapshots "is the SM
currently busy" via NVML and emits a lower-fidelity synthetic KernelEvent
representing that window of activity (source="sampled", name="unknown").
This is intentionally described as lower-fidelity in the roadmap - it's a
usable stand-in for the 3D visualization's activity pulse, not a real
kernel trace.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Awaitable, Callable, Optional, Union

from telemetry_schema import KernelEvent, now_ms
from cupti_bridge import CUPTIBridge, CUPTIUnavailableError, probe as cupti_probe

logger = logging.getLogger("telemetry_engine.kernel_tracer")

EventCallback = Callable[[KernelEvent], Union[None, Awaitable[None]]]


class KernelTracerMode(str, Enum):
    AUTO = "auto"
    CUPTI = "cupti"
    SAMPLED = "sampled"


class KernelTracer:
    """
    Usage:
        tracer = KernelTracer(mode=KernelTracerMode.AUTO, on_event=cb,
                               nvml_handle_getter=lambda: poller_handle)
        await tracer.start()
        await tracer.run()   # runs until tracer.stop()
    """

    def __init__(
        self,
        on_event: EventCallback,
        mode: KernelTracerMode = KernelTracerMode.AUTO,
        sample_hz: float = 50.0,
        nvml_util_getter: Optional[Callable[[], float]] = None,
    ):
        """
        nvml_util_getter: zero-arg callable returning the *current*
        SM utilization percentage (0-100). kernel_tracer doesn't own NVML
        itself (nvml_poller.py does); main.py wires this in so the
        fallback sampler can piggyback on the same counter the poller
        already reads, instead of opening a second NVML handle.
        """
        self.on_event = on_event
        self.requested_mode = mode
        self.sample_hz = sample_hz
        self.nvml_util_getter = nvml_util_getter

        self.active_mode: Optional[KernelTracerMode] = None
        self._cupti: Optional[CUPTIBridge] = None
        self._running = False

    async def start(self) -> None:
        if self.requested_mode in (KernelTracerMode.AUTO, KernelTracerMode.CUPTI):
            cap = cupti_probe()
            if cap.lib_found and cap.native_shim_found:
                try:
                    bridge = CUPTIBridge(on_event=self._emit_sync)
                    bridge.start()
                    self._cupti = bridge
                    self.active_mode = KernelTracerMode.CUPTI
                    logger.info("kernel_tracer: using real CUPTI capture.")
                    return
                except CUPTIUnavailableError as e:
                    if self.requested_mode == KernelTracerMode.CUPTI:
                        raise  # caller explicitly demanded CUPTI; don't silently downgrade
                    logger.warning("CUPTI unavailable (%s); falling back to sampling.", e)
            elif self.requested_mode == KernelTracerMode.CUPTI:
                raise CUPTIUnavailableError(
                    f"CUPTI explicitly requested but unavailable: lib_found={cap.lib_found}, "
                    f"native_shim_found={cap.native_shim_found}"
                )

        self.active_mode = KernelTracerMode.SAMPLED
        logger.info("kernel_tracer: using sampling fallback (lower fidelity).")

    async def stop(self) -> None:
        self._running = False
        if self._cupti is not None:
            self._cupti.stop()

    def _emit_sync(self, event: KernelEvent) -> None:
        """Bridge for the CUPTI native-callback thread, which isn't inside
        our asyncio loop. Schedules the (possibly async) handler safely."""
        result = self.on_event(event)
        if asyncio.iscoroutine(result):
            try:
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(result, loop)
            except RuntimeError:
                logger.warning("No running loop to schedule CUPTI event handler on; dropping.")

    async def run(self) -> None:
        """
        For CUPTI mode: the native shim pushes events on its own thread,
        so this coroutine just idles and stays cancellable.

        For SAMPLED mode: this coroutine *is* the producer, snapshotting
        NVML utilization at sample_hz and emitting synthetic events.
        """
        self._running = True

        if self.active_mode == KernelTracerMode.CUPTI:
            while self._running:
                await asyncio.sleep(0.5)
            return

        # SAMPLED mode
        period = 1.0 / self.sample_hz
        while self._running:
            util_pct = self.nvml_util_getter() if self.nvml_util_getter else None
            if util_pct is not None and util_pct > 0:
                event = KernelEvent(
                    name="unknown/sampled",
                    start_ts_ms=now_ms(),
                    duration_ms=period * 1000.0,
                    grid_dim=(0, 0, 0),
                    block_dim=(0, 0, 0),
                    source="sampled",
                    stream_id=None,
                )
                result = self.on_event(event)
                if asyncio.iscoroutine(result):
                    await result
            await asyncio.sleep(period)
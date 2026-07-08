



# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.

"""
nvml_poller.py

Owns the NVML connection lifecycle end-to-end:
  - initializes NVML on startup
  - enumerates available devices
  - selects the target GPU (config-driven -> works against a remote/cloud
    box too, as long as NVML is exposed over that same host)
  - runs a fixed-interval polling loop (default ~20-30Hz) pulling
    SM utilization, memory used/total, power draw, temperature, and clock
    speed
  - packages each poll into a lightweight SMState and hands it to a
    callback

This file has NO networking logic of its own (that's ws_publisher.py's
job), which keeps it independently unit-testable: feed it a fake callback,
assert on what it collects, done.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Union

from telemetry_schema import SMState, now_ms

logger = logging.getLogger("telemetry_engine.nvml_poller")

try:
    import pynvml  # provided by the `nvidia-ml-py` package
    NVML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on non-GPU dev machines
    pynvml = None
    NVML_AVAILABLE = False


class NVMLUnavailableError(RuntimeError):
    """Raised when NVML can't be initialized (no driver, no GPU, no bindings)."""


class _TransientSampleError(RuntimeError):
    """Internal: one poll failed (e.g. GPU mid P-state transition). The
    run() loop catches this, logs it, and tries again next tick - it must
    never be allowed to kill the polling task outright."""


SampleCallback = Callable[[SMState], Union[None, Awaitable[None]]]


@dataclass
class DeviceInfo:
    index: int
    name: str
    uuid: str


class NVMLPoller:
    """
    Polls a single GPU's headline counters at a fixed tick rate and hands
    each sample to `on_sample`.

    Usage:
        poller = NVMLPoller(gpu_index=0, poll_hz=25, on_sample=my_callback)
        await poller.start()
        await poller.run()      # runs forever until poller.stop() is called
    """

    def __init__(
        self,
        gpu_index: int = 0,
        poll_hz: float = 25.0,
        on_sample: Optional[SampleCallback] = None,
    ):
        self.gpu_index = gpu_index
        self.poll_hz = poll_hz
        self.on_sample = on_sample
        self._handle = None
        self._running = False
        self._initialized = False

    # -- lifecycle -----------------------------------------------------

    async def start(self) -> None:
        """Initializes NVML and grabs a handle to the target device."""
        if not NVML_AVAILABLE:
            raise NVMLUnavailableError(
                "pynvml is not installed. `pip install nvidia-ml-py`."
            )
        try:
            pynvml.nvmlInit()
            self._initialized = True
        except pynvml.NVMLError as e:
            raise NVMLUnavailableError(f"nvmlInit failed: {e}") from e

        devices = self.enumerate_devices()
        if not devices:
            raise NVMLUnavailableError("NVML reports zero devices.")
        if self.gpu_index >= len(devices):
            raise NVMLUnavailableError(
                f"gpu_index={self.gpu_index} out of range "
                f"(only {len(devices)} device(s) visible)."
            )

        self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)
        info = devices[self.gpu_index]
        logger.info("NVML bound to device %d: %s (%s)", info.index, info.name, info.uuid)

    async def stop(self) -> None:
        self._running = False
        if self._initialized:
            try:
                pynvml.nvmlShutdown()
            except Exception:  # noqa: BLE001 - shutdown is best-effort
                logger.exception("nvmlShutdown raised; ignoring during teardown.")
            self._initialized = False

    @staticmethod
    def enumerate_devices() -> List[DeviceInfo]:
        """Static so callers (e.g. main.py's --list-gpus) can use it without an instance."""
        if not NVML_AVAILABLE:
            return []
        owns_init = False
        try:
            try:
                pynvml.nvmlInit()
                owns_init = True
            except pynvml.NVMLError as e:
                # NVML_ERROR_ALREADY_INITIALIZED means a caller up the stack
                # already has it open - safe to proceed without owning
                # teardown. Any other error (no driver, no permission, etc.)
                # means NVML genuinely isn't usable; bail out cleanly.
                if getattr(e, "value", None) != pynvml.NVML_ERROR_ALREADY_INITIALIZED:
                    logger.debug("nvmlInit failed during enumeration: %s", e)
                    return []

            count = pynvml.nvmlDeviceGetCount()
            out = []
            for i in range(count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(h)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                uuid = pynvml.nvmlDeviceGetUUID(h)
                if isinstance(uuid, bytes):
                    uuid = uuid.decode("utf-8")
                out.append(DeviceInfo(index=i, name=name, uuid=uuid))
            return out
        finally:
            if owns_init:
                try:
                    pynvml.nvmlShutdown()
                except Exception:  # noqa: BLE001
                    pass

    # -- sampling --------------------------------------------------------

    def _sample_once(self) -> SMState:
        """Pulls one snapshot of every counter we care about. Tolerates
        per-field unsupported-on-this-card errors instead of failing the
        whole sample."""
        h = self._handle

        util_pct = self._safe_call(lambda: pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        mem_info = self._safe_call(lambda: pynvml.nvmlDeviceGetMemoryInfo(h))

        if util_pct is None:
            # A transient NVML hiccup (common on laptop GPUs cycling P-states)
            # must not kill the polling loop - surface a zeroed/stale-flagged
            # sample instead of raising, and let run() log it and move on.
            raise _TransientSampleError("nvmlDeviceGetUtilizationRates failed")
        if mem_info is None:
            raise _TransientSampleError("nvmlDeviceGetMemoryInfo failed")

        power_draw = self._safe_call(
            lambda: pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0  # mW -> W
        )
        power_limit = self._safe_call(
            lambda: pynvml.nvmlDeviceGetEnforcedPowerLimit(h) / 1000.0
        )
        temperature = self._safe_call(
            lambda: pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
        )
        clock_sm = self._safe_call(
            lambda: pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)
        )
        clock_mem = self._safe_call(
            lambda: pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM)
        )

        return SMState(
            timestamp_ms=now_ms(),
            gpu_index=self.gpu_index,
            sm_utilization_pct=float(util_pct),
            memory_used_mb=mem_info.used / (1024 * 1024),
            memory_total_mb=mem_info.total / (1024 * 1024),
            power_draw_w=power_draw,
            power_limit_w=power_limit,
            temperature_c=temperature,
            clock_sm_mhz=clock_sm,
            clock_mem_mhz=clock_mem,
        )

    @staticmethod
    def _safe_call(fn):
        try:
            return fn()
        except pynvml.NVMLError:
            return None

    async def run(self) -> None:
        """Fixed-interval polling loop. Runs until `stop()` is called.

        Uses a drift-corrected sleep (target next-tick time rather than a
        flat `sleep(1/hz)`) so a slow poll doesn't compound into visible
        rate decay over a long training run.
        """
        if self._handle is None:
            raise NVMLUnavailableError("start() must be awaited before run().")

        self._running = True
        period = 1.0 / self.poll_hz
        loop = asyncio.get_event_loop()
        next_tick = loop.time()
        consecutive_failures = 0

        while self._running:
            try:
                sample = self._sample_once()
            except _TransientSampleError as e:
                consecutive_failures += 1
                logger.warning(
                    "NVML sample failed (%s); skipping this tick (%d consecutive failure(s)).",
                    e, consecutive_failures,
                )
                if consecutive_failures >= 20:
                    # ~1s+ of continuous failures at typical tick rates means
                    # something is genuinely wrong (GPU reset, driver crash,
                    # cable-pulled eGPU, etc.) rather than a one-off blip -
                    # surface it instead of polling forever into the void.
                    raise NVMLUnavailableError(
                        f"{consecutive_failures} consecutive NVML sample failures; giving up."
                    ) from e
                next_tick += period
                delay = next_tick - loop.time()
                if delay > 0:
                    await asyncio.sleep(delay)
                else:
                    next_tick = loop.time()
                continue

            consecutive_failures = 0

            if self.on_sample is not None:
                result = self.on_sample(sample)
                if asyncio.iscoroutine(result):
                    await result

            next_tick += period
            delay = next_tick - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                # We're behind schedule (slow poll or system hiccup) -
                # resync instead of spinning with zero sleeps.
                next_tick = loop.time()
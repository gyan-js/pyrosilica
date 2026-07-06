# IMPORTANT: all comments in this file are AI-generated for better understanding of the code, and "may" not reflect the original author's intent.

"""
cupti_bridge.py

So this bridge is split into two honest halves:

  1. A ctypes-based *capability probe* (real, robust): can we even dlopen
     libcupti and get a version out of it? This alone is useful signal
     and doesn't depend on struct-layout guessing.

  2. An *event stream* that only activates if a compiled native shim is
     present on the path (env var CUPTI_SHIM_PATH, or a `_cupti_native`
     extension module). That shim is expected to expose the small C ABI
     documented in `NATIVE_SHIM_CONTRACT` below and do the actual
     Activity API plumbing in C, where struct layout is resolved correctly
     by the CUDA toolkit's own headers at compile time instead of being
     guessed at runtime from Python.

If either half fails for any reason, this module raises
CUPTIUnavailableError and kernel_tracer.py swaps in the sampling fallback.
Nothing downstream needs to know which path was taken.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from telemetry_schema import KernelEvent, now_ms

logger = logging.getLogger("telemetry_engine.cupti_bridge")

CUPTI_SUCCESS = 0

# Candidate library names, most to least specific. Real installs vary by
# platform (Linux .so, versioned .so.<major>, Windows .dll).
_LIBCUPTI_CANDIDATES = [
    "libcupti.so",
    "libcupti.so.12",
    "libcupti.so.11",
    "cupti",  # let ctypes.util.find_library try its own search
]

NATIVE_SHIM_CONTRACT = """
Expected C ABI for a compiled CUPTI native shim (build this separately with
the CUDA toolkit's cupti.h so struct layouts are resolved correctly):

    int cupti_shim_init(void);
    // Returns 0 on success. Enables CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL
    // and registers the buffer callbacks internally.

    typedef void (*cupti_shim_event_cb)(
        const char* name,
        double start_ts_ms,
        double duration_ms,
        int grid_x, int grid_y, int grid_z,
        int block_x, int block_y, int block_z,
        int stream_id
    );

    int cupti_shim_start(cupti_shim_event_cb callback);
    // Begins streaming kernel activity records to `callback` from a
    // background thread owned by the shim.

    void cupti_shim_stop(void);
    // Flushes remaining activity buffers and stops the stream.

Compile it as `_cupti_native.so`, place it on LD_LIBRARY_PATH / next to
this file, and CUPTIBridge will pick it up automatically.
"""


class CUPTIUnavailableError(RuntimeError):
    """Raised whenever the real CUPTI path can't be used for any reason.
    kernel_tracer.py catches this specifically and falls back to sampling."""


@dataclass
class CUPTICapability:
    lib_found: bool
    lib_path: Optional[str]
    version: Optional[int]
    native_shim_found: bool


def probe() -> CUPTICapability:
    """
    Cheap, side-effect-free check of whether real CUPTI capture is even
    plausible on this machine. Safe to call speculatively at startup.
    """
    lib_path = None
    for candidate in _LIBCUPTI_CANDIDATES:
        resolved = ctypes.util.find_library(candidate) or candidate
        try:
            ctypes.CDLL(resolved)
            lib_path = resolved
            break
        except OSError:
            continue

    version = None
    if lib_path is not None:
        try:
            lib = ctypes.CDLL(lib_path)
            version_out = ctypes.c_uint32(0)
            # CUptiResult cuptiGetVersion(uint32_t* version)
            rc = lib.cuptiGetVersion(ctypes.byref(version_out))
            if rc == CUPTI_SUCCESS:
                version = version_out.value
        except (OSError, AttributeError) as e:
            logger.debug("cuptiGetVersion probe failed: %s", e)

    native_shim_found = _find_native_shim() is not None

    return CUPTICapability(
        lib_found=lib_path is not None,
        lib_path=lib_path,
        version=version,
        native_shim_found=native_shim_found,
    )


def _find_native_shim() -> Optional[str]:
    """Looks for a compiled shim matching NATIVE_SHIM_CONTRACT, either via
    an explicit env var or sitting next to this file."""
    env_path = os.environ.get("CUPTI_SHIM_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    local_candidate = os.path.join(os.path.dirname(__file__), "_cupti_native.so")
    if os.path.isfile(local_candidate):
        return local_candidate

    return None


# Matches `cupti_shim_event_cb` in NATIVE_SHIM_CONTRACT.
_SHIM_CALLBACK_TYPE = ctypes.CFUNCTYPE(
    None,
    ctypes.c_char_p,
    ctypes.c_double,
    ctypes.c_double,
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int,
)


class CUPTIBridge:
    """
    Real CUPTI event source. Only usable when a native shim (see
    NATIVE_SHIM_CONTRACT) is present - this class does not attempt to
    parse CUPTI activity records directly in Python for the ABI-fragility
    reasons explained at the top of this file.
    """

    def __init__(self, on_event: Callable[[KernelEvent], None]):
        self.on_event = on_event
        self._shim = None
        self._py_callback = None  # keep a reference so ctypes doesn't GC it
        self._started = False

    def start(self) -> None:
        cap = probe()
        if not cap.lib_found:
            raise CUPTIUnavailableError(
                "libcupti not found on this system. Is the CUDA toolkit installed "
                "and is libcupti on LD_LIBRARY_PATH?"
            )
        if not cap.native_shim_found:
            raise CUPTIUnavailableError(
                "libcupti is present, but no compiled native shim was found "
                "(set CUPTI_SHIM_PATH or drop _cupti_native.so next to cupti_bridge.py). "
                "See NATIVE_SHIM_CONTRACT for what to build."
            )

        shim_path = _find_native_shim()
        try:
            self._shim = ctypes.CDLL(shim_path)
            self._shim.cupti_shim_init.restype = ctypes.c_int
            self._shim.cupti_shim_start.argtypes = [_SHIM_CALLBACK_TYPE]
            self._shim.cupti_shim_start.restype = ctypes.c_int

            if self._shim.cupti_shim_init() != 0:
                raise CUPTIUnavailableError("cupti_shim_init() returned non-zero.")

            self._py_callback = _SHIM_CALLBACK_TYPE(self._on_native_event)
            if self._shim.cupti_shim_start(self._py_callback) != 0:
                raise CUPTIUnavailableError("cupti_shim_start() returned non-zero.")

        except (OSError, AttributeError) as e:
            raise CUPTIUnavailableError(f"Failed to load/initialize native shim: {e}") from e

        self._started = True
        logger.info("CUPTIBridge started via native shim at %s", shim_path)

    def stop(self) -> None:
        if self._started and self._shim is not None:
            try:
                self._shim.cupti_shim_stop()
            except Exception:  # noqa: BLE001 - best-effort teardown
                logger.exception("cupti_shim_stop() raised during teardown.")
        self._started = False

    def _on_native_event(
        self, name: bytes, start_ts_ms: float, duration_ms: float,
        gx: int, gy: int, gz: int, bx: int, by: int, bz: int, stream_id: int,
    ) -> None:
        """C-callback trampoline: normalizes the shim's raw args into a
        KernelEvent and forwards it. Kept tiny and exception-safe since
        it runs on a callback path the CUDA driver owns."""
        try:
            event = KernelEvent(
                name=name.decode("utf-8", errors="replace") if name else "unknown",
                start_ts_ms=float(start_ts_ms),
                duration_ms=float(duration_ms),
                grid_dim=(gx, gy, gz),
                block_dim=(bx, by, bz),
                source="cupti",
                stream_id=stream_id,
            )
            self.on_event(event)
        except Exception:  # noqa: BLE001 - never let a callback throw into C
            logger.exception("Error handling native CUPTI event; dropping this event.")
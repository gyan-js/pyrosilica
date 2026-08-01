# Pyrosilica — Architecture

This document describes the system as actually built and running, not the original planning document. Where the implementation diverged from the initial roadmap, that divergence is called out explicitly — most notably around per-SM telemetry granularity and model onboarding.

---

## 1. System Overview

Pyrosilica renders a live 3D visualization of a GPU while a real PyTorch training run executes on it. The system is a local, single-machine tool: telemetry engine, training harness, stream server, and frontend all run on the same host as the GPU being visualized. There is no hosted multi-tenant mode — running Pyrosilica means cloning the repo and running it against your own hardware.

```
[PyTorch Training Script]  (user-provided, matches load_model()/get_dataloader() contract)
        │  forward/backward hooks
        ▼
[Training Harness]  (Python)
        │  layer execution events
        ▼
[Telemetry Engine]  (Python) ◄──── NVML / CUPTI ◄──── [Physical GPU]
        │  TelemetryFrame (JSON), via ws_publisher.py
        ▼
[Stream Server]  (Node.js, WebSocket)
        │  validated, rebroadcast frames
        ▼
[React Frontend]  (Three.js scene, panels, timeline)
```

---

## 2. Data Flow, End to End

1. **`nvml_poller.py`** polls the GPU directly via NVML at a fixed tick rate, producing whole-device aggregate readings: SM utilization %, memory used/total, bandwidth, temperature, power draw, clock speed.
2. **`telemetry_schema.py`** is the canonical frame shape. Every frame sent over the wire matches this exactly:
   ```
   TelemetryFrame {
     schema_version: int
     timestamp: float
     gpu: {
       sm_utilization: float (0-100)
       memory: { used_mb, total_mb, bandwidth_gbps }
       temperature_c: float
       power_draw_w: float
       clock_mhz: float
     }
     kernels: [{ name, duration_us, grid_dim, block_dim }]
     process_memory: [{ pid, used_mb }]
   }
   ```
3. **`ws_publisher.py`** holds a persistent WebSocket connection to the stream server's `/ingest` endpoint, batching and sending frames at `batch_hz` (default 30/sec), with bounded buffering and exponential-backoff reconnection if the connection drops.
4. **`server.js`** (stream-server) receives frames on `/ingest`, validates them against **`frameSchema.js`** (Ajv), and — if valid — pushes them into a ring buffer (`frameBuffer.js`) and rebroadcasts to every client connected on `/telemetry`.
5. **`wsClient.js`** (frontend) connects to `/telemetry`, unwraps the server's message envelope (`{type: 'frame', frame}` vs `{type: 'backfill', frames: [...]}`), and hands the raw frame to the Zustand store.
6. **`telemetryStore.js`** ingests the frame, synthesizes per-SM values from the single real `gpu.sm_utilization` number (see §4), and exposes it to every component via `getSmUtilization(smId)`, `getPowerDrawW()`, `getBandwidthGbps()`, etc.
7. React components (`GPUDieScene.jsx`, `SMNode.jsx`, panels) re-render on every store update.

The training-harness side feeds into the same pipe rather than a separate one: layer-execution events captured by `event_hooks.py` are merged into the same outgoing `TelemetryFrame` stream, so the frontend's compute graph highlighting and the GPU die visualization stay frame-synced by construction — they're riding the same socket.

---

## 3. Schema Enforcement

Three independent representations of the frame shape exist and must be kept in lockstep:

| Layer | File | Role |
|---|---|---|
| Python (producer) | `telemetry-engine/src/telemetry_schema.py` | Source dataclasses, `.to_json()` |
| Node (gatekeeper) | `stream-server/src/schemas/frameSchema.js` | Ajv validator — the actual enforced contract; invalid frames are silently dropped with a log line |
| JS (reference) | `shared-schemas/telemetry-types.js` | JSDoc typedefs mirroring the above, no runtime effect, exists to catch drift at edit-time |

**Node's `frameSchema.js` is the canonical contract** — it's the one with actual runtime enforcement. Python and the shared-schemas typedefs must match it, not the other way around. Earlier in development these three drifted independently (different field names, `sm_state` vs `gpu`, `duration_ms` vs `duration_us`, string vs integer schema version) and every frame was being silently rejected at `/ingest` with no visible error beyond a server console log. This class of bug is why `shared-schemas/telemetry-types.js` exists — check it before changing any frame field, in any of the three files.

---

## 4. Known Divergence: Per-SM Granularity

The original design intent (see `SMNode.jsx`, individually addressable SM units) was for each of the GPU's SMs to reflect real, independent utilization data. This is not what NVML provides.

**NVML exposes one whole-device `sm_utilization` value, not per-SM breakdowns.** True per-SM occupancy requires CUPTI-level profiling (`cupti_bridge.py`), which is high-difficulty and, as of this writing, not the data source driving the visual.

**Current behavior:** `telemetryStore.js`'s `ingestFrame()` synthesizes a per-SM spread from the single real aggregate value, using deterministic jitter seeded by SM index and timestamp:

```js
function synthesizeSmStates(baseUtilPct, smCount, timestamp) {
  // deterministic per-SM jitter around the real aggregate value —
  // grounded in a real number, not fabricated from nothing, but
  // not true per-SM telemetry either
}
```

This means: the GPU die's *overall* brightness/activity level is real and accurate. The *specific pattern* of which individual SMs appear brighter than others is synthetic, not measured. This should be stated plainly in any demo or documentation aimed at technical viewers (NVIDIA/AMD engineers will notice), rather than implied to be true per-SM telemetry. Closing this gap requires `cupti_bridge.py` to actually ship.

---

## 5. How a User's Model Gets Trained

There is no upload mechanism, and none is planned — hosting arbitrary user-submitted code execution against a shared GPU is a materially different, much larger project (sandboxing, compute provisioning, abuse handling) and is explicitly out of scope.

Instead, a user's PyTorch script is adapted to a fixed two-function contract:

```python
# training-harness/models/their_script.py
def load_model():
    return TheirModel()          # any nn.Module

def get_dataloader():
    return TheirDataLoader()     # any torch DataLoader
```

`model_loader.py` calls these two functions generically — it never needs to know what the model actually is. `graph_extractor.py` walks the returned module with `torch.fx` at load time to build the static compute graph (sent to the frontend once, before training starts, so `ModelGraphPanel.jsx` has nodes to highlight against). `event_hooks.py` attaches forward/backward hooks the same generic way, regardless of the specific architecture.

**Full local usage path:**
```bash
git clone https://github.com/<you>/pyrosilica.git
cd pyrosilica

cd telemetry-engine -> pip install -r requirements.txt
cd stream-server -> npm install 
cd frontend -> npm install 

--------------------------------------------------------------------------------------------------------
node stream-server/server.js   # terminal 1

python telemetry-engine/main.py --gpu-index 0 --tick-rate 25 --kernel-mode auto --output-mode live --ws-uri ws://localhost:8080/ingest         # terminal 2

cd frontend -> npm run dev         # terminal 3

python training-harness/main.py --model big_cnn --device cuda --batch-size 64 --epochs 1 --max-steps 200 --output-mode live --stream-server ws://localhost:8080/ingest   # terminal 4
```

A physical NVIDIA GPU with drivers installed is a hard requirement for the live-data path — without one, only replay mode (pre-recorded `.ndjson` runs via `replayLoader.js`) is usable.

---

## 6. Replay Mode ( ! BUILD IN PROGRESS ! )

`server.js` treats live ingest and replay as mutually exclusive on purpose — exactly one active source at a time, enforced at the `/ingest` upgrade handshake (a live publisher connecting while a replay is active gets refused with `409 Conflict`, and `startReplay()` refuses to start if a live publisher is already connected).

Replay frames are pushed through the exact same `relayFrame()` fan-out used for live frames, so the frontend cannot distinguish a replayed run from a live one at the code level — both arrive as `{type: 'frame', frame}` over `/telemetry`. This was a deliberate design principle from the original roadmap and held up through implementation: recorded and live runs render through identical code paths.

Playback is controlled via a command channel on the same `/telemetry` socket (`replay:start`, `replay:pause`, `replay:play`, `replay:seek`, `replay:speed`), handled by `handleTelemetryCommand()` in `server.js`.

---

## 7. Directory Structure (as built)

```
pyrosilica/
├── packages/
│   ├── telemetry-engine/       Python — NVML polling, kernel capture, frame assembly
│   ├── training-harness/       Python — user model wrapping, hook-based event capture
│   ├── stream-server/          Node.js — WebSocket relay, validation, replay, ring buffer
│   ├── frontend/           React + Three.js — 3D scene, panels, telemetry store
│   └── shared-schemas/         JSDoc typedefs mirroring frameSchema.js
├── docs/
│   └── architecture.md         This file
├── scripts/
│   └── record_run.sh  (BUID IN PROGRESS)
├── package.json                npm workspaces root
└── README.md
```

---

## 8. Open Items / Honest Limitations

- **Per-SM data is synthesized, not measured** (§4) — the single largest gap between what the visualization implies and what's actually being read off the hardware.
- **Tensor-core-specific activity is not distinguished from general ALU activity** — both currently drive the same utilization signal.
- **CUPTI kernel capture** (`cupti_bridge.py`) — the roadmap's designated high-fidelity kernel-launch source — should be verified as actually active vs. the lower-fidelity sampling fallback described in the original spec.
- **No hosted/multi-user mode** (§5) — by design, not an oversight. Any future "try it without cloning" version is a separate, larger project (sandboxed execution, provisioned GPU access) and not an extension of the current architecture.
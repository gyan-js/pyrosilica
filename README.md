<div align="center">

# Pyrosilica

**A live 3D visualization of a GPU while it trains.**

SM activity, memory bandwidth, kernel execution, and training loss — rendered in sync with what's actually happening on the hardware, not a canned animation.

<br/>

![status](https://img.shields.io/badge/status-active-brightgreen?style=flat-square)
![python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![node](https://img.shields.io/badge/node-18+-339933?style=flat-square&logo=node.js&logoColor=white)
![react](https://img.shields.io/badge/react-19-61DAFB?style=flat-square&logo=react&logoColor=black)
![three.js](https://img.shields.io/badge/three.js-black?style=flat-square&logo=three.js&logoColor=white)
![pytorch](https://img.shields.io/badge/pytorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)
<br/>
![license](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)
![platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey?style=flat-square)
![gpu](https://img.shields.io/badge/requires-NVIDIA%20GPU-76B900?style=flat-square&logo=nvidia&logoColor=white)
![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)

</div>

---

## What this is

Most GPU monitoring tools give you a number on a dashboard. Pyrosilica gives you a chip — every SM rendered, lighting up in near-real time as your model trains, with the kernel timeline, memory bandwidth, and training loss all moving in sync underneath it.

It's built on real telemetry, not a canned animation: `nvml_poller.py` reads directly off your GPU via NVML, streams it through a WebSocket relay, and a Three.js scene renders it live. Point it at any PyTorch training script and watch the hardware work.

## Why

Most visualizers stop at "GPU util: 84%." That number doesn't tell you *where* the work is happening, *when* memory bandwidth spikes relative to compute, or *what* a training step actually looks like as it moves through a model's layers. Pyrosilica exists to make that legible — partly as a systems/graphics exercise, partly because I wanted to actually *see* what I'd previously only read as a number in `nvidia-smi`.

## Architecture

```
[PyTorch training script]
        │  forward/backward hooks
        ▼
[training-harness]  ──── layer execution events ────┐
                                                      ▼
[telemetry-engine]  ◄── NVML/CUPTI ◄── [GPU]   [merged TelemetryFrame]
        │
        ▼  WebSocket
[stream-server]  ── validates, relays, buffers ──▶  [viz-frontend]
                                                      React + Three.js
```

Five packages, one npm workspace:

| Package | Role |
|---|---|
| `telemetry-engine/` | Python — polls NVML/CUPTI, assembles frames |
| `training-harness/` | Python — wraps a user's PyTorch model, captures layer events via hooks |
| `stream-server/` | Node.js — validates and relays frames over WebSocket, handles replay |
| `viz-frontend/` | React + Three.js — the actual 3D scene, panels, kernel timeline |
| `shared-schemas/` | JSDoc typedefs keeping the frame contract honest across languages |

Full write-up: [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
git clone https://github.com/<you>/pyrosilica.git
cd pyrosilica

cd telemetry-engine -> pip install -r requirements.txt
cd stream-server -> npm install 
cd frontend -> npm install 
```

Wrap your training script to expose two functions:

```python
# training-harness/models/my_model.py
def load_model():
    return MyModel()          # any nn.Module

def get_dataloader():
    return MyDataLoader()     # any torch DataLoader
```

Then run it:

```bash

node stream-server/server.js   # terminal 1

python telemetry-engine/main.py --gpu-index 0 --tick-rate 25 --kernel-mode auto --output-mode live --ws-uri ws://localhost:8080/ingest         # terminal 2

cd frontend -> npm run dev         # terminal 3

python training-harness/main.py --model big_cnn --device cuda --batch-size 64 --epochs 1 --max-steps 200 --output-mode live --stream-server ws://localhost:8080/ingest   # terminal 4


```

Open `localhost:5173`. Watch your training run.

**Requires:** an NVIDIA GPU with drivers + NVML available.


## Honest limitations

Worth stating plainly rather than letting the visual imply more than it delivers:

- **Per-SM activity is synthesized, not measured.** NVML exposes one whole-device utilization number, not true per-SM occupancy — that requires CUPTI-level profiling. The per-SM spread you see is real data with deterministic variation layered on top, not 128 independently measured values. Full explanation in the architecture doc.
- **Local-only, single-user.** This runs on your own machine against your own GPU. There's no hosted upload — running arbitrary user code against shared GPU infrastructure is a different, much larger project than this one.
- **Tensor-core vs. general ALU activity isn't currently distinguished** — both drive the same signal for now.

## Stack

React 19 · Three.js · Zustand · Node.js · WebSocket (`ws`) · Python · NVML · CUPTI · PyTorch (`torch.fx` for graph extraction)

## Roadmap

See [`docs/architecture.md`](docs/architecture.md#8-open-items--honest-limitations) for what's built vs. what's next — CUPTI-based true per-SM data being the highest-value remaining piece.

## License

Apache 2.0
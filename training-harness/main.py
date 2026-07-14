from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from event_schema import TrainingEvent
from graph_extractor import GraphExtractor, build_module_id_map
from model_loader import list_presets, load_model
from run_recorder import RunRecorder
from training_loop import run_training

try:
    import websockets
    _WEBSOCKETS_AVAILABLE = True
except ImportError:
    _WEBSOCKETS_AVAILABLE = False


def _dummy_mnist_loader(batch_size: int = 32, num_batches: int = 50) -> DataLoader:
    """Synthetic MNIST-shaped data — enough to demo the pipeline without
    downloading a real dataset. Swap for a real DataLoader when this is
    wired into an actual run."""
    x = torch.randn(batch_size * num_batches, 1, 28, 28)
    y = torch.randint(0, 10, (batch_size * num_batches,))
    return DataLoader(TensorDataset(x, y), batch_size=batch_size)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Pyrosilica training-harness CLI")
    p.add_argument("--model", required=True, help=f"preset ({', '.join(list_presets())}) or path to a script")
    p.add_argument("--device", default="cuda")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--output-mode", choices=["live", "record", "both"], default="record")
    p.add_argument("--record-path", default="runs/latest.jsonl")
    p.add_argument("--stream-server", default="ws://localhost:8080/ingest",
                    help="stream-server /ingest URL, used when --output-mode is live or both")
    p.add_argument("--dump-graph", default=None, help="optional path to dump extracted model graph JSON")
    return p


def _make_ws_emitter(url: str):
    """Returns an emit() callable that fans training events out over a raw
    websocket to stream-server's /ingest — same idea as ws_publisher.py's
    live push for telemetry frames, just a different payload shape."""
    if not _WEBSOCKETS_AVAILABLE:
        raise RuntimeError("websockets package not installed — pip install websockets")

    loop = asyncio.new_event_loop()
    ws_holder: dict[str, object] = {}
    loop.run_until_complete(_connect_ws(url, ws_holder))

    def _emit(event: TrainingEvent) -> None:
        loop.run_until_complete(ws_holder["ws"].send(json.dumps(event.to_dict())))

    return _emit


async def _connect_ws(url: str, holder: dict) -> None:
    holder["ws"] = await websockets.connect(url)


def main() -> None:
    args = build_arg_parser().parse_args()

    model = load_model(args.model, device=args.device)

    extractor = GraphExtractor(model)
    graph_nodes = extractor.extract()
    node_ids = build_module_id_map(model)
    print(f"[main] extracted {len(graph_nodes)} graph nodes via {extractor.strategy}", file=sys.stderr)
    print(f"[main] {len(node_ids)} modules hookable for live events", file=sys.stderr)

    if args.dump_graph:
        Path(args.dump_graph).parent.mkdir(parents=True, exist_ok=True)
        Path(args.dump_graph).write_text(json.dumps(extractor.to_json(), indent=2))
        print(f"[main] graph written to {args.dump_graph}", file=sys.stderr)

    recorder: RunRecorder | None = None
    emit_fns = []

    if args.output_mode in ("record", "both"):
        recorder = RunRecorder(args.record_path)
        emit_fns.append(recorder.record_training_event)

    if args.output_mode in ("live", "both"):
        emit_fns.append(_make_ws_emitter(args.stream_server))

    def emit(event: TrainingEvent) -> None:
        for fn in emit_fns:
            fn(event)

    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    dataloader = _dummy_mnist_loader(batch_size=args.batch_size)

    run_training(
        model=model,
        dataloader=dataloader,
        optimizer=optimizer,
        loss_fn=loss_fn,
        node_ids=node_ids,
        emit=emit,
        device=args.device,
        epochs=args.epochs,
        max_steps=args.max_steps,
    )

    if recorder is not None:
        asyncio.run(recorder.stop())

    print("[main] run complete", file=sys.stderr)


if __name__ == "__main__":
    main()
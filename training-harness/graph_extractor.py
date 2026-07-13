
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import torch.nn as nn

try:
    import torch.fx as fx
    _FX_AVAILABLE = True
except ImportError:
    _FX_AVAILABLE = False


GRAPH_SCHEMA_VERSION = "1.0.0"


@dataclass
class GraphNode:
    id: str                      
    name: str                  
    op_type: str                
    parent_id: Optional[str]
    children: list[str] = field(default_factory=list)
    param_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def _stable_id(qualified_name: str) -> str:
    return qualified_name.replace(".", "/") if qualified_name else "root"


def _count_params(module: nn.Module) -> int:
    return sum(p.numel() for p in module.parameters(recurse=False))


def build_module_id_map(model: nn.Module) -> dict[str, str]:
    return {name: _stable_id(name) for name, _ in model.named_modules() if name != ""}


def _extract_via_modules(model: nn.Module) -> dict[str, GraphNode]:
    nodes: dict[str, GraphNode] = {
        "root": GraphNode(id="root", name=model.__class__.__name__, op_type="Module", parent_id=None)
    }

    for qualified_name, module in model.named_modules():
        if qualified_name == "":
            continue
        node_id = _stable_id(qualified_name)
        parent_qualified = qualified_name.rsplit(".", 1)[0] if "." in qualified_name else ""
        parent_id = _stable_id(parent_qualified) if parent_qualified else "root"

        nodes[node_id] = GraphNode(
            id=node_id,
            name=qualified_name.rsplit(".", 1)[-1],
            op_type=module.__class__.__name__,
            parent_id=parent_id,
            param_count=_count_params(module),
        )
        nodes[parent_id].children.append(node_id)

    return nodes


def _extract_via_fx(model: nn.Module) -> dict[str, GraphNode]:
    traced = fx.symbolic_trace(model)
    nodes: dict[str, GraphNode] = {
        "root": GraphNode(id="root", name=model.__class__.__name__, op_type="Module", parent_id=None)
    }
    module_map = dict(model.named_modules())

    for fx_node in traced.graph.nodes:
        node_id = _stable_id(fx_node.name)
        submodule = module_map.get(fx_node.target) if fx_node.op == "call_module" else None

        nodes[node_id] = GraphNode(
            id=node_id,
            name=fx_node.name,
            op_type=submodule.__class__.__name__ if submodule else fx_node.op,
            parent_id="root",
            param_count=_count_params(submodule) if submodule else 0,
            extra={"fx_op": fx_node.op, "fx_target": str(fx_node.target)},
        )
        nodes["root"].children.append(node_id)

    return nodes


class GraphExtractor:
    def __init__(self, model: nn.Module):
        self.model = model
        self.strategy: str = "module_hooks"
        self.nodes: dict[str, GraphNode] = {}

    def extract(self) -> dict[str, GraphNode]:
        if _FX_AVAILABLE:
            try:
                self.nodes = _extract_via_fx(self.model)
                self.strategy = "torch.fx"
                return self.nodes
            except Exception as exc:
                print(f"[graph_extractor] fx trace failed ({exc}); falling back to module-hook traversal")

        self.nodes = _extract_via_modules(self.model)
        self.strategy = "module_hooks"
        return self.nodes

    def to_json(self) -> dict[str, Any]:
        if not self.nodes:
            self.extract()
        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "strategy": self.strategy,
            "nodes": {nid: vars(n) for nid, n in self.nodes.items()},
        }


def export_graph(model: nn.Module) -> dict[str, Any]:
    return GraphExtractor(model).to_json()
    








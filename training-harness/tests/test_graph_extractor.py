

from __future__ import annotations

from graph_extractor import GraphExtractor, build_module_id_map


def test_build_module_id_map_excludes_root_and_uses_slash_ids(tiny_mlp):
    id_map = build_module_id_map(tiny_mlp)
    assert "" not in id_map
    assert id_map["net"] == "net"
    assert id_map["net.0"] == "net/0"


def test_module_tree_every_node_has_a_valid_parent(tiny_nested_cnn):
    extractor = GraphExtractor(tiny_nested_cnn)
    nodes = extractor.extract()

    for node_id, node in nodes.items():
        if node_id == "root":
            assert node.parent_id is None
            continue
        assert node.parent_id in nodes, f"{node_id} has parent_id {node.parent_id!r} which doesn't exist"
        assert node_id in nodes[node.parent_id].children, (
            f"{node_id} is not listed in its parent {node.parent_id}'s children"
        )


def test_module_tree_nesting_is_correct(tiny_nested_cnn):

    extractor = GraphExtractor(tiny_nested_cnn)
    nodes = extractor.extract()

    assert nodes["features"].parent_id == "root"
    assert nodes["features/0"].parent_id == "features"
    assert nodes["classifier"].parent_id == "root"
    assert "features/0" in nodes["features"].children


def test_graph_ids_are_a_superset_of_hookable_module_ids(tiny_nested_cnn):
   
    extractor = GraphExtractor(tiny_nested_cnn)
    graph_nodes = extractor.extract()
    hookable_ids = set(build_module_id_map(tiny_nested_cnn).values())

    missing = hookable_ids - set(graph_nodes.keys())
    assert not missing, f"hookable module ids missing from the graph: {missing}"


def test_container_module_has_its_own_node_not_flattened(tiny_nested_cnn):
   
    extractor = GraphExtractor(tiny_nested_cnn)
    nodes = extractor.extract()

    assert "features" in nodes
    assert nodes["features"].op_type == "Sequential"
    assert "classifier" in nodes
    assert nodes["classifier"].op_type == "Sequential"


def test_fx_strategy_used_when_available(tiny_mlp):
    extractor = GraphExtractor(tiny_mlp)
    extractor.extract()
    assert extractor.strategy == "torch.fx"


def test_module_fallback_produces_same_id_contract(tiny_nested_cnn, monkeypatch):

    import graph_extractor

    def _boom(model):
        raise RuntimeError("simulated fx failure")

    monkeypatch.setattr(graph_extractor.fx, "symbolic_trace", _boom)

    extractor = GraphExtractor(tiny_nested_cnn)
    nodes = extractor.extract()

    assert extractor.strategy == "module_hooks"
    hookable_ids = set(build_module_id_map(tiny_nested_cnn).values())
    assert hookable_ids.issubset(set(nodes.keys()))


def test_shared_module_reuse_does_not_duplicate_children(shared_module_model):
    extractor = GraphExtractor(shared_module_model)
    nodes = extractor.extract()

    root_children = nodes["root"].children
    assert root_children.count("act") == 1, f"'act' appears {root_children.count('act')} times in root.children"
    assert nodes["act"].extra.get("fx_call_sites"), "expected fx_call_sites to record both call sites"
    assert len(nodes["act"].extra["fx_call_sites"]) == 2


def test_to_json_shape(tiny_mlp):
    payload = GraphExtractor(tiny_mlp).to_json()
    assert payload["schema_version"] == "1.0.0"
    assert payload["strategy"] in ("torch.fx", "module_hooks")
    assert "root" in payload["nodes"]
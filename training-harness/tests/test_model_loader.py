

from __future__ import annotations

import torch.nn as nn

from model_loader import ModelLoadError, list_presets, load_model


def test_presets_load_on_cpu():
    for preset_name in list_presets():
        model = load_model(preset_name, device="cpu")
        assert isinstance(model, nn.Module)
        assert next(model.parameters()).device.type == "cpu"


def test_load_from_script_with_get_model(tmp_path):
    script = tmp_path / "custom_model.py"
    script.write_text(
        "import torch.nn as nn\n"
        "def get_model():\n"
        "    return nn.Linear(4, 2)\n"
    )
    model = load_model(str(script), device="cpu")
    assert isinstance(model, nn.Linear)


def test_load_from_script_get_model_wrong_return_type_raises(tmp_path):
    script = tmp_path / "bad_get_model.py"
    script.write_text(
        "def get_model():\n"
        "    return 'not a module'\n"
    )
    try:
        load_model(str(script), device="cpu")
        assert False, "expected ModelLoadError"
    except ModelLoadError as exc:
        assert "get_model()" in str(exc)


def test_load_from_script_single_subclass(tmp_path):
    script = tmp_path / "single_subclass.py"
    script.write_text(
        "import torch.nn as nn\n"
        "class MyModel(nn.Module):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self.fc = nn.Linear(4, 2)\n"
        "    def forward(self, x):\n"
        "        return self.fc(x)\n"
    )
    model = load_model(str(script), device="cpu")
    assert model.__class__.__name__ == "MyModel"


def test_load_from_script_no_subclass_raises(tmp_path):
    script = tmp_path / "no_model.py"
    script.write_text("x = 1\n")
    try:
        load_model(str(script), device="cpu")
        assert False, "expected ModelLoadError"
    except ModelLoadError as exc:
        assert "defines no" in str(exc)


def test_load_from_script_multiple_subclasses_raises(tmp_path):
    script = tmp_path / "ambiguous.py"
    script.write_text(
        "import torch.nn as nn\n"
        "class ModelA(nn.Module):\n"
        "    def forward(self, x): return x\n"
        "class ModelB(nn.Module):\n"
        "    def forward(self, x): return x\n"
    )
    try:
        load_model(str(script), device="cpu")
        assert False, "expected ModelLoadError"
    except ModelLoadError as exc:
        assert "ModelA" in str(exc) and "ModelB" in str(exc)


def test_load_from_nonexistent_script_raises(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    try:
        load_model(str(missing), device="cpu")
        assert False, "expected ModelLoadError"
    except ModelLoadError as exc:
        assert "not found" in str(exc)


def test_cuda_requested_but_unavailable_falls_back_to_cpu(monkeypatch, capsys):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    model = load_model("mnist_mlp", device="cuda")
    assert next(model.parameters()).device.type == "cpu"

    captured = capsys.readouterr()
    assert "falling back to CPU" in captured.err    
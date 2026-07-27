
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Callable

import torch
import torch.nn as nn



class MNIST_MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(28 * 28, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.net(x)


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 7 * 7, 128),
            nn.ReLU(),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


class BigCNN(nn.Module):
   

    def __init__(self, num_classes: int = 10):
        super().__init__()

        def block(in_ch, out_ch, num_convs=2):
            layers = []
            for i in range(num_convs):
                layers += [
                    nn.Conv2d(in_ch if i == 0 else out_ch, out_ch, 3, padding=1),
                    nn.BatchNorm2d(out_ch),
                   
                    nn.ReLU(inplace=False),
                ]
            layers.append(nn.MaxPool2d(2))
            return nn.Sequential(*layers)

        self.features = nn.Sequential(
            block(3, 64),
            block(64, 128),
            block(128, 256),
            block(256, 512),
            block(512, 512),
        )
        # 128x128 input / 2^5 (five pools) = 4x4 spatial at the end.
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(512 * 4 * 4, 1024),
            nn.ReLU(inplace=False),
            nn.Dropout(0.5),
            nn.Linear(1024, num_classes),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


PRESETS: dict[str, Callable[[], nn.Module]] = {
    "mnist_mlp": MNIST_MLP,
    "tiny_cnn": TinyCNN,
    "big_cnn": BigCNN,
}

INPUT_SHAPES: dict[str, tuple[int, int, int]] = {
    "mnist_mlp": (1, 28, 28),
    "tiny_cnn": (1, 28, 28),
    "big_cnn": (3, 128, 128),
}
DEFAULT_INPUT_SHAPE: tuple[int, int, int] = (1, 28, 28)


def get_input_shape(model_ref: str) -> tuple[int, int, int]:
  
    return INPUT_SHAPES.get(model_ref, DEFAULT_INPUT_SHAPE)


class ModelLoadError(RuntimeError):
    pass


def _load_from_script(script_path: Path) -> nn.Module:
   
    if not script_path.exists():
        raise ModelLoadError(f"model script not found: {script_path}")

    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        raise ModelLoadError(f"could not import {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    if hasattr(module, "get_model") and callable(module.get_model):
        model = module.get_model()
        if not isinstance(model, nn.Module):
            raise ModelLoadError(f"{script_path}:get_model() did not return an nn.Module")
        return model

    candidates = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, nn.Module) and obj.__module__ == module.__name__
    ]
    if len(candidates) == 1:
        return candidates[0]()
    if not candidates:
        raise ModelLoadError(f"{script_path} defines no nn.Module subclass and no get_model()")
    raise ModelLoadError(
        f"{script_path} defines {len(candidates)} nn.Module subclasses — "
        f"add a get_model() to disambiguate: {[c.__name__ for c in candidates]}"
    )


def load_model(model_ref: str, device: str = "cuda") -> nn.Module:
    """model_ref: a preset key (see PRESETS) or a filesystem path to a script."""
    if model_ref in PRESETS:
        model = PRESETS[model_ref]()
    else:
        model = _load_from_script(Path(model_ref))

    resolved_device = device if (device.startswith("cpu") or torch.cuda.is_available()) else "cpu"
    if device.startswith("cuda") and resolved_device == "cpu":
        print("[model_loader] CUDA requested but unavailable — falling back to CPU", file=sys.stderr)

    return model.to(resolved_device)


def list_presets() -> list[str]:
    return list(PRESETS.keys())
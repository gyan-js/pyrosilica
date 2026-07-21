from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch
import torch.nn as  nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

class TinyMLP(nn.Module):

 
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 8),
            nn.ReLU(),
            nn.Linear(8, 3),
        )
 
    def forward(self, x):
        return self.net(x)
 
 
class TinyNestedCNN(nn.Module):
    
 
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 2, 3, padding=1),
            nn.ReLU(),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(2 * 4 * 4, 3),
        )
 
    def forward(self, x):
        return self.classifier(self.features(x))
 
 
class SharedModuleModel(nn.Module):
  
 
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(4, 4)
        self.fc2 = nn.Linear(4, 4)
        self.act = nn.ReLU()
 
    def forward(self, x):
        x = self.act(self.fc1(x))
        return self.act(self.fc2(x))
 
 
@pytest.fixture
def tiny_mlp() -> nn.Module:
    return TinyMLP()
 
 
@pytest.fixture
def tiny_nested_cnn() -> nn.Module:
    return TinyNestedCNN()
 
 
@pytest.fixture
def shared_module_model() -> nn.Module:
    return SharedModuleModel()
 
 
@pytest.fixture
def tiny_mlp_dataloader() -> DataLoader:
    x = torch.randn(16, 4)
    y = torch.randint(0, 3, (16,))
    return DataLoader(TensorDataset(x, y), batch_size=4)
 
 
@pytest.fixture
def tiny_cnn_dataloader() -> DataLoader:
    x = torch.randn(8, 1, 4, 4)
    y = torch.randint(0, 3, (8,))
    return DataLoader(TensorDataset(x, y), batch_size=4)

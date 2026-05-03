from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .datasets import build_dataset
from .model import SimpleClassifier


@dataclass
class LocalTrainingMetrics:
    loss: float
    accuracy: float
    samples: int


def build_client_dataset(
    experiment_id: str,
    client_id: str,
    samples: int = 128,
    dataset_type: Literal["synthetic", "mnist", "cifar10"] = "synthetic",
    data_dir: str = "./data",
) -> TensorDataset:
    """
    Build a dataset for a client. Delegates to datasets module.

    Args:
        experiment_id: Experiment ID for seeding (synthetic) or dataset info
        client_id: Client identifier
        samples: Number of samples
        dataset_type: Type of dataset
        data_dir: Directory for cached datasets

    Returns:
        The client's dataset
    """
    return build_dataset(dataset_type, experiment_id, client_id, samples, data_dir)


def train_local_model(
    initial_state: dict,
    dataset,
    epochs: int = 1,
    learning_rate: float = 0.01,
    batch_size: int = 32,
    hidden_dim: int = 16,
    input_dim: int = 2,
    device: str = "cpu",
) -> Tuple[dict, LocalTrainingMetrics]:
    """
    Train a local model on the client's dataset.

    Args:
        initial_state: Initial model state dict
        dataset: PyTorch Dataset
        epochs: Number of training epochs
        learning_rate: Learning rate for optimizer
        batch_size: Batch size
        hidden_dim: Hidden dimension of the model
        input_dim: Input feature dimension (2 for synthetic, 784 for MNIST, 3*32*32 for CIFAR-10)
        device: Device (cpu or cuda)

    Returns:
        Tuple of (updated_state_dict, LocalTrainingMetrics)
    """
    model = SimpleClassifier(input_dim=input_dim, hidden_dim=hidden_dim)
    model.load_state_dict(initial_state)
    model.to(device)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.BCEWithLogitsLoss()
    loader = DataLoader(dataset, batch_size=min(batch_size, len(dataset)), shuffle=True)

    last_loss = 0.0
    total_correct = 0
    total_seen = 0
    for _ in range(max(1, epochs)):
        for batch in loader:
            # Handle both (features, labels) and single-item tuples
            if isinstance(batch, (list, tuple)) and len(batch) == 2:
                features, labels = batch
            else:
                features = batch
                labels = batch  # Fallback

            features = features.to(device).float()
            labels = labels.to(device).float()

            # Flatten features if needed (for image datasets)
            if features.dim() > 2:
                features = features.view(features.size(0), -1)

            optimizer.zero_grad()
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            last_loss = float(loss.item())
            predictions = (torch.sigmoid(logits) >= 0.5).float()
            total_correct += int((predictions == labels).sum().item())
            total_seen += int(labels.numel())

    accuracy = total_correct / total_seen if total_seen else 0.0
    return model.state_dict(), LocalTrainingMetrics(loss=last_loss, accuracy=accuracy, samples=len(dataset))





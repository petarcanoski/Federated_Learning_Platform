"""Dataset loading utilities for federated learning.

Legacy support remains for synthetic data, MNIST, and CIFAR-10, while the new
registry-based API exposes deterministic disease datasets such as sepsis for
hospital-scoped research simulations.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import torch
import torchvision.transforms as transforms
from torch.utils.data import TensorDataset, Subset
from torchvision import datasets


SEPSIS_FEATURES = [
    "age",
    "temperature",
    "heart_rate",
    "respiratory_rate",
    "wbc",
    "blood_pressure",
]
SEPSIS_HOSPITALS = ["Ohrid", "Bitola", "Skopje"]


@dataclass(frozen=True)
class DiseaseDatasetSpec:
    disease_type: str
    feature_names: list[str]
    hospital_order: list[str]
    default_patients: int
    input_dim: int
    default_hidden_dim: int


DATASET_REGISTRY: dict[str, DiseaseDatasetSpec] = {
    "sepsis": DiseaseDatasetSpec(
        disease_type="sepsis",
        feature_names=SEPSIS_FEATURES,
        hospital_order=SEPSIS_HOSPITALS,
        default_patients=900,
        input_dim=len(SEPSIS_FEATURES),
        default_hidden_dim=24,
    ),
}


def stable_seed(*parts: str) -> int:
    """Generate a stable seed from string parts."""
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**31)


def get_disease_spec(disease_type: str) -> DiseaseDatasetSpec:
    key = disease_type.lower().strip()
    if key not in DATASET_REGISTRY:
        raise ValueError(f"Unknown disease_type: {disease_type}")
    return DATASET_REGISTRY[key]


def _generate_sepsis_table(disease_type: str, total_patients: int | None = None) -> TensorDataset:
    spec = get_disease_spec(disease_type)
    total = total_patients or spec.default_patients
    seed = stable_seed(disease_type, "physionet-sepsis-sim")
    generator = torch.Generator().manual_seed(seed)

    age = torch.randint(18, 92, (total,), generator=generator).float()
    temperature = torch.normal(mean=torch.full((total,), 37.1), std=torch.full((total,), 0.8), generator=generator)
    heart_rate = torch.normal(mean=torch.full((total,), 88.0), std=torch.full((total,), 18.0), generator=generator)
    respiratory_rate = torch.normal(mean=torch.full((total,), 20.0), std=torch.full((total,), 5.5), generator=generator)
    wbc = torch.normal(mean=torch.full((total,), 9.0), std=torch.full((total,), 3.5), generator=generator).abs()
    blood_pressure = torch.normal(mean=torch.full((total,), 118.0), std=torch.full((total,), 18.0), generator=generator)

    risk_score = (
        0.02 * (age - 50)
        + 0.35 * (temperature - 37.0)
        + 0.03 * (heart_rate - 80)
        + 0.06 * (respiratory_rate - 18)
        + 0.12 * (wbc - 8)
        - 0.03 * (blood_pressure - 110)
    )
    noise = torch.normal(mean=torch.zeros(total), std=torch.full((total,), 0.75), generator=generator)
    label = ((risk_score + noise) > 0.25).float()

    features = torch.stack([age, temperature, heart_rate, respiratory_rate, wbc, blood_pressure], dim=1)
    return TensorDataset(features, label)


def describe_tensor_dataset(dataset: TensorDataset, columns: list[str]) -> dict:
    features = dataset.tensors[0]
    return {
        "num_patients": int(features.shape[0]),
        "num_columns": int(features.shape[1]),
        "columns": list(columns),
    }


def build_hospital_dataset(
    disease_type: str,
    hospital_name: str,
    total_patients: int | None = None,
) -> tuple[TensorDataset, dict]:
    spec = get_disease_spec(disease_type)
    dataset = _generate_sepsis_table(disease_type, total_patients=total_patients)
    features, labels = dataset.tensors
    hospital_index = spec.hospital_order.index(hospital_name)
    boundaries = [0, len(dataset) // 3, (2 * len(dataset)) // 3, len(dataset)]
    start, end = boundaries[hospital_index], boundaries[hospital_index + 1]
    if hospital_index == len(spec.hospital_order) - 1:
        end = len(dataset)
    subset = TensorDataset(features[start:end].clone(), labels[start:end].clone())
    return subset, describe_tensor_dataset(subset, spec.feature_names)


def build_dataset_registry() -> dict[str, DiseaseDatasetSpec]:
    return dict(DATASET_REGISTRY)


def build_synthetic_dataset(experiment_id: str, client_id: str, samples: int = 128) -> TensorDataset:
    """Build synthetic 2D binary classification dataset."""
    seed = stable_seed(experiment_id, client_id)
    generator = torch.Generator().manual_seed(seed)
    half = max(1, samples // 2)
    remainder = max(0, samples - 2 * half)
    class0 = torch.randn(half, 2, generator=generator) + torch.tensor([-2.0, 0.5])
    class1 = torch.randn(half + remainder, 2, generator=generator) + torch.tensor([2.0, -0.5])
    features = torch.cat([class0, class1], dim=0)
    labels = torch.cat(
        [torch.zeros(class0.shape[0]), torch.ones(class1.shape[0])],
        dim=0,
    )
    perm = torch.randperm(features.shape[0], generator=generator)
    return TensorDataset(features[perm], labels[perm])


def _load_mnist_dataset(data_dir: str = "./data", train: bool = True) -> datasets.MNIST:
    """Load MNIST dataset with standard preprocessing."""
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    return datasets.MNIST(root=data_dir, train=train, download=True, transform=transform)


def _load_cifar10_dataset(data_dir: str = "./data", train: bool = True) -> datasets.CIFAR10:
    """Load CIFAR-10 dataset with standard preprocessing."""
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
    ])
    return datasets.CIFAR10(root=data_dir, train=train, download=True, transform=transform)


def partition_dataset_for_client(
    full_dataset,
    client_id: int,
    num_clients: int,
    samples: int = 128,
    shuffle: bool = True,
) -> Subset:
    """
    Partition a full dataset for a specific client using deterministic splitting.

    Args:
        full_dataset: The full dataset (e.g., MNIST training set)
        client_id: 0-indexed client identifier
        num_clients: Total number of clients
        samples: Target samples per client (may be less if dataset is small)
        shuffle: Whether to shuffle the partition

    Returns:
        A Subset of the full dataset assigned to this client.
    """
    if shuffle:
        seed = stable_seed(f"client_{client_id}", f"total_{num_clients}")
        generator = torch.Generator().manual_seed(seed)
        indices = torch.randperm(len(full_dataset), generator=generator).tolist()
    else:
        indices = list(range(len(full_dataset)))

    # Partition indices evenly across clients
    partition_size = max(samples, len(full_dataset) // num_clients)
    start = client_id * partition_size
    end = min(start + partition_size, len(full_dataset))

    if start >= len(full_dataset):
        # If we've run out of samples, wrap around
        start = client_id % len(full_dataset)
        end = min(start + partition_size, len(full_dataset))

    client_indices = indices[start:end]
    return Subset(full_dataset, client_indices)


def build_dataset(
    dataset_type: Literal["synthetic", "mnist", "cifar10"] = "synthetic",
    experiment_id: str = "default",
    client_id: str = "0",
    samples: int = 128,
    data_dir: str = "./data",
) -> TensorDataset | Subset:
    """
    Build a dataset for a client.

    Args:
        dataset_type: "synthetic" | "mnist" | "cifar10"
        experiment_id: Experiment identifier (used for synthetic data seeding)
        client_id: Client identifier (used for data partitioning)
        samples: Target number of samples
        data_dir: Directory to cache downloaded datasets

    Returns:
        A PyTorch Dataset (TensorDataset for synthetic, Subset for real datasets)
    """
    if dataset_type == "synthetic":
        return build_synthetic_dataset(experiment_id, client_id, samples)

    elif dataset_type == "mnist":
        full_dataset = _load_mnist_dataset(data_dir, train=True)
        client_idx = int(client_id) if isinstance(client_id, str) and client_id.isdigit() else 0
        num_clients = max(1, samples // 128)  # Estimate from sample size
        return partition_dataset_for_client(full_dataset, client_idx, num_clients, samples)

    elif dataset_type == "cifar10":
        full_dataset = _load_cifar10_dataset(data_dir, train=True)
        client_idx = int(client_id) if isinstance(client_id, str) and client_id.isdigit() else 0
        num_clients = max(1, samples // 128)
        return partition_dataset_for_client(full_dataset, client_idx, num_clients, samples)

    else:
        raise ValueError(f"Unknown dataset_type: {dataset_type}")



from __future__ import annotations

from collections import OrderedDict
from typing import Iterable, Tuple

import torch


StateDict = OrderedDict[str, torch.Tensor]
MONGO_KEY_DOT = "．"


def _encode_key(key: str) -> str:
    return key.replace(".", MONGO_KEY_DOT)


def _decode_key(key: str) -> str:
    return key.replace(MONGO_KEY_DOT, ".")


def average_state_dicts(weighted_updates: Iterable[Tuple[int, StateDict]]) -> StateDict:
    weighted_updates = list(weighted_updates)
    if not weighted_updates:
        raise ValueError("No client updates provided")

    total_samples = sum(samples for samples, _ in weighted_updates)
    if total_samples <= 0:
        raise ValueError("Total samples must be > 0")

    avg_state: StateDict = OrderedDict()
    for samples, state_dict in weighted_updates:
        weight = samples / total_samples
        for key, tensor in state_dict.items():
            if key not in avg_state:
                avg_state[key] = tensor.detach().clone().float() * weight
            else:
                avg_state[key] += tensor.detach().clone().float() * weight
    return avg_state


def state_dict_to_json(state_dict: StateDict) -> dict:
    return {_encode_key(key): tensor.detach().cpu().tolist() for key, tensor in state_dict.items()}


def json_to_state_dict(payload: dict) -> StateDict:
    return OrderedDict((_decode_key(key), torch.tensor(value, dtype=torch.float32)) for key, value in payload.items())


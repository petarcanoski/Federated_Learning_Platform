from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

import torch


@dataclass
class SecureAggregationConfig:
    enabled: bool = False
    round_seed: int = 0


def _mask_like(tensor: torch.Tensor, seed: int) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    return torch.randn(tensor.shape, generator=generator, device=tensor.device, dtype=tensor.dtype)


def mask_state_dict(state_dict: OrderedDict, seed: int) -> tuple[OrderedDict, OrderedDict]:
    masked = OrderedDict()
    masks = OrderedDict()
    for index, (key, tensor) in enumerate(state_dict.items()):
        mask = _mask_like(tensor, seed + index + 1)
        masked[key] = tensor.detach().clone().float() + mask
        masks[key] = mask
    return masked, masks


def unmask_state_dict(state_dict: OrderedDict, masks: OrderedDict) -> OrderedDict:
    return OrderedDict((key, tensor.detach().clone().float() - masks[key]) for key, tensor in state_dict.items())



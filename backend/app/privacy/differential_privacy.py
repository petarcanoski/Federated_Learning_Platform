from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass, field

import torch


@dataclass
class DifferentialPrivacyConfig:
    """Configuration for differential privacy in federated learning."""
    enabled: bool = False
    clipping_norm: float = 1.0
    noise_multiplier: float = 0.0
    seed: int = 0
    delta: float = 1e-5  # Standard delta for epsilon-delta DP


@dataclass
class DifferentialPrivacyAccounting:
    """Tracks DP accounting across rounds using RDP (Rényi Differential Privacy)."""
    epsilon: float = 0.0
    delta: float = 1e-5
    noise_multiplier: float = 0.0
    clipping_norm: float = 1.0
    num_rounds: int = 0
    rdp_list: list[float] = field(default_factory=list)  # RDP values at different alpha
    
    def get_epsilon(self, alpha: float = 10) -> float:
        """
        Convert RDP to epsilon using the formula:
        epsilon(delta) = (1 / (alpha - 1)) * (log(1/delta) + log(alpha) - log(alpha - 1))
        
        where RDP_alpha = (1 / (alpha - 1)) * log(E[(M(x)/M(x'))^(alpha-1)])
        
        For Gaussian mechanism: RDP_alpha = (alpha / (2 * sigma^2))
        where sigma is noise_multiplier (scaled by clipping norm)
        """
        if self.noise_multiplier <= 0:
            return float('inf')
        
        # RDP for Gaussian mechanism
        sigma = self.noise_multiplier
        rdp_alpha = (alpha * self.num_rounds) / (2 * sigma ** 2)
        
        # Convert RDP to epsilon-delta
        if rdp_alpha <= 0:
            return float('inf')
        
        epsilon = (rdp_alpha / (alpha - 1)) * (math.log(1 / self.delta) + math.log(alpha)) - math.log(alpha - 1)
        return epsilon
    
    def update_accounting(self, noise_multiplier: float, clipping_norm: float, num_rounds: int, delta: float = 1e-5) -> None:
        """Update accounting parameters."""
        self.noise_multiplier = noise_multiplier
        self.clipping_norm = clipping_norm
        self.num_rounds = num_rounds
        self.delta = delta
        self.epsilon = self.get_epsilon()


def clip_and_noise_update(base_state: OrderedDict, updated_state: OrderedDict, config: DifferentialPrivacyConfig) -> OrderedDict:
    """
    Apply gradient clipping and Gaussian noise for differential privacy.
    
    Args:
        base_state: Initial model state (before update)
        updated_state: Updated model state (after local training)
        config: DP configuration with clipping norm and noise multiplier
    
    Returns:
        DP-protected model update
    """
    if not config.enabled:
        return updated_state

    # Compute gradient delta
    delta = OrderedDict()
    for k in base_state:
        delta[k] = updated_state[k].detach().clone().float() - base_state[k].detach().clone().float()
    
    # Compute L2 norm of gradient
    squared_norm = sum(torch.sum(tensor * tensor) for tensor in delta.values())
    norm = torch.sqrt(squared_norm + 1e-12)
    
    # Clip gradient
    clip_factor = min(1.0, config.clipping_norm / float(norm.item())) if float(norm.item()) > 0 else 1.0

    # Add Gaussian noise
    generator = torch.Generator().manual_seed(config.seed)
    noisy_state = OrderedDict()
    for key, tensor in base_state.items():
        clipped_delta = delta[key] * clip_factor
        # Noise scale: noise_multiplier * clipping_norm
        noise_scale = config.noise_multiplier * config.clipping_norm
        noise = torch.randn(
            clipped_delta.shape,
            generator=generator,
            device=clipped_delta.device,
            dtype=clipped_delta.dtype
        ) * noise_scale
        noisy_state[key] = tensor.detach().clone().float() + clipped_delta + noise
    
    return noisy_state


def compute_dp_epsilon(
    noise_multiplier: float,
    num_rounds: int,
    num_clients: int,
    delta: float = 1e-5,
    alpha: float = 10,
) -> float:
    """
    Compute epsilon for the composition using RDP.
    
    Args:
        noise_multiplier: Ratio of noise to clipping norm
        num_rounds: Total number of federated rounds
        num_clients: Number of clients per round (sampling effect)
        delta: Target delta for epsilon-delta DP
        alpha: RDP order (default 10, typical range [1.5, 100])
    
    Returns:
        epsilon value
    """
    accounting = DifferentialPrivacyAccounting(delta=delta)
    accounting.update_accounting(noise_multiplier, 1.0, num_rounds, delta)
    return accounting.epsilon



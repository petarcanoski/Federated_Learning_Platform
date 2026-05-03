from collections import OrderedDict

import torch

from backend.app.privacy.differential_privacy import DifferentialPrivacyConfig, clip_and_noise_update
from backend.app.privacy.secure_aggregation import mask_state_dict, unmask_state_dict


def test_dp_hook_changes_updates_when_enabled():
    base = OrderedDict({'w': torch.zeros(3)})
    updated = OrderedDict({'w': torch.ones(3)})
    disabled = clip_and_noise_update(base, updated, DifferentialPrivacyConfig(enabled=False))
    enabled = clip_and_noise_update(base, updated, DifferentialPrivacyConfig(enabled=True, clipping_norm=0.5, noise_multiplier=0.0, seed=1))

    assert torch.allclose(disabled['w'], updated['w'])
    assert not torch.allclose(enabled['w'], updated['w'])


def test_secure_aggregation_mask_roundtrip():
    state = OrderedDict({'w': torch.tensor([1.0, 2.0])})
    masked, masks = mask_state_dict(state, seed=42)
    restored = unmask_state_dict(masked, masks)
    assert torch.allclose(restored['w'], state['w'])


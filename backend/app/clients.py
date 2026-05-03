import numpy as np


def simulate_client_training(global_weights: np.ndarray, epochs: int = 1, samples: int = 100):
    """Simulate local training by adding small noise to global weights and returning updated weights.

    Returns: (updated_weights_list, sample_count, metric)
    metric is a dummy accuracy that increases slightly with training and randomness
    """
    # simple simulation: take global weights and perform a tiny gradient step toward random "local optimum"
    local_optimum = np.random.normal(loc=0.5, scale=1.0, size=global_weights.shape)
    lr = 0.1 / max(1, epochs)
    updated = global_weights.copy()
    for _ in range(epochs):
        # gradient is (updated - local_optimum)
        grad = (updated - local_optimum)
        updated = updated - lr * grad + np.random.normal(scale=0.01, size=updated.shape)

    # fake metric: higher when closer to local_optimum
    distance = np.linalg.norm(updated - local_optimum)
    metric = float(max(0.0, 1.0 / (1.0 + distance)))

    return updated.tolist(), samples, metric


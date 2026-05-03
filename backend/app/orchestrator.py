import uuid
import numpy as np
from typing import Dict, Any
from .clients import simulate_client_training


class Orchestrator:
    """Simple in-memory orchestrator that runs federated rounds with local client simulation.

    - Keeps jobs in-memory (dict)
    - Each job has global_weights (list), clients metadata, round counter, config
    """

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def start_experiment(self, num_clients=3, rounds=3, epochs=1, model_size=10):
        job_id = str(uuid.uuid4())
        # initialize global weights as zeros
        global_weights = np.zeros(model_size).tolist()
        clients = []
        # assign random sample counts to clients for weighted averaging
        for i in range(num_clients):
            samples = int(100 + np.random.randint(-20, 20))
            clients.append({"id": f"client_{i+1}", "samples": samples})

        job = {
            "job_id": job_id,
            "global_weights": global_weights,
            "clients": clients,
            "round": 0,
            "rounds": rounds,
            "epochs": epochs,
            "status": "running",
            "history": []
        }
        self.jobs[job_id] = job
        return job_id

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)

    def run_round(self, job_id: str):
        job = self.jobs.get(job_id)
        if job is None:
            return None
        if job['round'] >= job['rounds']:
            job['status'] = 'finished'
            return None

        global_w = np.array(job['global_weights'])
        updates = []
        total_samples = 0
        metrics = []
        # simulate each client training locally and returning updated weights and sample count
        for c in job['clients']:
            updated_w, sample_count, metric = simulate_client_training(global_w, epochs=job['epochs'], samples=c['samples'])
            updates.append((np.array(updated_w), sample_count))
            total_samples += sample_count
            metrics.append({"client_id": c['id'], "samples": sample_count, "metric": metric})

        # Federated averaging (FedAvg): weighted average by number of samples
        new_global = np.zeros_like(global_w)
        for w, n in updates:
            new_global += (n / total_samples) * w

        job['global_weights'] = new_global.tolist()
        job['round'] += 1
        job['history'].append({
            "round": job['round'],
            "metrics": metrics,
            "global_weights": job['global_weights']
        })

        if job['round'] >= job['rounds']:
            job['status'] = 'finished'

        return {
            "job_id": job_id,
            "round": job['round'],
            "status": job['status'],
            "metrics": metrics,
            "global_weights": job['global_weights']
        }


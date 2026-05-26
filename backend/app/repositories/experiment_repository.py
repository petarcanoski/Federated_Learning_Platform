from __future__ import annotations

from typing import Iterable

from ..models import ClientMetric, Experiment, ExperimentRound


class ExperimentRepository:
    def create_experiment(self, experiment: Experiment) -> Experiment:
        experiment.save()
        return experiment

    def get_by_job_id(self, job_id: str) -> Experiment | None:
        return Experiment.objects(job_id=job_id).first()

    def list_experiments(self) -> list[Experiment]:
        return list(Experiment.objects.order_by("-created_at"))

    def add_round(self, experiment: Experiment, round_obj: ExperimentRound, metrics: Iterable[ClientMetric]) -> ExperimentRound:
        round_obj.client_metrics.extend(metrics)
        experiment.rounds.append(round_obj)
        experiment.save()
        return round_obj



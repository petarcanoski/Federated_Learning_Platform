from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy.orm import Session

from ..models import ClientMetric, Experiment, ExperimentRound


class ExperimentRepository:
    def create_experiment(self, db: Session, experiment: Experiment) -> Experiment:
        db.add(experiment)
        db.flush()
        return experiment

    def get_by_job_id(self, db: Session, job_id: str) -> Optional[Experiment]:
        return db.query(Experiment).filter(Experiment.job_id == job_id).first()

    def list_experiments(self, db: Session) -> list[Experiment]:
        return db.query(Experiment).order_by(Experiment.created_at.desc()).all()

    def add_round(self, db: Session, round_obj: ExperimentRound, metrics: Iterable[ClientMetric]) -> ExperimentRound:
        db.add(round_obj)
        db.flush()
        for metric in metrics:
            round_obj.client_metrics.append(metric)
        return round_obj



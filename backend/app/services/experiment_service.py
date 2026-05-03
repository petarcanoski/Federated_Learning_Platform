from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import torch
from sqlalchemy import desc
from sqlalchemy.orm import Session
from torch.utils.data import DataLoader, TensorDataset

from ..bootstrap import ensure_demo_data
from ..db import session_scope
from ..ml.datasets import DATASET_REGISTRY, build_hospital_dataset, get_disease_spec
from ..ml.fedavg import average_state_dicts, json_to_state_dict, state_dict_to_json
from ..ml.model import SimpleClassifier
from ..ml.trainer import build_client_dataset, train_local_model
from ..models import ClientMetric, Experiment, ExperimentHospitalState, ExperimentRound, Hospital, User
from ..privacy.differential_privacy import DifferentialPrivacyConfig, clip_and_noise_update, compute_dp_epsilon
from ..privacy.secure_aggregation import SecureAggregationConfig, mask_state_dict, unmask_state_dict
from ..schemas import (
    AggregateResult,
    AdminDashboardOut,
    BroadcastResult,
    ExperimentCreateRequest,
    ExperimentOut,
    ExperimentRoundOut,
    ExperimentSummary,
    HospitalCreateRequest,
    HospitalDashboardOut,
    HospitalDatasetStatsOut,
    HospitalOut,
    HospitalStateOut,
    LoginRequest,
    MeOut,
    TokenResponse,
    UserOut,
)
from ..security import create_access_token, hash_password, verify_password


LEGACY_DATASET_INPUT_DIMS = {"synthetic": 2, "mnist": 784, "cifar10": 3 * 32 * 32}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExperimentService:
    def __init__(self) -> None:
        self._seeded = False

    def _ensure_seeded(self, db: Session) -> None:
        if not self._seeded:
            ensure_demo_data(db)
            self._seeded = True

    def _initial_state(self, hidden_dim: int, input_dim: int) -> dict[str, Any]:
        model = SimpleClassifier(input_dim=input_dim, hidden_dim=hidden_dim)
        return model.state_dict()

    def _experiment_payload(self, request: ExperimentCreateRequest) -> dict[str, Any]:
        payload = {key: value for key, value in request.__dict__.items() if not key.startswith("_")}
        if payload.get("disease_type"):
            payload["dataset_type"] = payload["disease_type"]
        return payload

    def _is_healthcare_experiment(self, experiment: Experiment) -> bool:
        return experiment.disease_type.lower() in DATASET_REGISTRY

    def _input_dim(self, experiment: Experiment) -> int:
        if self._is_healthcare_experiment(experiment):
            return get_disease_spec(experiment.disease_type).input_dim
        return LEGACY_DATASET_INPUT_DIMS.get(experiment.config.get("dataset_type", "synthetic"), 2)

    def _hidden_dim(self, experiment: Experiment) -> int:
        if self._is_healthcare_experiment(experiment):
            return int(experiment.config.get("hidden_dim") or get_disease_spec(experiment.disease_type).default_hidden_dim)
        return int(experiment.config.get("hidden_dim", 16))

    def _serialize_user(self, user: User) -> UserOut:
        return UserOut(id=user.id, username=user.username, role=user.role, hospital_id=user.hospital_id, is_active=user.is_active)

    def _serialize_hospital(self, hospital: Hospital) -> HospitalOut:
        return HospitalOut(
            id=hospital.id,
            code=hospital.code,
            name=hospital.name,
            city=hospital.city,
            status=hospital.status,
            disease_type=hospital.disease_type,
            dataset_rows=hospital.dataset_rows,
            dataset_columns=hospital.dataset_columns,
            is_active=hospital.is_active,
        )

    def _serialize_state(self, state: ExperimentHospitalState) -> HospitalStateOut:
        return HospitalStateOut(
            hospital_id=state.hospital_id,
            hospital_code=state.hospital.code,
            hospital_name=state.hospital.name,
            status=state.status,
            training_progress=float(state.training_progress),
            sample_count=state.sample_count,
            column_count=state.column_count,
            local_accuracy=state.local_accuracy,
            previous_accuracy=state.previous_accuracy,
            new_accuracy=state.new_accuracy,
            weights_json=state.weights_json,
            notification=state.notification,
            last_trained_round=state.last_trained_round,
            weights_sent_at=state.weights_sent_at.isoformat() if state.weights_sent_at else None,
            model_received_at=state.model_received_at.isoformat() if state.model_received_at else None,
        )

    def _serialize_round(self, round_obj: ExperimentRound) -> ExperimentRoundOut:
        return ExperimentRoundOut(
            round_index=round_obj.round_index,
            loss=round_obj.loss,
            accuracy=round_obj.accuracy,
            global_accuracy=round_obj.global_accuracy,
            total_samples=round_obj.total_samples,
            client_metrics=[
                {
                    "client_id": metric.client_id,
                    "hospital_id": metric.hospital_id,
                    "hospital_name": metric.hospital.name if metric.hospital else None,
                    "samples": metric.samples,
                    "loss": metric.loss,
                    "accuracy": metric.accuracy,
                    "masked": metric.masked,
                }
                for metric in round_obj.client_metrics
            ],
        )

    def _serialize_experiment(self, experiment: Experiment) -> ExperimentOut:
        return ExperimentOut(
            job_id=experiment.job_id,
            status=experiment.status,
            current_round=experiment.current_round,
            total_rounds=experiment.total_rounds,
            disease_type=experiment.disease_type,
            model_name=experiment.model_name,
            round_progress=experiment.round_progress,
            global_accuracy=experiment.global_accuracy,
            config=experiment.config,
            rounds=[self._serialize_round(item) for item in experiment.rounds],
            current_weights=experiment.current_weights,
            dp_epsilon=experiment.dp_epsilon,
            dp_delta=experiment.dp_delta,
            hospital_states=[self._serialize_state(state) for state in experiment.hospital_states],
        )

    def _evaluate_state(self, state_dict: dict[str, Any], dataset: TensorDataset, hidden_dim: int, input_dim: int) -> tuple[float, float]:
        if len(dataset) == 0:
            return 0.0, 0.0
        model = SimpleClassifier(input_dim=input_dim, hidden_dim=hidden_dim)
        model.load_state_dict(json_to_state_dict(state_dict))
        model.eval()
        loader = DataLoader(dataset, batch_size=min(64, len(dataset)), shuffle=False)
        criterion = torch.nn.BCEWithLogitsLoss()
        total_loss = 0.0
        total_seen = 0
        total_correct = 0
        with torch.no_grad():
            for features, labels in loader:
                features = features.float()
                labels = labels.float()
                if features.dim() > 2:
                    features = features.view(features.size(0), -1)
                logits = model(features)
                loss = criterion(logits, labels)
                batch_size = int(labels.numel())
                total_loss += float(loss.item()) * batch_size
                predictions = (torch.sigmoid(logits) >= 0.5).float()
                total_correct += int((predictions == labels).sum().item())
                total_seen += batch_size
        return total_loss / max(1, total_seen), total_correct / max(1, total_seen)

    def _evaluate_global_accuracy(self, experiment: Experiment, state_dict: dict[str, Any]) -> float:
        if not self._is_healthcare_experiment(experiment):
            return 0.0
        spec = get_disease_spec(experiment.disease_type)
        datasets = []
        for hospital_name in spec.hospital_order:
            dataset, _ = build_hospital_dataset(experiment.disease_type, hospital_name)
            datasets.append(dataset)
        features = torch.cat([item.tensors[0] for item in datasets], dim=0)
        labels = torch.cat([item.tensors[1] for item in datasets], dim=0)
        combined = TensorDataset(features, labels)
        _, accuracy = self._evaluate_state(state_dict, combined, self._hidden_dim(experiment), self._input_dim(experiment))
        return accuracy

    def _combine_healthcare_state(self, experiment: Experiment) -> dict[str, Any]:
        states = [state for state in experiment.hospital_states if state.raw_weights_json]
        if not states:
            raise ValueError("No hospital weights available")
        weighted_states = []
        total_samples = 0
        weighted_masks: list[tuple[int, OrderedDict[str, torch.Tensor]]] = []
        secure_enabled = bool(experiment.config.get("secure_aggregation_enabled", False))
        for index, state in enumerate(states):
            payload = state.raw_weights_json or state.weights_json
            if payload is None:
                continue
            raw_state = json_to_state_dict(payload)
            weighted_states.append((state.sample_count, raw_state))
            total_samples += state.sample_count
            if secure_enabled and state.weights_json is not None:
                masked_state = json_to_state_dict(state.weights_json)
                raw_state = json_to_state_dict(state.raw_weights_json)
                masks = OrderedDict((key, masked_state[key] - raw_state[key]) for key in raw_state)
                weighted_masks.append((state.sample_count, masks))
        aggregated_state = average_state_dicts(weighted_states)
        if secure_enabled and weighted_masks:
            aggregated_masks: OrderedDict[str, torch.Tensor] = OrderedDict()
            for samples, masks in weighted_masks:
                weight = samples / max(1, total_samples)
                for key, tensor in masks.items():
                    aggregated_masks[key] = aggregated_masks.get(key, torch.zeros_like(tensor)) + tensor * weight
            aggregated_state = unmask_state_dict(aggregated_state, aggregated_masks)
        return state_dict_to_json(aggregated_state)

    def _legacy_round(self, db: Session, experiment: Experiment) -> ExperimentOut:
        current_state = json_to_state_dict(experiment.current_weights)
        client_results: list[dict[str, Any]] = []
        client_metrics: list[ClientMetric] = []
        weighted_states = []
        weighted_masks = []
        total_samples = 0
        dataset_type = experiment.config.get("dataset_type", "synthetic")
        input_dim = self._input_dim(experiment)
        privacy_cfg = DifferentialPrivacyConfig(
            enabled=bool(experiment.config.get("dp_enabled", False)),
            clipping_norm=float(experiment.config.get("clipping_norm", 1.0)),
            noise_multiplier=float(experiment.config.get("noise_multiplier", 0.0)),
            seed=experiment.current_round + 42,
        )
        secure_cfg = SecureAggregationConfig(
            enabled=bool(experiment.config.get("secure_aggregation_enabled", False)),
            round_seed=experiment.current_round + 7,
        )

        for index in range(int(experiment.config.get("num_clients", 3))):
            client_id = f"client_{index + 1}"
            dataset = build_client_dataset(experiment.job_id, client_id, samples=int(experiment.config.get("samples_per_client", 128)), dataset_type=dataset_type)
            local_state, metrics = train_local_model(
                initial_state=current_state,
                dataset=dataset,
                epochs=int(experiment.config.get("epochs", 1)),
                learning_rate=float(experiment.config.get("learning_rate", 0.01)),
                hidden_dim=self._hidden_dim(experiment),
                input_dim=input_dim,
            )
            local_state = OrderedDict(local_state)
            if privacy_cfg.enabled:
                local_state = clip_and_noise_update(current_state, local_state, privacy_cfg)
            if secure_cfg.enabled:
                masked_state, masks = mask_state_dict(local_state, seed=secure_cfg.round_seed + index)
                weighted_masks.append((metrics.samples, masks))
                local_state = masked_state
            weighted_states.append((metrics.samples, local_state))
            total_samples += metrics.samples
            client_metrics.append(
                ClientMetric(
                    client_id=client_id,
                    samples=metrics.samples,
                    loss=metrics.loss,
                    accuracy=metrics.accuracy,
                    masked=bool(secure_cfg.enabled),
                )
            )
            client_results.append({"client_id": client_id, **asdict(metrics)})

        aggregated_state = average_state_dicts(weighted_states)
        if secure_cfg.enabled:
            aggregated_masks = {}
            for samples, masks in weighted_masks:
                weight = samples / max(1, total_samples)
                for key, tensor in masks.items():
                    aggregated_masks[key] = aggregated_masks.get(key, torch.zeros_like(tensor)) + tensor * weight
            aggregated_state = unmask_state_dict(aggregated_state, aggregated_masks)

        experiment.current_weights = state_dict_to_json(aggregated_state)
        experiment.current_round += 1
        experiment.round_progress = f"{experiment.current_round}/{experiment.total_rounds}"
        if experiment.current_round >= experiment.total_rounds:
            experiment.status = "finished"

        round_loss = sum(item["loss"] * item["samples"] for item in client_results) / max(1, total_samples)
        round_accuracy = sum(item["accuracy"] * item["samples"] for item in client_results) / max(1, total_samples)
        round_global_accuracy = self._evaluate_global_accuracy(experiment, experiment.current_weights) if self._is_healthcare_experiment(experiment) else round_accuracy

        round_obj = ExperimentRound(
            experiment_id=experiment.id,
            round_index=experiment.current_round,
            loss=round_loss,
            accuracy=round_accuracy,
            global_accuracy=round_global_accuracy,
            total_samples=total_samples,
            global_weights=state_dict_to_json(aggregated_state),
        )
        db.add(round_obj)
        db.flush()
        for metric in client_metrics:
            metric.round_id = round_obj.id
            db.add(metric)

        if privacy_cfg.enabled and privacy_cfg.noise_multiplier > 0:
            experiment.dp_epsilon = compute_dp_epsilon(
                noise_multiplier=privacy_cfg.noise_multiplier,
                num_rounds=experiment.current_round,
                num_clients=int(experiment.config.get("num_clients", 3)),
                delta=privacy_cfg.delta,
            )
            experiment.dp_delta = privacy_cfg.delta
        experiment.global_accuracy = round_global_accuracy
        return self._serialize_experiment(experiment)

    def _healthcare_round(self, db: Session, experiment: Experiment, send_immediately: bool = True) -> ExperimentOut:
        hospital_states = [state for state in experiment.hospital_states if state.hospital.is_active]
        if not hospital_states:
            raise ValueError("No hospital states configured")
        for state in hospital_states:
            state.status = "training"
            state.training_progress = 5.0
            state.notification = f"Training local model for {state.hospital.name}..."
            state.hospital.status = "training"

        spec = get_disease_spec(experiment.disease_type)
        current_state = json_to_state_dict(experiment.current_weights)
        privacy_cfg = DifferentialPrivacyConfig(
            enabled=bool(experiment.config.get("dp_enabled", False)),
            clipping_norm=float(experiment.config.get("clipping_norm", 1.0)),
            noise_multiplier=float(experiment.config.get("noise_multiplier", 0.0)),
            seed=experiment.current_round + 42,
        )
        secure_cfg = SecureAggregationConfig(
            enabled=bool(experiment.config.get("secure_aggregation_enabled", False)),
            round_seed=experiment.current_round + 7,
        )

        client_metrics: list[ClientMetric] = []
        weighted_states = []
        weighted_masks = []
        total_samples = 0
        all_dataset_features = []
        all_dataset_labels = []

        for index, state in enumerate(hospital_states):
            dataset, stats = build_hospital_dataset(experiment.disease_type, state.hospital.name)
            features, labels = dataset.tensors
            all_dataset_features.append(features)
            all_dataset_labels.append(labels)
            local_state, metrics = train_local_model(
                initial_state=current_state,
                dataset=dataset,
                epochs=int(experiment.config.get("epochs", 1)),
                learning_rate=float(experiment.config.get("learning_rate", 0.01)),
                hidden_dim=self._hidden_dim(experiment),
                input_dim=spec.input_dim,
            )
            local_state = OrderedDict(local_state)
            if privacy_cfg.enabled:
                local_state = clip_and_noise_update(current_state, local_state, privacy_cfg)
            raw_state_json = state_dict_to_json(local_state)
            sent_state = local_state
            if secure_cfg.enabled:
                sent_state, masks = mask_state_dict(local_state, seed=secure_cfg.round_seed + index)
                weighted_masks.append((metrics.samples, masks))
            weighted_states.append((metrics.samples, sent_state))
            total_samples += metrics.samples
            state.sample_count = metrics.samples
            state.column_count = stats["num_columns"]
            state.local_accuracy = metrics.accuracy
            state.previous_accuracy = experiment.global_accuracy if experiment.global_accuracy is not None else metrics.accuracy
            state.new_accuracy = None
            state.raw_weights_json = raw_state_json
            state.weights_json = state_dict_to_json(sent_state)
            state.dataset_preview = self._dataset_preview(dataset, spec.feature_names)
            state.last_trained_round = experiment.current_round + 1
            state.weights_sent_at = _now()
            state.status = "weights sent"
            state.training_progress = 100.0
            state.notification = "Weights sent to Ministry ✅"
            state.hospital.status = "weights sent"
            state.hospital.dataset_rows = stats["num_patients"]
            state.hospital.dataset_columns = stats["num_columns"]
            state.hospital.disease_type = experiment.disease_type
            client_metrics.append(
                ClientMetric(
                    hospital_id=state.hospital_id,
                    client_id=state.hospital.code,
                    samples=metrics.samples,
                    loss=metrics.loss,
                    accuracy=metrics.accuracy,
                    masked=bool(secure_cfg.enabled),
                )
            )

        aggregated_state = average_state_dicts(weighted_states)
        if secure_cfg.enabled:
            aggregated_masks = {}
            for samples, masks in weighted_masks:
                weight = samples / max(1, total_samples)
                for key, tensor in masks.items():
                    aggregated_masks[key] = aggregated_masks.get(key, torch.zeros_like(tensor)) + tensor * weight
            aggregated_state = unmask_state_dict(aggregated_state, aggregated_masks)

        experiment.current_round += 1
        experiment.current_weights = state_dict_to_json(aggregated_state)
        experiment.round_progress = f"{experiment.current_round}/{experiment.total_rounds}"
        if experiment.current_round >= experiment.total_rounds:
            experiment.status = "finished"
        else:
            experiment.status = "waiting for Ministry to aggregate"

        global_loss, global_accuracy = self._evaluate_state(experiment.current_weights, TensorDataset(torch.cat(all_dataset_features, dim=0), torch.cat(all_dataset_labels, dim=0)), self._hidden_dim(experiment), spec.input_dim)
        experiment.global_accuracy = global_accuracy

        round_obj = ExperimentRound(
            experiment_id=experiment.id,
            round_index=experiment.current_round,
            loss=global_loss,
            accuracy=global_accuracy,
            global_accuracy=global_accuracy,
            total_samples=total_samples,
            global_weights=state_dict_to_json(aggregated_state),
        )
        db.add(round_obj)
        db.flush()
        for metric in client_metrics:
            metric.round_id = round_obj.id
            db.add(metric)

        if privacy_cfg.enabled and privacy_cfg.noise_multiplier > 0:
            experiment.dp_epsilon = compute_dp_epsilon(
                noise_multiplier=privacy_cfg.noise_multiplier,
                num_rounds=experiment.current_round,
                num_clients=len(hospital_states),
                delta=privacy_cfg.delta,
            )
            experiment.dp_delta = privacy_cfg.delta

        if send_immediately:
            self._broadcast_current_model(db, experiment)
        return self._serialize_experiment(experiment)

    def _broadcast_current_model(self, db: Session, experiment: Experiment) -> list[str]:
        notifications = []
        for state in experiment.hospital_states:
            if state.raw_weights_json is None:
                continue
            spec = get_disease_spec(experiment.disease_type)
            dataset, _ = build_hospital_dataset(experiment.disease_type, state.hospital.name)
            _, new_accuracy = self._evaluate_state(experiment.current_weights, dataset, self._hidden_dim(experiment), spec.input_dim)
            state.previous_accuracy = state.local_accuracy
            state.new_accuracy = new_accuracy
            state.model_received_at = _now()
            state.status = "done"
            state.notification = f"Improved model received ✅ Previous accuracy: {int((state.previous_accuracy or 0) * 100)}% | New accuracy: {int(new_accuracy * 100)}%"
            state.hospital.status = "done"
            notifications.append(state.notification)
        return notifications

    def _dataset_preview(self, dataset: TensorDataset, columns: list[str]) -> list[dict[str, Any]]:
        features, labels = dataset.tensors
        preview = []
        for idx in range(min(5, len(dataset))):
            row = {name: round(float(features[idx][col]), 3) for col, name in enumerate(columns)}
            row["sepsis_label"] = int(labels[idx].item())
            preview.append(row)
        return preview

    def create_experiment(self, request: ExperimentCreateRequest, creator: User | None = None) -> ExperimentOut:
        job_id = str(uuid.uuid4())
        config = self._experiment_payload(request)
        disease_type = (request.disease_type or request.dataset_type or "sepsis").lower()
        healthcare = disease_type in DATASET_REGISTRY
        input_dim = get_disease_spec(disease_type).input_dim if healthcare else LEGACY_DATASET_INPUT_DIMS.get(request.dataset_type, 2)
        hidden_dim = request.hidden_dim if request.hidden_dim else (get_disease_spec(disease_type).default_hidden_dim if healthcare else 16)
        initial_state = self._initial_state(hidden_dim, input_dim)

        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = Experiment(
                job_id=job_id,
                created_by_user_id=creator.id if creator else None,
                disease_type=disease_type,
                model_name="simple_classifier",
                status="running",
                config={**config, "disease_type": disease_type, "input_dim": input_dim, "hidden_dim": hidden_dim},
                current_round=0,
                total_rounds=request.rounds,
                current_weights=state_dict_to_json(initial_state),
                round_progress=f"0/{request.rounds}",
            )
            db.add(experiment)
            db.flush()

            if healthcare:
                spec = get_disease_spec(disease_type)
                selected_codes = [code.lower() for code in (request.hospital_codes or spec.hospital_order)]
                hospitals = db.query(Hospital).filter(Hospital.code.in_(selected_codes)).order_by(Hospital.id).all()
                if not hospitals:
                    hospitals = db.query(Hospital).order_by(Hospital.id).all()
                for hospital in hospitals:
                    dataset, stats = build_hospital_dataset(disease_type, hospital.name)
                    db.add(
                        ExperimentHospitalState(
                            experiment=experiment,
                            hospital=hospital,
                            status="waiting",
                            training_progress=0.0,
                            sample_count=stats["num_patients"],
                            column_count=stats["num_columns"],
                            local_accuracy=None,
                            previous_accuracy=None,
                            new_accuracy=None,
                            weights_json=None,
                            raw_weights_json=None,
                            dataset_preview=self._dataset_preview(dataset, spec.feature_names),
                            notification="Waiting for hospital training to start",
                        )
                    )
                    hospital.dataset_rows = stats["num_patients"]
                    hospital.dataset_columns = stats["num_columns"]
                    hospital.disease_type = disease_type
                    hospital.status = "waiting"

            return self._serialize_experiment(experiment)

    def start_experiment(self, request: ExperimentCreateRequest) -> ExperimentOut:
        return self.create_experiment(request)

    def list_experiments(self) -> list[ExperimentSummary]:
        with session_scope() as db:
            self._ensure_seeded(db)
            experiments = db.query(Experiment).order_by(desc(Experiment.created_at)).all()
            return [
                ExperimentSummary(
                    job_id=exp.job_id,
                    status=exp.status,
                    current_round=exp.current_round,
                    total_rounds=exp.total_rounds,
                    rounds_completed=len(exp.rounds),
                    disease_type=exp.disease_type,
                    global_accuracy=exp.global_accuracy,
                    round_progress=exp.round_progress,
                )
                for exp in experiments
            ]

    def get_experiment(self, job_id: str) -> ExperimentOut:
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            return self._serialize_experiment(experiment)

    def run_round(self, job_id: str) -> ExperimentOut:
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            if experiment.status == "finished":
                return self._serialize_experiment(experiment)
            if self._is_healthcare_experiment(experiment):
                return self._healthcare_round(db, experiment, send_immediately=True)
            return self._legacy_round(db, experiment)

    def login(self, request: LoginRequest) -> TokenResponse:
        with session_scope() as db:
            self._ensure_seeded(db)
            user = db.query(User).filter(User.username == request.username).first()
            if user is None or not verify_password(request.password, user.password_hash):
                raise PermissionError("Invalid credentials")
            token = create_access_token(subject=str(user.id), role=user.role, hospital_id=user.hospital_id, username=user.username)
            return TokenResponse(access_token=token, role=user.role, username=user.username, hospital_id=user.hospital_id)

    def me(self, user: User) -> MeOut:
        with session_scope() as db:
            self._ensure_seeded(db)
            fresh_user = db.query(User).filter(User.id == user.id).first()
            if fresh_user is None:
                raise KeyError("user not found")
            hospital = fresh_user.hospital if fresh_user.hospital else None
            return MeOut(user=self._serialize_user(fresh_user), hospital=self._serialize_hospital(hospital) if hospital else None)

    def create_hospital_account(self, request: HospitalCreateRequest, current_user: User) -> dict[str, Any]:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can create hospital accounts")
        with session_scope() as db:
            self._ensure_seeded(db)
            if db.query(Hospital).filter(Hospital.code == request.code).first() is not None:
                raise ValueError("Hospital already exists")
            if db.query(User).filter(User.username == request.username).first() is not None:
                raise ValueError("Username already exists")
            hospital = Hospital(code=request.code, name=request.name, city=request.city, status="waiting", disease_type="sepsis", dataset_rows=0, dataset_columns=0, is_active=True)
            db.add(hospital)
            db.flush()
            user = User(username=request.username, password_hash=hash_password(request.password), role="HOSPITAL", hospital_id=hospital.id, is_active=True)
            db.add(user)
            db.flush()
            return {"hospital": self._serialize_hospital(hospital), "user": self._serialize_user(user), "temporary_password": request.password}

    def list_hospitals(self, current_user: User) -> list[HospitalOut]:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can view all hospitals")
        with session_scope() as db:
            self._ensure_seeded(db)
            hospitals = db.query(Hospital).order_by(Hospital.id).all()
            return [self._serialize_hospital(hospital) for hospital in hospitals]

    def get_admin_dashboard(self, current_user: User) -> AdminDashboardOut:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can view dashboard")
        with session_scope() as db:
            self._ensure_seeded(db)
            db_user = db.query(User).filter(User.id == current_user.id).first()
            experiments = db.query(Experiment).order_by(desc(Experiment.created_at)).all()
            hospitals = db.query(ExperimentHospitalState).join(Hospital).order_by(Hospital.id).all()
            return AdminDashboardOut(
                admin=self._serialize_user(db_user or current_user),
                hospitals=[self._serialize_state(state) for state in hospitals],
                experiments=[
                    {
                        "job_id": exp.job_id,
                        "status": exp.status,
                        "disease_type": exp.disease_type,
                        "round_progress": exp.round_progress,
                        "current_round": exp.current_round,
                        "total_rounds": exp.total_rounds,
                        "global_accuracy": exp.global_accuracy,
                        "dp_epsilon": exp.dp_epsilon,
                        "dp_delta": exp.dp_delta,
                    }
                    for exp in experiments
                ],
            )

    def get_hospital_dashboard(self, current_user: User) -> HospitalDashboardOut:
        if current_user.role != "HOSPITAL":
            raise PermissionError("Only HOSPITAL users can view hospital dashboard")
        with session_scope() as db:
            self._ensure_seeded(db)
            user = db.query(User).filter(User.id == current_user.id).first()
            if user is None or user.hospital is None:
                raise KeyError("hospital not found")
            hospital = user.hospital
            state = (
                db.query(ExperimentHospitalState)
                .join(Experiment)
                .filter(ExperimentHospitalState.hospital_id == hospital.id)
                .order_by(desc(Experiment.created_at))
                .first()
            )
            experiment_payload = None
            notifications: list[str] = []
            if state is not None:
                experiment_payload = {
                    "job_id": state.experiment.job_id,
                    "status": state.experiment.status,
                    "round_progress": state.experiment.round_progress,
                    "current_round": state.experiment.current_round,
                    "total_rounds": state.experiment.total_rounds,
                    "global_accuracy": state.experiment.global_accuracy,
                    "disease_type": state.experiment.disease_type,
                    "local_accuracy": state.local_accuracy,
                    "previous_accuracy": state.previous_accuracy,
                    "new_accuracy": state.new_accuracy,
                    "notification": state.notification,
                }
                if state.notification:
                    notifications.append(state.notification)
            stats = HospitalDatasetStatsOut(
                hospital_code=hospital.code,
                hospital_name=hospital.name,
                disease_type=hospital.disease_type,
                num_patients=hospital.dataset_rows,
                num_columns=hospital.dataset_columns,
                columns=get_disease_spec(hospital.disease_type).feature_names + ["sepsis_label"] if hospital.disease_type in DATASET_REGISTRY else [],
            )
            return HospitalDashboardOut(user=self._serialize_user(user), hospital=self._serialize_hospital(hospital), active_experiment=experiment_payload, dataset_stats=stats, notifications=notifications)

    def train_hospital_local_model(self, current_user: User, job_id: str | None = None) -> HospitalDashboardOut:
        if current_user.role != "HOSPITAL":
            raise PermissionError("Only hospitals can train locally")
        with session_scope() as db:
            self._ensure_seeded(db)
            user = db.query(User).filter(User.id == current_user.id).first()
            if user is None or user.hospital is None:
                raise KeyError("hospital not found")
            hospital = user.hospital
            experiment = None
            if job_id:
                experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            else:
                experiment = (
                    db.query(Experiment)
                    .join(ExperimentHospitalState)
                    .filter(ExperimentHospitalState.hospital_id == hospital.id)
                    .order_by(desc(Experiment.created_at))
                    .first()
                )
            if experiment is None:
                raise KeyError("experiment not found")
            state = next((item for item in experiment.hospital_states if item.hospital_id == hospital.id), None)
            if state is None:
                raise KeyError("hospital not enrolled in experiment")
            spec = get_disease_spec(experiment.disease_type)
            dataset, stats = build_hospital_dataset(experiment.disease_type, hospital.name)
            current_state = json_to_state_dict(experiment.current_weights)
            privacy_cfg = DifferentialPrivacyConfig(
                enabled=bool(experiment.config.get("dp_enabled", False)),
                clipping_norm=float(experiment.config.get("clipping_norm", 1.0)),
                noise_multiplier=float(experiment.config.get("noise_multiplier", 0.0)),
                seed=experiment.current_round + 42,
            )
            secure_cfg = SecureAggregationConfig(
                enabled=bool(experiment.config.get("secure_aggregation_enabled", False)),
                round_seed=experiment.current_round + 7,
            )
            state.status = "training"
            state.training_progress = 10.0
            local_state, metrics = train_local_model(
                initial_state=current_state,
                dataset=dataset,
                epochs=int(experiment.config.get("epochs", 1)),
                learning_rate=float(experiment.config.get("learning_rate", 0.01)),
                hidden_dim=self._hidden_dim(experiment),
                input_dim=spec.input_dim,
            )
            if privacy_cfg.enabled:
                local_state = clip_and_noise_update(current_state, local_state, privacy_cfg)
            sent_state = local_state
            if secure_cfg.enabled:
                sent_state, _ = mask_state_dict(local_state, seed=secure_cfg.round_seed + hospital.id)
            state.raw_weights_json = state_dict_to_json(local_state)
            state.weights_json = state_dict_to_json(sent_state)
            state.local_accuracy = metrics.accuracy
            state.previous_accuracy = state.local_accuracy if state.previous_accuracy is None else state.previous_accuracy
            state.new_accuracy = None
            state.sample_count = metrics.samples
            state.column_count = stats["num_columns"]
            state.dataset_preview = self._dataset_preview(dataset, spec.feature_names)
            state.training_progress = 100.0
            state.status = "weights sent"
            state.weights_sent_at = _now()
            state.notification = "Weights sent to Ministry ✅"
            state.last_trained_round = experiment.current_round + 1
            hospital.status = "weights sent"
            hospital.dataset_rows = stats["num_patients"]
            hospital.dataset_columns = stats["num_columns"]

            if all(item.status == "weights sent" for item in experiment.hospital_states):
                experiment.status = "training complete"

            return self.get_hospital_dashboard(user)

    def admin_run_fedavg(self, current_user: User, job_id: str) -> AggregateResult:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can run FedAvg")
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            if not self._is_healthcare_experiment(experiment):
                return AggregateResult(job_id=experiment.job_id, status=experiment.status, round_index=experiment.current_round, global_accuracy=experiment.global_accuracy, epsilon=experiment.dp_epsilon, round_progress=experiment.round_progress)
            if any(state.weights_json is None for state in experiment.hospital_states):
                raise ValueError("All hospitals must send weights before aggregation")
            payload = self._combine_healthcare_state(experiment)
            experiment.current_weights = payload
            experiment.current_round = min(experiment.current_round + 1, experiment.total_rounds)
            experiment.round_progress = f"{experiment.current_round}/{experiment.total_rounds}"
            experiment.global_accuracy = self._evaluate_global_accuracy(experiment, payload)
            if experiment.config.get("dp_enabled", False) and float(experiment.config.get("noise_multiplier", 0.0)) > 0:
                experiment.dp_epsilon = compute_dp_epsilon(
                    noise_multiplier=float(experiment.config.get("noise_multiplier", 0.0)),
                    num_rounds=experiment.current_round,
                    num_clients=len(experiment.hospital_states),
                    delta=float(experiment.config.get("dp_delta", 1e-5)),
                )
                experiment.dp_delta = float(experiment.config.get("dp_delta", 1e-5))

            round_loss, round_accuracy = 0.0, 0.0
            total_samples = sum(state.sample_count for state in experiment.hospital_states)
            if total_samples > 0:
                round_accuracy = sum((state.local_accuracy or 0.0) * state.sample_count for state in experiment.hospital_states) / total_samples
            round_obj = ExperimentRound(
                experiment=experiment,
                round_index=experiment.current_round,
                loss=round_loss,
                accuracy=round_accuracy,
                global_accuracy=experiment.global_accuracy,
                total_samples=total_samples,
                global_weights=payload,
            )
            db.add(round_obj)
            for state in experiment.hospital_states:
                metric = ClientMetric(
                    round=round_obj,
                    hospital_id=state.hospital_id,
                    client_id=state.hospital.code,
                    samples=state.sample_count,
                    loss=0.0,
                    accuracy=state.local_accuracy or 0.0,
                    masked=bool(experiment.config.get("secure_aggregation_enabled", False)),
                )
                db.add(metric)
                state.status = "aggregation pending"
                state.notification = "Waiting for Ministry to aggregate... ⏳"
            if experiment.current_round >= experiment.total_rounds:
                experiment.status = "finished"
            else:
                experiment.status = "aggregated"
            return AggregateResult(job_id=experiment.job_id, status=experiment.status, round_index=experiment.current_round, global_accuracy=experiment.global_accuracy, epsilon=experiment.dp_epsilon, round_progress=experiment.round_progress)

    def admin_broadcast_model(self, current_user: User, job_id: str) -> BroadcastResult:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can broadcast models")
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            notifications = self._broadcast_current_model(db, experiment)
            return BroadcastResult(job_id=experiment.job_id, status=experiment.status, notifications=notifications)

    def export_results(self, current_user: User, job_id: str) -> dict[str, Any]:
        if current_user.role != "ADMIN":
            raise PermissionError("Only ADMIN can export results")
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            result = self._serialize_experiment(experiment)
            return result.model_dump() if hasattr(result, "model_dump") else result.dict()

    def list_hospitals_for_experiment(self, job_id: str) -> list[HospitalStateOut]:
        with session_scope() as db:
            self._ensure_seeded(db)
            experiment = db.query(Experiment).filter(Experiment.job_id == job_id).first()
            if experiment is None:
                raise KeyError(job_id)
            return [self._serialize_state(state) for state in experiment.hospital_states]

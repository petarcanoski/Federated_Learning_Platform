from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RoleType = Literal["ADMIN", "HOSPITAL"]
HospitalStatusType = Literal["waiting", "training", "weights sent", "done", "aggregation pending"]


class ExperimentCreateRequest(BaseModel):
    num_clients: int = Field(default=3, ge=1, le=50)
    rounds: int = Field(default=5, ge=1, le=100)
    epochs: int = Field(default=1, ge=1, le=50)
    samples_per_client: int = Field(default=128, ge=8, le=10000)
    learning_rate: float = Field(default=0.01, gt=0)
    hidden_dim: int = Field(default=16, ge=2, le=256)
    dataset_type: Literal["synthetic", "mnist", "cifar10"] = Field(default="synthetic")
    disease_type: Optional[str] = None
    hospital_codes: Optional[List[str]] = None
    dp_enabled: bool = False
    clipping_norm: float = Field(default=1.0, gt=0)
    noise_multiplier: float = Field(default=0.0, ge=0)
    secure_aggregation_enabled: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleType
    username: str
    hospital_id: Optional[int] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: RoleType
    hospital_id: Optional[int] = None
    is_active: bool


class HospitalCreateRequest(BaseModel):
    code: str
    name: str
    city: str
    username: str
    password: str


class HospitalOut(BaseModel):
    id: int
    code: str
    name: str
    city: str
    status: str
    disease_type: str
    dataset_rows: int
    dataset_columns: int
    is_active: bool


class HospitalDatasetStatsOut(BaseModel):
    hospital_code: str
    hospital_name: str
    disease_type: str
    num_patients: int
    num_columns: int
    columns: List[str]


class HospitalStateOut(BaseModel):
    hospital_id: int
    hospital_code: str
    hospital_name: str
    status: HospitalStatusType
    training_progress: float
    sample_count: int
    column_count: int
    local_accuracy: Optional[float] = None
    previous_accuracy: Optional[float] = None
    new_accuracy: Optional[float] = None
    weights_json: Optional[Dict[str, Any]] = None
    notification: Optional[str] = None
    last_trained_round: int
    weights_sent_at: Optional[str] = None
    model_received_at: Optional[str] = None


class AdminDashboardOut(BaseModel):
    admin: UserOut
    hospitals: List[HospitalStateOut]
    experiments: List[Dict[str, Any]] = Field(default_factory=list)


class HospitalDashboardOut(BaseModel):
    user: UserOut
    hospital: HospitalOut
    active_experiment: Optional[Dict[str, Any]] = None
    dataset_stats: HospitalDatasetStatsOut
    notifications: List[str] = Field(default_factory=list)


class ClientMetricOut(BaseModel):
    client_id: str
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    samples: int
    loss: float
    accuracy: float
    masked: bool = False


class ExperimentRoundOut(BaseModel):
    round_index: int
    loss: float
    accuracy: float
    global_accuracy: Optional[float] = None
    total_samples: int
    client_metrics: List[ClientMetricOut]


class ExperimentOut(BaseModel):
    job_id: str
    status: str
    current_round: int
    total_rounds: int
    disease_type: str = "sepsis"
    model_name: str = "simple_classifier"
    round_progress: str = "0/0"
    global_accuracy: Optional[float] = None
    config: Dict[str, Any]
    rounds: List[ExperimentRoundOut]
    current_weights: Dict[str, Any]
    dp_epsilon: float | None = None
    dp_delta: float | None = None
    hospital_states: List[HospitalStateOut] = Field(default_factory=list)


class ExperimentSummary(BaseModel):
    job_id: str
    status: str
    current_round: int
    total_rounds: int
    rounds_completed: int
    disease_type: str = "sepsis"
    global_accuracy: Optional[float] = None
    round_progress: str = "0/0"


class RoundResult(BaseModel):
    job_id: str
    round_index: int
    status: str
    rounds: List[ExperimentRoundOut]
    current_weights: Dict[str, Any]


class AggregateResult(BaseModel):
    job_id: str
    status: str
    round_index: int
    global_accuracy: Optional[float] = None
    epsilon: Optional[float] = None
    round_progress: str


class BroadcastResult(BaseModel):
    job_id: str
    status: str
    notifications: List[str]


class MeOut(BaseModel):
    user: UserOut
    hospital: Optional[HospitalOut] = None



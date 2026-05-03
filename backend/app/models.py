from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    disease_type = Column(String(64), nullable=False, default="sepsis")
    model_name = Column(String(64), nullable=False, default="simple_classifier")
    status = Column(String(32), nullable=False, default="running")
    config = Column(JSON, nullable=False)
    current_round = Column(Integer, default=0, nullable=False)
    total_rounds = Column(Integer, nullable=False)
    current_weights = Column(JSON, nullable=False)
    global_accuracy = Column(Float, default=None, nullable=True)
    # Privacy accounting fields
    dp_epsilon = Column(Float, default=None, nullable=True)  # Computed epsilon for DP experiments
    dp_delta = Column(Float, default=1e-5, nullable=True)
    round_progress = Column(String(32), default="0/0", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    created_by = relationship("User", back_populates="created_experiments")
    rounds = relationship(
        "ExperimentRound",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ExperimentRound.round_index",
    )
    hospital_states = relationship(
        "ExperimentHospitalState",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="ExperimentHospitalState.id",
    )


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    city = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="waiting")
    disease_type = Column(String(64), nullable=False, default="sepsis")
    dataset_rows = Column(Integer, nullable=False, default=0)
    dataset_columns = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="hospital")
    states = relationship("ExperimentHospitalState", back_populates="hospital")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hospital = relationship("Hospital", back_populates="users")
    created_experiments = relationship("Experiment", back_populates="created_by")


class ExperimentHospitalState(Base):
    __tablename__ = "experiment_hospital_states"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(32), nullable=False, default="waiting")
    training_progress = Column(Float, nullable=False, default=0.0)
    sample_count = Column(Integer, nullable=False, default=0)
    column_count = Column(Integer, nullable=False, default=0)
    local_accuracy = Column(Float, nullable=True)
    previous_accuracy = Column(Float, nullable=True)
    new_accuracy = Column(Float, nullable=True)
    weights_json = Column(JSON, nullable=True)
    raw_weights_json = Column(JSON, nullable=True)
    dataset_preview = Column(JSON, nullable=True)
    notification = Column(Text, nullable=True)
    last_trained_round = Column(Integer, nullable=False, default=0)
    weights_sent_at = Column(DateTime(timezone=True), nullable=True)
    model_received_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    experiment = relationship("Experiment", back_populates="hospital_states")
    hospital = relationship("Hospital", back_populates="states")


class ExperimentRound(Base):
    __tablename__ = "experiment_rounds"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    round_index = Column(Integer, nullable=False)
    loss = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=False)
    global_accuracy = Column(Float, nullable=True)
    total_samples = Column(Integer, nullable=False)
    global_weights = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment", back_populates="rounds")
    client_metrics = relationship(
        "ClientMetric",
        back_populates="round",
        cascade="all, delete-orphan",
    )


class ClientMetric(Base):
    __tablename__ = "client_metrics"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("experiment_rounds.id", ondelete="CASCADE"), nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(String(64), nullable=False)
    samples = Column(Integer, nullable=False)
    loss = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=False)
    masked = Column(Boolean, default=False, nullable=False)

    round = relationship("ExperimentRound", back_populates="client_metrics")
    hospital = relationship("Hospital")


from __future__ import annotations

from datetime import datetime, timezone

from mongoengine import BooleanField, DateTimeField, DictField, Document, EmbeddedDocument, EmbeddedDocumentListField, FloatField, IntField, ListField, StringField

from .db import next_sequence


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampedDocument(Document):
    meta = {"abstract": True}

    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = utcnow()
        return super().save(*args, **kwargs)


class ClientMetric(EmbeddedDocument):
    hospital_id = IntField(null=True)
    hospital_name = StringField(null=True)
    client_id = StringField(required=True)
    samples = IntField(required=True)
    loss = FloatField(required=True)
    accuracy = FloatField(required=True)
    masked = BooleanField(default=False)


class ExperimentRound(EmbeddedDocument):
    round_index = IntField(required=True)
    loss = FloatField(required=True)
    accuracy = FloatField(required=True)
    global_accuracy = FloatField(null=True)
    total_samples = IntField(required=True)
    global_weights = DictField(required=True)
    created_at = DateTimeField(default=utcnow)
    client_metrics = EmbeddedDocumentListField(ClientMetric, default=list)


class ExperimentHospitalState(EmbeddedDocument):
    hospital_id = IntField(required=True)
    hospital_code = StringField(required=True)
    hospital_name = StringField(required=True)
    status = StringField(default="waiting")
    training_progress = FloatField(default=0.0)
    sample_count = IntField(default=0)
    column_count = IntField(default=0)
    local_accuracy = FloatField(null=True)
    previous_accuracy = FloatField(null=True)
    new_accuracy = FloatField(null=True)
    weights_json = DictField(null=True)
    raw_weights_json = DictField(null=True)
    dataset_preview = ListField(DictField(), default=list)
    notification = StringField(null=True)
    last_trained_round = IntField(default=0)
    weights_sent_at = DateTimeField(null=True)
    model_received_at = DateTimeField(null=True)
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)


class User(TimestampedDocument):
    meta = {"collection": "users", "indexes": ["username"]}

    id = IntField(primary_key=True, default=lambda: next_sequence("users"))
    username = StringField(required=True, unique=True)
    password_hash = StringField(required=True)
    role = StringField(required=True)
    hospital_id = IntField(null=True)
    is_active = BooleanField(default=True)


class Hospital(TimestampedDocument):
    meta = {"collection": "hospitals", "indexes": ["code"]}

    id = IntField(primary_key=True, default=lambda: next_sequence("hospitals"))
    code = StringField(required=True, unique=True)
    name = StringField(required=True)
    city = StringField(required=True)
    status = StringField(default="waiting")
    disease_type = StringField(default="sepsis")
    dataset_rows = IntField(default=0)
    dataset_columns = IntField(default=0)
    is_active = BooleanField(default=True)


class Experiment(TimestampedDocument):
    meta = {"collection": "experiments", "indexes": ["job_id", "created_at"]}

    id = IntField(primary_key=True, default=lambda: next_sequence("experiments"))
    job_id = StringField(required=True, unique=True)
    created_by_user_id = IntField(null=True)
    disease_type = StringField(default="sepsis")
    model_name = StringField(default="simple_classifier")
    status = StringField(default="running")
    config = DictField(required=True)
    current_round = IntField(default=0)
    total_rounds = IntField(required=True)
    current_weights = DictField(required=True)
    global_accuracy = FloatField(null=True)
    dp_epsilon = FloatField(null=True)
    dp_delta = FloatField(default=1e-5, null=True)
    round_progress = StringField(default="0/0")
    rounds = EmbeddedDocumentListField(ExperimentRound, default=list)
    hospital_states = EmbeddedDocumentListField(ExperimentHospitalState, default=list)


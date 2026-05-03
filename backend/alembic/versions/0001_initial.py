"""Initial federated learning tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'waiting'")),
        sa.Column("disease_type", sa.String(length=64), nullable=False, server_default=sa.text("'sepsis'")),
        sa.Column("dataset_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dataset_columns", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("disease_type", sa.String(length=64), nullable=False, server_default=sa.text("'sepsis'")),
        sa.Column("model_name", sa.String(length=64), nullable=False, server_default=sa.text("'simple_classifier'")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("current_round", sa.Integer(), nullable=False),
        sa.Column("total_rounds", sa.Integer(), nullable=False),
        sa.Column("current_weights", sa.JSON(), nullable=False),
        sa.Column("global_accuracy", sa.Float(), nullable=True),
        sa.Column("round_progress", sa.String(length=32), nullable=False, server_default=sa.text("'0/0'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "experiment_hospital_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'waiting'")),
        sa.Column("training_progress", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("column_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("local_accuracy", sa.Float(), nullable=True),
        sa.Column("previous_accuracy", sa.Float(), nullable=True),
        sa.Column("new_accuracy", sa.Float(), nullable=True),
        sa.Column("weights_json", sa.JSON(), nullable=True),
        sa.Column("raw_weights_json", sa.JSON(), nullable=True),
        sa.Column("dataset_preview", sa.JSON(), nullable=True),
        sa.Column("notification", sa.Text(), nullable=True),
        sa.Column("last_trained_round", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("weights_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "experiment_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("loss", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("global_accuracy", sa.Float(), nullable=True),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("global_weights", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "client_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), sa.ForeignKey("experiment_rounds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("loss", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("masked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_table("client_metrics")
    op.drop_table("experiment_hospital_states")
    op.drop_table("experiment_rounds")
    op.drop_table("experiments")
    op.drop_table("users")
    op.drop_table("hospitals")


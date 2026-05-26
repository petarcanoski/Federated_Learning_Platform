"""Legacy SQLAlchemy migration retained only for historical reference.

MongoDB documents now define the persistence model directly in application code,
so this migration is intentionally a no-op.
"""

from __future__ import annotations


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass


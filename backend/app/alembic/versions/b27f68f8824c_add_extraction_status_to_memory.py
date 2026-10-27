"""add extraction status to memory

Revision ID: b27f68f8824c
Revises: 331ca176af86
Create Date: 2026-10-26 17:38:06.945986

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "b27f68f8824c"
down_revision = "331ca176af86"
branch_labels = None
depends_on = None


def upgrade():
    # Existing memories were extracted (or failed silently) before this column
    # existed; "done" is the honest default and shows no notice
    op.add_column(
        "memory",
        sa.Column(
            "extraction_status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            server_default="done",
            nullable=False,
        ),
    )
    op.add_column(
        "memory",
        sa.Column(
            "extraction_error",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("memory", "extraction_error")
    op.drop_column("memory", "extraction_status")

"""add confirmed_at to extracted memory

Revision ID: f226d932feed
Revises: a9f4e9aa69bd
Create Date: 2026-10-28 16:44:55.776823

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'f226d932feed'
down_revision = 'a9f4e9aa69bd'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('extractedmemory', sa.Column('confirmed_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True))
    # Items the family already corrected count as confirmed (editing confirms), so
    # no correction is lost. Nothing else is backfilled: the rest start unconfirmed
    op.execute(
        sa.text(
            "UPDATE extractedmemory SET confirmed_at = COALESCE(updated_at, now()) "
            "WHERE was_edited"
        )
    )


def downgrade():
    # Lossy for the confirmations themselves, which are derived from what the
    # family confirmed after this migration; no memory text is touched
    op.drop_column('extractedmemory', 'confirmed_at')

"""add was edited to extracted memory

Revision ID: 331ca176af86
Revises: 9d55b22f1179
Create Date: 2026-10-26 17:27:42.896392

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "331ca176af86"
down_revision = "9d55b22f1179"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "extractedmemory",
        sa.Column("was_edited", sa.Boolean(), server_default="false", nullable=False),
    )
    # Items edited so far are the ones with the edited status; a rejected item's
    # earlier state was not recorded, so those stay unmarked
    op.execute(
        sa.text("UPDATE extractedmemory SET was_edited = true WHERE status = 'edited'")
    )


def downgrade():
    op.drop_column("extractedmemory", "was_edited")

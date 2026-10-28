"""add person table

Revision ID: a9f4e9aa69bd
Revises: b27f68f8824c
Create Date: 2026-10-28 14:44:10.718897

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a9f4e9aa69bd'
down_revision = 'b27f68f8824c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('person',
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('other_names', sa.JSON(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_person_owner_id'), 'person', ['owner_id'], unique=False)
    op.add_column('memory', sa.Column('person_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_memory_person_id'), 'memory', ['person_id'], unique=False)
    op.create_foreign_key('memory_person_id_fkey', 'memory', 'person', ['person_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('memory_person_id_fkey', 'memory', type_='foreignkey')
    op.drop_index(op.f('ix_memory_person_id'), table_name='memory')
    op.drop_column('memory', 'person_id')
    op.drop_index(op.f('ix_person_owner_id'), table_name='person')
    op.drop_table('person')

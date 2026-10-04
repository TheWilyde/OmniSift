"""add query_logs table for telemetry

Revision ID: f9d621d3ffb0
Revises: a6c419d26bd9
Create Date: 2026-10-03 23:29:49.260688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f9d621d3ffb0'
down_revision: Union[str, None] = 'a6c419d26bd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'query_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('role', sa.String(length=64), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('dense_matches_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sparse_matches_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('relevance_scores', postgresql.ARRAY(sa.Float()), nullable=False, server_default='{}'),
        sa.Column('retrieval_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('rerank_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('generation_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('prompt_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('has_sufficient_context', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('finish_reason', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_logs_created_at'), 'query_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_query_logs_role'), 'query_logs', ['role'], unique=False)
    op.create_index('ix_query_logs_role_created', 'query_logs', ['role', 'created_at'], unique=False)
    op.create_index('ix_query_logs_user_created', 'query_logs', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_query_logs_user_id'), 'query_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_query_logs_user_id'), table_name='query_logs')
    op.drop_index('ix_query_logs_user_created', table_name='query_logs')
    op.drop_index('ix_query_logs_role_created', table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_role'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_created_at'), table_name='query_logs')
    op.drop_table('query_logs')
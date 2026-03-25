"""add moderation results table

Revision ID: 002
Revises: 001
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS moderation_results (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES advertisements(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'completed', 'failed')),
            is_violation BOOLEAN,
            probability FLOAT,
            error_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMP
        )
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS moderation_results")
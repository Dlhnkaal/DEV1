from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id SERIAL PRIMARY KEY,
            login TEXT NOT NULL,
            password TEXT NOT NULL,
            is_blocked BOOLEAN DEFAULT FALSE
        )
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS account
    """)
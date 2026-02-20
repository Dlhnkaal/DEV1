from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        ALTER TABLE advertisements 
        ADD COLUMN IF NOT EXISTS is_closed BOOLEAN NOT NULL DEFAULT FALSE
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_advertisements_is_closed 
        ON advertisements(is_closed)
    """)

def downgrade():
    op.execute("""
        ALTER TABLE advertisements 
        DROP COLUMN IF EXISTS is_closed
    """)
    
    op.execute("""
        DROP INDEX IF EXISTS idx_advertisements_is_closed
    """)
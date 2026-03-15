"""initial schema

Revision ID: 001
Revises: 
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            login VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            is_verified_seller BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS advertisements (
            id SERIAL PRIMARY KEY,
            seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            category INTEGER NOT NULL,
            images_qty INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_advertisements_seller_id_category 
        ON advertisements(seller_id, category)
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS update_users_updated_at ON users
    """)
    op.execute("""
        CREATE TRIGGER update_users_updated_at 
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS update_advertisements_updated_at ON advertisements
    """)
    op.execute("""
        CREATE TRIGGER update_advertisements_updated_at 
            BEFORE UPDATE ON advertisements
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS advertisements CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE")
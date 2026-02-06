CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    is_verified_seller BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);


CREATE TABLE IF NOT EXISTS advertisements (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category INTEGER NOT NULL CHECK (category >= 0 AND category <= 100),
    images_qty INTEGER NOT NULL CHECK (images_qty >= 0 AND images_qty <= 10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);


CREATE INDEX IF NOT EXISTS idx_advertisements_seller_id ON advertisements(seller_id);
CREATE INDEX IF NOT EXISTS idx_advertisements_category ON advertisements(category);


CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_advertisements_updated_at 
    BEFORE UPDATE ON advertisements
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
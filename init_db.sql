CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_format VARCHAR(10) NOT NULL,
    content_type VARCHAR(50) NOT NULL DEFAULT 'image/jpeg',
    data BYTEA NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    quality INTEGER,
    file_size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_images_id ON images(id);
CREATE INDEX IF NOT EXISTS idx_images_created_at ON images(created_at DESC);

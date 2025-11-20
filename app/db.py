import logging
from typing import Any, Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


class Database:
    """Класс-обёртка для работы с PostgreSQL через asyncpg."""

    def __init__(self, database_url: str) -> None:
        """Инициализация объекта базы данных."""
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Инициализирует пул соединений к базе данных."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
            await self.init_schema()
            logger.info(
                "Database pool created",
                extra={"route": "db.connect"},
            )
        except Exception as exc:
            logger.error(
                f"Failed to connect to database: {exc}",
                extra={"route": "db.connect"},
            )
            raise

    async def init_schema(self) -> None:
        """Создает таблицы при необходимости (CREATE TABLE IF NOT EXISTS)."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
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
                CREATE INDEX IF NOT EXISTS idx_images_created_at
                ON images(created_at DESC);
                """,
            )
        logger.info(
            "Database schema ensured",
            extra={"route": "db.init_schema"},
        )

    async def close(self) -> None:
        """Закрывает пул соединений."""
        if self.pool:
            await self.pool.close()
            logger.info(
                "Database pool closed",
                extra={"route": "db.close"},
            )

    async def save_image(self, data: Dict[str, Any]) -> int:
        """Сохраняет изображение в базу данных."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO images
                (filename, original_format, content_type, data,
                 width, height, quality, file_size)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                data["filename"],
                data["original_format"],
                data["content_type"],
                data["data"],
                data["width"],
                data["height"],
                data.get("quality"),
                data["file_size"],
            )
        image_id = int(row["id"])
        logger.info(
            "Image saved",
            extra={"route": "db.save_image"},
        )
        return image_id

    async def get_image(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Получает изображение по ID из базы данных."""
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, filename, content_type, data, width, height,
                       quality, created_at
                FROM images
                WHERE id = $1
                """,
                image_id,
            )
        logger.info(
            "Image fetched",
            extra={"route": "db.get_image"},
        )
        return dict(row) if row else None

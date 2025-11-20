import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/image_db",
)

BEARER_TOKEN = os.getenv(
    "BEARER_TOKEN",
    "xK6mP2vQ7wR4tY8uI0oP3aS6dF9gH2jK4",
)

HOST = os.getenv("HOST", "0.0.0.0")

PORT = int(os.getenv("PORT", 8080))

MAX_FILE_SIZE = int(
    os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024),
)

MAX_IMAGE_DIMENSION = int(
    os.getenv("MAX_IMAGE_DIMENSION", 10000),
)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/webp",
    "image/tiff",
}

LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOG_FORMAT = (
    "%(asctime)s,%(msecs)d: %(route)s: %(functionName)s: "
    "%(levelname)s: %(message)s"
)

LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

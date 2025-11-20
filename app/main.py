import asyncio
import logging
import os
from typing import Awaitable, Callable, Optional

import aiofiles
from aiohttp import web
from aiohttp_apispec import (
    docs,
    request_schema,
    response_schema,
    setup_aiohttp_apispec,
)

from app.config import (
    ALLOWED_MIME_TYPES,
    BEARER_TOKEN,
    DATABASE_URL,
    HOST,
    LOG_DATE_FORMAT,
    LOG_FILE,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_FILE_SIZE,
    PORT,
)
from app.db import Database
from app.schemas import (
    ErrorSchema,
    ImageResponseSchema,
    LogsQuerySchema,
    LogsResponseSchema,
)
from app.utils import process_image, validate_dimension, validate_quality


class RouteContextFilter(logging.Filter):
    """Фильтр добавляет поле route во все записи логов."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Обогащает запись лога полем route и functionName (требование ТЗ)."""
        if not hasattr(record, "route"):
            record.route = "N/A"
        record.functionName = record.funcName
        return True


def setup_logging() -> None:
    """Настраивает логирование согласно требованиям ТЗ."""
    os.makedirs(
        os.path.dirname(LOG_FILE),
        exist_ok=True,
    )
    formatter = logging.Formatter(
        LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    route_filter = RouteContextFilter()

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(route_filter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(route_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.info(
        "Logging initialized",
        extra={"route": "startup"},
    )


@web.middleware
async def auth_middleware(
    request: web.Request,
    handler: Callable[
        [web.Request],
        Awaitable[web.StreamResponse],
    ],
) -> web.StreamResponse:
    """Middleware для проверки Bearer токена."""
    if request.path.startswith("/api/docs") or request.path.startswith(
        "/static/swagger"
    ):
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger = logging.getLogger(__name__)
        logger.warning(
            "Missing token",
            extra={"route": request.path},
        )
        return web.json_response(
            {"error": "Missing or invalid Authorization header"},
            status=401,
        )
    token = auth_header[7:]
    if token != BEARER_TOKEN:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Invalid token",
            extra={"route": request.path},
        )
        return web.json_response(
            {"error": "Invalid token"},
            status=401,
        )
    return await handler(request)


@web.middleware
async def logging_middleware(
    request: web.Request,
    handler: Callable[
        [web.Request],
        Awaitable[web.StreamResponse],
    ],
) -> web.StreamResponse:
    """Middleware для логирования всех запросов и ответов."""
    logger = logging.getLogger(__name__)
    logger.info(
        f"Request {request.method} {request.path}",
        extra={"route": request.path},
    )
    try:
        response = await handler(request)
        logger.info(
            f"Response {response.status}",
            extra={"route": request.path},
        )
        return response
    except web.HTTPException as exc:
        logger.warning(
            f"HTTP error {exc.status}",
            extra={"route": request.path},
        )
        raise
    except Exception as exc:
        logger.error(
            f"Unhandled error: {exc}",
            extra={"route": request.path},
            exc_info=True,
        )
        raise


@docs(
    tags=["Images"],
    summary="Загрузка и обработка изображения",
    description=("Загружает изображение, конвертирует в JPEG, применяет компрессию."),
    consumes=["multipart/form-data"],
    parameters=[
        {
            "in": "formData",
            "name": "file",
            "type": "file",
            "required": True,
            "description": "Файл изображения",
        },
        {
            "in": "formData",
            "name": "quality",
            "type": "integer",
            "required": False,
            "description": "Качество JPEG (1-100)",
        },
        {
            "in": "formData",
            "name": "x",
            "type": "integer",
            "required": False,
            "description": "Ширина в пикселях",
        },
        {
            "in": "formData",
            "name": "y",
            "type": "integer",
            "required": False,
            "description": "Высота в пикселях",
        },
    ],
)
@response_schema(
    ImageResponseSchema,
    code=201,
    description="Изображение успешно загружено",
)
@response_schema(ErrorSchema, code=400, description="Ошибка валидации")
@response_schema(ErrorSchema, code=401, description="Не авторизован")
@response_schema(ErrorSchema, code=413, description="Файл слишком большой")
@response_schema(ErrorSchema, code=415, description="Неподдерживаемый формат")
@response_schema(
    ErrorSchema,
    code=422,
    description="Ошибка обработки изображения",
)
async def upload_image(request: web.Request) -> web.Response:
    """Обработчик загрузки и обработки изображения."""
    logger = logging.getLogger(__name__)
    if request.content_type != "multipart/form-data":
        logger.warning(
            "Bad content type",
            extra={"route": request.path},
        )
        return web.json_response(
            {"error": "Content-Type must be multipart/form-data"},
            status=400,
        )

    reader = await request.multipart()
    file_bytes: bytes = b""
    filename: Optional[str] = None
    content_type: Optional[str] = None
    quality: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

    async for part in reader:
        if part.name == "file":
            filename = part.filename
            content_type = part.headers.get("Content-Type", "")
            if content_type not in ALLOWED_MIME_TYPES:
                logger.warning(
                    "Unsupported MIME",
                    extra={"route": request.path},
                )
                return web.json_response(
                    {"error": f"Unsupported image format: {content_type}"},
                    status=415,
                )
            while True:
                chunk = await part.read_chunk(8192)
                if not chunk:
                    break
                file_bytes += chunk
                if len(file_bytes) > MAX_FILE_SIZE:
                    logger.warning(
                        "File too large",
                        extra={"route": request.path},
                    )
                    return web.json_response(
                        {"error": "File too large"},
                        status=413,
                    )
        elif part.name == "quality":
            try:
                quality = validate_quality(await part.text())
            except ValueError as exc:
                logger.warning(
                    f"Validation error: {exc}",
                    extra={"route": request.path},
                )
                return web.json_response({"error": str(exc)}, status=400)
        elif part.name == "x":
            try:
                width = validate_dimension(await part.text())
            except ValueError as exc:
                logger.warning(
                    f"Validation error: {exc}",
                    extra={"route": request.path},
                )
                return web.json_response({"error": str(exc)}, status=400)
        elif part.name == "y":
            try:
                height = validate_dimension(await part.text())
            except ValueError as exc:
                logger.warning(
                    f"Validation error: {exc}",
                    extra={"route": request.path},
                )
                return web.json_response({"error": str(exc)}, status=400)

    if filename:
        filename = os.path.basename(filename)
    if not file_bytes or not filename or not content_type:
        logger.warning(
            "No file provided",
            extra={"route": request.path},
        )
        return web.json_response({"error": "No file provided"}, status=400)
    if filename.startswith("."):
        logger.warning(
            "Invalid filename",
            extra={"route": request.path},
        )
        return web.json_response({"error": "Invalid filename"}, status=400)

    loop = asyncio.get_event_loop()
    try:
        (
            processed_bytes,
            final_w,
            final_h,
            final_quality,
        ) = await loop.run_in_executor(
            None,
            process_image,
            file_bytes,
            content_type.split("/")[-1],
            quality,
            width,
            height,
        )
    except Exception as exc:
        logger.error(
            f"Image processing failed: {exc}",
            extra={"route": request.path},
        )
        return web.json_response(
            {"error": "Failed to process image"},
            status=422,
        )

    db: Database = request.app["db"]
    image_id = await db.save_image(
        {
            "filename": filename,
            "original_format": content_type.split("/")[-1],
            "content_type": "image/jpeg",
            "data": processed_bytes,
            "width": final_w,
            "height": final_h,
            "quality": final_quality,
            "file_size": len(processed_bytes),
        },
    )
    logger.info(
        "Image stored",
        extra={"route": request.path},
    )
    return web.json_response(
        {
            "id": image_id,
            "filename": filename,
            "width": final_w,
            "height": final_h,
            "quality": final_quality,
            "size": len(processed_bytes),
        },
        status=201,
    )


@docs(
    tags=["Images"],
    summary="Получение изображения по ID",
    description="Возвращает сохранённое изображение из базы данных.",
    parameters=[
        {
            "in": "path",
            "name": "id",
            "schema": {"type": "integer"},
            "required": True,
            "description": "ID изображения",
        }
    ],
    responses={
        "200": {
            "description": "Изображение найдено",
            "content": {"image/jpeg": {}},
        }
    },
)
@response_schema(ErrorSchema, code=400, description="Неверный ID")
@response_schema(ErrorSchema, code=401, description="Не авторизован")
@response_schema(ErrorSchema, code=404, description="Изображение не найдено")
async def get_image(
    request: web.Request,
) -> web.StreamResponse:
    """Обработчик получения изображения по ID."""
    logger = logging.getLogger(__name__)
    try:
        image_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return web.json_response(
            {"error": "Invalid image ID"},
            status=400,
        )
    db: Database = request.app["db"]
    image = await db.get_image(image_id)
    if not image:
        logger.warning(
            "Image not found",
            extra={"route": request.path},
        )
        return web.json_response({"error": "Image not found"}, status=404)
    logger.info(
        "Image returned",
        extra={"route": request.path},
    )
    return web.Response(
        body=image["data"],
        content_type=image["content_type"],
        headers={
            "Content-Disposition": (f'inline; filename="{image["filename"]}"'),
        },
    )


@docs(
    tags=["Logs"],
    summary="Чтение логов приложения",
    description="Возвращает последние строки из лог-файла.",
)
@request_schema(LogsQuerySchema, location="query")
@response_schema(LogsResponseSchema, code=200, description="Логи получены")
@response_schema(ErrorSchema, code=400, description="Неверный параметр lines")
@response_schema(ErrorSchema, code=401, description="Не авторизован")
async def get_logs(request: web.Request) -> web.Response:
    """Обработчик чтения логов."""
    logger = logging.getLogger(__name__)
    try:
        lines = int(request.query.get("lines", 100))
    except ValueError:
        return web.json_response(
            {"error": "Invalid lines parameter"},
            status=400,
        )
    lines = max(1, min(lines, 1000))
    if not os.path.exists(LOG_FILE):
        return web.json_response({"logs": []})
    async with aiofiles.open(
        LOG_FILE,
        "r",
        encoding="utf-8",
    ) as log_file:
        content = await log_file.read()
    log_lines = content.strip().split("\n") if content else []
    payload = log_lines[-lines:] if len(log_lines) > lines else log_lines
    logger.info(
        "Logs returned",
        extra={"route": request.path},
    )
    return web.json_response(
        {
            "total_lines": len(log_lines),
            "returned_lines": len(payload),
            "logs": payload,
        }
    )


async def on_startup(app: web.Application) -> None:
    """Инициализирует подключение к базе данных при запуске."""
    logger = logging.getLogger(__name__)
    db = Database(DATABASE_URL)
    await db.connect()
    app["db"] = db
    logger.info(
        "Startup complete",
        extra={"route": "startup"},
    )


async def on_cleanup(app: web.Application) -> None:
    """Закрывает соединения с базой данных при остановке."""
    logger = logging.getLogger(__name__)
    db: Optional[Database] = app.get("db")
    if db:
        await db.close()
    logger.info(
        "Cleanup done",
        extra={"route": "shutdown"},
    )


def setup_routes(app: web.Application) -> None:
    """Регистрирует маршруты приложения."""
    app.router.add_post("/images", upload_image)
    app.router.add_get("/images/{id}", get_image)
    app.router.add_get("/logs", get_logs)


def create_app() -> web.Application:
    """Создаёт и настраивает aiohttp приложение."""
    setup_logging()
    app = web.Application(
        middlewares=[
            logging_middleware,
            auth_middleware,
        ],
        client_max_size=MAX_FILE_SIZE,
    )
    setup_routes(app)
    setup_aiohttp_apispec(
        app=app,
        title="Image Processing API",
        version="1.0.0",
        url="/api/docs/swagger.json",
        swagger_path="/api/docs",
        description=(
            "Асинхронное API для обработки изображений. "
            "Все эндпоинты требуют Bearer токен."
        ),
        securityDefinitions={
            "bearerAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Введи: Bearer xK6mP2vQ7wR4tY8uI0oP3aS6dF9gH2jK4",
            }
        },
        security=[{"bearerAuth": []}],
    )
    app.on_startup.append(on_startup)  # type: ignore[arg-type]
    app.on_cleanup.append(on_cleanup)  # type: ignore[arg-type]
    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host=HOST,
        port=PORT,
    )

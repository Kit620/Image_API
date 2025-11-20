"""Marshmallow схемы для валидации и документации API."""

from marshmallow import Schema, fields


class ErrorSchema(Schema):
    """Схема ответа с ошибкой."""

    error = fields.Str(
        required=True,
        metadata={"description": "Описание ошибки"},
    )


class ImageResponseSchema(Schema):
    """Схема ответа с метаданными изображения."""

    id = fields.Int(
        required=True,
        metadata={"description": "ID изображения в базе данных"},
    )
    filename = fields.Str(
        required=True,
        metadata={"description": "Имя файла"},
    )
    width = fields.Int(
        required=True,
        metadata={"description": "Ширина изображения в пикселях"},
    )
    height = fields.Int(
        required=True,
        metadata={"description": "Высота изображения в пикселях"},
    )
    quality = fields.Int(
        allow_none=True,
        metadata={"description": "Качество JPEG (1-100)"},
    )
    size = fields.Int(
        required=True,
        metadata={"description": "Размер файла в байтах"},
    )


class LogsQuerySchema(Schema):
    """Схема query параметров для получения логов."""

    lines = fields.Int(
        required=False,
        missing=100,
        validate=lambda x: 1 <= x <= 1000,
        metadata={
            "description": "Количество строк (по умолчанию 100, макс 1000)",
            "example": 100,
        },
    )


class LogsResponseSchema(Schema):
    """Схема ответа с логами."""

    total_lines = fields.Int(
        required=True,
        metadata={"description": "Всего строк в файле логов"},
    )
    returned_lines = fields.Int(
        required=True,
        metadata={"description": "Количество возвращённых строк"},
    )
    logs = fields.List(
        fields.Str(),
        required=True,
        metadata={"description": "Массив строк логов"},
    )

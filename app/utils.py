import io
import logging
from typing import Any, Optional, Tuple, cast

from PIL import Image

from app.config import MAX_IMAGE_DIMENSION

logger = logging.getLogger(__name__)

ImageType = Any


def process_image(
    file_bytes: bytes,
    original_format: str,
    quality: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Tuple[bytes, int, int, Optional[int]]:
    """
    Обработка изображения согласно ТЗ.

    Пункт 2: Конвертирование отличного от JPEG в JPEG.
    Пункт 4: Компрессия только при заданных параметрах.
    """
    is_jpeg = original_format.lower() in ("jpeg", "jpg")
    has_compression_params = (
        quality is not None or width is not None or height is not None
    )

    image: ImageType = Image.open(io.BytesIO(file_bytes))

    if is_jpeg and not has_compression_params:
        final_w, final_h = image.size
        logger.info(
            "JPEG file saved without conversion",
            extra={"route": "utils.process_image"},
        )
        return file_bytes, final_w, final_h, None

    if not is_jpeg:
        if image.mode in ("RGBA", "LA", "P"):
            background: ImageType = Image.new(
                "RGB",
                image.size,
                cast(Any, (255, 255, 255)),
            )
            if image.mode == "P":
                image = image.convert("RGBA")
            mask: Optional[ImageType] = (
                image.split()[-1] if image.mode in ("RGBA", "LA") else None
            )
            background.paste(image, mask=mask)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        logger.info(
            "Image converted to RGB",
            extra={"route": "utils.process_image"},
        )

    if width or height:
        orig_w, orig_h = cast(Tuple[int, int], image.size)
        if width and not height:
            height = int(orig_h * (width / orig_w))
        elif height and not width:
            width = int(orig_w * (height / orig_h))
        width = min(width or orig_w, MAX_IMAGE_DIMENSION)
        height = min(height or orig_h, MAX_IMAGE_DIMENSION)
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        logger.info(
            "Image resized",
            extra={"route": "utils.process_image"},
        )

    if has_compression_params:
        compression_quality = quality if quality is not None else 85
    else:
        compression_quality = None

    buffer = io.BytesIO()
    if compression_quality is not None:
        image.save(
            buffer,
            format="JPEG",
            quality=compression_quality,
            optimize=True,
        )
        logger.info(
            "Image compressed with quality",
            extra={"route": "utils.process_image"},
        )
    else:
        image.save(buffer, format="JPEG", quality=100)
        logger.info(
            "Image converted to JPEG without compression",
            extra={"route": "utils.process_image"},
        )
    jpeg_bytes = buffer.getvalue()
    final_w, final_h = image.size
    logger.info(
        "Image processed",
        extra={"route": "utils.process_image"},
    )
    return jpeg_bytes, final_w, final_h, compression_quality


def validate_quality(value: Optional[str]) -> Optional[int]:
    """Валидация параметра quality (1-100)."""
    if value is None or value == "":
        return None
    try:
        quality = int(value)
    except ValueError as exc:
        raise ValueError("Quality must be integer") from exc
    if not 1 <= quality <= 100:
        raise ValueError("Quality must be between 1 and 100")
    return quality


def validate_dimension(value: Optional[str]) -> Optional[int]:
    """Валидация размеров изображения."""
    if value is None or value == "":
        return None
    try:
        dimension = int(value)
    except ValueError as exc:
        raise ValueError("Dimension must be integer") from exc
    if dimension <= 0:
        raise ValueError("Dimension must be positive")
    if dimension > MAX_IMAGE_DIMENSION:
        raise ValueError(f"Dimension must be <= {MAX_IMAGE_DIMENSION}")
    return dimension

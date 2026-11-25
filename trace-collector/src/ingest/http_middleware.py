"""HTTP middleware: согласование Content-Type и базовая валидация запроса."""
from typing import Tuple


SUPPORTED_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
}


def check_content_type(header: str | None) -> Tuple[bool, str]:
    """Проверяет Content-Type запроса.

    Возвращает (ok, message):
      ok=True  — тип поддерживается
      ok=False — message содержит причину отказа (для 415)
    """
    if not header:
        return False, "missing Content-Type header"

    # нормализуем: нижний регистр, убираем пробелы вокруг ';'
    normalized = ";".join(part.strip().lower() for part in header.split(";"))
    if normalized in SUPPORTED_CONTENT_TYPES:
        return True, ""

    # допустим любой application/json с произвольным charset
    if normalized.startswith("application/json"):
        return True, ""

    return False, f"unsupported Content-Type: {header}"


def validate_content_length(header: str | None, max_bytes: int = 1_048_576) -> Tuple[bool, str]:
    """Проверяет наличие и допустимость Content-Length.

    max_bytes по умолчанию 1 МиБ — защита от переполнения.
    """
    if header is None:
        return False, "missing Content-Length"
    try:
        n = int(header)
    except ValueError:
        return False, "Content-Length must be integer"
    if n <= 0:
        return False, "Content-Length must be positive"
    if n > max_bytes:
        return False, f"Content-Length exceeds {max_bytes} bytes"
    return True, ""
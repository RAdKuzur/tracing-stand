from typing import Tuple


SUPPORTED_CONTENT_TYPES = {
    "application/json",
    "application/json; charset=utf-8",
    "application/json;charset=utf-8",
}


def check_content_type(header: str | None) -> Tuple[bool, str]:
    if not header:
        return False, "missing Content-Type header"

    normalized = ";".join(part.strip().lower() for part in header.split(";"))
    if normalized in SUPPORTED_CONTENT_TYPES:
        return True, ""

    if normalized.startswith("application/json"):
        return True, ""

    return False, f"unsupported Content-Type: {header}"


def validate_content_length(header: str | None, max_bytes: int = 1_048_576) -> Tuple[bool, str]:
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
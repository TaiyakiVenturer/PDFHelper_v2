from __future__ import annotations

from schemas.response import ErrorMessage


def classify_error_message(stage: str, message: str) -> tuple[str, str, bool]:
    normalized = message.lower().strip()

    if "not implemented" in normalized or "尚未實作" in normalized:
        return f"NIM_{stage.upper()}_NOT_IMPLEMENTED", "not_implemented", False

    if "invalid request payload" in normalized:
        return f"REQ_{stage.upper()}_INVALID_PAYLOAD", "request", False

    if "no request payload" in normalized:
        return f"REQ_{stage.upper()}_PAYLOAD_TIMEOUT", "request", True

    if "absolute path" in normalized:
        return f"INP_{stage.upper()}_ABSOLUTE_PATH_REQUIRED", "input", False

    if "not found" in normalized:
        return f"INP_{stage.upper()}_FILE_NOT_FOUND", "input", False

    if "must be a list" in normalized:
        return f"INP_{stage.upper()}_INVALID_JSON_STRUCTURE", "input", False

    if "cli not found" in normalized or "未安裝" in normalized:
        return f"DEP_{stage.upper()}_MISSING_DEPENDENCY", "dependency", False

    if "execution failed" in normalized or "return code" in normalized:
        return f"DEP_{stage.upper()}_EXTERNAL_EXECUTION_FAILED", "dependency", True

    if "output" in normalized and "missing" in normalized:
        return f"PIPE_{stage.upper()}_OUTPUT_MISSING", "pipeline", False

    if "no chunks" in normalized or "0 chunks" in normalized:
        return f"PIPE_{stage.upper()}_NO_CHUNKS", "pipeline", False

    if "stage is busy" in normalized or "another stage" in normalized:
        return f"REQ_{stage.upper()}_STAGE_BUSY", "request", True

    return f"SYS_{stage.upper()}_UNEXPECTED", "system", False


def build_error_message(
    *,
    stage: str,
    message: str,
    code: str | None = None,
    category: str | None = None,
    retryable: bool | None = None,
    detail: str | None = None,
) -> ErrorMessage:
    if code is None or category is None or retryable is None:
        inferred_code, inferred_category, inferred_retryable = classify_error_message(
            stage,
            message,
        )
        if code is None:
            code = inferred_code
        if category is None:
            category = inferred_category
        if retryable is None:
            retryable = inferred_retryable

    if category is not None and not isinstance(category, str):
        category = str(getattr(category, "value", category))

    return ErrorMessage(
        code=code,
        category=category,
        message=message,
        stage=stage,
        retryable=retryable,
        detail=detail,
    )

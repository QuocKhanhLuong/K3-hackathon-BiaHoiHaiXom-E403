"""Typed application errors that are safe to map to public HTTP responses."""


class BackendError(Exception):
    """Base class for expected backend errors."""

    code = "BACKEND_ERROR"
    status_code = 500
    public_message = "Không thể hoàn tất yêu cầu."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)


class ResourceNotFoundError(BackendError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404
    public_message = "Không tìm thấy tài nguyên được yêu cầu."


class ConflictError(BackendError):
    code = "STATE_CONFLICT"
    status_code = 409
    public_message = "Trạng thái hiện tại không cho phép thao tác này."


class InvalidActionError(BackendError):
    code = "INVALID_ACTION"
    status_code = 400
    public_message = "Phản hồi không hợp lệ hoặc hành động đã kết thúc."


class AIServiceError(BackendError):
    code = "AI_SERVICE_UNAVAILABLE"
    status_code = 503
    public_message = "Trợ lý AI tạm thời chưa thể xử lý yêu cầu."

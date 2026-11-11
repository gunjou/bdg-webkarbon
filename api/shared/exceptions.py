# api/shared/exceptions.py

class AppError(Exception):
    def __init__(
        self,
        message,
        code="APP_ERROR",
        status_code=400,
        errors=None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.errors = errors
        super().__init__(message)


class AuthError(AppError):
    def __init__(self, message="Unauthorized"):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=401
        )


class ForbiddenError(AppError):
    def __init__(self, message="Forbidden"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403
        )


class NotFoundError(AppError):
    def __init__(self, message="Data tidak ditemukan"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404
        )


class ValidationError(AppError):
    def __init__(self, message="Validasi gagal", errors=None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            errors=errors
        )


class DatabaseError(AppError):
    def __init__(self, message="Kesalahan database"):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500
        )

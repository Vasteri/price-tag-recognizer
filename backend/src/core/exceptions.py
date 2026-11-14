class AppException(Exception):
    status_code: int = 500
    default_message: str = "Internal error"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class BadRequestError(AppException):
    status_code = 400
    default_message = "Некорректный запрос"


class UnsupportedMediaTypeError(AppException):
    status_code = 415
    default_message = "Неподдерживаемый формат"


class PayloadTooLargeError(AppException):
    status_code = 413
    default_message = "Файл слишком большой"


class TaskNotReadyError(AppException):
    status_code = 409
    default_message = "Результат ещё не готов"
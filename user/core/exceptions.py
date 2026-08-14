class TutorError(Exception):
    def __init__(self, detail: str, status_code: int = 400, extra: dict = None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.extra = extra or {}
"""
Structured exception types for the AI Digital Tutor backend.

Replace bare `except Exception` with specific catches + this hierarchy.
Middleware in serve.py catches unhandled TutorError subtypes and returns
proper HTTP responses.
"""


class TutorError(Exception):
    """Base exception for all tutor-related errors."""
    status_code: int = 500
    detail: str = "Internal tutor error"

    def __init__(self, detail: str = None, **extra):
        self.detail = detail or self.__class__.detail
        self.extra = extra
        super().__init__(self.detail)


class LLMError(TutorError):
    """All LLM models failed or timed out."""
    status_code = 503
    detail = "AI model unavailable — please try again shortly"


class LLMParseError(TutorError):
    """LLM returned unparseable or invalid response."""
    status_code = 502
    detail = "AI returned an invalid response — retrying may help"


class StudentNotFoundError(TutorError):
    """Student record not found in DB."""
    status_code = 404
    detail = "Student not found"


class CurriculumNotFoundError(TutorError):
    """Curriculum or subject not found."""
    status_code = 404
    detail = "Curriculum not found for this subject"


class QuizNotFoundError(TutorError):
    """Active quiz not found."""
    status_code = 404
    detail = "Quiz session not found or expired"


class MasteryGateError(TutorError):
    """Student hasn't met prerequisite mastery threshold."""
    status_code = 403
    detail = "Prerequisites not yet mastered"


class RateLimitError(TutorError):
    """User hit daily LLM budget."""
    status_code = 429
    detail = "Daily learning limit reached — come back tomorrow"


class ValidationError(TutorError):
    """Input validation failed beyond Pydantic."""
    status_code = 422
    detail = "Invalid input"


class InjectionDetectedError(TutorError):
    """Prompt injection attempt detected."""
    status_code = 400
    detail = "Invalid input detected"

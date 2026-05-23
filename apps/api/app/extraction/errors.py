"""Errors surfaced when LLM claim extraction cannot run."""


class ExtractionAPIError(Exception):
    """OpenAI (or compatible API) rejected the request — do not silently ignore."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

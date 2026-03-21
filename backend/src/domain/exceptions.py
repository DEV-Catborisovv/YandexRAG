from __future__ import annotations
from typing import Any

class AppException(Exception):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

class InfrastructureException(AppException):
    pass

class ExternalAPIException(InfrastructureException):
    def __init__(self, service: str, status_code: int, detail: str) -> None:
        super().__init__(f"Error from {service}: [{status_code}] {detail}")
        self.service = service
        self.status_code = status_code
        self.detail = detail

class DomainException(AppException):
    pass

class ConfigurationException(AppException):
    pass

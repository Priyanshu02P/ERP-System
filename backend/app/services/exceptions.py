class ServiceError(Exception):
    """Base class for all business-rule errors raised by the service layer."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(ServiceError):
    """Raised when a requested entity does not exist."""


class ConflictError(ServiceError):
    """Raised when an operation would violate a uniqueness or state constraint."""


class ValidationError(ServiceError):
    """Raised when input fails a business rule (distinct from Pydantic schema validation)."""


class ReferencedEntityError(ServiceError):
    """Raised when deletion is blocked because other records still reference this entity."""

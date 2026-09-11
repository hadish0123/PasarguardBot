class DomainError(Exception):
    """Expected business error safe to show to a Telegram user."""


class PermissionDenied(DomainError):
    pass


class ValidationError(DomainError):
    pass


class ExternalServiceError(DomainError):
    pass

"""Domain exceptions — no HTTP semantics here; mapping lives in main.py."""


class GovernanceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(GovernanceError):
    def __init__(self, entity: str, entity_id: str) -> None:
        super().__init__("not_found", f"{entity} '{entity_id}' not found.")


class IllegalTransition(GovernanceError):
    def __init__(self, from_status: str | None, to_status: str) -> None:
        super().__init__(
            "illegal_transition",
            f"No transition rule from '{from_status}' to '{to_status}'.",
        )


class MissingRequiredField(GovernanceError):
    def __init__(self, field: str) -> None:
        super().__init__("missing_required_field", f"Required field '{field}' is missing.")
        self.field = field


class MissingRequiredAttachment(GovernanceError):
    def __init__(self) -> None:
        super().__init__(
            "missing_required_attachment",
            "This transition requires at least one attachment.",
        )


class IdempotencyConflict(GovernanceError):
    def __init__(self, key: str) -> None:
        super().__init__(
            "idempotency_conflict",
            f"Idempotency key '{key}' already used with different payload.",
        )


class TenantIsolationViolation(GovernanceError):
    def __init__(self) -> None:
        super().__init__("tenant_isolation_violation", "Cross-tenant access denied.")

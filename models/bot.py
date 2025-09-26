from typing import Literal, TypedDict


ModuleType = Literal["register", "tasks", "stats", "accounts", "verify", "login"]


class OperationResult(TypedDict):
    email: str
    email_password: str
    data: dict | str | None
    status: bool

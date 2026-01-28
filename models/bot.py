from typing import Literal, TypedDict, Union, Optional


ModuleType = Literal["register", "tasks", "stats", "accounts", "verify", "login"]


class OperationResult(TypedDict):
    email: str
    email_password: str
    data: Optional[Union[dict, str]]
    status: bool

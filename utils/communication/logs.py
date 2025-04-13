from models import OperationResult, StatisticData


def operation_failed(email: str, password: str) -> OperationResult:
    return OperationResult(
        identifier=email,
        data=password,
        status=False,
    )


def operation_success(email: str, password: str) -> OperationResult:
    return OperationResult(
        identifier=email,
        data=password,
        status=True,
    )


def operation_export_stats_success(user_info: dict) -> StatisticData:
    return StatisticData(
        success=True,
        referralPoint=user_info["referralPoint"],
        rewardPoint=user_info["rewardPoint"],
    )


def operation_export_stats_failed() -> StatisticData:
    return StatisticData(
        success=False,
        referralPoint=None,
        rewardPoint=None,
    )


def validate_error(error: Exception) -> str:
    error_message = str(error).lower()

    if (
        "curl: (7)" in error_message
        or "curl: (28)" in error_message
        or "curl: (16)" in error_message
        or "connect tunnel failed" in error_message
    ):
        return "Proxy failed"

    elif "timed out" in error_message or "operation timed out" in error_message:
        return "Connection timed out"

    elif "empty document" in error_message or "expecting value" in error_message:
        return "Received empty response"

    elif (
        "curl: (35)" in error_message
        or "curl: (97)" in error_message
        or "eof" in error_message
        or "curl: (56)" in error_message
        or "ssl" in error_message
    ):
        return "SSL Error. If there are a lot of such errors, try installing certificates."

    elif "417 Expectation Failed" in error_message:
        return "417 Expectation Failed"

    elif "unsuccessful tunnel" in error_message:
        return "Unsuccessful TLS Tunnel"

    elif "connection error" in error_message:
        return "Connection Error"

    else:
        return error_message

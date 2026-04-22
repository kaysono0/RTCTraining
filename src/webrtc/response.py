def success_payload(data=None):
    return {"ok": True, "data": data if data is not None else {}}


def error_payload(code, message, details=None):
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        },
    }

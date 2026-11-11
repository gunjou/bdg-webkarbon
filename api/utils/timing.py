# api/utils/timing.py
import time
from functools import wraps


def measure_execution_time(fn):
    """Tambahkan meta.execution_time_ms pada response (body, status_code)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        response = fn(*args, **kwargs)
        execution_time = round((time.perf_counter() - start_time) * 1000, 2)

        if isinstance(response, tuple) and len(response) == 2 and isinstance(response[0], dict):
            body, status = response
            body["meta"] = {**(body.get("meta") or {}), "execution_time_ms": execution_time}
            return body, status
        return response
    return wrapper

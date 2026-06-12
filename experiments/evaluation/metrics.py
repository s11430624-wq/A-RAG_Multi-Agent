from experiments.runtime.patching import InvalidPatchError, PatchApplyError
from experiments.runtime.workspace import CleanupError

class EmptyResponseError(Exception):
    """Raised when the generated patch is None, empty, or pure commentary."""
    pass

class TestTimeoutError(Exception):
    """Raised when test execution times out."""
    __test__ = False

class RunnerError(Exception):
    """Raised on test runner errors, such as pytest collection errors, or malformed XML output."""
    pass

class MetricsCollector:
    """
    Centralized collector mapping exceptions and run results to standardized error metrics.
    Guarantees valid_run == (not infra_error).
    """
    @staticmethod
    def get_metrics_for_exception(exc: Exception) -> dict:
        if isinstance(exc, EmptyResponseError):
            return {
                "error_type": "empty_response",
                "infra_error": False,
                "valid_run": True,
                "stop_reason": "repair_limit"
            }
        elif isinstance(exc, InvalidPatchError):
            return {
                "error_type": "invalid_patch",
                "infra_error": False,
                "valid_run": True,
                "stop_reason": "repair_limit"
            }
        elif isinstance(exc, PatchApplyError):
            return {
                "error_type": "patch_apply_error",
                "infra_error": False,
                "valid_run": True,
                "stop_reason": "repair_limit"
            }
        elif isinstance(exc, TestTimeoutError):
            return {
                "error_type": "test_timeout",
                "infra_error": True,
                "valid_run": False,
                "stop_reason": "infra_error"
            }
        elif isinstance(exc, (RunnerError, CleanupError)):
            return {
                "error_type": "runner_error",
                "infra_error": True,
                "valid_run": False,
                "stop_reason": "infra_error"
            }
        else:
            return {
                "error_type": "unknown",
                "infra_error": True,
                "valid_run": False,
                "stop_reason": "infra_error"
            }

    @staticmethod
    def get_success_metrics() -> dict:
        return {
            "error_type": "none",
            "infra_error": False,
            "valid_run": True,
            "stop_reason": "public_pass"
        }

    @staticmethod
    def get_repair_limit_metrics() -> dict:
        return {
            "error_type": "none",
            "infra_error": False,
            "valid_run": True,
            "stop_reason": "repair_limit"
        }

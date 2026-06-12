import json
import time
from pathlib import Path
from typing import Dict, Any, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from experiments.runtime.workspace import WorkspaceManager, WorkspaceError, CleanupError
from experiments.runtime.patching import PatchEngine, InvalidPatchError, PatchApplyError
from experiments.runtime.test_runner import SecureTestRunner
from experiments.evaluation.metrics import (
    MetricsCollector,
    EmptyResponseError,
    TestTimeoutError,
    RunnerError,
)

class PublicFeedbackRecord:
    """
    Sanitized public feedback history for the repair strategy / caller.
    Does NOT contain hidden passed/total, path, name, or outputs.
    """
    def __init__(self, round_index: int, sanitized_public_feedback: str,
                 public_passed: bool, public_passed_count: int, public_total: int):
        self.round_index = round_index
        self.sanitized_public_feedback = sanitized_public_feedback
        self.public_passed = public_passed
        self.public_passed_count = public_passed_count
        self.public_total = public_total

class PrivateAuditRecord:
    """
    Evaluator-only private audit structure containing detailed run metrics
    including hidden tests results.
    """
    def __init__(self, round_index: int, hidden_passed_count: int, hidden_total: int):
        self.round_index = round_index
        self.hidden_passed_count = hidden_passed_count
        self.hidden_total = hidden_total

class Evaluator:
    """
    Core experimental evaluation engine (M3.2).
    """
    def __init__(self, task_config_path: str | Path | None = None):
        if task_config_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            self.task_config_path = project_root / "experiments" / "tasks.json"
        else:
            self.task_config_path = Path(task_config_path).resolve()
            
        self.tasks: Dict[str, Any] = {}
        self.public_feedback_history: list[PublicFeedbackRecord] = []
        self._private_audit_records: list[PrivateAuditRecord] = []
        self._load_and_validate_tasks()
        
    def _load_and_validate_tasks(self) -> None:
        project_root = self.task_config_path.parent.parent
        task_schema_path = project_root / "contracts" / "task.schema.json"
        
        if not self.task_config_path.exists():
            raise FileNotFoundError(f"Tasks configuration file not found at {self.task_config_path}")
            
        try:
            with open(self.task_config_path, "r", encoding="utf-8") as f:
                tasks_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse tasks JSON: {e}")
            
        if not isinstance(tasks_data, list):
            raise ValueError("tasks.json must contain a JSON array of tasks")
            
        # Load schema
        if not task_schema_path.exists():
            raise FileNotFoundError(f"Task schema not found at {task_schema_path}")
            
        try:
            with open(task_schema_path, "r", encoding="utf-8") as f:
                task_schema = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse task schema: {e}")
            
        validator = Draft202012Validator(task_schema)
        
        for idx, task in enumerate(tasks_data):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {idx} must be a JSON object")
            if "task_id" not in task:
                raise ValueError(f"Task at index {idx} is missing 'task_id'")
                
            # Validate task schema
            try:
                validator.validate(task)
            except ValidationError as ve:
                raise ValueError(f"Task {task.get('task_id', f'at index {idx}')} failed schema validation: {ve.message}")
                
            self.tasks[task["task_id"]] = task

    def evaluate_task(self, task_id: str, 
                      initial_patch: str | None, 
                      repair_patches: Sequence[str] = (),
                      max_repair_rounds: int = 2,
                      **kwargs) -> Dict[str, Any]:
        """
        Runs evaluation on a task including Pass 1 and Pass 2 repair rounds.
        Returns validated result dictionary compliant with result.schema.json.
        """
        # Reset feedback history and audit records for this execution run
        self.public_feedback_history = []
        self._private_audit_records = []

        # Resolve paths
        project_root = self.task_config_path.parent.parent
        snapshot_path = project_root / "student_system" / "SNAPSHOT.json"
        result_schema_path = project_root / "contracts" / "result.schema.json"
        
        # Validate requested max_repair_rounds limit (negative/bool/float/string must be rejected)
        if max_repair_rounds is not None:
            if not isinstance(max_repair_rounds, int) or isinstance(max_repair_rounds, bool):
                raise ValueError("max_repair_rounds must be an integer")
            if max_repair_rounds < 0:
                raise ValueError("max_repair_rounds cannot be negative")

        # Prepare basic fields
        run_id = kwargs.get("run_id", f"run_{task_id.lower()}")
        strategy = kwargs.get("strategy", "A")
        repetition = kwargs.get("repetition", 1)
        model = kwargs.get("model", "deterministic-fixture")
        seed = kwargs.get("seed", 42)
        tool_calls = kwargs.get("tool_calls", 0)
        retrieved_tokens = kwargs.get("retrieved_tokens", 0)
        retrieval_success = kwargs.get("retrieval_success", None)
        input_tokens = kwargs.get("input_tokens", 0)
        output_tokens = kwargs.get("output_tokens", 0)
        estimated_cost = kwargs.get("estimated_cost", None)
        model_latency_seconds = kwargs.get("model_latency_seconds", 0.0)
        manual_review_status = kwargs.get("manual_review_status", "pending")
        artifact_path = kwargs.get("artifact_path", None)
        
        # Enforce scores on reviewed/disputed status
        if manual_review_status == "pending":
            api_correct = None
            hallucinated_api = None
            requirement_score = None
            quality_score = None
        else:
            api_correct = kwargs.get("api_correct")
            hallucinated_api = kwargs.get("hallucinated_api")
            requirement_score = kwargs.get("requirement_score")
            quality_score = kwargs.get("quality_score")
            
            if api_correct is None or hallucinated_api is None or requirement_score is None or quality_score is None:
                raise ValueError(
                    "For reviewed/disputed status, manual review scores "
                    "(api_correct, hallucinated_api, requirement_score, quality_score) "
                    "must be explicitly provided."
                )

        start_time = time.time()
        test_latency_seconds = 0.0
        
        # Invariants and state trackers
        valid_run = True
        pass1_public = False
        pass1_hidden = False
        pass1_public_tests_passed = 0
        pass1_hidden_tests_passed = 0
        final_public = False
        final_hidden = False
        public_tests_passed = 0
        public_tests_total = 0
        hidden_tests_passed = 0
        hidden_tests_total = 0
        repair_rounds = 0
        patch_apply_failures = 0
        
        error_type = "none"
        stop_reason = "public_pass"
        infra_error = False
        
        if task_id not in self.tasks:
            raise ValueError(f"Task ID {task_id} not found in config")
            
        task = self.tasks[task_id]
        
        limits = task.get("limits", {})
        task_max_repair_rounds = limits.get("max_repair_rounds", 2)
        
        # Calculate effective_max_repair_rounds
        if max_repair_rounds is None:
            effective_max_repair_rounds = task_max_repair_rounds
        else:
            effective_max_repair_rounds = min(max_repair_rounds, task_max_repair_rounds)
            
        public_timeout = limits.get("public_test_timeout_seconds", 30)
        hidden_timeout = limits.get("hidden_test_timeout_seconds", 30)
        
        files_to_modify = task.get("files_to_modify", [])
        public_test_paths = task.get("public_test_paths", [])
        hidden_test_id = task.get("hidden_test_id", task_id)
        public_feedback_policy = task.get("public_feedback_policy", {})
        
        hidden_tests_dir = project_root / "evaluation" / "hidden_tests"
        hidden_test_path = hidden_tests_dir / f"test_{hidden_test_id.lower()}.py"
        hidden_test_abs_path = str(hidden_test_path.resolve())
        
        workspace_mgr = WorkspaceManager(run_id, task_id, snapshot_path=str(snapshot_path))
        workspace_path = None
        
        try:
            workspace_path = workspace_mgr.create()
            runner = SecureTestRunner(workspace_path, approved_hidden_root=str(hidden_tests_dir), timeout_seconds=public_timeout)
            
            def run_public():
                nonlocal test_latency_seconds
                runner.timeout_seconds = public_timeout
                t0 = time.time()
                res = runner.run_public_tests(public_test_paths)
                test_latency_seconds += (time.time() - t0)
                
                if res.timeout_occurred:
                    raise TestTimeoutError("Public test execution timed out")
                if res.runner_error:
                    raise RunnerError(f"Public test runner error: {res.collection_error}")
                return res
                
            def run_hidden():
                nonlocal test_latency_seconds
                runner.timeout_seconds = hidden_timeout
                t0 = time.time()
                res = runner.run_hidden_tests([hidden_test_abs_path])
                test_latency_seconds += (time.time() - t0)
                
                if res.timeout_occurred:
                    raise TestTimeoutError("Hidden test execution timed out")
                if res.runner_error:
                    raise RunnerError("Hidden test runner error")
                return res

            def check_empty_response(patch: str | None) -> bool:
                if patch is None or not patch.strip():
                    return True
                # 完全沒有 unified-diff file header pair (--- and +++) 的純說明文字
                lines = patch.splitlines()
                has_minus_header = any(line.startswith("--- ") for line in lines)
                has_plus_header = any(line.startswith("+++ ") for line in lines)
                return not (has_minus_header and has_plus_header)

            # 1. Apply initial patch
            if check_empty_response(initial_patch):
                raise EmptyResponseError("Initial patch is empty, None, or has no diff intent (missing header pair)")
                
            try:
                PatchEngine.apply_patch(workspace_path, initial_patch, files_to_modify)
            except (InvalidPatchError, PatchApplyError) as patch_exc:
                patch_apply_failures += 1
                raise patch_exc
                
            # Verify post-patch integrity
            try:
                workspace_mgr.verify_post_patch_integrity(files_to_modify)
            except WorkspaceError as we:
                raise InvalidPatchError(f"Post-patch integrity verification failed: {we}")
                
            # Run Pass 1 public tests
            res_pub_1 = run_public()
            pass1_public = res_pub_1.passed
            pass1_public_tests_passed = len(res_pub_1.passed_tests)
            public_tests_total = res_pub_1.total_count
            
            # Run Pass 1 hidden tests
            res_hid_1 = run_hidden()
            pass1_hidden = (res_hid_1.passed_count == res_hid_1.total_count and res_hid_1.total_count > 0)
            pass1_hidden_tests_passed = res_hid_1.passed_count
            hidden_tests_total = res_hid_1.total_count
            
            # Sanitize feedback for initial patch
            sanitized_feedback = SecureTestRunner.sanitize_feedback(res_pub_1, public_feedback_policy)
            
            # Record initial patch round (segregated structures)
            self.public_feedback_history.append(PublicFeedbackRecord(
                round_index=0,
                sanitized_public_feedback=sanitized_feedback,
                public_passed=pass1_public,
                public_passed_count=pass1_public_tests_passed,
                public_total=public_tests_total
            ))
            self._private_audit_records.append(PrivateAuditRecord(
                round_index=0,
                hidden_passed_count=pass1_hidden_tests_passed,
                hidden_total=hidden_tests_total
            ))
            
            final_public = pass1_public
            final_hidden = pass1_hidden
            public_tests_passed = pass1_public_tests_passed
            hidden_tests_passed = pass1_hidden_tests_passed
            
            # 2. Repair loop
            if not final_public and effective_max_repair_rounds > 0:
                for r_idx in range(min(len(repair_patches), effective_max_repair_rounds)):
                    repair_rounds += 1
                    patch_content = repair_patches[r_idx]
                    
                    if check_empty_response(patch_content):
                        raise EmptyResponseError(f"Repair patch at index {r_idx} is empty, None, or has no diff intent")
                        
                    try:
                        PatchEngine.apply_patch(workspace_path, patch_content, files_to_modify)
                    except (InvalidPatchError, PatchApplyError) as patch_exc:
                        patch_apply_failures += 1
                        raise patch_exc
                        
                    # Verify post-patch integrity
                    try:
                        workspace_mgr.verify_post_patch_integrity(files_to_modify)
                    except WorkspaceError as we:
                        raise InvalidPatchError(f"Post-patch integrity verification failed in repair round {r_idx}: {we}")
                        
                    res_pub = run_public()
                    res_hid = run_hidden()
                    
                    # Sanitize feedback for this repair round
                    sanitized_feedback = SecureTestRunner.sanitize_feedback(res_pub, public_feedback_policy)
                    
                    # Record this repair round (segregated structures)
                    self.public_feedback_history.append(PublicFeedbackRecord(
                        round_index=repair_rounds,
                        sanitized_public_feedback=sanitized_feedback,
                        public_passed=res_pub.passed,
                        public_passed_count=len(res_pub.passed_tests),
                        public_total=res_pub.total_count
                    ))
                    self._private_audit_records.append(PrivateAuditRecord(
                        round_index=repair_rounds,
                        hidden_passed_count=res_hid.passed_count,
                        hidden_total=res_hid.total_count
                    ))
                    
                    final_public = res_pub.passed
                    final_hidden = (res_hid.passed_count == res_hid.total_count and res_hid.total_count > 0)
                    public_tests_passed = len(res_pub.passed_tests)
                    public_tests_total = res_pub.total_count
                    hidden_tests_passed = res_hid.passed_count
                    hidden_tests_total = res_hid.total_count
                    
                    if final_public:
                        break

            # Determine stop reason
            if final_public:
                metrics = MetricsCollector.get_success_metrics()
            else:
                metrics = MetricsCollector.get_repair_limit_metrics()
            
            error_type = metrics["error_type"]
            infra_error = metrics["infra_error"]
            valid_run = metrics["valid_run"]
            stop_reason = metrics["stop_reason"]

        except Exception as exc:
            metrics = MetricsCollector.get_metrics_for_exception(exc)
            error_type = metrics["error_type"]
            infra_error = metrics["infra_error"]
            valid_run = metrics["valid_run"]
            stop_reason = metrics["stop_reason"]
            
        finally:
            if workspace_path is not None:
                try:
                    workspace_mgr.cleanup()
                except Exception as cleanup_exc:
                    # Cleanup failure ALWAYS overrides previous error/success status
                    error_type = "runner_error"
                    infra_error = True
                    valid_run = False
                    stop_reason = "infra_error"

        latency_seconds = time.time() - start_time
        
        result_data = {
            "run_id": run_id,
            "task_id": task_id,
            "strategy": strategy,
            "repetition": repetition,
            "model": model,
            "seed": seed,
            "valid_run": valid_run,
            "pass1_public": pass1_public,
            "pass1_hidden": pass1_hidden,
            "pass1_public_tests_passed": pass1_public_tests_passed,
            "pass1_hidden_tests_passed": pass1_hidden_tests_passed,
            "final_public": final_public,
            "final_hidden": final_hidden,
            "public_tests_passed": public_tests_passed,
            "public_tests_total": public_tests_total,
            "hidden_tests_passed": hidden_tests_passed,
            "hidden_tests_total": hidden_tests_total,
            "repair_rounds": repair_rounds,
            "patch_apply_failures": patch_apply_failures,
            "api_correct": api_correct,
            "hallucinated_api": hallucinated_api,
            "requirement_score": requirement_score,
            "quality_score": quality_score,
            "tool_calls": tool_calls,
            "retrieved_tokens": retrieved_tokens,
            "retrieval_success": retrieval_success,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": estimated_cost,
            "latency_seconds": latency_seconds,
            "model_latency_seconds": model_latency_seconds,
            "test_latency_seconds": test_latency_seconds,
            "infra_error": infra_error,
            "error_type": error_type,
            "stop_reason": stop_reason,
            "manual_review_status": manual_review_status,
            "artifact_path": artifact_path,
        }
        
        # Validate result schema
        try:
            with open(result_schema_path, "r", encoding="utf-8") as f:
                result_schema = json.load(f)
            validator = Draft202012Validator(result_schema)
            validator.validate(result_data)
        except Exception as e:
            raise ValueError(f"Generated result report is not schema-compliant: {e}")
            
        return result_data

    def evaluate_task_with_deterministic_patch(self, task_id: str, 
                                               initial_patch: str | None, 
                                               repair_patches: Sequence[str] = (),
                                               max_repair_rounds: int = 2,
                                               **kwargs) -> Dict[str, Any]:
        return self.evaluate_task(task_id, initial_patch, repair_patches, max_repair_rounds, **kwargs)
        
    def evaluate_task_with_deterministic_patches(self, task_id: str, 
                                                initial_patch: str | None, 
                                                repair_patches: Sequence[str] = (),
                                                max_repair_rounds: int = 2,
                                                **kwargs) -> Dict[str, Any]:
        return self.evaluate_task(task_id, initial_patch, repair_patches, max_repair_rounds, **kwargs)

def evaluate_task_with_deterministic_patches(task_id: str, 
                                            initial_patch: str | None, 
                                            repair_patches: Sequence[str] = (),
                                            max_repair_rounds: int = 2,
                                            **kwargs) -> Dict[str, Any]:
    evaluator = Evaluator()
    return evaluator.evaluate_task(task_id, initial_patch, repair_patches, max_repair_rounds, **kwargs)

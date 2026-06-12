from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.evaluation.evaluator import Evaluator
from experiments.runner.config import ExperimentConfigError, load_experiment_config
from experiments.runner.derived import generate_derived_outputs
from experiments.runner.errors import ResultValidationError, ResultWriteError
from experiments.runner.result_writer import ResultJsonlWriter
from experiments.runner.resume import filter_pending_runs, load_completed_run_index
from experiments.runner.scheduler import build_scheduler_plan
from experiments.runner.strategy_factory import StrategyFactory
from experiments.runner.orchestrator import ExperimentOrchestrator
from experiments.strategies.artifacts import ArtifactWriteError


@dataclass(frozen=True)
class MockRunSummary:
    attempted: int
    written: int
    valid_runs: int
    experimental_failures: int
    infra_failures: int
    skipped_existing: int
    writer_failures: int
    execution_failures: int = 0


_SMOKE_EXPERIMENT_ID_PATTERN = re.compile(r"^m7d_smoke_[0-9]{8}T[0-9]{6}Z$")
_APPROVED_SMOKE_BUDGET = {
    "--max-provider-calls": 22,
    "--max-input-tokens": 120000,
    "--max-output-tokens": 48000,
    "--max-wall-clock-seconds": 1800,
    "--consecutive-infra-failure-threshold": 2,
}


def main(argv: list[str] | None = None) -> int:
    command_argv = list(argv) if argv is not None else sys.argv[1:]
    # Scan for plaintext credentials in CLI args before parsing for live-run
    if command_argv and "live-run" in command_argv:
        forbidden_keys = {
            "--api-key",
            "--api_key",
            "--apikey",
            "--credential",
            "--credentials",
            "--secret",
            "--token",
            "--authorization",
        }
        for arg in command_argv:
            if arg.lower() in forbidden_keys:
                print("Error: Plaintext credential-like content is forbidden in CLI arguments.")
                return 2
            for pattern in [
                re.compile(r"(?i)bearer\s+"),
                re.compile(r"(?i)(api[_-]?key|secret|credential)[:=]\s*\w+"),
            ]:
                if pattern.search(arg):
                    print("Error: Plaintext credential-like content is forbidden in CLI arguments.")
                    return 2
    if _has_forbidden_smoke_flags(command_argv):
        print("Error: full-run-only flags are forbidden for live-smoke.")
        return 2
    parser = _build_parser()
    args = parser.parse_args(command_argv)
    try:
        if args.command == "dry-run":
            repo_root = Path(args.repo_root).resolve()
            config = _load_config(repo_root, mode="dry_run")
            plan = build_scheduler_plan(config=config, repo_root=repo_root, today=args.today)
            print(f"{len(plan.runs)} planned runs")
            print(plan.experiment_id)
            return 0
        if args.command == "mock-run":
            repo_root = Path(args.repo_root).resolve()
            summary = run_mock_runs(repo_root=repo_root, limit=args.limit)
            print(
                "mock-run "
                f"attempted={summary.attempted} "
                f"written={summary.written} "
                f"valid={summary.valid_runs} "
                f"experimental_failures={summary.experimental_failures} "
                f"infra_failures={summary.infra_failures} "
                f"skipped_existing={summary.skipped_existing} "
                f"writer_failures={summary.writer_failures} "
                f"execution_failures={summary.execution_failures}"
            )
            return 1 if summary.writer_failures or summary.execution_failures else 0
        if args.command == "derive":
            generate_derived_outputs(
                raw_jsonl_path=Path(args.raw_jsonl),
                derived_csv_path=Path(args.csv),
                summary_path=Path(args.summary),
                approved_derived_root=Path(args.derived_root),
                schema_path=Path(args.schema),
            )
            print("derived outputs written")
            return 0
        if args.command == "live-probe":
            repo_root = Path(args.repo_root).resolve()
            from experiments.live.probe import run_live_probe_cli
            return run_live_probe_cli(repo_root)
        if args.command == "live-run":
            if os.environ.get("ARAG_RUN_LIVE_GATEWAY") != "1":
                raise ValueError("ARAG_RUN_LIVE_GATEWAY=1 is required for live-run")
            # Scan for plaintext credentials in CLI args
            for arg in command_argv:
                for pattern in [
                    re.compile(r"(?i)bearer\s+"),
                    re.compile(r"(?i)(api[_-]?key|secret|credential)[:=]\s*\w+"),
                ]:
                    if pattern.search(arg):
                        print("Error: Plaintext credential-like content is forbidden in CLI arguments.")
                        return 2

            repo_root = Path(args.repo_root).resolve()
            
            # Check required arguments presence
            required_run_flags = {
                "--approved-smoke-report": args.approved_smoke_report,
                "--approved-smoke-sha256": args.approved_smoke_sha256,
                "--full-experiment-id": args.full_experiment_id,
                "--human-approval": args.human_approval,
                "--approved-input-token-budget": args.approved_input_token_budget,
                "--approved-output-token-budget": args.approved_output_token_budget,
                "--approved-wall-clock-seconds": args.approved_wall_clock_seconds,
            }
            missing_run_flags = [f for f, v in required_run_flags.items() if v is None]
            if missing_run_flags:
                print(f"Error: Missing required full-run approval arguments: {', '.join(missing_run_flags)}")
                return 2

            # Perform gate check
            from experiments.live.smoke_gate import FullRunApproval, FullRunApprovalValidator
            import json
            import hashlib

            report_path = Path(args.approved_smoke_report)
            if not report_path.is_file():
                print("Error: approved smoke report file not found.")
                return 2
            
            report_bytes = report_path.read_bytes()
            try:
                report_data = json.loads(report_bytes.decode("utf-8"))
                smoke_id = report_data.get("smoke_experiment_id")
            except Exception as exc:
                print(f"Error: Failed to parse smoke report: {exc}")
                return 2

            approval = FullRunApproval(
                approved_smoke_report_path=args.approved_smoke_report,
                smoke_report_sha256=args.approved_smoke_sha256,
                smoke_experiment_id=smoke_id or "",
                full_experiment_id=args.full_experiment_id,
                approved_token_budget_input=args.approved_input_token_budget,
                approved_token_budget_output=args.approved_output_token_budget,
                approved_wall_clock_seconds=args.approved_wall_clock_seconds,
                allow_unknown_cost=args.allow_unknown_cost,
                human_approval=args.human_approval,
            )

            jsonl_path = repo_root / "results" / "raw" / f"{args.full_experiment_id}.jsonl"
            is_resume = False
            if jsonl_path.is_file():
                try:
                    from experiments.runner.resume import load_completed_run_index
                    completed_index = load_completed_run_index(
                        raw_path=jsonl_path,
                        schema_path=repo_root / "contracts" / "result.schema.json"
                    )
                    is_resume = len(completed_index.run_ids) > 0
                except Exception:
                    is_resume = False
            try:
                # To check approval path, we pass is_resume if needed. But in CLI gate check, this is fresh run.
                FullRunApprovalValidator.validate_approval(report_bytes, approval, repo_root, is_resume=is_resume)
            except Exception as exc:
                print(f"Error: Validation failed: {exc}")
                return 2

            is_fake_provider = os.environ.get("ARAG_USE_FAKE_FULL_RUN_PROVIDER") == "1"
            pilot_run_count = args.pilot_run_count
            if pilot_run_count is not None:
                if pilot_run_count != 15:
                    print("Error: --pilot-run-count must be exactly 15.")
                    return 2
                if (
                    not is_fake_provider
                    and os.environ.get("ARAG_EXECUTE_PILOT15_ONCE") != "1"
                ):
                    print(
                        "Error: 15-run pilot live execution is blocked; "
                        "ARAG_EXECUTE_PILOT15_ONCE=1 is required."
                    )
                    return 2
                if (
                    is_fake_provider
                    and os.environ.get("ARAG_EXECUTE_FULL_RUN_ONCE") != "1"
                ):
                    print("full-run approval validated, execution requires M7-E.3 approval.")
                    return 2
            elif os.environ.get("ARAG_EXECUTE_FULL_RUN_ONCE") != "1":
                print("full-run approval validated, execution requires M7-E.3 approval.")
                return 2

            if (
                not is_fake_provider
                and pilot_run_count is None
                and "PYTEST_CURRENT_TEST" in os.environ
            ):
                print("full-run live execution is blocked until M7-E.3.")
                return 2

            # Already imported at module level
            from experiments.live.smoke_executor import (
                LiveExecutionRequest,
                LiveExperimentExecutor,
            )
            from experiments.live.budget import BudgetLimits
            from experiments.runner.config import load_experiment_config, ExperimentPaths
            from dataclasses import replace
            
            mode_str = "mock_run" if is_fake_provider else "live"
            base_config = load_experiment_config(
                experiment_path=repo_root / "configs" / "experiment.yaml",
                models_path=repo_root / "configs" / "models.yaml",
                repo_root=repo_root,
                mode=mode_str,
                env=os.environ,
            )
            paths = ExperimentPaths(
                tasks_definition=(repo_root / "experiments" / "tasks.json").resolve(),
                raw_results_dir=(repo_root / "results" / "raw").resolve(),
                derived_results_dir=(repo_root / "results" / "derived").resolve(),
                reviews_dir=(repo_root / "results" / "reviews").resolve(),
                workspace_base_dir=(repo_root / "workspaces" / args.full_experiment_id).resolve(),
                artifact_root=(repo_root / "results" / "raw" / "artifacts" / args.full_experiment_id).resolve(),
                retrieval_log_root=(repo_root / "results" / "raw" / "retrieval" / args.full_experiment_id).resolve(),
            )
            config = replace(base_config, repetitions=3, paths=paths)
            
            today_str = args.full_experiment_id[len("m7e_full_") : len("m7e_full_") + 8]
            plan = build_scheduler_plan(config=config, repo_root=repo_root, today=today_str)
            
            from experiments.live.smoke_executor import _bind_plan_to_request
            bound_runs = _bind_plan_to_request(plan.runs, args.full_experiment_id)
            execution_runs = bound_runs[:15] if pilot_run_count == 15 else bound_runs
            execution_mode = "pilot15" if pilot_run_count == 15 else "full"
            
            budget_limits = BudgetLimits(
                max_total_input_tokens=args.approved_input_token_budget,
                max_total_output_tokens=args.approved_output_token_budget,
                max_total_calls=660,  # amended attempt limit
                max_infra_failures=2,
                max_consecutive_infra_failures=2,
                max_gateway_failures=2,
                max_wall_clock_seconds=float(args.approved_wall_clock_seconds),
            )
            
            if is_fake_provider:
                if pilot_run_count == 15:
                    print("Starting fixed first-15 fake/scripted provider dry activation run...")
                else:
                    print("Starting 45-run fake/scripted provider dry activation run...")
                class DeterministicFakeFullRunProvider:
                    def __init__(self, run, hooks):
                        self.run = run
                        self.hooks = hooks
                        self.call_index = 0

                    def generate(self, request):
                        self.call_index += 1
                        self.hooks.reserve_provider_attempt()
                        
                        strategy = self.run.identity.strategy
                        task_id = self.run.identity.task_id
                        
                        files_to_modify = self.run.task_record["files_to_modify"]
                        target_file = files_to_modify[0]
                        
                        valid_patch = f"""--- {target_file}
+++ {target_file}
@@ -1,1 +1,2 @@
 # comment
+def dummy(): pass
"""
                        text = ""
                        if strategy == "A":
                            text = valid_patch
                        elif strategy == "C":
                            if self.call_index == 1:
                                text = json.dumps({
                                    "implementation_steps": ["step 1"],
                                    "risks": ["risk 1"],
                                    "files_to_modify": files_to_modify
                                })
                            elif self.call_index == 2:
                                text = valid_patch
                            else:
                                text = '{"verdict": "pass", "issues": []}'
                        elif strategy == "E":
                            if self.call_index == 1:
                                text = '{"action": "retrieve", "tool": "keyword_search", "query": "criteria", "top_k": 2}'
                            elif self.call_index == 2:
                                text = json.dumps({
                                    "implementation_steps": ["step 1"],
                                    "risks": ["risk 1"],
                                    "files_to_modify": files_to_modify
                                })
                            elif self.call_index == 3:
                                text = '{"action": "retrieve", "tool": "keyword_search", "query": "solution help", "top_k": 1}'
                            elif self.call_index == 4:
                                text = valid_patch
                            else:
                                text = '{"verdict": "pass", "issues": []}'
                                
                        from experiments.providers.models import ProviderAttemptRecord, ModelResponse, Usage
                        attempt = ProviderAttemptRecord(self.call_index, 1, 0.0, 0.0, "response", None)
                        return ModelResponse(
                            text=text,
                            finish_reason="stop",
                            usage=Usage(100, 50, 150, "provider"),
                            provider_request_id=f"fake-{task_id}-{strategy}-{self.call_index}",
                            model=request.parameters.model,
                            latency_seconds=0.0,
                            retry_count=0,
                            seed_applied=True,
                            sanitized_metadata=(),
                            attempt_records=(attempt,),
                        )
                
                def final_provider_factory(run, hooks):
                    return DeterministicFakeFullRunProvider(run, hooks)
            else:
                if pilot_run_count == 15:
                    print("Starting fixed first-15 REAL live provider pilot run...")
                else:
                    print("Starting 45-run REAL live provider execution run...")
                from experiments.live.factory import LiveProviderFactory
                def final_provider_factory(run, hooks):
                    return LiveProviderFactory.create_provider(
                        config,
                        model_id=config.model,
                        env=os.environ,
                        credential_provider=None,
                        attempt_reservation=hooks.reserve_provider_attempt,
                        limiter=getattr(hooks, "limiter", None),
                    )
                
            request = LiveExecutionRequest(
                experiment_id=args.full_experiment_id,
                repo_root=repo_root,
                planned_runs=execution_runs,
                raw_jsonl_path=(repo_root / "results" / "raw" / f"{args.full_experiment_id}.jsonl").resolve(),
                artifact_root=(repo_root / "results" / "raw" / "artifacts" / args.full_experiment_id).resolve(),
                retrieval_log_root=(repo_root / "results" / "raw" / "retrieval" / args.full_experiment_id).resolve(),
                budget_limits=budget_limits,
                provider_factory=final_provider_factory,
                mode=execution_mode,
                smoke_report_path=report_path,
            )
            
            executor = LiveExperimentExecutor()
            result = executor.execute(request)
            
            if result.quarantined or result.abort_reason is not None:
                print(f"Error: full-run execution failed. Reason: {result.abort_reason}")
                return 1
                
            if is_fake_provider:
                print("fake-full-run completed successfully.")
            else:
                print("real-full-run completed successfully.")
            print(f"completed_runs: {len(result.completed_run_ids)}")
            return 0
        if args.command == "live-smoke":
            gate_error = _validate_live_smoke_gate(args, env=os.environ)
            if gate_error is not None:
                print(f"Error: {gate_error}")
                return 2
            from experiments.live.budget import BudgetLimits
            from experiments.live.smoke_composition import (
                build_live_smoke_request,
                validate_live_smoke_composition,
            )

            request = build_live_smoke_request(
                repo_root=Path(args.repo_root),
                experiment_id=args.experiment_id,
                human_approval=args.human_approval,
                raw_jsonl_path=Path(args.raw_jsonl),
                artifact_root=Path(args.artifact_root),
                retrieval_log_root=Path(args.retrieval_log_root),
                smoke_report_path=Path(args.smoke_report),
                budget_limits=BudgetLimits(
                    max_total_input_tokens=args.max_input_tokens,
                    max_total_output_tokens=args.max_output_tokens,
                    max_total_calls=args.max_provider_calls,
                    max_infra_failures=2,
                    max_consecutive_infra_failures=args.consecutive_infra_failure_threshold,
                    max_gateway_failures=2,
                    max_wall_clock_seconds=args.max_wall_clock_seconds,
                ),
                env=os.environ,
            )
            validate_live_smoke_composition(request, env=os.environ)
            if os.environ.get("ARAG_EXECUTE_LIVE_SMOKE_ONCE") != "1":
                print("live-smoke composition validated, execution requires M7-D.2 approval.")
                return 2

            from experiments.live.smoke_executor import SmokeExecutor
            import hashlib

            executor = SmokeExecutor()
            result = executor.execute(request)
            if result.quarantined or result.report is None or not result.report.automated_gate_passed:
                abort_reason = result.abort_reason or "Automated gate check failed"
                print(f"Error: smoke execution failed or quarantined. Reason: {abort_reason}")
                return 1

            report_bytes = Path(args.smoke_report).read_bytes()
            report_hash = hashlib.sha256(report_bytes).hexdigest()
            print("smoke-run completed successfully.")
            print(f"report_path: {args.smoke_report}")
            print(f"report_sha256: {report_hash}")
            return 0
        if args.command in ("smoke-audit", "experiment-audit"):
            # Enforce M7-A fail-closed boundary
            print(f"Error: Command {args.command} is blocked. M7-B credential adapter is required.")
            return 2
    except (ExperimentConfigError, ValueError) as exc:
        if os.environ.get("ARAG_DEBUG_TRACEBACK") == "1":
            import traceback
            traceback.print_exc()
        print(f"configuration error: {exc}")
        return 2
    return 2


def run_mock_runs(*, repo_root: Path, limit: int | None) -> MockRunSummary:
    config = _load_config(repo_root, mode="mock_run")
    plan = build_scheduler_plan(config=config, repo_root=repo_root, today="20260611")
    index = load_completed_run_index(raw_path=plan.raw_jsonl_path, schema_path=repo_root / "contracts" / "result.schema.json")
    pending = filter_pending_runs(plan.runs, index)
    selected = pending[:limit] if limit is not None else pending
    writer = ResultJsonlWriter(
        approved_raw_root=config.paths.raw_results_dir,
        jsonl_path=plan.raw_jsonl_path,
        schema_path=repo_root / "contracts" / "result.schema.json",
    )
    evaluator = Evaluator(task_config_path=config.paths.tasks_definition)
    factory = StrategyFactory(repo_root=repo_root)
    orchestrator = ExperimentOrchestrator(
        config=config,
        repo_root=repo_root,
        evaluator=evaluator,
        strategy_factory=factory,
        writer=writer,
    )
    attempted = 0
    written = 0
    valid_runs = 0
    experimental_failures = 0
    infra_failures = 0
    writer_failures = 0
    execution_failures = 0
    for run in selected:
        attempted += 1
        try:
            execution = orchestrator.execute_run(run)
        except (ResultValidationError, ResultWriteError):
            writer_failures += 1
            infra_failures += 1
            break
        except ArtifactWriteError:
            execution_failures += 1
            infra_failures += 1
            break
        written += 1
        record = execution.result_record
        if record["infra_error"]:
            infra_failures += 1
        elif record["valid_run"]:
            valid_runs += 1
            if not record["final_public"]:
                experimental_failures += 1
    return MockRunSummary(
        attempted=attempted,
        written=written,
        valid_runs=valid_runs,
        experimental_failures=experimental_failures,
        infra_failures=infra_failures,
        skipped_existing=len(plan.runs) - len(pending),
        writer_failures=writer_failures,
        execution_failures=execution_failures,
    )


def _load_config(repo_root: Path, *, mode: str):
    return load_experiment_config(
        experiment_path=repo_root / "configs" / "experiment.yaml",
        models_path=repo_root / "configs" / "models.yaml",
        repo_root=repo_root,
        mode=mode,
        env=os.environ,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arag-experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--repo-root", required=True)
    dry.add_argument("--today", default="20260611")

    mock = subparsers.add_parser("mock-run")
    mock.add_argument("--repo-root", required=True)
    mock.add_argument("--limit", type=_positive_int, default=None)

    derive = subparsers.add_parser("derive")
    derive.add_argument("--raw-jsonl", required=True)
    derive.add_argument("--csv", required=True)
    derive.add_argument("--summary", required=True)
    derive.add_argument("--derived-root", required=True)
    derive.add_argument("--schema", required=True)

    live_probe = subparsers.add_parser("live-probe")
    live_probe.add_argument("--repo-root", required=True)

    live_smoke = subparsers.add_parser("live-smoke")
    live_smoke.add_argument("--repo-root", required=True)
    live_smoke.add_argument("--experiment-id")
    live_smoke.add_argument("--human-approval")
    live_smoke.add_argument("--raw-jsonl")
    live_smoke.add_argument("--artifact-root")
    live_smoke.add_argument("--retrieval-log-root")
    live_smoke.add_argument("--smoke-report")
    live_smoke.add_argument("--max-provider-calls", type=_positive_int)
    live_smoke.add_argument("--max-input-tokens", type=_positive_int)
    live_smoke.add_argument("--max-output-tokens", type=_positive_int)
    live_smoke.add_argument("--max-wall-clock-seconds", type=_positive_int)
    live_smoke.add_argument("--consecutive-infra-failure-threshold", type=_positive_int)

    smoke_audit = subparsers.add_parser("smoke-audit")
    smoke_audit.add_argument("--repo-root", required=True)

    live_run = subparsers.add_parser("live-run")
    live_run.add_argument("--repo-root", required=True)
    live_run.add_argument("--approved-smoke-report")
    live_run.add_argument("--approved-smoke-sha256")
    live_run.add_argument("--full-experiment-id")
    live_run.add_argument("--human-approval")
    live_run.add_argument("--approved-input-token-budget", type=int)
    live_run.add_argument("--approved-output-token-budget", type=int)
    live_run.add_argument("--approved-wall-clock-seconds", type=float)
    live_run.add_argument("--allow-unknown-cost", action="store_true")
    live_run.add_argument("--pilot-run-count", type=int)

    exp_audit = subparsers.add_parser("experiment-audit")
    exp_audit.add_argument("--repo-root", required=True)
    return parser


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _has_forbidden_smoke_flags(argv: list[str]) -> bool:
    if not argv or argv[0] != "live-smoke":
        return False
    full_run_only_flags = {
        "--approved-smoke-report",
        "--approved-smoke-sha256",
        "--allow-unknown-cost",
        "--full-experiment-id",
    }
    return any(item in full_run_only_flags for item in argv)


def _validate_live_smoke_gate(args: argparse.Namespace, *, env: dict[str, str]) -> str | None:
    if env.get("ARAG_RUN_LIVE_GATEWAY") != "1":
        return "live-smoke requires ARAG_RUN_LIVE_GATEWAY=1"
    if env.get("ARAG_ALLOW_SMOKE_RUN") != "1":
        return "live-smoke requires ARAG_ALLOW_SMOKE_RUN=1"
    if args.human_approval != "SMOKE_RUN":
        return "live-smoke requires --human-approval SMOKE_RUN"
    if not args.experiment_id or _SMOKE_EXPERIMENT_ID_PATTERN.fullmatch(args.experiment_id) is None:
        return "experiment id must match canonical format ^m7d_smoke_[0-9]{8}T[0-9]{6}Z$"

    required_values = {
        "--raw-jsonl": args.raw_jsonl,
        "--artifact-root": args.artifact_root,
        "--retrieval-log-root": args.retrieval_log_root,
        "--smoke-report": args.smoke_report,
        "--max-provider-calls": args.max_provider_calls,
        "--max-input-tokens": args.max_input_tokens,
        "--max-output-tokens": args.max_output_tokens,
        "--max-wall-clock-seconds": args.max_wall_clock_seconds,
        "--consecutive-infra-failure-threshold": args.consecutive_infra_failure_threshold,
    }
    missing = [flag for flag, value in required_values.items() if value is None]
    if missing:
        return f"live-smoke requires explicit gate arguments: {', '.join(missing)}"

    for flag, approved_value in _APPROVED_SMOKE_BUDGET.items():
        actual_value = required_values[flag]
        if actual_value != approved_value:
            return f"{flag} must equal exact approved budget {approved_value}"

    repo_root = Path(args.repo_root).resolve()
    experiment_id = args.experiment_id
    path_contracts = {
        "--raw-jsonl": (
            repo_root / "results" / "raw",
            repo_root / "results" / "raw" / f"{experiment_id}.jsonl",
        ),
        "--artifact-root": (
            repo_root / "results" / "raw" / "artifacts",
            repo_root / "results" / "raw" / "artifacts" / experiment_id,
        ),
        "--retrieval-log-root": (
            repo_root / "results" / "raw" / "retrieval",
            repo_root / "results" / "raw" / "retrieval" / experiment_id,
        ),
        "--smoke-report": (
            repo_root / "results" / "raw" / "gates",
            repo_root / "results" / "raw" / "gates" / f"{experiment_id}.json",
        ),
    }
    for flag, (approved_root, expected) in path_contracts.items():
        actual = Path(getattr(args, flag[2:].replace("-", "_"))).resolve()
        approved_root = approved_root.resolve()
        try:
            actual.relative_to(approved_root)
        except ValueError:
            return f"{flag} must remain under exact approved root {approved_root}"
        if actual != expected.resolve():
            return f"{flag} must be smoke-specific and exactly match {expected.resolve()}"
        if actual.exists():
            return f"{flag} already exists; smoke outputs must never overwrite existing data"
    return None


if __name__ == "__main__":
    raise SystemExit(main())

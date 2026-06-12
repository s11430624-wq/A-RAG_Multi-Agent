from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from experiments.providers.models import ProviderAttemptRecord, ProviderFailureAuditRecord


@dataclass(frozen=True)
class StarterFile:
    file_path: str
    content: str
    sha256: str


@dataclass(frozen=True)
class ModelVisibleTask:
    task_id: str
    task_description: str
    starter_files: tuple[StarterFile, ...]
    files_to_modify: tuple[str, ...]
    expected_behavior: tuple[str, ...]
    forbidden_behaviors: tuple[str, ...]


@dataclass(frozen=True)
class SanitizedPublicFeedback:
    round_index: int
    text: str
    sha256: str


@dataclass(frozen=True)
class CapabilityContext:
    retrieval_enabled: bool


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    raw_bytes: bytes
    sha256: str


@dataclass(frozen=True)
class RenderedPrompt:
    template_name: str
    template_hash: str
    user_prompt: str
    rendered_prompt_hash: str


RoleName = Literal["Single", "Planner", "Coder", "Reviewer"]
PhaseName = Literal["initial", "repair_1", "repair_2"]


@dataclass(frozen=True)
class PlannerOutput:
    implementation_steps: tuple[str, ...]
    risks: tuple[str, ...]
    files_to_modify: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalSearchRequest:
    action: Literal["retrieve"]
    tool: Literal["keyword_search", "semantic_search"]
    query: str
    top_k: int


@dataclass(frozen=True)
class RetrievalChunkReadRequest:
    action: Literal["retrieve"]
    tool: Literal["chunk_read"]
    file_path: str
    chunk_id: str


RetrievalRequest = RetrievalSearchRequest | RetrievalChunkReadRequest


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    run_id: str
    task_id: str
    role: RoleName
    phase: PhaseName
    tool_name: Literal["keyword_search", "semantic_search", "chunk_read"]
    file_path: str
    chunk_id: str
    content_hash: str
    text: str
    token_count: int


@dataclass(frozen=True)
class SearchAuthorization:
    run_id: str
    task_id: str
    role: RoleName
    phase: PhaseName
    file_path: str
    chunk_id: str


@dataclass(frozen=True)
class EvidenceLedger:
    run_id: str
    task_id: str
    next_sequence: int
    items: tuple[EvidenceItem, ...]
    search_authorizations: tuple[SearchAuthorization, ...]

    def add_item(self, item: EvidenceItem) -> "EvidenceLedger":
        if item.run_id != self.run_id or item.task_id != self.task_id:
            raise ValueError("evidence cannot cross run or task")
        return EvidenceLedger(
            self.run_id,
            self.task_id,
            self.next_sequence + 1,
            self.items + (item,),
            self.search_authorizations,
        )


@dataclass(frozen=True)
class ResponseClassification:
    kind: Literal["retrieval_request", "final_output", "invalid"]
    response_sha256: str
    retrieval_request: RetrievalRequest | None
    final_text: str | None
    reason: str | None


@dataclass(frozen=True)
class ReviewerIssue:
    category: Literal[
        "requirement",
        "api_usage",
        "forbidden_behavior",
        "patch_scope",
        "correctness",
        "exception_handling",
        "style",
    ]
    message: str
    evidence_chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewerVerdict:
    verdict: Literal["PASS", "FAIL", "pass", "fail"]
    issues: tuple[ReviewerIssue, ...]


@dataclass(frozen=True)
class ModelCallRecord:
    call_index: int
    role: str
    phase: str
    template_name: str
    template_hash: str
    rendered_prompt_hash: str
    response_hash: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    model_latency_seconds: float
    retry_count: int
    finish_reason: Literal["stop"]
    seed_applied: bool
    audit_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class StrategyMetrics:
    model_call_count: int
    provider_attempt_count: int
    failed_provider_call_count: int
    tool_calls: int
    retrieved_tokens: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: float | None
    model_latency_seconds: float
    retrieval_success: bool | None
    call_records: tuple[ModelCallRecord, ...]
    attempt_records: tuple[ProviderAttemptRecord, ...]
    failure_audit_records: tuple[ProviderFailureAuditRecord, ...]


@dataclass(frozen=True)
class StrategyPatchOutput:
    patch: str
    reviewer_verdict: ReviewerVerdict | None
    metrics: StrategyMetrics


@dataclass(frozen=True)
class StrategyFinalization:
    metrics: StrategyMetrics
    artifact_path: str
    manifest_sha256: str


@dataclass(frozen=True)
class StrategyResultProjection:
    tool_calls: int
    retrieved_tokens: int
    retrieval_success: bool | None
    input_tokens: int
    output_tokens: int
    estimated_cost: float | None
    model_latency_seconds: float
    artifact_path: str | None


@dataclass(frozen=True)
class ArtifactFileHash:
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ArtifactManifest:
    manifest_version: str
    created_at: str
    run_id: str
    task_id: str
    strategy: Literal["A", "C", "E"]
    model: str
    seed: int
    template_hashes: tuple[tuple[str, str], ...]
    rendered_prompt_hashes: tuple[tuple[int, str], ...]
    response_hashes: tuple[tuple[int, str], ...]
    patch_hashes: tuple[tuple[str, str], ...]
    provider_request_ids: tuple[tuple[int, str | None], ...]
    call_records: tuple[ModelCallRecord, ...]
    attempt_records: tuple[ProviderAttemptRecord, ...]
    failure_audit_records: tuple[ProviderFailureAuditRecord, ...]
    usage_complete: bool
    retry_count: int
    provider_attempt_count: int
    failed_provider_call_count: int
    retrieval_log_relative_path: str | None
    artifact_files: tuple[ArtifactFileHash, ...]

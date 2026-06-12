from __future__ import annotations

from dataclasses import replace
import hashlib
from typing import Any, Callable

from experiments.providers.models import ModelParameters, ModelProvider, ModelRequest, ProviderError
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import ChunkReadResult, FrozenRetrievalStore, SearchResult
from experiments.retrieval.service import RetrievalFacade, RetrievalSession
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.base import BaseStrategySession, StrategySessionClosedError
from experiments.strategies.models import (
    CapabilityContext,
    EvidenceItem,
    EvidenceLedger,
    ModelVisibleTask,
    PlannerOutput,
    RetrievalChunkReadRequest,
    RetrievalSearchRequest,
    ReviewerVerdict,
    SanitizedPublicFeedback,
    SearchAuthorization,
    StrategyPatchOutput,
)
from experiments.strategies.parsers import (
    PatchResponseParser,
    PlannerResponseParser,
    ResponseEnvelopeClassifier,
    RetrievalBudgetExceededError,
    RetrievalRequestParser,
    ReviewerResponseParser,
    StrategyResponseError,
)


class ARAGMultiAgentStrategySession(BaseStrategySession):
    _BUDGETS = {("Planner", "initial"): 5, ("Coder", "initial"): 3, ("Reviewer", "initial"): 1}
    _MAX_CACHE_HITS_PER_ROLE_PHASE = 2

    def __init__(
        self,
        *,
        run_id: str,
        task: ModelVisibleTask,
        provider: ModelProvider,
        parameters: ModelParameters,
        artifact_writer: ArtifactBundleWriter,
        store: FrozenRetrievalStore,
        retrieval_facade: RetrievalFacade,
        log_writer: RetrievalLogWriter | None = None,
    ) -> None:
        if store.corpus.task_id != task.task_id:
            raise ValueError("retrieval store task does not match visible task")
        super().__init__(
            run_id=run_id,
            task=task,
            provider=provider,
            parameters=parameters,
            artifact_writer=artifact_writer,
            retrieval_success=False,
        )
        self.store = store
        self.retrieval_cache: dict[tuple, Any] = {}
        self.evidence_ledger = EvidenceLedger(run_id, task.task_id, 1, (), ())
        self.role_sessions: dict[str, RetrievalSession] = {
            role: retrieval_facade.create_session(
                run_id=run_id,
                strategy="E",
                agent_role=role,
                store=store,
                log_writer=log_writer,
            )
            for role in ("Planner", "Coder", "Reviewer")
        }
        self._plan: PlannerOutput | None = None
        self._reviewer_verdict: ReviewerVerdict | None = None
        self._coder_evidence_ids: tuple[str, ...] = ()

    def generate_initial_patch(self) -> StrategyPatchOutput:
        self._assert_callable()
        if self._initial_generated:
            raise StrategySessionClosedError("initial patch already generated")
        try:
            plan = self._role_turn(
                role="Planner",
                phase="initial",
                template_name="planner.txt",
                data={},
                final_parser=lambda text: PlannerResponseParser.parse(
                    text,
                    allowed_files=self.task.files_to_modify,
                ),
            )
            planner_evidence_ids = tuple(
                item.evidence_id
                for item in self.evidence_ledger.items
                if (
                    item.run_id == self.run_id
                    and item.task_id == self.task.task_id
                    and item.role == "Planner"
                    and item.phase == "initial"
                )
            )
            patch = self._role_turn(
                role="Coder",
                phase="initial",
                template_name="coder.txt",
                data={"plan": plan},
                final_parser=PatchResponseParser.parse,
                inherited_evidence_ids=planner_evidence_ids,
            )
            self.artifact_writer.stage_bytes("patches/initial.diff", patch.encode("utf-8"))
            self._coder_evidence_ids = tuple(
                item.evidence_id
                for item in self.evidence_ledger.items
                if item.role == "Coder" and item.phase == "initial"
            )
            verdict = self._role_turn(
                role="Reviewer",
                phase="initial",
                template_name="reviewer.txt",
                data={"plan": plan, "patch": patch, "coder_evidence_ids": self._coder_evidence_ids},
                final_parser=lambda text: ReviewerResponseParser.parse(
                    text,
                    allowed_evidence_ids=self._coder_evidence_ids,
                ),
                inherited_evidence_ids=self._coder_evidence_ids,
            )
            self._plan = plan
            self._reviewer_verdict = verdict
            self._initial_generated = True
            return StrategyPatchOutput(patch, verdict, self.metrics_collector.snapshot())
        except Exception:
            if not self._closed:
                self._terminal_close()
            raise

    def generate_repair_patch(
        self,
        feedback: SanitizedPublicFeedback,
        previous_patch: str,
    ) -> StrategyPatchOutput:
        self._assert_callable()
        if not isinstance(feedback, SanitizedPublicFeedback):
            raise TypeError("feedback must be SanitizedPublicFeedback")
        if not self._initial_generated or self._plan is None:
            raise StrategySessionClosedError("initial flow must complete first")
        if self._repair_count >= 2:
            raise StrategySessionClosedError("repair limit reached")
        self._repair_count += 1
        phase = f"repair_{self._repair_count}"
        try:
            patch = self._role_turn(
                role="Coder",
                phase=phase,
                template_name="repair.txt",
                data={
                    "feedback": feedback,
                    "previous_patch": previous_patch,
                    "plan": self._plan,
                    "reviewer_verdict": self._reviewer_verdict,
                },
                final_parser=PatchResponseParser.parse,
                inherited_evidence_ids=self._coder_evidence_ids,
            )
            self.artifact_writer.stage_bytes(f"patches/{phase}.diff", patch.encode("utf-8"))
            return StrategyPatchOutput(patch, self._reviewer_verdict, self.metrics_collector.snapshot())
        except Exception:
            if not self._closed:
                self._terminal_close()
            raise

    def _role_turn(
        self,
        *,
        role: str,
        phase: str,
        template_name: str,
        data: dict[str, Any],
        final_parser: Callable[[str], Any],
        inherited_evidence_ids: tuple[str, ...] = (),
    ) -> Any:
        retrieval_count = 0
        cache_hit_count = 0
        budget = 2 if phase.startswith("repair_") else self._BUDGETS[(role, phase)]
        retrieved_queries: list[Any] = []
        retrieval_progress_note: str | None = None
        while True:
            visible_evidence = tuple(
                item
                for item in self.evidence_ledger.items
                if (item.role == role and item.phase == phase) or item.evidence_id in inherited_evidence_ids
            )
            has_visible_retrieval_evidence = any(
                item.tool_name in ("keyword_search", "semantic_search", "chunk_read")
                for item in visible_evidence
            )
            retrieval_required = role in ("Planner", "Coder") and not has_visible_retrieval_evidence
            rendered = self.prompt_loader.render(
                template_name,
                task=self.task,
                capability=CapabilityContext(True),
                data=data,
                evidence=visible_evidence,
                retrieved_queries=tuple(retrieved_queries),
                retrieval_required=retrieval_required,
                retrieval_progress_note=retrieval_progress_note,
            )
            self._call_index += 1
            request = ModelRequest(
                self._call_index,
                f"{self.run_id}-{self._call_index:04d}",
                "",
                rendered.user_prompt,
                self.parameters,
                None,
            )
            self._active_turn = True
            try:
                response = self.provider.generate(request)
                self._ensure_stop(response)
                classification = ResponseEnvelopeClassifier.classify(
                    expected_role=role,
                    response_text=response.text,
                    finish_reason=response.finish_reason,
                )
                if classification.kind == "retrieval_request":
                    try:
                        retrieval_request = RetrievalRequestParser.parse(
                            response.text,
                            ledger=self.evidence_ledger,
                            run_id=self.run_id,
                            task_id=self.task.task_id,
                            role=role,
                            phase=phase,
                        )
                    except Exception as parser_exc:
                        if not hasattr(parser_exc, "raw_response"):
                            setattr(parser_exc, "raw_response", response.text)
                        if not hasattr(parser_exc, "role"):
                            setattr(parser_exc, "role", role)
                        raise
                    retrieved_queries.append(retrieval_request)
                    # Construct cache key
                    if hasattr(retrieval_request, "tool"):
                        if retrieval_request.tool == "chunk_read":
                            cache_key = (role, phase, "chunk_read", retrieval_request.file_path, retrieval_request.chunk_id)
                        else:
                            cache_key = (role, phase, retrieval_request.tool, retrieval_request.query, retrieval_request.top_k)
                    else:
                        cache_key = None

                    if cache_key is not None and cache_key in self.retrieval_cache:
                        if cache_hit_count >= self._MAX_CACHE_HITS_PER_ROLE_PHASE:
                            raise RetrievalBudgetExceededError(
                                f"{role}/{phase} cached retrieval repetition limit exceeded"
                            )
                        cache_hit_count += 1
                        retrieval_progress_note = (
                            "The requested retrieval is already satisfied by visible evidence. "
                            "Do not repeat the same retrieval. Proceed using the current evidence."
                        )
                        self._record_accepted_response(response, rendered, role, phase, template_name)
                        continue

                    if retrieval_count >= budget:
                        raise RetrievalBudgetExceededError(f"{role}/{phase} retrieval budget exhausted")
                    self._record_accepted_response(response, rendered, role, phase, template_name)
                    result = self._execute_retrieval(role, phase, retrieval_request)
                    if cache_key is not None:
                        self.retrieval_cache[cache_key] = result
                    retrieval_count += 1
                    retrieval_progress_note = None
                    self.metrics_collector.record_tool_result(token_count=result.token_count)
                    self._append_evidence(role, phase, result)
                    continue
                if classification.kind != "final_output":
                    exc = StrategyResponseError(f"{role} returned invalid response")
                    exc.raw_response = response.text
                    exc.role = role
                    raise exc
                try:
                    parsed = final_parser(response.text)
                except Exception as parser_exc:
                    if not hasattr(parser_exc, "raw_response"):
                        setattr(parser_exc, "raw_response", response.text)
                    if not hasattr(parser_exc, "role"):
                        setattr(parser_exc, "role", role)
                    raise parser_exc
                self._record_accepted_response(response, rendered, role, phase, template_name)
                return parsed
            except ProviderError as exc:
                self.metrics_collector.record_error(exc)
                raise
            finally:
                self._active_turn = False

    def _record_accepted_response(self, response, rendered, role, phase, template_name) -> None:
        digest = hashlib.sha256(response.text.encode("utf-8")).hexdigest()
        self.metrics_collector.record_response(
            response,
            role=role,
            phase=phase,
            template_name=template_name,
            template_hash=rendered.template_hash,
            rendered_prompt_hash=rendered.rendered_prompt_hash,
            response_hash=digest,
        )
        prefix = f"{self._call_index:04d}_{role.casefold()}"
        self.artifact_writer.stage_bytes(f"prompts/{prefix}.txt", rendered.user_prompt.encode("utf-8"))
        self.artifact_writer.stage_bytes(f"responses/{prefix}.txt", response.text.encode("utf-8"))

    def _execute_retrieval(self, role: str, phase: str, request):
        session = self.role_sessions[role]
        if isinstance(request, RetrievalSearchRequest):
            if request.tool == "keyword_search":
                return session.keyword_search(request.query, request.top_k)
            return session.semantic_search(request.query, request.top_k)
        if isinstance(request, RetrievalChunkReadRequest):
            return session.chunk_read(request.file_path, request.chunk_id)
        raise StrategyResponseError("unsupported retrieval request")

    def _append_evidence(self, role: str, phase: str, result: SearchResult | ChunkReadResult) -> None:
        items = list(self.evidence_ledger.items)
        authorizations = list(self.evidence_ledger.search_authorizations)
        next_sequence = self.evidence_ledger.next_sequence
        if isinstance(result, SearchResult):
            result_items = result.hits
        else:
            result_items = (result,)
        for hit in result_items:
            evidence_id = f"E{next_sequence:06d}"
            next_sequence += 1
            file_path = hit.file_path
            chunk_id = hit.chunk_id
            text = hit.text if isinstance(hit, ChunkReadResult) else hit.excerpt
            items.append(
                EvidenceItem(
                    evidence_id,
                    self.run_id,
                    self.task.task_id,
                    role,
                    phase,
                    result.tool_name,
                    file_path,
                    chunk_id,
                    hit.content_hash,
                    text,
                    hit.token_count,
                )
            )
            if isinstance(result, SearchResult):
                authorizations.append(
                    SearchAuthorization(
                        self.run_id,
                        self.task.task_id,
                        role,
                        phase,
                        file_path,
                        chunk_id,
                    )
                )
        self.evidence_ledger = replace(
            self.evidence_ledger,
            next_sequence=next_sequence,
            items=tuple(items),
            search_authorizations=tuple(authorizations),
        )

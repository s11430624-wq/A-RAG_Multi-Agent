from __future__ import annotations

from experiments.providers.models import ModelParameters, ModelProvider
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.base import BaseStrategySession, StrategySessionClosedError
from experiments.strategies.models import (
    ModelVisibleTask,
    PlannerOutput,
    ReviewerVerdict,
    SanitizedPublicFeedback,
    StrategyPatchOutput,
)
from experiments.strategies.parsers import PlannerResponseParser, ReviewerResponseParser


class MultiAgentStrategySession(BaseStrategySession):
    def __init__(
        self,
        *,
        run_id: str,
        task: ModelVisibleTask,
        provider: ModelProvider,
        parameters: ModelParameters,
        artifact_writer: ArtifactBundleWriter,
    ) -> None:
        super().__init__(
            run_id=run_id,
            task=task,
            provider=provider,
            parameters=parameters,
            artifact_writer=artifact_writer,
            retrieval_success=None,
        )
        self._plan: PlannerOutput | None = None
        self._reviewer_verdict: ReviewerVerdict | None = None

    def generate_initial_patch(self) -> StrategyPatchOutput:
        self._assert_callable()
        if self._initial_generated:
            raise StrategySessionClosedError("initial patch already generated")
        plan, _text, _metrics = self._invoke_role(
            template_name="planner.txt",
            role="Planner",
            phase="initial",
            data={},
            parser=lambda value: PlannerResponseParser.parse(
                value,
                allowed_files=self.task.files_to_modify,
            ),
        )
        patch, _metrics = self._invoke_patch(
            template_name="coder.txt",
            role="Coder",
            phase="initial",
            data={"plan": plan},
        )
        verdict, _text, metrics = self._invoke_role(
            template_name="reviewer.txt",
            role="Reviewer",
            phase="initial",
            data={"plan": plan, "patch": patch},
            parser=lambda value: ReviewerResponseParser.parse(
                value,
                allowed_evidence_ids=(),
            ),
        )
        self._plan = plan
        self._reviewer_verdict = verdict
        self._initial_generated = True
        return StrategyPatchOutput(patch, verdict, metrics)

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
        patch, metrics = self._invoke_patch(
            template_name="repair.txt",
            role="Coder",
            phase=f"repair_{self._repair_count}",
            data={
                "feedback": feedback,
                "previous_patch": previous_patch,
                "plan": self._plan,
                "reviewer_verdict": self._reviewer_verdict,
            },
        )
        return StrategyPatchOutput(patch, self._reviewer_verdict, metrics)

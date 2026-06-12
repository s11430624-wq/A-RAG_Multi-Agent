from __future__ import annotations

from experiments.providers.models import ModelParameters, ModelProvider
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.base import BaseStrategySession, StrategySessionClosedError
from experiments.strategies.models import (
    ModelVisibleTask,
    SanitizedPublicFeedback,
    StrategyPatchOutput,
)


class SingleLLMStrategySession(BaseStrategySession):
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

    def generate_initial_patch(self) -> StrategyPatchOutput:
        self._assert_callable()
        if self._initial_generated:
            raise StrategySessionClosedError("initial patch already generated")
        patch, metrics = self._invoke_patch(
            template_name="single_llm.txt",
            role="Single",
            phase="initial",
            data={},
        )
        self._initial_generated = True
        return StrategyPatchOutput(patch, None, metrics)

    def generate_repair_patch(
        self,
        feedback: SanitizedPublicFeedback,
        previous_patch: str,
    ) -> StrategyPatchOutput:
        self._assert_callable()
        if not isinstance(feedback, SanitizedPublicFeedback):
            raise TypeError("feedback must be SanitizedPublicFeedback")
        if not self._initial_generated:
            raise StrategySessionClosedError("initial patch must be generated first")
        if self._repair_count >= 2:
            raise StrategySessionClosedError("repair limit reached")
        self._repair_count += 1
        patch, metrics = self._invoke_patch(
            template_name="repair.txt",
            role="Repair",
            phase=f"repair_{self._repair_count}",
            data={"feedback": feedback, "previous_patch": previous_patch},
        )
        return StrategyPatchOutput(patch, None, metrics)

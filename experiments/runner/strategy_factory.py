from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
from pathlib import Path
from typing import Callable

from experiments.providers.config import load_provider_config
from experiments.providers.fake import FakeProvider
from experiments.providers.models import Usage
from experiments.retrieval.logging import RetrievalLogWriter
from experiments.retrieval.models import RetrievalTaskSpec
from experiments.retrieval.service import RetrievalFacade
from experiments.runner.config import ExperimentConfig
from experiments.runner.scheduler import PlannedRun
from experiments.strategies.arag_multi_agent import ARAGMultiAgentStrategySession
from experiments.strategies.artifacts import ArtifactBundleWriter
from experiments.strategies.multi_agent import MultiAgentStrategySession
from experiments.strategies.single_llm import SingleLLMStrategySession
from experiments.strategies.visibility import ModelVisibleTaskFactory


REVIEW = '{"issues":[],"verdict":"pass"}'


@dataclass(frozen=True)
class StrategyBundle:
    session: object
    provider: object
    strategy: str
    model: str
    seed: int
    retrieval_log_path: Path | None


class StrategyFactory:
    def __init__(
        self,
        *,
        repo_root: Path,
        provider_builder: Callable | None = None,
        artifact_root: Path | None = None,
        retrieval_log_root: Path | None = None,
        retrieval_facade: RetrievalFacade | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.provider_builder = provider_builder
        self.artifact_root = Path(artifact_root).resolve() if artifact_root is not None else None
        self.retrieval_log_root = Path(retrieval_log_root).resolve() if retrieval_log_root is not None else None
        self.retrieval_facade = retrieval_facade or RetrievalFacade()
        self._retrieval_store_cache: dict[str, object] = {}

    def create(self, *, run: PlannedRun, config: ExperimentConfig, repo_root: Path) -> StrategyBundle:
        root = Path(repo_root).resolve()
        provider_config = load_provider_config(
            root / "configs" / "models.yaml",
            root / "configs" / "experiment.yaml",
        )
        task = self._create_visible_task(run.task_record)
        provider = (
            self.provider_builder(run, task, provider_config)
            if self.provider_builder is not None
            else self._new_provider(run=run, task=task)
        )
        artifact_writer = ArtifactBundleWriter(
            self.artifact_root or config.paths.artifact_root,
            run_id=run.identity.run_id,
            task_id=run.identity.task_id,
            strategy=run.identity.strategy,
            model=config.model,
            provider_id=provider_config.provider_id,
            seed=config.seed,
        )
        if run.identity.strategy == "A":
            session = SingleLLMStrategySession(
                run_id=run.identity.run_id,
                task=task,
                provider=provider,
                parameters=provider_config.parameters,
                artifact_writer=artifact_writer,
            )
            return StrategyBundle(session, provider, "A", config.model, config.seed, None)
        if run.identity.strategy == "C":
            session = MultiAgentStrategySession(
                run_id=run.identity.run_id,
                task=task,
                provider=provider,
                parameters=provider_config.parameters,
                artifact_writer=artifact_writer,
            )
            return StrategyBundle(session, provider, "C", config.model, config.seed, None)
        facade = self.retrieval_facade
        store = self._retrieval_store_cache.get(run.identity.task_id)
        if store is None:
            store = facade.build_store(
                spec=RetrievalTaskSpec(
                    task_id=run.identity.task_id,
                    allowed_corpus=tuple(run.task_record["allowed_corpus"]),
                ),
                repo_root=root,
                strategy="E",
            )
            self._retrieval_store_cache[run.identity.task_id] = store
        log_root = self.retrieval_log_root or config.paths.retrieval_log_root / run.identity.experiment_id
        log_path = log_root / f"{run.identity.run_id}.jsonl"
        log_writer = RetrievalLogWriter(approved_log_root=log_root, log_file_path=log_path)
        session = ARAGMultiAgentStrategySession(
            run_id=run.identity.run_id,
            task=task,
            provider=provider,
            parameters=provider_config.parameters,
            artifact_writer=artifact_writer,
            store=store,
            retrieval_facade=facade,
            log_writer=log_writer,
        )
        return StrategyBundle(session, provider, "E", config.model, config.seed, log_path)

    def _create_visible_task(self, task_record: dict):
        return ModelVisibleTaskFactory.from_task_record(task_record, repo_root=self.repo_root)

    def _new_provider(self, *, run: PlannedRun, task) -> FakeProvider:
        target = task.files_to_modify[0]
        starter = next(file for file in task.starter_files if file.file_path == target)
        patches = _deterministic_patch_sequence(
            file_path=target,
            original=starter.content,
            run_id=run.identity.run_id,
        )
        plan = json.dumps(
            {
                "files_to_modify": list(task.files_to_modify),
                "implementation_steps": ["apply deterministic offline mock patch"],
                "risks": [],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        if run.identity.strategy == "A":
            responses = patches
        else:
            responses = (plan, patches[0], REVIEW, patches[1], patches[2])
        return FakeProvider(responses=responses, usage=Usage(11, 7, 18, "provider"))


def _deterministic_patch_sequence(*, file_path: str, original: str, run_id: str) -> tuple[str, str, str]:
    states = [original]
    for round_index in range(3):
        prior = states[-1]
        separator = "" if prior.endswith("\n") else "\n"
        states.append(f"{prior}{separator}# M6 deterministic mock {run_id} round {round_index + 1}\n")
    return tuple(
        "".join(
            difflib.unified_diff(
                states[index].splitlines(keepends=True),
                states[index + 1].splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
        )
        for index in range(3)
    )

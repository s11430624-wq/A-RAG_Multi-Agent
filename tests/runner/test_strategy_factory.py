from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.runner.strategy_factory import StrategyFactory
from experiments.runtime.patching import PatchEngine
from experiments.strategies.arag_multi_agent import ARAGMultiAgentStrategySession
from experiments.strategies.multi_agent import MultiAgentStrategySession
from experiments.strategies.single_llm import SingleLLMStrategySession


def test_factory_constructs_a_c_e_with_same_provider_parameters(project_root, experiment_config, a_planned_run, c_planned_run, e_planned_run):
    factory = StrategyFactory(repo_root=project_root)
    bundles = [
        factory.create(run=a_planned_run, config=experiment_config, repo_root=project_root),
        factory.create(run=c_planned_run, config=experiment_config, repo_root=project_root),
        factory.create(run=e_planned_run, config=experiment_config, repo_root=project_root),
    ]

    assert [bundle.strategy for bundle in bundles] == ["A", "C", "E"]
    assert isinstance(bundles[0].session, SingleLLMStrategySession)
    assert isinstance(bundles[1].session, MultiAgentStrategySession)
    assert isinstance(bundles[2].session, ARAGMultiAgentStrategySession)
    assert {bundle.model for bundle in bundles} == {"google/gemini-3.5-flash"}
    assert {bundle.seed for bundle in bundles} == {42}
    assert len({id(bundle.provider) for bundle in bundles}) == 3
    assert {
        bundle.session.artifact_writer.provider_id for bundle in bundles
    } == {"hermes_vertex_gateway"}


def test_provider_response_cursor_is_isolated_per_run(project_root, experiment_config, planned_runs, tmp_path):
    config = _with_output_roots(experiment_config, tmp_path)
    first_run = next(run for run in planned_runs if run.identity.task_id == "T01" and run.identity.strategy == "A" and run.identity.repetition == 1)
    second_run = next(run for run in planned_runs if run.identity.task_id == "T01" and run.identity.strategy == "A" and run.identity.repetition == 2)
    factory = StrategyFactory(repo_root=project_root)
    first = factory.create(run=first_run, config=config, repo_root=project_root)
    second = factory.create(run=second_run, config=config, repo_root=project_root)

    first_patch = first.session.generate_initial_patch().patch
    second_patch = second.session.generate_initial_patch().patch

    assert first.provider is not second.provider
    assert len(first.provider.requests) == 1
    assert len(second.provider.requests) == 1
    assert f"{first_run.identity.run_id} round 1" in first_patch
    assert f"{second_run.identity.run_id} round 1" in second_patch
    assert "round 2" not in first_patch
    assert "round 2" not in second_patch
    first.session.close()
    second.session.close()


@pytest.mark.parametrize("strategy", ["A", "C", "E"])
def test_mock_provider_is_task_aware_and_initial_patch_applies(
    project_root,
    experiment_config,
    planned_runs,
    tmp_path,
    strategy,
):
    config = _with_output_roots(experiment_config, tmp_path)
    run = next(
        run
        for run in planned_runs
        if run.identity.task_id == "T01" and run.identity.strategy == strategy and run.identity.repetition == 1
    )
    bundle = StrategyFactory(repo_root=project_root).create(run=run, config=config, repo_root=project_root)

    output = bundle.session.generate_initial_patch()
    workspace = tmp_path / f"workspace-{strategy}"
    target = workspace / run.task_record["files_to_modify"][0]
    target.parent.mkdir(parents=True)
    target.write_bytes((project_root / run.task_record["files_to_modify"][0]).read_bytes())
    PatchEngine.apply_patch(workspace, output.patch, run.task_record["files_to_modify"])

    assert target.read_bytes() != (project_root / run.task_record["files_to_modify"][0]).read_bytes()
    if strategy in ("C", "E"):
        planner_response = bundle.provider.requests[0]
        assert run.task_record["files_to_modify"][0] in planner_response.user_prompt
    bundle.session.close()


def test_all_45_runs_have_fresh_non_exhausted_mock_provider(
    project_root,
    experiment_config,
    planned_runs,
    tmp_path,
):
    config = _with_output_roots(experiment_config, tmp_path)
    factory = StrategyFactory(repo_root=project_root)
    providers = []

    for run in planned_runs:
        bundle = factory.create(run=run, config=config, repo_root=project_root)
        output = bundle.session.generate_initial_patch()
        assert output.patch.startswith("--- ")
        providers.append(bundle.provider)
        bundle.session.close()

    assert len({id(provider) for provider in providers}) == 45


def test_strategy_e_gets_one_store_and_approved_retrieval_log(project_root, experiment_config, e_planned_run):
    bundle = StrategyFactory(repo_root=project_root).create(
        run=e_planned_run,
        config=experiment_config,
        repo_root=project_root,
    )

    assert bundle.strategy == "E"
    assert bundle.retrieval_log_path is not None
    assert bundle.retrieval_log_path.suffix == ".jsonl"
    assert bundle.retrieval_log_path.parent == experiment_config.paths.retrieval_log_root / e_planned_run.identity.experiment_id
    assert bundle.session.store is bundle.session.role_sessions["Planner"].store
    assert bundle.session.role_sessions["Planner"].store is bundle.session.role_sessions["Coder"].store


def test_strategy_a_and_c_do_not_construct_retrieval(project_root, experiment_config, a_planned_run, c_planned_run, monkeypatch):
    import experiments.runner.strategy_factory as strategy_factory

    def forbidden(*args, **kwargs):
        raise AssertionError("A/C must not construct retrieval")

    monkeypatch.setattr(strategy_factory.RetrievalFacade, "build_store", forbidden)
    factory = StrategyFactory(repo_root=project_root)

    assert factory.create(run=a_planned_run, config=experiment_config, repo_root=project_root).retrieval_log_path is None
    assert factory.create(run=c_planned_run, config=experiment_config, repo_root=project_root).retrieval_log_path is None


def test_strategy_receives_visible_task_not_full_mapping(project_root, experiment_config, a_planned_run):
    bundle = StrategyFactory(repo_root=project_root).create(
        run=a_planned_run,
        config=experiment_config,
        repo_root=project_root,
    )

    assert not isinstance(bundle.session.task, dict)
    assert "required_evidence" not in repr(bundle.session.task)
    assert "grading" not in repr(bundle.session.task)
    assert "hidden_test_id" not in repr(bundle.session.task)


def _with_output_roots(config, tmp_path: Path):
    raw = (tmp_path / "results" / "raw").resolve()
    paths = replace(
        config.paths,
        raw_results_dir=raw,
        derived_results_dir=(tmp_path / "results" / "derived").resolve(),
        artifact_root=(raw / "artifacts").resolve(),
        retrieval_log_root=(raw / "retrieval").resolve(),
    )
    return replace(config, paths=paths)

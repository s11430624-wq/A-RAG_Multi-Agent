from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


StrategyName = Literal["A", "C", "E"]


@dataclass(frozen=True)
class RunIdentity:
    experiment_id: str
    task_id: str
    strategy: StrategyName
    repetition: int
    seed: int
    run_id: str


def make_experiment_id(*, today: str, model: str, seed: int, repetitions: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", model.casefold()).strip("-")[:48].strip("-")
    return f"exp-{today}-{slug}-seed{seed}-r{repetitions}"


def make_run_id(
    *,
    experiment_id: str,
    task_id: str,
    strategy: StrategyName,
    repetition: int,
    seed: int,
) -> str:
    run_id = f"{experiment_id}__{task_id}__{strategy}__rep{repetition:02d}__seed{seed}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?:__[A-Za-z0-9_.-]+)*", run_id):
        raise ValueError("unsafe run_id")
    if ".." in run_id.split("__"):
        raise ValueError("unsafe run_id")
    return run_id


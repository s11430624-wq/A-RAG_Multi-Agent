from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def models_config_path(project_root: Path) -> Path:
    return project_root / "configs" / "models.yaml"


@pytest.fixture
def experiment_config_path(project_root: Path) -> Path:
    return project_root / "configs" / "experiment.yaml"

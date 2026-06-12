def test_strategy_modules_do_not_name_private_task_fields():
    from experiments.strategies.models import ModelVisibleTask

    assert set(ModelVisibleTask.__dataclass_fields__) == {
        "task_id",
        "task_description",
        "starter_files",
        "files_to_modify",
        "expected_behavior",
        "forbidden_behaviors",
    }

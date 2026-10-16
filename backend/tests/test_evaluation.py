from pathlib import Path
import sys
from types import SimpleNamespace

from backend.app.evaluation.runner import EvaluationRunner


DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "intent_entity_eval.json"


def test_evaluation_dataset_and_rule_baseline_are_executable():
    runner = EvaluationRunner(DATASET_PATH)
    dataset = runner.load_dataset()

    assert len(dataset) == 100
    records = runner.run_rule_baseline(dataset)
    summary = runner.summarize(records)

    assert summary["status"] == "completed"
    assert summary["sample_count"] == 100
    assert summary["completed_count"] == 100
    assert 0 < summary["accuracy"] < 1
    assert summary["error_count"] > 0


def test_prompt_strategies_are_not_marked_as_run_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runner = EvaluationRunner(DATASET_PATH)
    runs = runner.run_prompt_strategies(runner.load_dataset())

    assert [run["strategy_id"] for run in runs] == ["A", "B", "C"]
    assert all(run["status"] == "not_run_no_key" for run in runs)
    assert all(run["metrics"] is None for run in runs)
    assert all(run["records"] == [] for run in runs)


def test_prompt_strategy_runner_records_structured_output_without_network(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        @staticmethod
        def create(**_kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"intent":"comparison","entities":'
                                '[{"brand":"小米","model":"SU7"}]}'
                            )
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8),
            )

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeClient))
    runner = EvaluationRunner(DATASET_PATH)
    runs = runner.run_prompt_strategies([runner.load_dataset()[0]])

    assert [run["status"] for run in runs] == ["completed", "completed", "completed"]
    assert all(len(run["records"]) == 1 for run in runs)
    assert all(run["records"][0].input_tokens == 12 for run in runs)
    assert all(run["records"][0].output_tokens == 8 for run in runs)

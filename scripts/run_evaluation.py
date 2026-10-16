"""运行 Phase 5 独立评测并生成 CSV、JSON、Markdown 和错误案例。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.evaluation.runner import EvaluationRunner


def main() -> None:
    dataset_path = PROJECT_ROOT / "data" / "evaluation" / "intent_entity_eval.json"
    output_dir = PROJECT_ROOT / "reports" / "generated"
    runner = EvaluationRunner(dataset_path)
    dataset = runner.load_dataset()
    records = runner.run_rule_baseline(dataset)
    summary = runner.summarize(records)
    strategy_runs = runner.run_prompt_strategies(dataset)
    outputs = runner.write_outputs(output_dir, records, summary, strategy_runs)
    print(json.dumps({"summary": summary, "outputs": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""汽车 NLP 评测运行器：真实记录结果，不填充未运行的指标。"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backend.app.evaluation.metrics import (
    accuracy,
    confusion_matrix,
    entity_prf,
    macro_f1,
    per_intent_accuracy,
)
from backend.app.evaluation.prompts import PROMPT_STRATEGIES
from backend.app.schemas.nlp import (
    AnalysisStrategy,
    IntentLabel,
    NlpAnalysis,
    normalize_llm_payload,
)
from backend.app.services.llm import LLMUnavailableError
from backend.app.services.nlp_pipeline import RuleNlpPipeline


INTENT_LABELS = [label.value for label in IntentLabel]

load_dotenv()


@dataclass
class EvaluationRecord:
    sample_id: str
    text: str
    expected_intent: str
    predicted_intent: str | None
    expected_entities: dict[str, Any]
    predicted_entities: dict[str, Any]
    status: str
    error_type: str | None
    error_message: str | None
    raw_output: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float | None
    strategy_id: str
    prompt_version: str


class EvaluationRunner:
    def __init__(self, dataset_path: Path) -> None:
        self.dataset_path = dataset_path
        self.pipeline = RuleNlpPipeline()

    def load_dataset(self) -> list[dict[str, Any]]:
        with self.dataset_path.open("r", encoding="utf-8") as file:
            dataset = json.load(file)
        if not isinstance(dataset, list) or len(dataset) < 100:
            raise ValueError("评测集必须是至少 100 条人工标注样本的 JSON 数组")
        for sample in dataset:
            if not {"id", "text", "intent", "entities"}.issubset(sample):
                raise ValueError("评测样本必须包含 id、text、intent、entities")
        return dataset

    def run_rule_baseline(self, dataset: list[dict[str, Any]]) -> list[EvaluationRecord]:
        records: list[EvaluationRecord] = []
        for sample in dataset:
            started = time.perf_counter()
            try:
                analysis = self.pipeline.analyze(sample["text"])
                records.append(
                    EvaluationRecord(
                        sample_id=sample["id"],
                        text=sample["text"],
                        expected_intent=sample["intent"],
                        predicted_intent=analysis.intent.value,
                        expected_entities=sample["entities"],
                        predicted_entities=analysis.entities.model_dump(exclude_none=True),
                        status="completed",
                        error_type=None,
                        error_message=None,
                        raw_output=analysis.model_dump_json(ensure_ascii=False),
                        input_tokens=None,
                        output_tokens=None,
                        latency_ms=round((time.perf_counter() - started) * 1000, 4),
                        strategy_id="rule",
                        prompt_version="rule-baseline-v1",
                    )
                )
            except Exception as error:  # pragma: no cover - dataset safety boundary
                records.append(
                    EvaluationRecord(
                        sample_id=sample["id"],
                        text=sample["text"],
                        expected_intent=sample["intent"],
                        predicted_intent=None,
                        expected_entities=sample["entities"],
                        predicted_entities={},
                        status="failed",
                        error_type="runtime_error",
                        error_message=str(error),
                        raw_output=None,
                        input_tokens=None,
                        output_tokens=None,
                        latency_ms=round((time.perf_counter() - started) * 1000, 4),
                        strategy_id="rule",
                        prompt_version="rule-baseline-v1",
                    )
                )
        return records

    def run_prompt_strategies(self, dataset: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按同一数据集逐条运行 A/B/C；没有密钥时只记录未运行状态。"""

        if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")):
            return [
                {
                    "strategy_id": strategy.strategy_id,
                    "version": strategy.version,
                    "name": strategy.name,
                    "status": "not_run_no_key",
                    "metrics": None,
                    "records": [],
                }
                for strategy in PROMPT_STRATEGIES
            ]

        return [self._run_prompt_strategy(strategy, dataset) for strategy in PROMPT_STRATEGIES]

    def run_prompt_strategy_sample(self, strategy_id: str, text: str) -> EvaluationRecord:
        if not (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")):
            raise LLMUnavailableError("未配置 API Key，无法运行 Prompt 策略实验")
        strategy = next(
            (item for item in PROMPT_STRATEGIES if item.strategy_id == strategy_id),
            None,
        )
        if strategy is None:
            raise ValueError(f"未知 Prompt 策略：{strategy_id}")
        run = self._run_prompt_strategy(
            strategy,
            [{"id": "adhoc", "text": text, "intent": "其他", "entities": {}}],
        )
        record = run["records"][0]
        if record.status != "completed":
            raise RuntimeError(record.error_message or "Prompt 策略调用失败")
        return record

    def _run_prompt_strategy(self, strategy, dataset: list[dict[str, Any]]) -> dict[str, Any]:
        from openai import OpenAI

        project_root = self.dataset_path.resolve().parents[2]
        system_prompt = (project_root / strategy.prompt_path).read_text(encoding="utf-8")
        if strategy.uses_few_shot:
            examples_path = project_root / "prompts" / "few_shot_examples.json"
            examples = examples_path.read_text(encoding="utf-8")
            system_prompt += f"\n\n以下是 Few-shot 示例（仅用于学习格式，不是评测集）：\n{examples}"

        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=10.0,
            max_retries=2,
        )
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        records: list[EvaluationRecord] = []
        for sample in dataset:
            started = time.perf_counter()
            raw_output: str | None = None
            input_tokens: int | None = None
            output_tokens: int | None = None
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    max_tokens=800,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": sample["text"]},
                    ],
                )
                raw_output = response.choices[0].message.content or ""
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "prompt_tokens", None)
                output_tokens = getattr(usage, "completion_tokens", None)
                payload = normalize_llm_payload(json.loads(raw_output))
                analysis = NlpAnalysis.model_validate(
                    {
                        "text": sample["text"],
                        "intent": payload["intent"],
                        "intent_evidence": [f"prompt_strategy_{strategy.strategy_id}"],
                        "entities": payload.get("entities", {}),
                        "strategy": AnalysisStrategy.LLM_STRUCTURED,
                        "raw_output": raw_output,
                    }
                )
                records.append(
                    EvaluationRecord(
                        sample_id=sample["id"],
                        text=sample["text"],
                        expected_intent=sample["intent"],
                        predicted_intent=analysis.intent.value,
                        expected_entities=sample["entities"],
                        predicted_entities=analysis.entities.model_dump(exclude_none=True),
                        status="completed",
                        error_type=None,
                        error_message=None,
                        raw_output=raw_output,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=round((time.perf_counter() - started) * 1000, 4),
                        strategy_id=strategy.strategy_id,
                        prompt_version=strategy.version,
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                records.append(
                    self._failed_record(
                        sample,
                        strategy,
                        "parse_error",
                        str(error),
                        raw_output,
                        input_tokens,
                        output_tokens,
                        started,
                    )
                )
            except Exception as error:  # pragma: no cover - external provider boundary
                records.append(
                    self._failed_record(
                        sample,
                        strategy,
                        "provider_error",
                        str(error),
                        raw_output,
                        input_tokens,
                        output_tokens,
                        started,
                    )
                )

        completed = sum(record.status == "completed" for record in records)
        return {
            "strategy_id": strategy.strategy_id,
            "version": strategy.version,
            "name": strategy.name,
            "status": "completed" if completed == len(records) else "partial",
            "metrics": self.summarize(records),
            "records": records,
        }

    @staticmethod
    def _failed_record(
        sample: dict[str, Any],
        strategy,
        error_type: str,
        error_message: str,
        raw_output: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        started: float,
    ) -> EvaluationRecord:
        return EvaluationRecord(
            sample_id=sample["id"],
            text=sample["text"],
            expected_intent=sample["intent"],
            predicted_intent=None,
            expected_entities=sample["entities"],
            predicted_entities={},
            status="failed",
            error_type=error_type,
            error_message=error_message,
            raw_output=raw_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round((time.perf_counter() - started) * 1000, 4),
            strategy_id=strategy.strategy_id,
            prompt_version=strategy.version,
        )

    def summarize(self, records: list[EvaluationRecord]) -> dict[str, Any]:
        completed = [record for record in records if record.status == "completed"]
        expected_intents = [record.expected_intent for record in completed]
        predicted_intents = [record.predicted_intent or "解析失败" for record in completed]
        expected_entities = [self._entity_mentions(record.expected_entities) for record in completed]
        predicted_entities = [self._entity_mentions(record.predicted_entities) for record in completed]
        errors = [
            {
                "sample_id": record.sample_id,
                "text": record.text,
                "expected_intent": record.expected_intent,
                "predicted_intent": record.predicted_intent,
                "error_type": "intent_mismatch",
            }
            for record in completed
            if record.predicted_intent != record.expected_intent
        ]
        errors.extend(
            {
                "sample_id": record.sample_id,
                "text": record.text,
                "expected_intent": record.expected_intent,
                "predicted_intent": record.predicted_intent,
                "error_type": record.error_type,
                "error_message": record.error_message,
            }
            for record in records
            if record.status != "completed"
        )
        return {
            "status": "completed" if len(completed) == len(records) else "partial",
            "sample_count": len(records),
            "completed_count": len(completed),
            "accuracy": round(accuracy(expected_intents, predicted_intents), 6),
            "macro_f1": round(macro_f1(expected_intents, predicted_intents, INTENT_LABELS), 6),
            "confusion_matrix": confusion_matrix(expected_intents, predicted_intents, INTENT_LABELS),
            "per_intent_accuracy": per_intent_accuracy(expected_intents, predicted_intents),
            "entity": entity_prf(expected_entities, predicted_entities),
            "error_count": len(errors),
            "errors": errors,
            "latency_ms": {
                "average": self._average_latency(records),
                "p95": self._percentile_latency(records, 0.95),
            },
            "tokens": {
                "input_total": self._sum_optional(record.input_tokens for record in records),
                "output_total": self._sum_optional(record.output_tokens for record in records),
            },
        }

    @staticmethod
    def _entity_mentions(entities: dict[str, Any]) -> set[tuple[str, str]]:
        mentions: set[tuple[str, str]] = set()
        for field, value in entities.items():
            if value is None or value == []:
                continue
            if isinstance(value, list):
                mentions.update((field, str(item)) for item in value)
            else:
                mentions.add((field, str(value)))
        return mentions

    @staticmethod
    def _average_latency(records: list[EvaluationRecord]) -> float | None:
        values = [record.latency_ms for record in records if record.latency_ms is not None]
        return round(sum(values) / len(values), 4) if values else None

    @staticmethod
    def _percentile_latency(records: list[EvaluationRecord], percentile: float) -> float | None:
        values = sorted(record.latency_ms for record in records if record.latency_ms is not None)
        if not values:
            return None
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * percentile))))
        return round(values[index], 4)

    @staticmethod
    def _sum_optional(values) -> int | None:
        numbers = [value for value in values if value is not None]
        return sum(numbers) if numbers else None

    def write_outputs(
        self,
        output_dir: Path,
        records: list[EvaluationRecord],
        summary: dict[str, Any],
        strategy_runs: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "rule_baseline_records.csv"
        json_path = output_dir / "evaluation_results.json"
        report_path = output_dir / "evaluation_report.md"
        error_path = output_dir / "error_cases.json"
        strategy_csv_path = output_dir / "prompt_strategy_records.csv"

        if strategy_runs is None:
            strategy_runs = self.run_prompt_strategies([])

        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(asdict(records[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(record) for record in records)

        strategy_summaries = [
            {
                "strategy_id": run["strategy_id"],
                "version": run["version"],
                "name": run["name"],
                "status": run["status"],
                "metrics": run["metrics"],
            }
            for run in strategy_runs
        ]
        strategy_records = [
            record
            for run in strategy_runs
            for record in run.get("records", [])
        ]
        if strategy_records:
            with strategy_csv_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=list(asdict(strategy_records[0]).keys()))
                writer.writeheader()
                writer.writerows(asdict(record) for record in strategy_records)

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": str(self.dataset_path),
            "dataset_type": "synthetic_manual_eval",
            "strategies": strategy_summaries,
            "rule_baseline": summary,
        }
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        all_errors = [
            {"strategy_id": "rule", **error}
            for error in summary["errors"]
        ]
        for run in strategy_runs:
            for error in (run.get("metrics") or {}).get("errors", []):
                all_errors.append({"strategy_id": run["strategy_id"], **error})
        error_path.write_text(json.dumps(all_errors, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(self._markdown_report(report), encoding="utf-8")
        outputs = {
            "records_csv": str(csv_path),
            "results_json": str(json_path),
            "report_md": str(report_path),
            "errors_json": str(error_path),
        }
        if strategy_records:
            outputs["prompt_strategy_records_csv"] = str(strategy_csv_path)
        return outputs

    @staticmethod
    def _markdown_report(report: dict[str, Any]) -> str:
        baseline = report["rule_baseline"]
        lines = [
            "# AutoInsight Phase 5 评测报告",
            "",
            f"- 数据集：`{report['dataset_path']}`",
            f"- 数据集类型：`{report['dataset_type']}`",
            f"- 样本数：{baseline['sample_count']}",
            "",
            "## 规则 Baseline 实际结果",
            "",
            f"- Accuracy：`{baseline['accuracy']}`",
            f"- Macro-F1：`{baseline['macro_f1']}`",
            f"- 实体 Precision：`{baseline['entity']['precision']}`",
            f"- 实体 Recall：`{baseline['entity']['recall']}`",
            f"- 实体 F1：`{baseline['entity']['f1']}`",
            f"- 平均延迟（毫秒）：`{baseline['latency_ms']['average']}`",
            f"- P95 延迟（毫秒）：`{baseline['latency_ms']['p95']}`",
            "- Token 消耗：规则 Baseline 不调用模型，因此为 `null`。",
            "",
            "## Prompt 策略运行状态",
            "",
            "| 策略 | 版本 | 状态 | Accuracy | Macro-F1 |",
            "|---|---|---|---:|---:|",
        ]
        for strategy in report["strategies"]:
            metrics = strategy["metrics"] or {}
            lines.append(
                f"| {strategy['name']} | `{strategy['version']}` | `{strategy['status']}` | "
                f"{metrics.get('accuracy', '未运行')} | {metrics.get('macro_f1', '未运行')} |"
            )
        lines.extend(
            [
                "",
                "策略指标只有在对应模型调用真实完成后才会写入；无 API Key 时状态为 `not_run_no_key`。",
                "",
            "## 错误案例",
            "",
            f"共记录 {baseline['error_count']} 条错误案例，详见 `error_cases.json`。",
            "",
            ]
        )
        return "\n".join(lines)

"""Phase 5 Prompt 策略元数据。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptStrategy:
    strategy_id: str
    version: str
    name: str
    prompt_path: str
    uses_few_shot: bool


PROMPT_STRATEGIES = (
    PromptStrategy("A", "prompt-a-v1", "基础 Prompt", "prompts/strategy_a_basic.md", False),
    PromptStrategy("B", "prompt-b-v2", "结构化 Prompt", "prompts/strategy_b_structured.md", False),
    PromptStrategy("C", "prompt-c-v2", "Few-shot Prompt", "prompts/strategy_c_fewshot.md", True),
)

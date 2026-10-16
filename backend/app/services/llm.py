"""OpenAI-compatible 结构化输出适配器，支持 DeepSeek 等兼容服务。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key, unset_key

from backend.app.schemas.nlp import AnalysisStrategy, NlpAnalysis, normalize_llm_payload


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"


class LLMUnavailableError(RuntimeError):
    """未配置可用的 LLM 服务。"""


class LLMStructuredAnalyzer:
    """只在显式选择 llm_structured 且配置密钥时调用外部模型。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._client = None
        persisted_key = dotenv_values(LOCAL_ENV_PATH).get("DEEPSEEK_API_KEY")
        self.persistence = "local_env" if persisted_key else "process_memory_only"

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def configure_runtime(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        persist: bool | None = None,
    ) -> None:
        """配置当前进程；persist=True 时额外保存到本机 .env。"""

        # 前端留空 API Key 代表沿用当前 Key，避免只修改模型时误清空密钥。
        if api_key and api_key.strip():
            self.api_key = api_key.strip()
        self.base_url = base_url.strip()
        self.model = model.strip()
        if self.api_key:
            os.environ["DEEPSEEK_API_KEY"] = self.api_key
        os.environ["DEEPSEEK_BASE_URL"] = self.base_url
        os.environ["DEEPSEEK_MODEL"] = self.model
        self._client = None

        if persist is True:
            if self.api_key:
                set_key(str(LOCAL_ENV_PATH), "DEEPSEEK_API_KEY", self.api_key, quote_mode="auto")
            set_key(str(LOCAL_ENV_PATH), "DEEPSEEK_BASE_URL", self.base_url, quote_mode="auto")
            set_key(str(LOCAL_ENV_PATH), "DEEPSEEK_MODEL", self.model, quote_mode="auto")
            self.persistence = "local_env"
        elif persist is False:
            # 前端明确取消记住配置时，移除本机持久化项，但保留当前进程配置。
            for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
                unset_key(str(LOCAL_ENV_PATH), key)
            self.persistence = "process_memory_only"

    def analyze(self, text: str) -> NlpAnalysis:
        if not self.available:
            raise LLMUnavailableError(
                "未配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY，当前只能使用 rule_baseline"
            )

        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=10.0,
                max_retries=2,
            )

        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是汽车领域信息抽取器。只返回 JSON，不要返回 Markdown。"
                        "intent 必须是：购车推荐、车型对比、参数查询、价格查询、"
                        "用户评价、用车知识、其他之一。entities 必须符合项目 Schema。"
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        raw_output = response.choices[0].message.content or ""
        payload = normalize_llm_payload(json.loads(raw_output))
        result = NlpAnalysis.model_validate(
            {
                "text": text,
                "intent": payload["intent"],
                "intent_evidence": ["llm_structured_output"],
                "entities": payload.get("entities", {}),
                "strategy": AnalysisStrategy.LLM_STRUCTURED,
                "raw_output": raw_output,
            }
        )
        return result
